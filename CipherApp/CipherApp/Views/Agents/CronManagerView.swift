import SwiftUI

// MARK: - Cron Manager View

struct CronManagerView: View {
    @State private var viewModel = CronManagerViewModel()
    @State private var showAddSheet = false

    var body: some View {
        ZStack {
            CipherTheme.background.ignoresSafeArea()

            VStack(spacing: 0) {
                headerBar

                if viewModel.cronTasks.isEmpty {
                    emptyState
                } else {
                    taskList
                }
            }
        }
        .navigationTitle("Schedules")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                addButton
            }
        }
        .sheet(isPresented: $showAddSheet) {
            AddScheduleSheet(isPresented: $showAddSheet) { newTask in
                Task {
                    await viewModel.createTask(newTask)
                }
            }
        }
        .onAppear {
            Task {
                await viewModel.fetchCronTasks()
            }
        }
    }

    // MARK: - Add Button

    private var addButton: some View {
        Button(action: { showAddSheet = true }) {
            HStack(spacing: Spacing.xs) {
                Image(systemName: "plus")
                    .font(.system(size: 14, weight: .semibold))
                Text("Add")
                    .font(.system(size: 14, weight: .semibold))
            }
            .foregroundColor(CipherTheme.accent)
        }
    }

    // MARK: - Task List

    private var taskList: some View {
        ScrollView(.vertical, showsIndicators: false) {
            VStack(spacing: 0) {
                if !viewModel.activeTasks.isEmpty {
                    sectionHeader("Active")
                    activeSection
                }

                if !viewModel.pausedTasks.isEmpty {
                    sectionHeader("Paused")
                    pausedSection
                }

                Spacer(minLength: 40)
            }
        }
    }

    private var activeSection: some View {
        VStack(spacing: Spacing.sm) {
            ForEach(viewModel.activeTasks) { task in
                cronRow(for: task)
            }
        }
        .padding(Spacing.lg)
    }

    private var pausedSection: some View {
        VStack(spacing: Spacing.sm) {
            ForEach(viewModel.pausedTasks) { task in
                cronRow(for: task)
            }
        }
        .padding(Spacing.lg)
    }

    private func cronRow(for task: CronTaskInfo) -> some View {
        let taskId = task.taskId
        let isEnabled = task.enabled
        return CronTaskRow(
            task: task,
            onToggle: {
                Task { await viewModel.toggleTask(taskId: taskId, enabled: !isEnabled) }
            },
            onRunNow: {
                Task { await viewModel.triggerTask(taskId: taskId) }
            },
            onDelete: {
                Task { await viewModel.deleteTask(taskId: taskId) }
            }
        )
    }

    // MARK: - Header Bar

    private var headerBar: some View {
        VStack(spacing: Spacing.md) {
            HStack {
                VStack(alignment: .leading, spacing: Spacing.xs) {
                    let count = viewModel.cronTasks.count
                    Text("\(count) Scheduled Tasks")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(CipherTheme.textPrimary)

                    let activeCount = viewModel.activeTasks.count
                    Text("\(activeCount) active")
                        .font(.system(size: 13))
                        .foregroundColor(CipherTheme.textSecondary)
                }

                Spacer()
            }
            .padding(Spacing.lg)
        }
        .background(CipherTheme.surface)
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: Spacing.lg) {
            Spacer()

            Image(systemName: "calendar.badge.clock")
                .font(.system(size: 48))
                .foregroundColor(CipherTheme.textTertiary)

            VStack(spacing: Spacing.xs) {
                Text("No scheduled tasks")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(CipherTheme.textSecondary)

                Text("Create a schedule to automate tasks")
                    .font(.system(size: 13))
                    .foregroundColor(CipherTheme.textTertiary)
            }

            Button(action: { showAddSheet = true }) {
                HStack(spacing: Spacing.sm) {
                    Image(systemName: "plus.circle.fill")
                        .font(.system(size: 16))
                    Text("Add Schedule")
                        .font(.system(size: 14, weight: .semibold))
                }
                .foregroundColor(CipherTheme.textOnAccent)
                .padding(.horizontal, Spacing.xl)
                .padding(.vertical, Spacing.md)
                .background(CipherTheme.accentGradient)
                .clipShape(Capsule())
            }

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Section Header

    @ViewBuilder
    private func sectionHeader(_ title: String) -> some View {
        HStack {
            Text(title)
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(CipherTheme.textTertiary)
                .textCase(.uppercase)
                .tracking(0.5)

            Spacer()
        }
        .padding(.horizontal, Spacing.lg)
        .padding(.top, Spacing.md)
        .padding(.bottom, Spacing.sm)
    }
}

// MARK: - Cron Task Row

struct CronTaskRow: View {
    let task: CronTaskInfo
    let onToggle: () -> Void
    let onRunNow: () -> Void
    let onDelete: () -> Void

    var agentDefinition: AgentDefinition? {
        AgentDefinition.all.first { $0.name == task.agentName }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            topRow
            bottomRow
        }
        .padding(Spacing.md)
        .background(CipherTheme.surface)
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
        .overlay(
            RoundedRectangle(cornerRadius: CornerRadius.md)
                .stroke(CipherTheme.border, lineWidth: 1)
        )
        .contextMenu {
            Button(action: onRunNow) {
                Label("Run Now", systemImage: "play.fill")
            }
            Button(role: .destructive, action: onDelete) {
                Label("Delete", systemImage: "trash")
            }
        }
    }

    private var topRow: some View {
        HStack {
            VStack(alignment: .leading, spacing: Spacing.xs) {
                let name = agentDefinition?.displayName ?? task.agentName
                Text(name)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(CipherTheme.textPrimary)

                let schedule = cronToReadable(task.cronExpression)
                Text(schedule)
                    .font(.system(size: 13))
                    .foregroundColor(CipherTheme.textSecondary)
            }

            Spacer()

            Button(action: onToggle) {
                let iconName = task.enabled ? "checkmark.circle.fill" : "circle"
                let iconColor = task.enabled ? CipherTheme.accent : CipherTheme.textTertiary
                Image(systemName: iconName)
                    .font(.system(size: 24))
                    .foregroundColor(iconColor)
            }
        }
    }

    private var bottomRow: some View {
        HStack(spacing: Spacing.lg) {
            lastRunLabel
            nextRunLabel
            Spacer()
        }
    }

    private var lastRunLabel: some View {
        VStack(alignment: .leading, spacing: Spacing.xxs) {
            Text("Last run")
                .font(.system(size: 11, weight: .medium))
                .foregroundColor(CipherTheme.textTertiary)

            if let lastRun = task.lastRun, let date = parseISO8601(lastRun) {
                Text(date.timeAgoDisplay())
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(CipherTheme.textSecondary)
            } else {
                Text("Never")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(CipherTheme.textTertiary)
            }
        }
    }

    private var nextRunLabel: some View {
        VStack(alignment: .leading, spacing: Spacing.xxs) {
            Text("Next run")
                .font(.system(size: 11, weight: .medium))
                .foregroundColor(CipherTheme.textTertiary)

            if let nextRun = task.nextRun, let date = parseISO8601(nextRun) {
                Text(date.relativeToNow())
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(CipherTheme.success)
            } else {
                Text("—")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(CipherTheme.textTertiary)
            }
        }
    }
}

// MARK: - Cron to Human-Readable

func cronToReadable(_ cron: String) -> String {
    let components = cron.split(separator: " ").map(String.init)

    guard components.count == 5 else {
        return cron
    }

    let minute = components[0]
    let hour = components[1]
    let dayOfMonth = components[2]
    let month = components[3]
    let dayOfWeek = components[4]

    if minute == "0" || minute == "*" {
        if hour == "*" {
            return "Every hour"
        }

        if dayOfMonth == "*" && month == "*" {
            if dayOfWeek == "*" {
                if let hourNum = Int(hour) {
                    let displayHour = hourNum % 12 == 0 ? 12 : hourNum % 12
                    let amPm = hourNum >= 12 ? "PM" : "AM"
                    return "Daily at \(displayHour):00 \(amPm)"
                }
                return "Daily"
            } else if dayOfWeek == "1-5" || dayOfWeek == "0-4" {
                if let hourNum = Int(hour) {
                    let displayHour = hourNum % 12 == 0 ? 12 : hourNum % 12
                    let amPm = hourNum >= 12 ? "PM" : "AM"
                    return "Weekdays at \(displayHour):00 \(amPm)"
                }
                return "Weekdays"
            }
        }
    }

    if minute.hasPrefix("*/"), let interval = Int(minute.dropFirst(2)) {
        if interval == 60 { return "Every hour" }
        if interval == 240 { return "Every 4 hours" }
        if interval == 480 { return "Every 8 hours" }
        if interval == 1440 { return "Daily" }
        return "Every \(interval) minutes"
    }

    return cron
}

// MARK: - Parse ISO8601

func parseISO8601(_ dateString: String) -> Date? {
    let formatter = ISO8601DateFormatter()
    return formatter.date(from: dateString)
}

// MARK: - Add Schedule Sheet

struct AddScheduleSheet: View {
    @Binding var isPresented: Bool
    let onAdd: (CronTaskInfo) -> Void

    @State private var selectedAgentName: String = AgentDefinition.all.first?.name ?? ""
    @State private var cronExpression = ""
    @State private var taskName = ""

    private var cronAgents: [AgentDefinition] {
        AgentDefinition.all.filter { $0.actions.contains(.cron) }
    }

    private var selectedAgent: AgentDefinition? {
        AgentDefinition.all.first { $0.name == selectedAgentName }
    }

    var body: some View {
        NavigationStack {
            Form {
                agentSection
                scheduleSection
                detailsSection
            }
            .navigationTitle("Add Schedule")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    cancelButton
                }
                ToolbarItem(placement: .topBarTrailing) {
                    addButton
                }
            }
        }
    }

    private var agentSection: some View {
        Section("Agent") {
            Picker("Select Agent", selection: $selectedAgentName) {
                ForEach(cronAgents) { agent in
                    Text(agent.displayName).tag(agent.name)
                }
            }
        }
    }

    private var scheduleSection: some View {
        Section("Schedule") {
            TextField("Cron Expression", text: $cronExpression)
                .font(.system(.body, design: .monospaced))
            Text("E.g., \"0 7 * * *\" for daily at 7 AM")
                .font(.caption)
                .foregroundColor(CipherTheme.textTertiary)
        }
    }

    private var detailsSection: some View {
        Section("Details") {
            TextField("Task Name", text: $taskName)
        }
    }

    private var cancelButton: some View {
        Button("Cancel") {
            isPresented = false
        }
        .foregroundColor(CipherTheme.accent)
    }

    private var addButton: some View {
        Button("Add") {
            addSchedule()
        }
        .foregroundColor(CipherTheme.accent)
        .disabled(cronExpression.isEmpty || taskName.isEmpty)
    }

    private func addSchedule() {
        let agentDisplayName = selectedAgent?.displayName ?? selectedAgentName
        let name = taskName.isEmpty ? agentDisplayName : taskName
        let newTask = CronTaskInfo(
            taskId: UUID().uuidString,
            name: name,
            cronExpression: cronExpression,
            agentName: selectedAgentName,
            operation: "spawn",
            enabled: true,
            description: "",
            lastRun: nil,
            nextRun: nil,
            runCount: 0,
            lastError: nil
        )
        onAdd(newTask)
        isPresented = false
    }
}

#Preview {
    NavigationStack {
        CronManagerView()
    }
    .background(CipherTheme.background)
}

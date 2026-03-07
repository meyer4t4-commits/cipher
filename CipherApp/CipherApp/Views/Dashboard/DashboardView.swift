import SwiftUI

// MARK: - Agent Dashboard

struct DashboardView: View {
    @State private var viewModel = DashboardViewModel()
    @State private var selectedSection = 0

    var body: some View {
        NavigationStack {
            ZStack {
                CipherTheme.background.ignoresSafeArea()

                ScrollView(.vertical, showsIndicators: false) {
                    VStack(spacing: Spacing.lg) {
                        // Stats Header
                        statsHeader

                        // Pending Approvals (urgent, always on top)
                        if !viewModel.pendingApprovals.isEmpty {
                            approvalsSection
                        }

                        // Section Picker
                        Picker("Section", selection: $selectedSection) {
                            Text("Agents").tag(0)
                            Text("Scheduled").tag(1)
                            Text("History").tag(2)
                        }
                        .pickerStyle(.segmented)
                        .padding(.horizontal, Spacing.lg)

                        // Content
                        switch selectedSection {
                        case 0: agentsSection
                        case 1: cronSection
                        case 2: historySection
                        default: EmptyView()
                        }
                    }
                    .padding(.vertical, Spacing.md)
                }
            }
            .navigationTitle("Dashboard")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        Task { await viewModel.loadAll() }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                            .foregroundColor(CipherTheme.accent)
                    }
                }
            }
            .task {
                await viewModel.loadAll()
            }
            .refreshable {
                await viewModel.loadAll()
            }
        }
    }

    // MARK: - Stats Header

    private var statsHeader: some View {
        HStack(spacing: Spacing.md) {
            StatCard(
                title: "Agents",
                value: "\(viewModel.totalAgents)",
                icon: "cpu",
                color: CipherTheme.accent
            )
            StatCard(
                title: "Scheduled",
                value: "\(viewModel.cronTasks.filter { $0.enabled }.count)",
                icon: "clock.arrow.circlepath",
                color: CipherTheme.success
            )
            StatCard(
                title: "Approvals",
                value: "\(viewModel.pendingApprovals.count)",
                icon: "exclamationmark.circle",
                color: viewModel.pendingApprovals.isEmpty ? CipherTheme.textTertiary : CipherTheme.warning
            )
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Approvals Section

    private var approvalsSection: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            HStack {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundColor(CipherTheme.warning)
                Text("Pending Approvals")
                    .font(.headline)
                    .foregroundColor(CipherTheme.textPrimary)
                Spacer()
                Text("\(viewModel.pendingApprovals.count)")
                    .font(.caption)
                    .foregroundColor(CipherTheme.warning)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(CipherTheme.warning.opacity(0.2))
                    .clipShape(Capsule())
            }
            .padding(.horizontal, Spacing.lg)

            ForEach(viewModel.pendingApprovals) { approval in
                ApprovalCard(approval: approval) {
                    Task { await viewModel.approveTask(approval.taskId) }
                } onReject: {
                    Task { await viewModel.rejectTask(approval.taskId) }
                }
            }
            .padding(.horizontal, Spacing.lg)
        }
    }

    // MARK: - Agents Section

    private var agentsSection: some View {
        LazyVStack(spacing: Spacing.sm) {
            ForEach(viewModel.agents) { agent in
                AgentCard(agent: agent)
            }
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Cron Section

    private var cronSection: some View {
        LazyVStack(spacing: Spacing.sm) {
            ForEach(viewModel.cronTasks) { task in
                CronTaskCard(task: task) { enable in
                    Task { await viewModel.toggleCronTask(task.taskId, enable: enable) }
                } onTrigger: {
                    Task { await viewModel.triggerCronTask(task.taskId) }
                }
            }
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - History Section

    private var historySection: some View {
        LazyVStack(spacing: Spacing.sm) {
            if viewModel.executionHistory.isEmpty {
                Text("No execution history yet")
                    .font(.subheadline)
                    .foregroundColor(CipherTheme.textTertiary)
                    .frame(maxWidth: .infinity)
                    .padding(.top, Spacing.xxxl)
            }
            ForEach(viewModel.executionHistory) { result in
                HistoryCard(result: result)
            }
        }
        .padding(.horizontal, Spacing.lg)
    }
}

// MARK: - Stat Card

struct StatCard: View {
    let title: String
    let value: String
    let icon: String
    let color: Color

    var body: some View {
        VStack(spacing: Spacing.xs) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(color)
            Text(value)
                .font(.title2.bold())
                .foregroundColor(CipherTheme.textPrimary)
            Text(title)
                .font(.caption)
                .foregroundColor(CipherTheme.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Spacing.md)
        .background(CipherTheme.surface)
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
    }
}

// MARK: - Approval Card

struct ApprovalCard: View {
    let approval: PendingApproval
    let onApprove: () -> Void
    let onReject: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            HStack {
                Text(approval.agentName.replacingOccurrences(of: "_", with: " ").capitalized)
                    .font(.subheadline.bold())
                    .foregroundColor(CipherTheme.warning)
                Spacer()
            }

            Text(approval.instruction)
                .font(.caption)
                .foregroundColor(CipherTheme.textSecondary)
                .lineLimit(3)

            HStack(spacing: Spacing.md) {
                Button {
                    onApprove()
                } label: {
                    HStack {
                        Image(systemName: "checkmark")
                        Text("Approve")
                    }
                    .font(.caption.bold())
                    .foregroundColor(.white)
                    .padding(.horizontal, Spacing.lg)
                    .padding(.vertical, Spacing.sm)
                    .background(CipherTheme.success)
                    .clipShape(Capsule())
                }

                Button {
                    onReject()
                } label: {
                    HStack {
                        Image(systemName: "xmark")
                        Text("Reject")
                    }
                    .font(.caption.bold())
                    .foregroundColor(.white)
                    .padding(.horizontal, Spacing.lg)
                    .padding(.vertical, Spacing.sm)
                    .background(CipherTheme.error)
                    .clipShape(Capsule())
                }

                Spacer()
            }
        }
        .padding(Spacing.md)
        .background(CipherTheme.surfaceElevated)
        .overlay(
            RoundedRectangle(cornerRadius: CornerRadius.md)
                .stroke(CipherTheme.warning.opacity(0.3), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
    }
}

// MARK: - Agent Card

struct AgentCard: View {
    let agent: AgentInfo
    @State private var isExpanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            HStack {
                Image(systemName: iconForAgent(agent.name))
                    .foregroundColor(CipherTheme.accent)
                    .frame(width: 24)

                VStack(alignment: .leading, spacing: 2) {
                    Text(agent.name.replacingOccurrences(of: "_", with: " ").capitalized)
                        .font(.subheadline.bold())
                        .foregroundColor(CipherTheme.textPrimary)
                    Text(agent.description)
                        .font(.caption2)
                        .foregroundColor(CipherTheme.textTertiary)
                        .lineLimit(isExpanded ? nil : 1)
                }

                Spacer()

                Text("\(agent.capabilities.count)")
                    .font(.caption2.bold())
                    .foregroundColor(CipherTheme.accent)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(CipherTheme.accent.opacity(0.15))
                    .clipShape(Capsule())

                Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                    .font(.caption)
                    .foregroundColor(CipherTheme.textTertiary)
            }

            if isExpanded {
                Divider()
                    .overlay(CipherTheme.border)

                ForEach(agent.capabilities) { cap in
                    HStack(spacing: Spacing.sm) {
                        Circle()
                            .fill(CipherTheme.accent)
                            .frame(width: 4, height: 4)
                        Text(cap.name.replacingOccurrences(of: "_", with: " "))
                            .font(.caption)
                            .foregroundColor(CipherTheme.textSecondary)
                        Spacer()
                        if cap.requiresApproval {
                            Image(systemName: "lock.fill")
                                .font(.caption2)
                                .foregroundColor(CipherTheme.warning)
                        }
                    }
                }
            }
        }
        .padding(Spacing.md)
        .background(CipherTheme.surface)
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
        .onTapGesture {
            withAnimation(.easeInOut(duration: 0.2)) {
                isExpanded.toggle()
            }
        }
    }

    private func iconForAgent(_ name: String) -> String {
        // Omni-Savant Organization (Central Nervous System)
        if name.contains("chronos") { return "clock.badge.checkmark" }
        if name.contains("archivist") { return "archivebox" }
        if name.contains("sentinel") { return "bell.badge" }
        if name.contains("synthesis") { return "brain.head.profile" }
        // Apex Asset Hunter (Real Estate)
        if name.contains("market_pulse") { return "chart.line.uptrend.xyaxis" }
        if name.contains("profitability") { return "dollarsign.circle" }
        if name.contains("neighborhood") { return "map" }
        if name.contains("deal_flow") { return "building.2" }
        // Global Expansion Pulse
        if name.contains("scout") { return "binoculars" }
        if name.contains("analyst") { return "chart.bar.xaxis" }
        if name.contains("outreach") { return "paperplane" }
        if name.contains("provisioning") { return "server.rack" }
        // Core Agents
        if name.contains("shell") { return "terminal" }
        if name.contains("web") { return "globe" }
        if name.contains("code") { return "chevron.left.forwardslash.chevron.right" }
        if name.contains("trading") { return "chart.xyaxis.line" }
        if name.contains("deploy") { return "icloud.and.arrow.up" }
        if name.contains("research") { return "magnifyingglass" }
        if name.contains("communication") { return "message" }
        if name.contains("image") { return "photo" }
        if name.contains("video") { return "film" }
        if name.contains("legal") { return "scale.3d" }
        if name.contains("apex") { return "crown" }
        if name.contains("monitor") { return "waveform.path.ecg" }
        if name.contains("brave") || name.contains("search") { return "magnifyingglass.circle" }
        if name.contains("file") { return "doc" }
        if name.contains("data") { return "cylinder" }
        if name.contains("scheduler") { return "calendar.badge.clock" }
        if name.contains("skill") { return "hammer" }
        return "cpu"
    }
}

// MARK: - Cron Task Card

struct CronTaskCard: View {
    let task: CronTaskInfo
    let onToggle: (Bool) -> Void
    let onTrigger: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            HStack {
                Image(systemName: task.enabled ? "clock.fill" : "clock")
                    .foregroundColor(task.enabled ? CipherTheme.success : CipherTheme.textTertiary)

                VStack(alignment: .leading, spacing: 2) {
                    Text(task.name)
                        .font(.subheadline.bold())
                        .foregroundColor(CipherTheme.textPrimary)
                    Text(task.cronExpression)
                        .font(.caption.monospaced())
                        .foregroundColor(CipherTheme.accent)
                }

                Spacer()

                Toggle("", isOn: Binding(
                    get: { task.enabled },
                    set: { onToggle($0) }
                ))
                .labelsHidden()
                .tint(CipherTheme.accent)
            }

            Text(task.description)
                .font(.caption2)
                .foregroundColor(CipherTheme.textTertiary)
                .lineLimit(2)

            HStack {
                if let lastRun = task.lastRun {
                    Label(formatDate(lastRun), systemImage: "checkmark.circle")
                        .font(.caption2)
                        .foregroundColor(CipherTheme.textTertiary)
                }

                Spacer()

                if task.lastError != nil {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.caption2)
                        .foregroundColor(CipherTheme.error)
                }

                Text("Runs: \(task.runCount)")
                    .font(.caption2)
                    .foregroundColor(CipherTheme.textTertiary)

                Button {
                    onTrigger()
                } label: {
                    Image(systemName: "play.circle.fill")
                        .foregroundColor(CipherTheme.accent)
                }
            }
        }
        .padding(Spacing.md)
        .background(CipherTheme.surface)
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
    }

    private func formatDate(_ iso: String) -> String {
        let formatter = ISO8601DateFormatter()
        guard let date = formatter.date(from: iso) else { return iso }
        let display = DateFormatter()
        display.dateFormat = "MMM d, h:mm a"
        return display.string(from: date)
    }
}

// MARK: - History Card

struct HistoryCard: View {
    let result: AgentExecutionResult

    var body: some View {
        HStack(spacing: Spacing.md) {
            Circle()
                .fill(result.success ? CipherTheme.success : CipherTheme.error)
                .frame(width: 8, height: 8)

            VStack(alignment: .leading, spacing: 2) {
                Text(result.agentName.replacingOccurrences(of: "_", with: " ").capitalized)
                    .font(.caption.bold())
                    .foregroundColor(CipherTheme.textPrimary)

                if let error = result.error {
                    Text(error)
                        .font(.caption2)
                        .foregroundColor(CipherTheme.error)
                        .lineLimit(1)
                }
            }

            Spacer()

            if let ms = result.executionTimeMs {
                Text("\(ms)ms")
                    .font(.caption2.monospaced())
                    .foregroundColor(CipherTheme.textTertiary)
            }

            if result.verified == true {
                Image(systemName: "checkmark.seal.fill")
                    .font(.caption2)
                    .foregroundColor(CipherTheme.success)
            }
        }
        .padding(Spacing.md)
        .background(CipherTheme.surface)
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
    }
}

#Preview {
    DashboardView()
}

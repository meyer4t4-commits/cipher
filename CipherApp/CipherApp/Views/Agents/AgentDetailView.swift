import SwiftUI

// MARK: - Agent Detail View

struct AgentDetailView: View {
    @Environment(\.dismiss) var dismiss
    let agent: AgentInfo

    @State private var selectedTab = 0
    @State private var showExecuteTask = false
    @State private var taskInstruction = ""
    @State private var isExecuting = false
    @State private var executionResult: AgentExecutionResult?
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            ZStack {
                CipherTheme.background.ignoresSafeArea()

                ScrollView(.vertical, showsIndicators: false) {
                    VStack(spacing: Spacing.lg) {
                        // Header with agent info
                        agentHeader

                        // Tab selector
                        Picker("View", selection: $selectedTab) {
                            Text("Capabilities").tag(0)
                            Text("Details").tag(1)
                            Text("Execute").tag(2)
                        }
                        .pickerStyle(.segmented)
                        .padding(.horizontal, Spacing.lg)

                        // Tab content
                        switch selectedTab {
                        case 0:
                            capabilitiesSection
                        case 1:
                            detailsSection
                        case 2:
                            executeSection
                        default:
                            EmptyView()
                        }

                        Spacer(minLength: Spacing.xxxl)
                    }
                    .padding(.vertical, Spacing.md)
                }

                // Error banner
                if let error = errorMessage {
                    VStack {
                        HStack {
                            Image(systemName: "exclamationmark.circle.fill")
                                .foregroundColor(CipherTheme.error)
                            Text(error)
                                .font(.caption)
                                .foregroundColor(CipherTheme.textPrimary)
                            Spacer()
                            Button {
                                errorMessage = nil
                            } label: {
                                Image(systemName: "xmark")
                                    .foregroundColor(CipherTheme.textTertiary)
                            }
                        }
                        .padding(Spacing.md)
                        .background(CipherTheme.error.opacity(0.12))
                        .overlay(
                            RoundedRectangle(cornerRadius: CornerRadius.md)
                                .stroke(CipherTheme.error.opacity(0.3), lineWidth: 1)
                        )
                        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
                        .padding(Spacing.lg)

                        Spacer()
                    }
                }
            }
            .navigationTitle("Agent Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(action: { dismiss() }) {
                        HStack(spacing: Spacing.xs) {
                            Image(systemName: "chevron.left")
                                .font(.system(size: 16, weight: .semibold))
                            Text("Back")
                        }
                        .foregroundColor(CipherTheme.accent)
                    }
                }
            }
        }
    }

    // MARK: - Agent Header

    private var agentHeader: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            HStack(alignment: .top, spacing: Spacing.md) {
                // Icon background
                ZStack {
                    RoundedRectangle(cornerRadius: CornerRadius.lg)
                        .fill(CipherTheme.accent.opacity(0.12))
                        .frame(width: 60, height: 60)

                    Image(systemName: iconForAgent(agent.name))
                        .font(.system(size: 28, weight: .semibold))
                        .foregroundColor(CipherTheme.accent)
                }

                VStack(alignment: .leading, spacing: Spacing.xs) {
                    Text(agent.name.replacingOccurrences(of: "_", with: " ").capitalized)
                        .font(.title2.bold())
                        .foregroundColor(CipherTheme.textPrimary)

                    HStack(spacing: Spacing.sm) {
                        Circle()
                            .fill(CipherTheme.success)
                            .frame(width: 8, height: 8)

                        Text("Active")
                            .font(.caption)
                            .foregroundColor(CipherTheme.success)

                        Divider()
                            .frame(height: 12)

                        Text("v\(agent.version)")
                            .font(.caption)
                            .foregroundColor(CipherTheme.textTertiary)
                    }

                    Text(agent.description)
                        .font(.caption)
                        .foregroundColor(CipherTheme.textSecondary)
                        .lineLimit(2)
                }

                Spacer()
            }
            .padding(Spacing.lg)
            .background(
                LinearGradient(
                    colors: [CipherTheme.surface, CipherTheme.surfaceElevated.opacity(0.6)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .overlay(
                RoundedRectangle(cornerRadius: CornerRadius.lg)
                    .stroke(CipherTheme.border, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: CornerRadius.lg))
            .padding(.horizontal, Spacing.lg)
        }
    }

    // MARK: - Capabilities Section

    private var capabilitiesSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            if agent.capabilities.isEmpty {
                Text("No capabilities available")
                    .font(.caption)
                    .foregroundColor(CipherTheme.textTertiary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Spacing.xxl)
            } else {
                ForEach(agent.capabilities) { capability in
                    CapabilityCard(capability: capability)
                }
            }
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Details Section

    private var detailsSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            DetailRow(label: "Agent Name", value: agent.name)
            DetailRow(label: "Version", value: agent.version)
            DetailRow(label: "Description", value: agent.description)
            DetailRow(label: "Total Capabilities", value: "\(agent.capabilities.count)")
            DetailRow(label: "Status", value: "Active")
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Execute Section

    private var executeSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            if let result = executionResult {
                executionResultCard(result)
            } else {
                VStack(alignment: .leading, spacing: Spacing.md) {
                    Text("Execute Task")
                        .font(.subheadline.bold())
                        .foregroundColor(CipherTheme.textPrimary)

                    Text("Enter a task instruction for this agent to execute")
                        .font(.caption)
                        .foregroundColor(CipherTheme.textSecondary)

                    TextEditor(text: $taskInstruction)
                        .frame(height: 120)
                        .padding(Spacing.sm)
                        .background(CipherTheme.surface)
                        .overlay(
                            RoundedRectangle(cornerRadius: CornerRadius.md)
                                .stroke(CipherTheme.border, lineWidth: 1)
                        )
                        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
                        .foregroundColor(CipherTheme.textPrimary)

                    Button(action: executeTask) {
                        HStack {
                            if isExecuting {
                                SpinningCipherLogo(size: 14, spinning: true)
                            } else {
                                Image(systemName: "play.fill")
                            }
                            Text(isExecuting ? "Executing..." : "Execute Task")
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, Spacing.md)
                        .foregroundColor(.white)
                        .background(CipherTheme.accentGradient)
                        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
                    }
                    .disabled(taskInstruction.trimmingCharacters(in: .whitespaces).isEmpty || isExecuting)
                    .opacity(taskInstruction.trimmingCharacters(in: .whitespaces).isEmpty || isExecuting ? 0.6 : 1.0)
                }
                .padding(.horizontal, Spacing.lg)
            }
        }
    }

    // MARK: - Execution Result Card

    @ViewBuilder
    private func executionResultCard(_ result: AgentExecutionResult) -> some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            HStack {
                VStack(alignment: .leading, spacing: Spacing.sm) {
                    HStack(spacing: Spacing.sm) {
                        Image(systemName: result.success ? "checkmark.circle.fill" : "xmark.circle.fill")
                            .foregroundColor(result.success ? CipherTheme.success : CipherTheme.error)
                        Text(result.success ? "Success" : "Failed")
                            .font(.subheadline.bold())
                            .foregroundColor(result.success ? CipherTheme.success : CipherTheme.error)
                    }

                    if let ms = result.executionTimeMs {
                        Text("Execution Time: \(ms)ms")
                            .font(.caption)
                            .foregroundColor(CipherTheme.textTertiary)
                    }

                    if let error = result.error {
                        Text("Error: \(error)")
                            .font(.caption)
                            .foregroundColor(CipherTheme.error)
                            .lineLimit(2)
                    }
                }

                Spacer()

                Button(action: { executionResult = nil }) {
                    Image(systemName: "xmark")
                        .foregroundColor(CipherTheme.textTertiary)
                }
            }
            .padding(Spacing.md)
            .background(result.success ? CipherTheme.success.opacity(0.08) : CipherTheme.error.opacity(0.08))
            .overlay(
                RoundedRectangle(cornerRadius: CornerRadius.md)
                    .stroke(
                        result.success ? CipherTheme.success.opacity(0.3) : CipherTheme.error.opacity(0.3),
                        lineWidth: 1
                    )
            )
            .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))

            Button(action: { executionResult = nil; taskInstruction = "" }) {
                Text("Execute Another Task")
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Spacing.md)
                    .foregroundColor(.white)
                    .background(CipherTheme.accentGradient)
                    .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
            }
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Methods

    private func executeTask() {
        isExecuting = true
        errorMessage = nil

        Task {
            do {
                let result = try await AgentsViewModel().executeTask(
                    agentName: agent.name,
                    instruction: taskInstruction
                )
                await MainActor.run {
                    executionResult = result
                    isExecuting = false
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isExecuting = false
                }
            }
        }
    }

    private func iconForAgent(_ name: String) -> String {
        let lowerName = name.lowercased()

        if lowerName.contains("chronos") { return "clock.badge.checkmark" }
        if lowerName.contains("archivist") { return "archivebox" }
        if lowerName.contains("sentinel") { return "bell.badge" }
        if lowerName.contains("synthesis") { return "brain.head.profile" }
        if lowerName.contains("market") { return "chart.line.uptrend.xyaxis" }
        if lowerName.contains("profitability") { return "dollarsign.circle" }
        if lowerName.contains("neighborhood") { return "map" }
        if lowerName.contains("deal") { return "building.2" }
        if lowerName.contains("scout") { return "binoculars" }
        if lowerName.contains("analyst") { return "chart.bar.xaxis" }
        if lowerName.contains("outreach") { return "paperplane" }
        if lowerName.contains("provisioning") { return "server.rack" }
        if lowerName.contains("shell") { return "terminal" }
        if lowerName.contains("web") { return "globe" }
        if lowerName.contains("code") { return "chevron.left.forwardslash.chevron.right" }
        if lowerName.contains("trading") { return "chart.xyaxis.line" }
        if lowerName.contains("deploy") { return "icloud.and.arrow.up" }
        if lowerName.contains("research") { return "magnifyingglass" }
        if lowerName.contains("communication") { return "message" }
        if lowerName.contains("image") { return "photo" }
        if lowerName.contains("video") { return "film" }
        if lowerName.contains("legal") { return "scale.3d" }
        if lowerName.contains("apex") { return "crown" }
        if lowerName.contains("monitor") { return "waveform.path.ecg" }
        if lowerName.contains("brave") || lowerName.contains("search") { return "magnifyingglass.circle" }
        if lowerName.contains("file") { return "doc" }
        if lowerName.contains("data") { return "cylinder" }
        if lowerName.contains("scheduler") { return "calendar.badge.clock" }
        if lowerName.contains("skill") { return "hammer" }

        return "cpu"
    }
}

// MARK: - Capability Card

struct CapabilityCard: View {
    let capability: AgentCapabilityInfo

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            HStack {
                VStack(alignment: .leading, spacing: Spacing.xs) {
                    Text(capability.name.replacingOccurrences(of: "_", with: " "))
                        .font(.subheadline.bold())
                        .foregroundColor(CipherTheme.textPrimary)

                    Text(capability.description)
                        .font(.caption2)
                        .foregroundColor(CipherTheme.textSecondary)
                        .lineLimit(2)
                }

                Spacer()

                VStack(alignment: .trailing, spacing: Spacing.xs) {
                    if capability.requiresApproval {
                        HStack(spacing: Spacing.xs) {
                            Image(systemName: "lock.fill")
                                .font(.caption2)
                            Text("Approval")
                                .font(.caption2)
                        }
                        .foregroundColor(CipherTheme.warning)
                    }

                    Text("\(capability.timeoutSeconds)s")
                        .font(.caption2)
                        .foregroundColor(CipherTheme.textTertiary)
                }
            }

            HStack(spacing: Spacing.sm) {
                Text(capability.category.capitalized)
                    .font(.caption)
                    .foregroundColor(CipherTheme.accent)
                    .padding(.horizontal, Spacing.sm)
                    .padding(.vertical, 2)
                    .background(CipherTheme.accent.opacity(0.12))
                    .clipShape(Capsule())

                Spacer()
            }
        }
        .padding(Spacing.md)
        .background(CipherTheme.surface)
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
    }
}

// MARK: - Detail Row

struct DetailRow: View {
    let label: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.xs) {
            Text(label)
                .font(.caption)
                .foregroundColor(CipherTheme.textTertiary)
                .textCase(.uppercase)
                .tracking(0.5)

            Text(value)
                .font(.subheadline)
                .foregroundColor(CipherTheme.textPrimary)
                .lineLimit(3)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Spacing.md)
        .background(CipherTheme.surface)
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
    }
}

#Preview {
    AgentDetailView(
        agent: AgentInfo(
            name: "Code",
            description: "Execute code in various programming languages",
            version: "1.0.0",
            capabilities: [
                AgentCapabilityInfo(
                    name: "Execute Python",
                    description: "Run Python code",
                    category: "execution",
                    requiresApproval: false,
                    timeoutSeconds: 30
                ),
                AgentCapabilityInfo(
                    name: "Execute JavaScript",
                    description: "Run JavaScript code",
                    category: "execution",
                    requiresApproval: false,
                    timeoutSeconds: 30
                )
            ]
        )
    )
}

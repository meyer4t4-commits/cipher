import SwiftUI

// MARK: - Active Spawns View

struct ActiveSpawnsView: View {
    let sessionId: String

    @State private var viewModel = SpawnSessionViewModel()
    @State private var refreshTask: Task<Void, Never>?

    var body: some View {
        ZStack {
            CipherTheme.background.ignoresSafeArea()

            VStack(spacing: 0) {
                summaryBar

                if viewModel.runningAgents.isEmpty && !viewModel.isLoading {
                    emptyState
                } else {
                    ScrollView(.vertical, showsIndicators: false) {
                        VStack(spacing: Spacing.sm) {
                            ForEach(viewModel.runningAgents) { agent in
                                SpawnAgentCard(
                                    agent: agent,
                                    onCancel: {
                                        Task {
                                            await viewModel.cancelAgent(taskId: agent.taskId)
                                        }
                                    }
                                )
                            }
                        }
                        .padding(Spacing.lg)
                    }
                }
            }
        }
        .navigationTitle("Active Agents")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            viewModel.currentSessionId = sessionId
            Task {
                await viewModel.refreshStatus()
                startAutoRefresh()
            }
        }
        .onDisappear {
            stopAutoRefresh()
        }
    }

    // MARK: - Summary Bar

    private var summaryBar: some View {
        VStack(spacing: Spacing.md) {
            HStack(spacing: Spacing.xl) {
                summaryItem(
                    count: viewModel.summary?.running ?? 0,
                    label: "running",
                    color: CipherTheme.accent
                )

                summaryItem(
                    count: viewModel.summary?.completed ?? 0,
                    label: "completed",
                    color: CipherTheme.success
                )

                summaryItem(
                    count: viewModel.summary?.failed ?? 0,
                    label: "failed",
                    color: CipherTheme.error
                )

                Spacer()
            }
            .padding(Spacing.lg)
        }
        .background(CipherTheme.surface)
        .border(top: CipherTheme.border)
    }

    @ViewBuilder
    private func summaryItem(count: Int, label: String, color: Color) -> some View {
        HStack(spacing: Spacing.sm) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)

            VStack(alignment: .leading, spacing: 0) {
                Text("\(count) \(label)")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(CipherTheme.textPrimary)
            }
        }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: Spacing.lg) {
            Spacer()

            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 48))
                .foregroundColor(CipherTheme.textTertiary)

            Text("No active spawns")
                .font(.system(size: 16, weight: .semibold))
                .foregroundColor(CipherTheme.textSecondary)

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Auto Refresh

    private func startAutoRefresh() {
        stopAutoRefresh()
        refreshTask = Task {
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 2_000_000_000)
                await viewModel.refreshStatus()
            }
        }
    }

    private func stopAutoRefresh() {
        refreshTask?.cancel()
        refreshTask = nil
    }
}

// MARK: - Spawn Agent Card

struct SpawnAgentCard: View {
    let agent: RunningAgentStatus
    let onCancel: () -> Void

    var statusColor: Color {
        switch agent.status.lowercased() {
        case "running": return CipherTheme.accent
        case "completed": return CipherTheme.success
        case "failed": return CipherTheme.error
        default: return CipherTheme.textTertiary
        }
    }

    var agentDefinition: AgentDefinition? {
        AgentDefinition.all.first { $0.name == agent.agentName }
    }

    var body: some View {
        HStack(spacing: Spacing.md) {
            // Left: Agent icon in colored circle
            ZStack {
                Circle()
                    .fill(statusColor.opacity(0.12))
                    .frame(width: 44, height: 44)

                if let definition = agentDefinition {
                    Image(systemName: definition.icon)
                        .font(.system(size: 18, weight: .semibold))
                        .foregroundColor(statusColor)
                } else {
                    Image(systemName: "gearshape")
                        .font(.system(size: 18, weight: .semibold))
                        .foregroundColor(statusColor)
                }
            }

            // Middle: Display name, current step, error
            VStack(alignment: .leading, spacing: Spacing.xs) {
                Text(agentDefinition?.displayName ?? agent.agentName)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(CipherTheme.textPrimary)

                if !agent.currentStep.isEmpty {
                    Text(agent.currentStep)
                        .font(.caption)
                        .foregroundColor(CipherTheme.textSecondary)
                        .lineLimit(1)
                }

                if let error = agent.error, !error.isEmpty {
                    HStack(spacing: Spacing.xs) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(.caption)
                        Text(error)
                            .font(.caption)
                    }
                    .foregroundColor(CipherTheme.error)
                    .lineLimit(1)
                }
            }

            Spacer()

            // Right: Progress ring + cancel button
            if agent.status.lowercased() == "running" {
                VStack(spacing: Spacing.sm) {
                    progressRing

                    Button(action: onCancel) {
                        Image(systemName: "xmark")
                            .font(.system(size: 11, weight: .semibold))
                            .foregroundColor(CipherTheme.error)
                            .frame(width: 24, height: 24)
                            .background(CipherTheme.error.opacity(0.12))
                            .clipShape(Circle())
                    }
                }
            } else {
                statusBadge
            }
        }
        .padding(Spacing.md)
        .background(CipherTheme.surface)
        .border(CipherTheme.border, width: 1)
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
    }

    private var progressRing: some View {
        ZStack {
            Circle()
                .stroke(CipherTheme.border, lineWidth: 2)
                .frame(width: 32, height: 32)

            Circle()
                .trim(from: 0, to: agent.progress)
                .stroke(
                    CipherTheme.accent,
                    style: StrokeStyle(lineWidth: 2, lineCap: .round)
                )
                .frame(width: 32, height: 32)
                .rotationEffect(.degrees(-90))

            Text("\(Int(agent.progress * 100))%")
                .font(.system(size: 9, weight: .bold, design: .monospaced))
                .foregroundColor(CipherTheme.textSecondary)
        }
    }

    private var statusBadge: some View {
        HStack(spacing: Spacing.xs) {
            Image(systemName: agent.status.lowercased() == "completed" ? "checkmark.circle.fill" : "exclamationmark.circle.fill")
                .font(.system(size: 12))

            Text(agent.status.capitalized)
                .font(.system(size: 12, weight: .semibold))
        }
        .foregroundColor(statusColor)
        .padding(.horizontal, Spacing.md)
        .padding(.vertical, Spacing.xs)
        .background(statusColor.opacity(0.12))
        .clipShape(Capsule())
    }
}

// MARK: - Border Modifier

extension View {
    func border(top color: Color, width: CGFloat = 1) -> some View {
        VStack(spacing: 0) {
            Divider()
                .background(color)
                .frame(height: width)
            self
        }
    }
}

#Preview {
    NavigationStack {
        ActiveSpawnsView(sessionId: "session-123")
    }
    .background(CipherTheme.background)
}

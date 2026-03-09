import SwiftUI

// MARK: - Research View (Self-Improvement Dashboard)

struct ResearchView: View {
    @State private var status: ResearchStatusResponse?
    @State private var selfTestResult: SelfTestResponse?
    @State private var isLoading = false
    @State private var isRunningTest = false
    @State private var isStarting = false
    @State private var errorMessage: String?

    let api = CipherAPI.shared

    var body: some View {
        ScrollView {
            VStack(spacing: Spacing.lg) {
                // Header
                headerSection

                // Status card
                statusCard

                // Self-test card
                selfTestCard

                // Experiment history
                if let experiments = status?.recentExperiments, !experiments.isEmpty {
                    experimentHistory(experiments)
                }

                // Stats card
                if let stats = status?.stats, (stats.totalExperiments ?? 0) > 0 {
                    statsCard(stats)
                }
            }
            .padding(Spacing.lg)
        }
        .background(CipherTheme.background.ignoresSafeArea())
        .task {
            await loadStatus()
        }
        .refreshable {
            await loadStatus()
        }
    }

    // MARK: - Header

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: Spacing.xs) {
            HStack {
                Image(systemName: "brain.head.profile")
                    .font(.system(size: 24, weight: .semibold))
                    .foregroundColor(CipherTheme.accent)

                Text("Self-Research")
                    .font(.system(size: 28, weight: .bold))
                    .foregroundColor(CipherTheme.textPrimary)

                Spacer()
            }

            Text("Cipher's autonomous self-improvement engine")
                .font(.system(size: 14))
                .foregroundColor(CipherTheme.textSecondary)
        }
    }

    // MARK: - Status Card

    private var statusCard: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            HStack {
                Circle()
                    .fill(isResearchRunning ? CipherTheme.success : CipherTheme.textTertiary)
                    .frame(width: 8, height: 8)

                Text(isResearchRunning ? "Research Loop Active" : "Research Loop Idle")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(CipherTheme.textPrimary)

                Spacer()
            }

            if isResearchRunning {
                Button(action: { Task { await stopResearch() } }) {
                    HStack(spacing: 6) {
                        Image(systemName: "stop.fill")
                            .font(.system(size: 12))
                        Text("Stop Research")
                            .font(.system(size: 14, weight: .semibold))
                    }
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Spacing.sm)
                    .background(CipherTheme.error.opacity(0.8))
                    .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
                }
            } else {
                Button(action: { Task { await startResearch() } }) {
                    HStack(spacing: 6) {
                        if isStarting {
                            ProgressView()
                                .tint(.white)
                                .scaleEffect(0.8)
                        } else {
                            Image(systemName: "play.fill")
                                .font(.system(size: 12))
                        }
                        Text("Start Overnight Research")
                            .font(.system(size: 14, weight: .semibold))
                    }
                    .foregroundColor(CipherTheme.textOnAccent)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Spacing.sm)
                    .background(CipherTheme.accentGradient)
                    .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
                }
                .disabled(isStarting)
            }

            if let error = errorMessage {
                Text(error)
                    .font(.system(size: 12))
                    .foregroundColor(CipherTheme.error)
            }
        }
        .padding(Spacing.lg)
        .background(
            RoundedRectangle(cornerRadius: CornerRadius.lg)
                .fill(.ultraThinMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: CornerRadius.lg)
                        .stroke(CipherTheme.border, lineWidth: 0.5)
                )
        )
    }

    // MARK: - Self-Test Card

    private var selfTestCard: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            HStack {
                Image(systemName: "checkmark.shield.fill")
                    .font(.system(size: 16))
                    .foregroundColor(CipherTheme.accent)

                Text("Self-Test Suite")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(CipherTheme.textPrimary)

                Spacer()

                if let result = selfTestResult {
                    Text(String(format: "%.0f%%", result.passRate * 100))
                        .font(.system(size: 13, weight: .bold, design: .monospaced))
                        .foregroundColor(result.passRate > 0.8 ? CipherTheme.success : CipherTheme.error)
                }
            }

            if let result = selfTestResult {
                HStack(spacing: Spacing.lg) {
                    statPill(label: "Score", value: String(format: "%.3f", result.aggregateScore))
                    statPill(label: "Passed", value: "\(result.testsPassed)/\(result.testsTotal)")
                    if let duration = result.totalDurationMs {
                        statPill(label: "Time", value: String(format: "%.1fs", duration / 1000))
                    }
                }

                if let failures = result.failures, !failures.isEmpty {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Failures:")
                            .font(.system(size: 12, weight: .medium))
                            .foregroundColor(CipherTheme.error)

                        ForEach(failures, id: \.name) { failure in
                            Text("• \(failure.name): \(failure.error ?? "unknown")")
                                .font(.system(size: 11))
                                .foregroundColor(CipherTheme.textTertiary)
                        }
                    }
                }
            }

            Button(action: { Task { await runSelfTest() } }) {
                HStack(spacing: 6) {
                    if isRunningTest {
                        ProgressView()
                            .tint(CipherTheme.accent)
                            .scaleEffect(0.7)
                    } else {
                        Image(systemName: "play.circle.fill")
                            .font(.system(size: 13))
                    }
                    Text(isRunningTest ? "Running Tests..." : "Run Self-Test")
                        .font(.system(size: 13, weight: .semibold))
                }
                .foregroundColor(CipherTheme.accent)
                .frame(maxWidth: .infinity)
                .padding(.vertical, Spacing.sm)
                .background(CipherTheme.accent.opacity(0.1))
                .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
            }
            .disabled(isRunningTest)
        }
        .padding(Spacing.lg)
        .background(
            RoundedRectangle(cornerRadius: CornerRadius.lg)
                .fill(.ultraThinMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: CornerRadius.lg)
                        .stroke(CipherTheme.border, lineWidth: 0.5)
                )
        )
    }

    // MARK: - Experiment History

    private func experimentHistory(_ experiments: [ExperimentEntry]) -> some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Recent Experiments")
                .font(.system(size: 15, weight: .semibold))
                .foregroundColor(CipherTheme.textPrimary)

            ForEach(experiments) { exp in
                experimentRow(exp)
            }
        }
        .padding(Spacing.lg)
        .background(
            RoundedRectangle(cornerRadius: CornerRadius.lg)
                .fill(.ultraThinMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: CornerRadius.lg)
                        .stroke(CipherTheme.border, lineWidth: 0.5)
                )
        )
    }

    private func experimentRow(_ exp: ExperimentEntry) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(verdictIcon(exp.verdict ?? ""))
                    .font(.system(size: 14))

                Text(exp.hypothesis ?? "Unknown experiment")
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(CipherTheme.textPrimary)
                    .lineLimit(1)

                Spacer()

                if let improvement = exp.improvement {
                    Text(String(format: "%+.1f%%", improvement * 100))
                        .font(.system(size: 12, weight: .bold, design: .monospaced))
                        .foregroundColor(improvement > 0 ? CipherTheme.success : CipherTheme.error)
                }
            }

            HStack(spacing: Spacing.sm) {
                if let file = exp.targetFile {
                    Text(file.split(separator: "/").last.map(String.init) ?? file)
                        .font(.system(size: 10, weight: .medium, design: .monospaced))
                        .foregroundColor(CipherTheme.textTertiary)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(CipherTheme.accent.opacity(0.1))
                        .clipShape(Capsule())
                }

                if let type = exp.modificationType {
                    Text(type.replacingOccurrences(of: "_", with: " "))
                        .font(.system(size: 10))
                        .foregroundColor(CipherTheme.textTertiary)
                }

                Spacer()

                if let duration = exp.durationSeconds {
                    Text(String(format: "%.0fs", duration))
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundColor(CipherTheme.textTertiary)
                }
            }
        }
        .padding(.vertical, 4)
    }

    // MARK: - Stats Card

    private func statsCard(_ stats: ResearchStats) -> some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Research Stats")
                .font(.system(size: 15, weight: .semibold))
                .foregroundColor(CipherTheme.textPrimary)

            LazyVGrid(columns: [
                GridItem(.flexible()),
                GridItem(.flexible()),
                GridItem(.flexible()),
            ], spacing: Spacing.md) {
                statBox(label: "Experiments", value: "\(stats.totalExperiments ?? 0)")
                statBox(label: "Kept", value: "\(stats.kept ?? 0)")
                statBox(label: "Keep Rate", value: String(format: "%.0f%%", (stats.keepRate ?? 0) * 100))
                statBox(label: "Discarded", value: "\(stats.discarded ?? 0)")
                statBox(label: "Errors", value: "\(stats.errors ?? 0)")
                statBox(label: "Runtime", value: String(format: "%.1fh", stats.totalRuntimeHours ?? 0))
            }
        }
        .padding(Spacing.lg)
        .background(
            RoundedRectangle(cornerRadius: CornerRadius.lg)
                .fill(.ultraThinMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: CornerRadius.lg)
                        .stroke(CipherTheme.border, lineWidth: 0.5)
                )
        )
    }

    // MARK: - Helpers

    private func statPill(label: String, value: String) -> some View {
        VStack(spacing: 2) {
            Text(value)
                .font(.system(size: 14, weight: .bold, design: .monospaced))
                .foregroundColor(CipherTheme.textPrimary)
            Text(label)
                .font(.system(size: 10))
                .foregroundColor(CipherTheme.textTertiary)
        }
    }

    private func statBox(label: String, value: String) -> some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.system(size: 16, weight: .bold, design: .monospaced))
                .foregroundColor(CipherTheme.textPrimary)
            Text(label)
                .font(.system(size: 10))
                .foregroundColor(CipherTheme.textTertiary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Spacing.sm)
        .background(
            RoundedRectangle(cornerRadius: CornerRadius.sm)
                .fill(CipherTheme.accent.opacity(0.05))
        )
    }

    private func verdictIcon(_ verdict: String) -> String {
        switch verdict.uppercased() {
        case "KEPT": return "✅"
        case "DISCARDED": return "⏭️"
        case "ERROR": return "❌"
        default: return "⚪"
        }
    }

    private var isResearchRunning: Bool {
        status?.running ?? false
    }

    // MARK: - API Calls

    private func loadStatus() async {
        isLoading = true
        defer { isLoading = false }

        do {
            status = try await api.getResearchStatus()
        } catch {
            // Silently fail — research endpoint may not be available yet
        }
    }

    private func startResearch() async {
        isStarting = true
        errorMessage = nil
        defer { isStarting = false }

        do {
            _ = try await api.startResearch(maxExperiments: 50, maxHours: 8.0)
            await loadStatus()
        } catch {
            errorMessage = "Failed to start: \(error.localizedDescription)"
        }
    }

    private func stopResearch() async {
        do {
            try await api.stopResearch()
            await loadStatus()
        } catch {
            errorMessage = "Failed to stop: \(error.localizedDescription)"
        }
    }

    private func runSelfTest() async {
        isRunningTest = true
        defer { isRunningTest = false }

        do {
            selfTestResult = try await api.runSelfTest()
        } catch {
            errorMessage = "Self-test failed: \(error.localizedDescription)"
        }
    }
}

#Preview {
    ResearchView()
}

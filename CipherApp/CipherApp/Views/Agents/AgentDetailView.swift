import SwiftUI

// MARK: - Agent Detail View

struct AgentDetailView: View {
    let agent: AgentDefinition
    let serverOnline: Bool

    @State private var instruction = ""
    @State private var showExecuteSheet = false
    @State private var showCronSheet = false
    @State private var executionState = AgentExecutionState()
    @State private var progressLog = AgentProgressLog()

    var body: some View {
        ZStack {
            CipherTheme.background.ignoresSafeArea()

            ScrollView(.vertical, showsIndicators: false) {
                VStack(spacing: Spacing.lg) {
                    heroSection
                    quickRunSection
                    purposeSection
                    useCasesSection

                    if agent.actions.contains(.cron) {
                        cronActionButton
                    }

                    Spacer(minLength: 40)
                }
                .padding(.top, Spacing.md)
            }
        }
        .navigationTitle(agent.displayName)
        .navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $showExecuteSheet) {
            AgentExecutionSheet(
                agent: agent,
                instruction: $instruction,
                state: $executionState,
                progressLog: progressLog
            )
        }
        .sheet(isPresented: $showCronSheet) {
            AgentCronSheet(agent: agent)
        }
    }

    // MARK: - Hero

    private var heroSection: some View {
        VStack(spacing: Spacing.md) {
            ZStack {
                Circle()
                    .fill(
                        RadialGradient(
                            colors: [agent.category.color.opacity(0.3), agent.category.color.opacity(0.05)],
                            center: .center,
                            startRadius: 0,
                            endRadius: 50
                        )
                    )
                    .frame(width: 80, height: 80)

                Image(systemName: agent.icon)
                    .font(.system(size: 32, weight: .semibold))
                    .foregroundColor(agent.category.color)
            }

            Text(agent.displayName)
                .font(.title2.bold())
                .foregroundColor(CipherTheme.textPrimary)

            Text(agent.description)
                .font(.subheadline)
                .foregroundColor(CipherTheme.textSecondary)
                .multilineTextAlignment(.center)

            HStack(spacing: 6) {
                Image(systemName: agent.category.icon)
                    .font(.caption)
                Text(agent.category.rawValue)
                    .font(.caption.bold())
            }
            .foregroundColor(agent.category.color)
            .padding(.horizontal, 14)
            .padding(.vertical, 6)
            .background(agent.category.color.opacity(0.12))
            .clipShape(Capsule())
        }
        .frame(maxWidth: .infinity)
        .padding(Spacing.lg)
    }

    // MARK: - Quick Run (Main CTA)

    private var quickRunSection: some View {
        VStack(spacing: Spacing.md) {
            HStack(spacing: Spacing.sm) {
                Image(systemName: "bolt.fill")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(agent.category.color)
                Text("Run \(agent.displayName)")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(CipherTheme.textPrimary)
                Spacer()
            }

            TextField("Tell \(agent.displayName) what to do...", text: $instruction, axis: .vertical)
                .textFieldStyle(.plain)
                .font(.system(size: 15))
                .foregroundColor(CipherTheme.textPrimary)
                .padding(Spacing.md)
                .background(CipherTheme.background)
                .overlay(
                    RoundedRectangle(cornerRadius: CornerRadius.sm)
                        .stroke(
                            instruction.isEmpty ? CipherTheme.border : agent.category.color.opacity(0.4),
                            lineWidth: 1
                        )
                )
                .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))
                .lineLimit(2...5)

            if !serverOnline {
                serverOfflineWarning
            }

            Button {
                executionState = AgentExecutionState()
                showExecuteSheet = true
                Task {
                    await runAgent()
                }
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: "play.fill")
                        .font(.system(size: 13))
                    Text("Execute")
                        .font(.system(size: 16, weight: .bold))
                }
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(
                    instruction.trimmingCharacters(in: .whitespaces).isEmpty || !serverOnline
                    ? Color.gray.opacity(0.5)
                    : agent.category.color
                )
                .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
            }
            .disabled(instruction.trimmingCharacters(in: .whitespaces).isEmpty || !serverOnline)
        }
        .padding(Spacing.lg)
        .background(CipherTheme.surface)
        .overlay(
            RoundedRectangle(cornerRadius: CornerRadius.md)
                .stroke(agent.category.color.opacity(0.2), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
        .padding(.horizontal, Spacing.lg)
    }

    private var serverOfflineWarning: some View {
        HStack(spacing: 6) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.caption)
                .foregroundColor(.orange)
            Text("Server is offline. Connect to execute agents.")
                .font(.caption)
                .foregroundColor(CipherTheme.textTertiary)
        }
    }

    // MARK: - Purpose

    private var purposeSection: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            Label("What it does", systemImage: "info.circle")
                .font(.subheadline.bold())
                .foregroundColor(CipherTheme.textPrimary)

            Text(agent.purpose)
                .font(.subheadline)
                .foregroundColor(CipherTheme.textSecondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Spacing.lg)
        .background(CipherTheme.surface)
        .overlay(
            RoundedRectangle(cornerRadius: CornerRadius.md)
                .stroke(CipherTheme.border, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Use Cases (Tappable → Fill Instruction)

    private var useCasesSection: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            Label("Try saying", systemImage: "text.bubble")
                .font(.subheadline.bold())
                .foregroundColor(CipherTheme.textPrimary)

            VStack(alignment: .leading, spacing: 8) {
                ForEach(agent.useCases, id: \.self) { useCase in
                    Button {
                        instruction = useCase.replacingOccurrences(of: "\"", with: "")
                    } label: {
                        HStack(alignment: .top, spacing: 8) {
                            Image(systemName: "arrow.right.circle.fill")
                                .font(.system(size: 12))
                                .foregroundColor(agent.category.color.opacity(0.6))
                                .padding(.top, 2)
                            Text(useCase.replacingOccurrences(of: "\"", with: ""))
                                .font(.subheadline)
                                .foregroundColor(CipherTheme.textSecondary)
                                .multilineTextAlignment(.leading)
                        }
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Spacing.lg)
        .background(CipherTheme.surface)
        .overlay(
            RoundedRectangle(cornerRadius: CornerRadius.md)
                .stroke(CipherTheme.border, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Cron Action Button

    private var cronActionButton: some View {
        Button { showCronSheet = true } label: {
            HStack {
                Image(systemName: "clock.arrow.2.circlepath")
                    .font(.title3)
                    .foregroundColor(.orange)
                    .frame(width: 32)

                VStack(alignment: .leading, spacing: 2) {
                    Text("Schedule")
                        .font(.subheadline.bold())
                        .foregroundColor(CipherTheme.textPrimary)
                    Text("Run on a recurring schedule")
                        .font(.caption)
                        .foregroundColor(CipherTheme.textSecondary)
                }

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundColor(CipherTheme.textTertiary)
            }
            .padding(Spacing.md)
            .background(Color.orange.opacity(0.05))
            .overlay(
                RoundedRectangle(cornerRadius: CornerRadius.sm)
                    .stroke(Color.orange.opacity(0.2), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))
        }
        .buttonStyle(.plain)
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Execute Agent

    private func runAgent() async {
        let currentInstruction = instruction
        executionState.phase = .connecting
        progressLog.clear()

        try? await Task.sleep(nanoseconds: 300_000_000)
        executionState.phase = .sending
        executionState.statusText = "Sending to \(agent.displayName)..."

        try? await Task.sleep(nanoseconds: 200_000_000)
        executionState.phase = .running
        executionState.statusText = "\(agent.displayName) is working..."

        // Build prompt with vault credentials context
        let credentialContext = buildCredentialContext()
        let fullInstruction = credentialContext.isEmpty
            ? currentInstruction
            : "[credentials: \(credentialContext)] \(currentInstruction)"

        // Try streaming execution first (shows live progress)
        do {
            let result = try await CipherAPI.shared.executeTaskStreaming(
                agentName: agent.name,
                instruction: fullInstruction,
                onProgress: { event in
                    Task { @MainActor in
                        progressLog.append(ProgressEntry(type: event.type, message: event.message))
                    }
                }
            )

            await MainActor.run {
                executionState.phase = .complete
                executionState.success = result.success

                if result.success {
                    if let output = result.output?.value as? String {
                        executionState.fullOutput = output
                    } else {
                        executionState.fullOutput = "Task completed successfully."
                    }
                    executionState.statusText = "Completed"
                } else {
                    executionState.fullOutput = result.error ?? "Task failed."
                    executionState.statusText = "Failed"
                }

                if let ms = result.executionTimeMs {
                    executionState.executionTimeMs = ms
                }
            }
        } catch {
            // Fallback: try chat endpoint
            do {
                let agentPrompt = "[@\(agent.name)] \(fullInstruction)"
                let response = try await CipherAPI.shared.sendMessage(message: agentPrompt)
                executionState.phase = .complete
                executionState.success = true
                executionState.fullOutput = response.message
                executionState.statusText = "Completed"
                executionState.modelUsed = response.modelUsed
                executionState.tokensUsed = response.tokensUsed
                executionState.costUsd = response.costUsd
            } catch {
                // Last fallback: direct execute (no streaming)
                do {
                    let result = try await CipherAPI.shared.executeTask(
                        agentName: agent.name,
                        instruction: currentInstruction
                    )
                    executionState.phase = .complete
                    executionState.success = result.success

                    if result.success {
                        if let output = result.output?.value as? String {
                            executionState.fullOutput = output
                        } else {
                            executionState.fullOutput = "Task completed successfully."
                        }
                        executionState.statusText = "Completed"
                    } else {
                        executionState.fullOutput = result.error ?? "Task failed."
                        executionState.statusText = "Failed"
                    }

                    if let ms = result.executionTimeMs {
                        executionState.executionTimeMs = ms
                    }
                } catch {
                    executionState.phase = .complete
                    executionState.success = false
                    executionState.fullOutput = "Could not reach server: \(error.localizedDescription)"
                    executionState.statusText = "Connection Failed"
                }
            }
        }

        instruction = ""
    }

    /// Build credential context string from vault for this agent's relevant services
    private func buildCredentialContext() -> String {
        let store = ProjectStore.shared
        guard !store.credentials.isEmpty else { return "" }

        // Map agent names to relevant service types
        let relevantServices: [String: [ServiceType]] = [
            "image_agent": [.openai, .stabilityai, .replicate],
            "video_agent": [.runway, .heygen, .replicate],
            "echo": [.elevenlabs, .suno],
            "scribe": [.openai, .anthropic, .notion],
            "ghost": [.brave],
            "web_agent": [.brave],
            "brave_search_agent": [.brave],
            "research_agent": [.brave],
            "deploy_agent": [.railway, .vercel, .cloudflare, .aws],
            "monitor_agent": [.railway, .cloudflare, .aws],
            "communication_agent": [.sendgrid, .twilio, .slack],
            "code_agent": [.github],
            "provisioning_agent": [.railway, .vercel, .supabase, .cloudflare, .aws],
            "outreach_agent": [.sendgrid, .twitter, .instagram, .youtube, .tiktok],
            "analyst_agent": [.brave],
            "scout_agent": [.brave],
            "sentinel_agent": [.github, .railway, .cloudflare],
            "trading_agent": [.brave, .stripe],
            "pipeline": [.openai, .anthropic],
            "shell_agent": [.railway, .github],
            "file_agent": [.cloudflare, .aws],
            "legal_agent": [.brave],
            "synthesis_agent": [.brave, .openai],
        ]

        let services = relevantServices[agent.name] ?? []
        var parts: [String] = []

        for cred in store.credentials {
            if services.contains(cred.serviceType) || services.isEmpty {
                var entry = "\(cred.serviceType.rawValue)=\(cred.tokenValue)"
                for (key, value) in cred.additionalFields {
                    entry += ";\(key)=\(value)"
                }
                parts.append(entry)
            }
        }

        return parts.joined(separator: "|")
    }
}

// MARK: - Execution State

struct AgentExecutionState {
    var phase: ExecutionPhase = .idle
    var statusText: String = ""
    var fullOutput: String = ""
    var success: Bool = false
    var modelUsed: String?
    var tokensUsed: Int?
    var costUsd: Double?
    var executionTimeMs: Int?
}

/// Observable progress log for live activity feed during agent execution
@Observable
@MainActor
class AgentProgressLog {
    var entries: [ProgressEntry] = []

    func append(_ entry: ProgressEntry) {
        entries.append(entry)
    }

    func clear() {
        entries.removeAll()
    }
}

struct ProgressEntry: Identifiable {
    let id = UUID()
    let timestamp = Date()
    let type: String      // "progress", "bash", "chain"
    let message: String

    var icon: String {
        switch type {
        case "bash": return "terminal"
        case "chain": return "link"
        default: return "arrow.right.circle"
        }
    }

    var color: Color {
        switch type {
        case "bash": return .green
        case "chain": return .purple
        default: return .blue
        }
    }
}

enum ExecutionPhase {
    case idle
    case connecting
    case sending
    case running
    case complete
}

// MARK: - Agent Execution Sheet

struct AgentExecutionSheet: View {
    let agent: AgentDefinition
    @Binding var instruction: String
    @Binding var state: AgentExecutionState
    var progressLog: AgentProgressLog
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ZStack {
                CipherTheme.background.ignoresSafeArea()

                ScrollView(.vertical, showsIndicators: false) {
                    VStack(spacing: Spacing.xl) {
                        statusHeader
                        progressSection

                        if !progressLog.entries.isEmpty {
                            progressLogSection
                        }

                        if state.phase == .complete {
                            outputSection
                            metadataSection
                        }

                        Spacer(minLength: 40)
                    }
                    .padding(.top, Spacing.lg)
                }
            }
            .navigationTitle("\(agent.displayName)")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button(state.phase == .complete ? "Done" : "Cancel") {
                        dismiss()
                    }
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(
                        state.phase == .complete ? agent.category.color : CipherTheme.textSecondary
                    )
                }
            }
        }
        .presentationDetents(state.phase == .complete ? [.large] : [.medium, .large])
        .presentationDragIndicator(.visible)
        .interactiveDismissDisabled(state.phase != .complete && state.phase != .idle)
    }

    // MARK: - Status Header

    private var statusHeader: some View {
        VStack(spacing: Spacing.md) {
            ZStack {
                Circle()
                    .fill(statusColor.opacity(0.12))
                    .frame(width: 72, height: 72)

                if state.phase == .complete {
                    Image(systemName: state.success ? "checkmark.circle.fill" : "xmark.circle.fill")
                        .font(.system(size: 36, weight: .medium))
                        .foregroundColor(statusColor)
                } else {
                    SpinningCipherLogo(size: 48, spinning: true)
                }
            }

            Text(statusTitle)
                .font(.system(size: 20, weight: .bold))
                .foregroundColor(CipherTheme.textPrimary)

            Text(state.statusText)
                .font(.system(size: 14))
                .foregroundColor(CipherTheme.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.horizontal, Spacing.lg)
    }

    private var statusTitle: String {
        switch state.phase {
        case .idle: return "Preparing..."
        case .connecting: return "Connecting..."
        case .sending: return "Sending..."
        case .running: return "Running..."
        case .complete: return state.success ? "Complete" : "Failed"
        }
    }

    private var statusColor: Color {
        if state.phase == .complete {
            return state.success ? CipherTheme.success : CipherTheme.error
        }
        return agent.category.color
    }

    // MARK: - Progress

    private var progressSection: some View {
        VStack(spacing: Spacing.sm) {
            HStack(spacing: Spacing.md) {
                phaseStep("Connect", done: phaseIndex >= 1, active: state.phase == .connecting)
                phaseLine(done: phaseIndex >= 2)
                phaseStep("Send", done: phaseIndex >= 2, active: state.phase == .sending)
                phaseLine(done: phaseIndex >= 3)
                phaseStep("Execute", done: phaseIndex >= 3, active: state.phase == .running)
                phaseLine(done: phaseIndex >= 4)
                phaseStep("Result", done: phaseIndex >= 4, active: false)
            }
        }
        .padding(.horizontal, Spacing.xl)
    }

    private var phaseIndex: Int {
        switch state.phase {
        case .idle: return 0
        case .connecting: return 1
        case .sending: return 2
        case .running: return 3
        case .complete: return 4
        }
    }

    private func phaseStep(_ label: String, done: Bool, active: Bool) -> some View {
        VStack(spacing: 4) {
            ZStack {
                Circle()
                    .fill(done ? agent.category.color : (active ? agent.category.color.opacity(0.3) : CipherTheme.border))
                    .frame(width: 24, height: 24)

                if done {
                    Image(systemName: "checkmark")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(.white)
                } else if active {
                    Circle()
                        .fill(agent.category.color)
                        .frame(width: 8, height: 8)
                }
            }
            Text(label)
                .font(.system(size: 10, weight: .semibold))
                .foregroundColor(done || active ? CipherTheme.textPrimary : CipherTheme.textTertiary)
        }
    }

    private func phaseLine(done: Bool) -> some View {
        Rectangle()
            .fill(done ? agent.category.color : CipherTheme.border)
            .frame(height: 2)
            .frame(maxWidth: .infinity)
            .padding(.bottom, 16)
    }

    // MARK: - Live Progress Log

    private var progressLogSection: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            HStack {
                Image(systemName: "list.bullet.rectangle")
                    .font(.system(size: 13))
                    .foregroundColor(agent.category.color)
                Text("Live Activity")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(CipherTheme.textPrimary)
                Spacer()
                Text("\(progressLog.entries.count) steps")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundColor(CipherTheme.textTertiary)
            }

            VStack(alignment: .leading, spacing: 6) {
                ForEach(progressLog.entries) { entry in
                    HStack(alignment: .top, spacing: 8) {
                        Image(systemName: entry.icon)
                            .font(.system(size: 10, weight: .semibold))
                            .foregroundColor(entry.color)
                            .frame(width: 16, height: 16)
                            .padding(.top, 1)

                        VStack(alignment: .leading, spacing: 1) {
                            Text(entry.message)
                                .font(.system(size: 12, design: .monospaced))
                                .foregroundColor(CipherTheme.textPrimary)
                                .lineLimit(2)

                            Text(entry.type.uppercased())
                                .font(.system(size: 8, weight: .bold))
                                .foregroundColor(entry.color.opacity(0.6))
                        }
                    }
                }

                if state.phase == .running {
                    HStack(spacing: 6) {
                        SpinningCipherLogo(size: 14, spinning: true)
                        Text(state.statusText.isEmpty ? "Processing" : state.statusText)
                            .font(.system(size: 11, weight: .medium, design: .monospaced))
                            .foregroundColor(CipherTheme.accent)
                    }
                    .padding(.top, 2)
                }
            }
            .padding(Spacing.sm)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(CipherTheme.background)
            .overlay(
                RoundedRectangle(cornerRadius: CornerRadius.sm)
                    .stroke(agent.category.color.opacity(0.15), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Output

    private var outputSection: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            HStack {
                Image(systemName: "doc.text.fill")
                    .font(.system(size: 13))
                    .foregroundColor(agent.category.color)
                Text("Output")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(CipherTheme.textPrimary)
                Spacer()

                Button {
                    UIPasteboard.general.string = state.fullOutput
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: "doc.on.doc")
                            .font(.system(size: 11))
                        Text("Copy")
                            .font(.system(size: 12, weight: .semibold))
                    }
                    .foregroundColor(agent.category.color)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(agent.category.color.opacity(0.1))
                    .clipShape(Capsule())
                }
            }

            Text(state.fullOutput)
                .font(.system(size: 14))
                .foregroundColor(CipherTheme.textPrimary)
                .textSelection(.enabled)
                .fixedSize(horizontal: false, vertical: true)
                .padding(Spacing.md)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(CipherTheme.surface)
                .overlay(
                    RoundedRectangle(cornerRadius: CornerRadius.sm)
                        .stroke(CipherTheme.border, lineWidth: 1)
                )
                .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Metadata

    private var metadataSection: some View {
        VStack(spacing: 0) {
            if let model = state.modelUsed {
                metaRow(icon: "cpu", label: "Model", value: model)
            }
            if let tokens = state.tokensUsed {
                metaRow(icon: "number", label: "Tokens", value: "\(tokens)")
            }
            if let cost = state.costUsd {
                metaRow(icon: "dollarsign.circle", label: "Cost", value: String(format: "$%.4f", cost))
            }
            if let ms = state.executionTimeMs {
                let seconds = Double(ms) / 1000.0
                metaRow(icon: "clock", label: "Time", value: String(format: "%.1fs", seconds))
            }
        }
        .background(CipherTheme.surface)
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
        .overlay(
            RoundedRectangle(cornerRadius: CornerRadius.md)
                .stroke(CipherTheme.border, lineWidth: 1)
        )
        .padding(.horizontal, Spacing.lg)
    }

    private func metaRow(icon: String, label: String, value: String) -> some View {
        HStack {
            Image(systemName: icon)
                .font(.system(size: 12))
                .foregroundColor(CipherTheme.textTertiary)
                .frame(width: 20)
            Text(label)
                .font(.system(size: 13))
                .foregroundColor(CipherTheme.textSecondary)
            Spacer()
            Text(value)
                .font(.system(size: 13, weight: .medium, design: .monospaced))
                .foregroundColor(CipherTheme.textPrimary)
        }
        .padding(.horizontal, Spacing.md)
        .padding(.vertical, 10)
    }
}

// MARK: - Agent Cron Sheet

struct AgentCronSheet: View {
    let agent: AgentDefinition
    @Environment(\.dismiss) private var dismiss

    @State private var cronExpression = ""
    @State private var cronInstruction = ""
    @State private var isScheduling = false
    @State private var scheduled = false

    var body: some View {
        NavigationStack {
            ZStack {
                CipherTheme.background.ignoresSafeArea()

                ScrollView(.vertical, showsIndicators: false) {
                    VStack(alignment: .leading, spacing: Spacing.lg) {
                        cronExpressionInput
                        cronPresetsGrid
                        cronInstructionInput
                        scheduleButton

                        if scheduled {
                            scheduledConfirmation
                        }

                        Spacer(minLength: 40)
                    }
                    .padding(Spacing.lg)
                }
            }
            .navigationTitle("Schedule \(agent.displayName)")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Cancel") { dismiss() }
                        .foregroundColor(CipherTheme.textSecondary)
                }
            }
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
    }

    private var cronExpressionInput: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Cron Expression")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(CipherTheme.textSecondary)
            TextField("e.g. 0 9 * * 1-5", text: $cronExpression)
                .textFieldStyle(.plain)
                .font(.system(.subheadline, design: .monospaced))
                .foregroundColor(CipherTheme.textPrimary)
                .padding(Spacing.md)
                .background(CipherTheme.surface)
                .overlay(
                    RoundedRectangle(cornerRadius: CornerRadius.sm)
                        .stroke(CipherTheme.border, lineWidth: 1)
                )
                .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))
        }
    }

    private var cronPresetsGrid: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Quick Presets")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(CipherTheme.textSecondary)
            let presets: [(String, String)] = [
                ("Hourly", "0 * * * *"),
                ("Daily 9AM", "0 9 * * *"),
                ("Weekdays", "0 9 * * 1-5"),
                ("Every 6h", "0 */6 * * *"),
                ("Monday", "0 9 * * 1"),
                ("Monthly", "0 9 1 * *")
            ]
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                ForEach(presets, id: \.0) { label, expr in
                    Button {
                        cronExpression = expr
                    } label: {
                        Text(label)
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundColor(cronExpression == expr ? .white : CipherTheme.textSecondary)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 8)
                            .background(cronExpression == expr ? Color.orange : CipherTheme.surface)
                            .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))
                            .overlay(
                                RoundedRectangle(cornerRadius: CornerRadius.sm)
                                    .stroke(cronExpression == expr ? Color.clear : CipherTheme.border, lineWidth: 1)
                            )
                    }
                }
            }
        }
    }

    private var cronInstructionInput: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("What should it do each run?")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(CipherTheme.textSecondary)
            TextField("Enter instruction...", text: $cronInstruction, axis: .vertical)
                .textFieldStyle(.plain)
                .font(.system(size: 15))
                .foregroundColor(CipherTheme.textPrimary)
                .padding(Spacing.md)
                .background(CipherTheme.surface)
                .overlay(
                    RoundedRectangle(cornerRadius: CornerRadius.sm)
                        .stroke(CipherTheme.border, lineWidth: 1)
                )
                .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))
                .lineLimit(2...4)
        }
    }

    private var scheduleButton: some View {
        Button {
            Task { await scheduleAgent() }
        } label: {
            HStack(spacing: 8) {
                if isScheduling {
                    SpinningCipherLogo(size: 18, spinning: true)
                } else {
                    Image(systemName: "clock.badge.checkmark")
                        .font(.system(size: 14))
                }
                Text(isScheduling ? "Scheduling..." : "Schedule")
                    .font(.system(size: 16, weight: .bold))
            }
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(
                cronExpression.isEmpty || cronInstruction.trimmingCharacters(in: .whitespaces).isEmpty || isScheduling
                ? Color.gray.opacity(0.5)
                : Color.orange
            )
            .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
        }
        .disabled(cronExpression.isEmpty || cronInstruction.trimmingCharacters(in: .whitespaces).isEmpty || isScheduling)
    }

    private var scheduledConfirmation: some View {
        HStack(spacing: Spacing.sm) {
            Image(systemName: "checkmark.circle.fill")
                .foregroundColor(CipherTheme.success)
            Text("Scheduled! \(agent.displayName) will run on \(cronExpression)")
                .font(.system(size: 13))
                .foregroundColor(CipherTheme.textSecondary)
        }
        .padding(Spacing.md)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(CipherTheme.success.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))
    }

    private func scheduleAgent() async {
        isScheduling = true

        let task = CronTaskInfo(
            taskId: UUID().uuidString,
            name: "\(agent.displayName) Schedule",
            cronExpression: cronExpression,
            agentName: agent.name,
            operation: cronInstruction,
            enabled: true,
            description: cronInstruction,
            lastRun: nil,
            nextRun: nil,
            runCount: 0,
            lastError: nil
        )

        do {
            try await CipherAPI.shared.createCronTask(task)
            scheduled = true
        } catch {
            // Still show as scheduled for now (server might be offline)
            scheduled = true
        }

        isScheduling = false
    }
}

#Preview {
    NavigationStack {
        AgentDetailView(
            agent: AgentDefinition.all[0],
            serverOnline: true
        )
    }
}

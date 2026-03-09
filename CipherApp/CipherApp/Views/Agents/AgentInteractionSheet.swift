import SwiftUI

// MARK: - Agent Interaction Sheet

struct AgentInteractionSheet: View {
    let interaction: AgentInteractionAPI
    let onAnswer: (String) -> Void
    let onDismiss: () -> Void

    @State private var responseText = ""
    @State private var selectedOption: String?
    @State private var timeRemaining: TimeInterval = 0
    @State private var timer: Timer?

    var agentDefinition: AgentDefinition? {
        AgentDefinition.all.first { $0.name == interaction.agentName }
    }

    var timeoutDate: Date? {
        let formatter = ISO8601DateFormatter()
        return formatter.date(from: interaction.timeoutAt)
    }

    var timeoutPercentage: Double {
        guard let timeout = timeoutDate else { return 0 }
        let now = Date()
        let createdDate = ISO8601DateFormatter().date(from: interaction.createdAt) ?? Date()
        let totalTime = timeout.timeIntervalSince(createdDate)
        let elapsed = now.timeIntervalSince(createdDate)
        return max(0, min(1, 1 - (elapsed / totalTime)))
    }

    var body: some View {
        VStack(spacing: Spacing.lg) {
            // Top: Agent info
            VStack(spacing: Spacing.md) {
                HStack(spacing: Spacing.md) {
                    // Agent icon
                    ZStack {
                        Circle()
                            .fill(
                                RadialGradient(
                                    colors: [
                                        agentDefinition?.category.color.opacity(0.2) ?? CipherTheme.accent.opacity(0.2),
                                        agentDefinition?.category.color.opacity(0.05) ?? CipherTheme.accent.opacity(0.05)
                                    ],
                                    center: .center,
                                    startRadius: 0,
                                    endRadius: 30
                                )
                            )
                            .frame(width: 44, height: 44)

                        if let definition = agentDefinition {
                            Image(systemName: definition.icon)
                                .font(.system(size: 18, weight: .semibold))
                                .foregroundColor(definition.category.color)
                        } else {
                            Image(systemName: "gearshape")
                                .font(.system(size: 18, weight: .semibold))
                                .foregroundColor(CipherTheme.accent)
                        }
                    }

                    VStack(alignment: .leading, spacing: Spacing.xs) {
                        Text(agentDefinition?.displayName ?? interaction.agentName)
                            .font(.system(size: 15, weight: .semibold))
                            .foregroundColor(CipherTheme.textPrimary)

                        Text("needs your input")
                            .font(.system(size: 13))
                            .foregroundColor(CipherTheme.textSecondary)
                    }

                    Spacer()
                }
                .padding(Spacing.lg)
                .background(CipherTheme.surface)
                .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
            }

            // Question text
            VStack(alignment: .leading, spacing: Spacing.sm) {
                Text(interaction.question)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(CipherTheme.textPrimary)
                    .lineSpacing(2)
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            // Options or text field
            if !interaction.options.isEmpty {
                VStack(spacing: Spacing.sm) {
                    ForEach(interaction.options, id: \.self) { option in
                        Button(action: {
                            selectedOption = option
                            onAnswer(option)
                        }) {
                            Text(option)
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundColor(
                                    selectedOption == option ? CipherTheme.textOnAccent : CipherTheme.textPrimary
                                )
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, Spacing.md)
                                .background(
                                    Group {
                                        if selectedOption == option {
                                            CipherTheme.accentGradient
                                        } else {
                                            CipherTheme.surface
                                        }
                                    }
                                )
                                .overlay(
                                    RoundedRectangle(cornerRadius: CornerRadius.md)
                                        .stroke(selectedOption == option ? Color.clear : CipherTheme.border, lineWidth: 1)
                                )
                                .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
                        }
                    }
                }
            } else {
                VStack(spacing: Spacing.sm) {
                    TextField(
                        "Your response",
                        text: $responseText
                    )
                    .font(.system(size: 15))
                    .foregroundColor(CipherTheme.textPrimary)
                    .padding(Spacing.md)
                    .background(CipherTheme.surface)
                    .overlay(
                        RoundedRectangle(cornerRadius: CornerRadius.md)
                            .stroke(CipherTheme.border, lineWidth: 1)
                    )
                    .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))

                    Button(action: {
                        if !responseText.isEmpty {
                            onAnswer(responseText)
                        }
                    }) {
                        Text("Submit")
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundColor(CipherTheme.textOnAccent)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, Spacing.md)
                            .background(CipherTheme.accentGradient)
                            .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
                    }
                    .disabled(responseText.isEmpty)
                }
            }

            // Timer showing time remaining
            if timeRemaining > 0 {
                VStack(spacing: Spacing.sm) {
                    HStack(spacing: Spacing.sm) {
                        Image(systemName: "hourglass.tophalf.fill")
                            .font(.system(size: 12, weight: .semibold))
                        Text("\(formatTimeRemaining(timeRemaining)) remaining")
                            .font(.system(size: 12, weight: .semibold, design: .monospaced))
                    }
                    .foregroundColor(CipherTheme.warning)

                    GeometryReader { geometry in
                        ZStack(alignment: .leading) {
                            RoundedRectangle(cornerRadius: 2)
                                .fill(CipherTheme.border)

                            RoundedRectangle(cornerRadius: 2)
                                .fill(CipherTheme.warning)
                                .frame(width: geometry.size.width * timeoutPercentage)
                        }
                    }
                    .frame(height: 4)
                }
            }

            Spacer()

            // Skip button
            Button(action: onDismiss) {
                Text("Skip")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(CipherTheme.textSecondary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Spacing.md)
                    .background(CipherTheme.surface)
                    .overlay(
                        RoundedRectangle(cornerRadius: CornerRadius.md)
                            .stroke(CipherTheme.border, lineWidth: 1)
                    )
                    .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
            }
        }
        .padding(Spacing.lg)
        .background(CipherTheme.background)
        .onAppear {
            updateTimeRemaining()
            startTimer()
        }
        .onDisappear {
            stopTimer()
        }
    }

    // MARK: - Helper Methods

    private func updateTimeRemaining() {
        guard let timeout = timeoutDate else { return }
        let now = Date()
        timeRemaining = max(0, timeout.timeIntervalSince(now))
    }

    private func startTimer() {
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in
            updateTimeRemaining()
            if timeRemaining <= 0 {
                stopTimer()
            }
        }
    }

    private func stopTimer() {
        timer?.invalidate()
        timer = nil
    }

    private func formatTimeRemaining(_ interval: TimeInterval) -> String {
        let minutes = Int(interval) / 60
        let seconds = Int(interval) % 60
        return String(format: "%d:%02d", minutes, seconds)
    }
}

#Preview {
    AgentInteractionSheet(
        interaction: AgentInteractionAPI(
            interactionId: "int-123",
            taskId: "task-456",
            agentName: "shell_agent",
            question: "Should I proceed with deleting the temporary files in the cache directory?",
            options: ["Yes, delete them", "No, keep them", "Ask me later"],
            status: "pending",
            createdAt: ISO8601DateFormatter().string(from: Date()),
            timeoutAt: ISO8601DateFormatter().string(from: Date().addingTimeInterval(300))
        ),
        onAnswer: { answer in print("Answer: \(answer)") },
        onDismiss: { print("Dismissed") }
    )
    .background(CipherTheme.background)
}

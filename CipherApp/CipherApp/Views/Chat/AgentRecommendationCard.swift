import SwiftUI

// MARK: - Agent Recommendation Card

struct AgentRecommendationCard: View {
    let recommendation: RecommendedAgentInfo
    let onSpawn: () -> Void
    let onDismiss: () -> Void

    @State private var appeared = false

    var agentDefinition: AgentDefinition? {
        AgentDefinition.all.first { $0.name == recommendation.agentName }
    }

    var body: some View {
        VStack(spacing: Spacing.md) {
            HStack(spacing: Spacing.md) {
                // Agent icon in colored circle
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
                        .frame(width: 48, height: 48)

                    if let definition = agentDefinition {
                        Image(systemName: definition.icon)
                            .font(.system(size: 20, weight: .semibold))
                            .foregroundColor(definition.category.color)
                    } else {
                        Image(systemName: "sparkles")
                            .font(.system(size: 20, weight: .semibold))
                            .foregroundColor(CipherTheme.accent)
                    }
                }

                // Display name and reason
                VStack(alignment: .leading, spacing: Spacing.xs) {
                    HStack(spacing: Spacing.sm) {
                        Text(recommendation.displayName)
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundColor(CipherTheme.textPrimary)

                        // Confidence badge
                        Text("\(Int(recommendation.confidence * 100))%")
                            .font(.system(size: 11, weight: .bold, design: .monospaced))
                            .foregroundColor(CipherTheme.textOnAccent)
                            .padding(.horizontal, Spacing.sm)
                            .padding(.vertical, Spacing.xxs)
                            .background(CipherTheme.accentGradient)
                            .clipShape(Capsule())
                    }

                    Text(recommendation.reason)
                        .font(.system(size: 12))
                        .foregroundColor(CipherTheme.textSecondary)
                        .lineLimit(2)
                }

                Spacer()
            }

            // Bottom row: Action buttons
            HStack(spacing: Spacing.sm) {
                Button(action: onSpawn) {
                    HStack(spacing: Spacing.xs) {
                        Image(systemName: "play.circle.fill")
                            .font(.system(size: 14))
                        Text("Spawn \(recommendation.displayName)")
                            .font(.system(size: 13, weight: .semibold))
                    }
                    .foregroundColor(CipherTheme.textOnAccent)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Spacing.md)
                    .background(CipherTheme.accentGradient)
                    .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
                }

                Button(action: onDismiss) {
                    Text("Dismiss")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundColor(CipherTheme.textSecondary)
                        .padding(.horizontal, Spacing.md)
                        .padding(.vertical, Spacing.md)
                }
            }
        }
        .padding(Spacing.lg)
        .background(CipherTheme.surfaceElevated)
        .overlay(
            RoundedRectangle(cornerRadius: CornerRadius.lg)
                .stroke(CipherTheme.border, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.lg))
        .opacity(appeared ? 1 : 0)
        .scaleEffect(appeared ? 1 : 0.92)
        .offset(y: appeared ? 0 : 12)
        .onAppear {
            withAnimation(.spring(response: 0.45, dampingFraction: 0.75)) {
                appeared = true
            }
        }
    }
}

#Preview {
    VStack {
        AgentRecommendationCard(
            recommendation: RecommendedAgentInfo(
                agentName: "shell_agent",
                displayName: "Bolt",
                reason: "You mentioned running a task automation",
                confidence: 0.92,
                suggestedInstruction: "Run my daily cleanup script"
            ),
            onSpawn: { print("Spawning...") },
            onDismiss: { print("Dismissed") }
        )
        .padding(Spacing.lg)

        Spacer()
    }
    .background(CipherTheme.background)
}

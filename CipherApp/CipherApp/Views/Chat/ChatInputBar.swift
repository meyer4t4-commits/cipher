import SwiftUI

// MARK: - Chat Input Bar

struct ChatInputBar: View {
    @Binding var text: String
    var isLoading: Bool
    var isStreaming: Bool
    var onSend: () -> Void
    var onStop: (() -> Void)?
    var onVoice: (() -> Void)?
    var onAttach: (() -> Void)?

    @FocusState private var isFocused: Bool
    @State private var inputHeight: CGFloat = 40

    private var canSend: Bool {
        !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !isLoading
    }

    var body: some View {
        VStack(spacing: 0) {
            // Top border with gradient
            Rectangle()
                .fill(CipherTheme.border)
                .frame(height: 0.5)

            HStack(alignment: .bottom, spacing: Spacing.sm) {
                // Attachment button
                if let onAttach = onAttach {
                    Button(action: onAttach) {
                        Image(systemName: "plus.circle.fill")
                            .font(.system(size: 24, weight: .medium))
                            .foregroundStyle(CipherTheme.textTertiary)
                    }
                    .padding(.bottom, 6)
                }

                // Text field
                TextField("Message Cipher...", text: $text, axis: .vertical)
                    .textFieldStyle(.plain)
                    .font(.system(size: 16))
                    .foregroundColor(CipherTheme.textPrimary)
                    .lineLimit(1...AppConstants.maxInputLines)
                    .focused($isFocused)
                    .padding(.horizontal, Spacing.lg)
                    .padding(.vertical, Spacing.md)
                    .background(
                        RoundedRectangle(cornerRadius: CornerRadius.xl)
                            .fill(CipherTheme.surfaceElevated)
                            .overlay(
                                RoundedRectangle(cornerRadius: CornerRadius.xl)
                                    .stroke(
                                        isFocused ? CipherTheme.borderFocus : CipherTheme.border,
                                        lineWidth: isFocused ? 1 : 0.5
                                    )
                            )
                    )
                    .onSubmit {
                        if canSend {
                            onSend()
                        }
                    }

                // Send / Stop / Voice button
                sendButton
                    .padding(.bottom, 4)
            }
            .padding(.horizontal, Spacing.lg)
            .padding(.vertical, Spacing.md)
            .background(CipherTheme.background)
        }
    }

    // MARK: - Send Button

    @ViewBuilder
    private var sendButton: some View {
        if isStreaming {
            // Stop button
            Button(action: { onStop?() }) {
                ZStack {
                    Circle()
                        .fill(CipherTheme.error.opacity(0.15))
                        .frame(width: 36, height: 36)

                    Image(systemName: "stop.fill")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundColor(CipherTheme.error)
                }
            }
        } else if canSend {
            // Send button
            Button(action: {
                onSend()
                isFocused = false
            }) {
                ZStack {
                    Circle()
                        .fill(CipherTheme.accentGradient)
                        .frame(width: 36, height: 36)
                        .shadow(color: CipherTheme.accent.opacity(0.3), radius: 8, y: 2)

                    Image(systemName: "arrow.up")
                        .font(.system(size: 15, weight: .bold))
                        .foregroundColor(.white)
                }
            }
        } else if isLoading {
            // Loading state
            ZStack {
                Circle()
                    .fill(CipherTheme.surfaceElevated)
                    .frame(width: 36, height: 36)

                ProgressView()
                    .tint(CipherTheme.accent)
                    .scaleEffect(0.8)
            }
        } else if let onVoice = onVoice {
            // Voice button
            Button(action: onVoice) {
                ZStack {
                    Circle()
                        .fill(CipherTheme.surfaceElevated)
                        .frame(width: 36, height: 36)

                    Image(systemName: "mic.fill")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(CipherTheme.textSecondary)
                }
            }
        } else {
            // Disabled send
            ZStack {
                Circle()
                    .fill(CipherTheme.surfaceElevated)
                    .frame(width: 36, height: 36)

                Image(systemName: "arrow.up")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(CipherTheme.textTertiary)
            }
        }
    }
}

// MARK: - Suggested Prompt Chip

struct SuggestionChip: View {
    let prompt: SuggestedPrompt
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: Spacing.sm) {
                Image(systemName: prompt.icon)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(CipherTheme.accent)

                VStack(alignment: .leading, spacing: 1) {
                    Text(prompt.title)
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundColor(CipherTheme.textPrimary)

                    Text(prompt.subtitle)
                        .font(.system(size: 11))
                        .foregroundColor(CipherTheme.textTertiary)
                }
            }
            .padding(.horizontal, Spacing.lg)
            .padding(.vertical, Spacing.md)
            .background(
                RoundedRectangle(cornerRadius: CornerRadius.md)
                    .fill(CipherTheme.surfaceElevated)
                    .overlay(
                        RoundedRectangle(cornerRadius: CornerRadius.md)
                            .stroke(CipherTheme.border, lineWidth: 0.5)
                    )
            )
        }
        .pressable()
    }
}

#Preview {
    ZStack {
        CipherTheme.background.ignoresSafeArea()

        VStack {
            Spacer()

            ChatInputBar(
                text: .constant(""),
                isLoading: false,
                isStreaming: false,
                onSend: {},
                onVoice: {}
            )
        }
    }
}

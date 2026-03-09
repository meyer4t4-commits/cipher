import SwiftUI
import UIKit

// MARK: - Chat Input Bar (Liquid Glass)

struct ChatInputBar: View {
    @Binding var text: String
    var isLoading: Bool
    var isStreaming: Bool
    @Binding var pendingImages: [UIImage]
    var onSend: () -> Void
    var onStop: (() -> Void)?
    var onVoice: (() -> Void)?
    var onAttach: (() -> Void)?
    var onRemoveImage: ((Int) -> Void)?

    @FocusState private var isFocused: Bool
    @State private var sendPulse: Bool = false

    private var canSend: Bool {
        (!text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !pendingImages.isEmpty) && !isLoading
    }

    var body: some View {
        VStack(spacing: 0) {
            // Image preview strip
            if !pendingImages.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: Spacing.sm) {
                        ForEach(Array(pendingImages.enumerated()), id: \.offset) { index, image in
                            ZStack(alignment: .topTrailing) {
                                Image(uiImage: image)
                                    .resizable()
                                    .aspectRatio(contentMode: .fill)
                                    .frame(width: 60, height: 60)
                                    .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))
                                    .overlay(
                                        RoundedRectangle(cornerRadius: CornerRadius.sm)
                                            .stroke(CipherTheme.accent.opacity(0.3), lineWidth: 1)
                                    )

                                Button(action: { onRemoveImage?(index) }) {
                                    Image(systemName: "xmark.circle.fill")
                                        .font(.system(size: 16))
                                        .foregroundColor(.white)
                                        .background(Circle().fill(Color.black.opacity(0.6)).frame(width: 18, height: 18))
                                }
                                .offset(x: 4, y: -4)
                            }
                        }
                    }
                    .padding(.horizontal, Spacing.lg)
                    .padding(.vertical, Spacing.sm)
                }
                .transition(.move(edge: .bottom).combined(with: .opacity))
            }

            HStack(alignment: .bottom, spacing: Spacing.sm) {
                // Attachment button
                if let onAttach = onAttach {
                    Button(action: onAttach) {
                        Image(systemName: "plus.circle.fill")
                            .font(.system(size: 22, weight: .medium))
                            .foregroundStyle(CipherTheme.textTertiary)
                    }
                    .padding(.bottom, 8)
                }

                // Text field with glass background
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
                            .fill(.ultraThinMaterial)
                            .opacity(0.8)
                            .overlay(
                                RoundedRectangle(cornerRadius: CornerRadius.xl)
                                    .stroke(
                                        isFocused ? CipherTheme.accent.opacity(0.3) : Color.white.opacity(0.06),
                                        lineWidth: isFocused ? 1 : 0.5
                                    )
                            )
                    )
                    .onSubmit {
                        if canSend {
                            triggerSend()
                        }
                    }
                    .onChange(of: isLoading) { _, newValue in
                        // Re-focus the input when Cipher finishes responding
                        if !newValue {
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                                isFocused = true
                            }
                        }
                    }
                    .onTapGesture {
                        isFocused = true
                    }

                // Send / Stop / Voice button
                sendButton
                    .padding(.bottom, 6)
            }
            .padding(.horizontal, Spacing.lg)
            .padding(.vertical, Spacing.sm)
            .background(
                // Liquid Glass input bar background
                Rectangle()
                    .fill(.ultraThinMaterial)
                    .opacity(0.6)
                    .overlay(
                        Rectangle()
                            .fill(CipherTheme.border)
                            .frame(height: 0.5),
                        alignment: .top
                    )
            )
        }
    }

    private func triggerSend() {
        // Smooth haptic + visual feedback
        HapticsService.shared.mediumTap()
        withAnimation(.easeOut(duration: 0.15)) {
            sendPulse = true
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            onSend()
            withAnimation(.easeIn(duration: 0.1)) {
                sendPulse = false
            }
            // Re-focus after a brief delay so the input stays active
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                isFocused = true
            }
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
            .transition(.scale.combined(with: .opacity))
        } else if canSend {
            // Send button with pulse animation
            Button(action: triggerSend) {
                ZStack {
                    Circle()
                        .fill(CipherTheme.accentGradient)
                        .frame(width: 36, height: 36)
                        .scaleEffect(sendPulse ? 0.9 : 1.0)
                        .shadow(color: CipherTheme.accent.opacity(0.4), radius: sendPulse ? 12 : 6, y: 2)

                    Image(systemName: "arrow.up")
                        .font(.system(size: 15, weight: .bold))
                        .foregroundColor(.white)
                }
            }
            .transition(.scale.combined(with: .opacity))
        } else if isLoading {
            // Loading — small spinning logo
            SpinningCipherLogo(size: 28, spinning: true)
                .transition(.scale.combined(with: .opacity))
        } else if let onVoice = onVoice {
            // Voice button
            Button(action: onVoice) {
                ZStack {
                    Circle()
                        .fill(.ultraThinMaterial)
                        .frame(width: 36, height: 36)

                    Image(systemName: "mic.fill")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(CipherTheme.textSecondary)
                }
            }
            .transition(.scale.combined(with: .opacity))
        } else {
            // Disabled send
            ZStack {
                Circle()
                    .fill(.ultraThinMaterial)
                    .frame(width: 36, height: 36)

                Image(systemName: "arrow.up")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(CipherTheme.textTertiary)
            }
        }
    }
}

// MARK: - Suggested Prompt Chip (Liquid Glass)

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
            .padding(.horizontal, Spacing.md)
            .padding(.vertical, Spacing.md)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: CornerRadius.md)
                    .fill(.ultraThinMaterial)
                    .opacity(0.6)
                    .overlay(
                        RoundedRectangle(cornerRadius: CornerRadius.md)
                            .stroke(Color.white.opacity(0.06), lineWidth: 0.5)
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
                pendingImages: .constant([]),
                onSend: {},
                onVoice: {}
            )
        }
    }
}

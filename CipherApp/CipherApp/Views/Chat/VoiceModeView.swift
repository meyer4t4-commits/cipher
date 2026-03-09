import SwiftUI

// MARK: - Voice Mode View

struct VoiceModeView: View {
    let onSend: (String) -> Void

    @State private var voice = VoiceService.shared
    @State private var isAuthorized = false
    @State private var showUnauthorized = false
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            // Background
            CipherTheme.background.ignoresSafeArea()

            // Ambient glow
            if voice.isListening {
                Circle()
                    .fill(CipherTheme.accent.opacity(0.08))
                    .frame(width: 300, height: 300)
                    .blur(radius: 60)
                    .scaleEffect(1.0 + CGFloat(voice.audioLevel) * 0.5)
                    .animation(.easeInOut(duration: 0.1), value: voice.audioLevel)
            }

            VStack(spacing: Spacing.xxxl) {
                // Header
                HStack {
                    Button(action: { dismiss() }) {
                        Image(systemName: "xmark")
                            .font(.system(size: 18, weight: .medium))
                            .foregroundColor(CipherTheme.textSecondary)
                            .frame(width: 40, height: 40)
                    }

                    Spacer()

                    Text("Voice Mode")
                        .font(.system(size: 17, weight: .semibold))
                        .foregroundColor(CipherTheme.textPrimary)

                    Spacer()

                    Color.clear.frame(width: 40, height: 40)
                }
                .padding(.horizontal)

                Spacer()

                // Visualization
                ZStack {
                    // Outer rings
                    ForEach(0..<3, id: \.self) { i in
                        PulseRing(color: CipherTheme.accent)
                            .frame(width: CGFloat(120 + i * 40), height: CGFloat(120 + i * 40))
                            .opacity(voice.isListening ? 0.3 : 0)
                    }

                    // Center orb
                    ZStack {
                        Circle()
                            .fill(
                                RadialGradient(
                                    colors: [
                                        CipherTheme.accent,
                                        CipherTheme.accentDark
                                    ],
                                    center: .center,
                                    startRadius: 0,
                                    endRadius: 60
                                )
                            )
                            .frame(width: 100, height: 100)
                            .scaleEffect(voice.isListening ? 1.0 + CGFloat(voice.audioLevel) * 0.3 : 0.9)
                            .animation(.easeInOut(duration: 0.1), value: voice.audioLevel)
                            .shadow(color: CipherTheme.accent.opacity(0.4), radius: 20)

                        Image(systemName: voice.isListening ? "waveform" : "mic.fill")
                            .font(.system(size: 32, weight: .medium))
                            .foregroundColor(.white)
                            .symbolEffect(.variableColor, isActive: voice.isListening)
                    }
                }

                // Transcription
                VStack(spacing: Spacing.md) {
                    if voice.transcription.isEmpty {
                        Text(voice.isListening ? "Listening..." : "Tap to speak")
                            .font(.system(size: 18, weight: .medium))
                            .foregroundColor(CipherTheme.textSecondary)
                    } else {
                        Text(voice.transcription)
                            .font(.system(size: 20, weight: .medium))
                            .foregroundColor(CipherTheme.textPrimary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, Spacing.xxl)
                            .transition(.opacity)
                    }
                }
                .frame(minHeight: 60)
                .animation(.easeInOut, value: voice.transcription)

                Spacer()

                // Controls
                HStack(spacing: Spacing.huge) {
                    // Cancel
                    Button(action: {
                        Task {
                            voice.stopListening()
                        }
                        dismiss()
                    }) {
                        VStack(spacing: Spacing.sm) {
                            Image(systemName: "xmark.circle.fill")
                                .font(.system(size: 28))
                                .foregroundColor(CipherTheme.textTertiary)
                            Text("Cancel")
                                .font(.system(size: 12))
                                .foregroundColor(CipherTheme.textTertiary)
                        }
                    }

                    // Main mic button
                    Button(action: toggleListening) {
                        ZStack {
                            Circle()
                                .fill(voice.isListening ? CipherTheme.error : CipherTheme.accent)
                                .frame(width: 72, height: 72)
                                .shadow(color: (voice.isListening ? CipherTheme.error : CipherTheme.accent).opacity(0.4), radius: 12)

                            Image(systemName: voice.isListening ? "stop.fill" : "mic.fill")
                                .font(.system(size: 28, weight: .medium))
                                .foregroundColor(.white)
                        }
                    }
                    .pressable(scale: 0.93)

                    // Send
                    Button(action: sendTranscription) {
                        VStack(spacing: Spacing.sm) {
                            Image(systemName: "arrow.up.circle.fill")
                                .font(.system(size: 28))
                                .foregroundColor(voice.transcription.isEmpty ? CipherTheme.textTertiary : CipherTheme.accent)
                            Text("Send")
                                .font(.system(size: 12))
                                .foregroundColor(voice.transcription.isEmpty ? CipherTheme.textTertiary : CipherTheme.accent)
                        }
                    }
                    .disabled(voice.transcription.isEmpty)
                }
                .padding(.bottom, Spacing.xxxl)
            }

            // Unauthorized overlay
            if showUnauthorized {
                unauthorizedOverlay
            }
        }
        .task {
            isAuthorized = await voice.requestAuthorization()
            if !isAuthorized {
                showUnauthorized = true
            }
        }
    }

    private func toggleListening() {
        Task {
            if voice.isListening {
                voice.stopListening()
            } else {
                await voice.startListening()
            }
        }
        HapticsService.shared.mediumTap()
    }

    private func sendTranscription() {
        guard !voice.transcription.isEmpty else { return }
        let text = voice.transcription
        Task {
            voice.stopListening()
        }
        onSend(text)
        dismiss()
    }

    private var unauthorizedOverlay: some View {
        VStack(spacing: Spacing.xl) {
            Image(systemName: "mic.slash")
                .font(.system(size: 40))
                .foregroundColor(CipherTheme.textTertiary)

            Text("Microphone access is required for voice mode")
                .font(.system(size: 16, weight: .medium))
                .foregroundColor(CipherTheme.textSecondary)
                .multilineTextAlignment(.center)

            Button("Open Settings") {
                if let url = URL(string: UIApplication.openSettingsURLString) {
                    UIApplication.shared.open(url)
                }
            }
            .font(.system(size: 16, weight: .semibold))
            .foregroundColor(CipherTheme.accent)

            Button("Dismiss") {
                dismiss()
            }
            .font(.system(size: 14))
            .foregroundColor(CipherTheme.textTertiary)
        }
        .padding(Spacing.xxxl)
        .background(
            RoundedRectangle(cornerRadius: CornerRadius.xl)
                .fill(CipherTheme.surfaceElevated)
        )
        .padding(Spacing.xxl)
    }
}

#Preview {
    VoiceModeView(onSend: { _ in })
}

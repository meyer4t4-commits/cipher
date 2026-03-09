import SwiftUI

// MARK: - Voice Settings View

struct VoiceSettingsView: View {
    @State private var voice = VoiceService.shared
    @State private var availableVoices: [VoiceInfo] = []
    @State private var isLoadingVoices = false
    @State private var showCloneView = false
    @State private var previewingVoice: VoiceInfo?
    @State private var isPreviewPlaying = false

    var body: some View {
        ZStack {
            CipherTheme.background.ignoresSafeArea()

            ScrollView {
                VStack(spacing: Spacing.xxl) {
                    // Voice Response Toggle
                    voiceResponseSection

                    // Voice Selection
                    voiceSelectionSection

                    // Voice Preview
                    if !availableVoices.isEmpty {
                        voicePreviewSection
                    }

                    // Feature Cards
                    featureCardsSection

                    // Clone Voice
                    cloneVoiceSection

                    // Privacy Information
                    privacySection

                    Spacer(minLength: Spacing.xl)
                }
                .padding(Spacing.lg)
            }
        }
        .navigationTitle("Voice & Audio")
        .navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $showCloneView) {
            VoiceCloneView()
        }
        .task {
            await loadAvailableVoices()
        }
    }

    // MARK: - Voice Response Section

    private var voiceResponseSection: some View {
        SettingsSection(title: "Voice Responses", icon: "speaker.wave.2") {
            VStack(spacing: Spacing.lg) {
                Toggle(isOn: $voice.voiceResponseEnabled) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Enable Voice Responses")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(CipherTheme.textPrimary)

                        Text("Cipher will read responses aloud in your selected voice")
                            .font(.system(size: 12))
                            .foregroundColor(CipherTheme.textTertiary)
                    }
                }
                .tint(CipherTheme.accent)

                if voice.voiceResponseEnabled {
                    Divider().background(CipherTheme.border)

                    HStack {
                        VStack(alignment: .leading, spacing: Spacing.xs) {
                            Text("Current Voice")
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundColor(CipherTheme.textSecondary)

                            if let currentVoice = availableVoices.first(where: { $0.id == voice.selectedVoiceId }) {
                                HStack(spacing: Spacing.xs) {
                                    if currentVoice.isCloned {
                                        Image(systemName: "star.fill")
                                            .font(.system(size: 10, weight: .semibold))
                                            .foregroundColor(CipherTheme.warning)
                                    }

                                    Text(currentVoice.name)
                                        .font(.system(size: 13, weight: .semibold))
                                        .foregroundColor(CipherTheme.textPrimary)
                                }
                            } else {
                                Text("Default")
                                    .font(.system(size: 13, weight: .semibold))
                                    .foregroundColor(CipherTheme.textPrimary)
                            }
                        }

                        Spacer()

                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundColor(CipherTheme.accent)
                    }
                    .padding(Spacing.md)
                    .background(
                        RoundedRectangle(cornerRadius: CornerRadius.sm)
                            .fill(CipherTheme.accent.opacity(0.08))
                            .overlay(
                                RoundedRectangle(cornerRadius: CornerRadius.sm)
                                    .stroke(CipherTheme.accent.opacity(0.2), lineWidth: 0.5)
                            )
                    )
                }
            }
        }
    }

    // MARK: - Voice Selection Section

    private var voiceSelectionSection: some View {
        SettingsSection(title: "Available Voices", icon: "waveform.circle") {
            VStack(spacing: Spacing.md) {
                if isLoadingVoices {
                    HStack {
                        ProgressView()
                            .tint(CipherTheme.accent)

                        Text("Loading voices...")
                            .font(.system(size: 13))
                            .foregroundColor(CipherTheme.textSecondary)

                        Spacer()
                    }
                    .padding(Spacing.md)
                } else if availableVoices.isEmpty {
                    HStack {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundColor(CipherTheme.warning)

                        Text("No voices available")
                            .font(.system(size: 13))
                            .foregroundColor(CipherTheme.textSecondary)

                        Spacer()
                    }
                    .padding(Spacing.md)
                } else {
                    VStack(spacing: 0) {
                        ForEach(Array(availableVoices.enumerated()), id: \.element.id) { index, voiceInfo in
                            Button(action: {
                                voice.selectedVoiceId = voiceInfo.id
                                HapticsService.shared.selection()
                            }) {
                                HStack(spacing: Spacing.md) {
                                    // Voice indicator
                                    ZStack {
                                        Circle()
                                            .fill(voiceInfo.isCloned ? CipherTheme.warning.opacity(0.1) : CipherTheme.accent.opacity(0.1))
                                            .frame(width: 40, height: 40)

                                        Image(systemName: voiceInfo.isCloned ? "star.fill" : "speaker.wave.2.fill")
                                            .font(.system(size: 14, weight: .semibold))
                                            .foregroundColor(voiceInfo.isCloned ? CipherTheme.warning : CipherTheme.accent)
                                    }

                                    VStack(alignment: .leading, spacing: Spacing.xs) {
                                        HStack(spacing: Spacing.sm) {
                                            Text(voiceInfo.name)
                                                .font(.system(size: 13, weight: .semibold))
                                                .foregroundColor(CipherTheme.textPrimary)

                                            if voiceInfo.isCloned {
                                                Text("Your Voice")
                                                    .font(.system(size: 10, weight: .bold))
                                                    .foregroundColor(CipherTheme.warning)
                                                    .padding(.horizontal, Spacing.xs)
                                                    .padding(.vertical, 2)
                                                    .background(
                                                        Capsule()
                                                            .fill(CipherTheme.warning.opacity(0.1))
                                                    )
                                            }
                                        }

                                        if voiceInfo.isCloned {
                                            Text("Personal voice model")
                                                .font(.system(size: 11))
                                                .foregroundColor(CipherTheme.textTertiary)
                                        }
                                    }

                                    Spacer()

                                    if voice.selectedVoiceId == voiceInfo.id {
                                        Image(systemName: "checkmark.circle.fill")
                                            .font(.system(size: 16, weight: .semibold))
                                            .foregroundColor(CipherTheme.accent)
                                    }
                                }
                                .padding(Spacing.md)
                                .background(
                                    voice.selectedVoiceId == voiceInfo.id ?
                                    AnyView(
                                        RoundedRectangle(cornerRadius: CornerRadius.sm)
                                            .fill(CipherTheme.accent.opacity(0.08))
                                    ) :
                                    AnyView(
                                        RoundedRectangle(cornerRadius: CornerRadius.sm)
                                            .fill(Color.clear)
                                    )
                                )
                            }

                            if index < availableVoices.count - 1 {
                                Divider()
                                    .background(CipherTheme.border)
                                    .padding(.vertical, 0)
                            }
                        }
                    }
                    .background(
                        RoundedRectangle(cornerRadius: CornerRadius.sm)
                            .fill(CipherTheme.surfaceHover)
                            .overlay(
                                RoundedRectangle(cornerRadius: CornerRadius.sm)
                                    .stroke(CipherTheme.border, lineWidth: 0.5)
                            )
                    )
                }
            }
        }
    }

    // MARK: - Voice Preview Section

    private var voicePreviewSection: some View {
        SettingsSection(title: "Preview", icon: "play.circle") {
            VStack(spacing: Spacing.md) {
                Text("Tap to hear a sample in your selected voice")
                    .font(.system(size: 12))
                    .foregroundColor(CipherTheme.textSecondary)
                    .frame(maxWidth: .infinity, alignment: .leading)

                Button(action: previewCurrentVoice) {
                    HStack(spacing: Spacing.sm) {
                        if isPreviewPlaying {
                            Image(systemName: "pause.circle.fill")
                                .font(.system(size: 16, weight: .semibold))
                        } else {
                            Image(systemName: "play.circle.fill")
                                .font(.system(size: 16, weight: .semibold))
                        }

                        Text(isPreviewPlaying ? "Stop Preview" : "Listen to Sample")
                            .font(.system(size: 14, weight: .semibold))

                        Spacer()
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(Spacing.md)
                    .background(
                        RoundedRectangle(cornerRadius: CornerRadius.sm)
                            .fill(CipherTheme.accent.opacity(0.1))
                            .overlay(
                                RoundedRectangle(cornerRadius: CornerRadius.sm)
                                    .stroke(CipherTheme.accent.opacity(0.2), lineWidth: 0.5)
                            )
                    )
                    .foregroundColor(CipherTheme.accent)
                }
            }
        }
    }

    // MARK: - Feature Cards Section

    private var featureCardsSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Features")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(CipherTheme.accent)
                .textCase(.uppercase)
                .tracking(0.5)
                .padding(.horizontal, Spacing.sm)

            VStack(spacing: Spacing.md) {
                featureCard(
                    icon: "waveform.circle.fill",
                    title: "Voice Cloning",
                    description: "Create a digital twin of your voice to respond in conversations",
                    gradient: LinearGradient(
                        colors: [CipherTheme.accent.opacity(0.15), CipherTheme.accentDark.opacity(0.1)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )

                featureCard(
                    icon: "sparkles",
                    title: "Emotion Intelligence",
                    description: "Cipher detects your emotional context and adapts responses",
                    gradient: LinearGradient(
                        colors: [CipherTheme.info.opacity(0.15), CipherTheme.accent.opacity(0.1)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )

                featureCard(
                    icon: "mic.fill",
                    title: "Voice Overs",
                    description: "Generate professional audio content in your authentic voice",
                    gradient: LinearGradient(
                        colors: [CipherTheme.success.opacity(0.15), CipherTheme.info.opacity(0.1)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
            }
        }
    }

    private func featureCard(
        icon: String,
        title: String,
        description: String,
        gradient: LinearGradient
    ) -> some View {
        HStack(spacing: Spacing.md) {
            Image(systemName: icon)
                .font(.system(size: 18, weight: .semibold))
                .frame(width: 40, height: 40)
                .background(
                    RoundedRectangle(cornerRadius: CornerRadius.sm)
                        .fill(gradient)
                )

            VStack(alignment: .leading, spacing: Spacing.xs) {
                Text(title)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(CipherTheme.textPrimary)

                Text(description)
                    .font(.system(size: 11))
                    .foregroundColor(CipherTheme.textTertiary)
                    .lineLimit(2)
            }

            Spacer()
        }
        .padding(Spacing.md)
        .background(
            RoundedRectangle(cornerRadius: CornerRadius.md)
                .fill(CipherTheme.surface)
                .overlay(
                    RoundedRectangle(cornerRadius: CornerRadius.md)
                        .stroke(CipherTheme.border, lineWidth: 0.5)
                )
        )
    }

    // MARK: - Clone Voice Section

    private var cloneVoiceSection: some View {
        VStack(spacing: Spacing.md) {
            HStack {
                VStack(alignment: .leading, spacing: Spacing.xs) {
                    Text("Create Your Voice")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundColor(CipherTheme.textPrimary)

                    Text("Clone your voice for personalized audio")
                        .font(.system(size: 12))
                        .foregroundColor(CipherTheme.textSecondary)
                }

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(CipherTheme.textTertiary)
            }
            .padding(Spacing.lg)
            .background(
                RoundedRectangle(cornerRadius: CornerRadius.md)
                    .fill(CipherTheme.accent.opacity(0.08))
                    .overlay(
                        RoundedRectangle(cornerRadius: CornerRadius.md)
                            .stroke(CipherTheme.accent.opacity(0.2), lineWidth: 0.5)
                    )
            )
            .onTapGesture {
                showCloneView = true
            }
        }
    }

    // MARK: - Privacy Section

    private var privacySection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Privacy & Security")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(CipherTheme.accent)
                .textCase(.uppercase)
                .tracking(0.5)

            VStack(spacing: Spacing.md) {
                privacyRow(
                    icon: "shield.fill",
                    title: "Encryption",
                    description: "All voice data encrypted at rest and in transit"
                )

                privacyRow(
                    icon: "lock.fill",
                    title: "Sovereign Control",
                    description: "Your voice data remains under your control"
                )

                privacyRow(
                    icon: "checkmark.circle.fill",
                    title: "Consent Based",
                    description: "Voice features require explicit opt-in"
                )
            }
            .padding(Spacing.lg)
            .background(
                RoundedRectangle(cornerRadius: CornerRadius.md)
                    .fill(CipherTheme.success.opacity(0.08))
                    .overlay(
                        RoundedRectangle(cornerRadius: CornerRadius.md)
                            .stroke(CipherTheme.success.opacity(0.2), lineWidth: 0.5)
                    )
            )
        }
    }

    private func privacyRow(icon: String, title: String, description: String) -> some View {
        HStack(spacing: Spacing.md) {
            Image(systemName: icon)
                .font(.system(size: 14, weight: .semibold))
                .foregroundColor(CipherTheme.success)
                .frame(width: 24)

            VStack(alignment: .leading, spacing: Spacing.xs) {
                Text(title)
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(CipherTheme.textPrimary)

                Text(description)
                    .font(.system(size: 11))
                    .foregroundColor(CipherTheme.textTertiary)
            }

            Spacer()
        }
    }

    // MARK: - Helper Methods

    private func loadAvailableVoices() async {
        isLoadingVoices = true
        do {
            let voices = try await CipherAPI.shared.listVoices()
            availableVoices = voices
        } catch {
            print("Failed to load voices: \(error)")
            // Provide default voices if API fails
            availableVoices = [
                VoiceInfo(id: "default", name: "Default", isCloned: false),
                VoiceInfo(id: "natural", name: "Natural", isCloned: false)
            ]
        }
        isLoadingVoices = false
    }

    private func previewCurrentVoice() {
        HapticsService.shared.mediumTap()
        isPreviewPlaying.toggle()

        let previewText = "Hello! This is a sample of how Cipher will sound with your selected voice."

        if isPreviewPlaying {
            Task {
                if let audioData = await voice.synthesizeSpeech(previewText) {
                    await MainActor.run {
                        voice.playVoiceResponse(audioData: audioData)
                    }
                }
            }
        } else {
            voice.stopPlayback()
        }
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        VoiceSettingsView()
    }
}

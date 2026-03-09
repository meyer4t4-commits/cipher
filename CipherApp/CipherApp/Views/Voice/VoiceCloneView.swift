import SwiftUI

// MARK: - Voice Clone View

struct VoiceCloneView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var recordingState: RecordingState = .idle
    @State private var recordingDuration: TimeInterval = 0
    @State private var recordingTimer: Timer?
    @State private var audioData: Data?
    @State private var hasConsentedToCloning = false
    @State private var isProcessing = false
    @State private var errorMessage: String?
    @State private var successMessage: String?

    var body: some View {
        ZStack {
            CipherTheme.background.ignoresSafeArea()

            VStack(spacing: 0) {
                // Header
                headerView

                ScrollView {
                    VStack(spacing: Spacing.xxxl) {
                        // Privacy explanation
                        privacySection

                        // Use cases
                        useCasesSection

                        // Recording section
                        recordingSection

                        // Consent
                        consentSection

                        // Action button
                        actionButton

                        Spacer(minLength: Spacing.xl)
                    }
                    .padding(Spacing.lg)
                }
            }
        }
        .alert("Recording Error", isPresented: .constant(errorMessage != nil)) {
            Button("Dismiss") { errorMessage = nil }
        } message: {
            if let error = errorMessage {
                Text(error)
            }
        }
        .alert("Success!", isPresented: .constant(successMessage != nil)) {
            Button("Done") {
                successMessage = nil
                dismiss()
            }
        } message: {
            if let success = successMessage {
                Text(success)
            }
        }
    }

    // MARK: - Header View

    private var headerView: some View {
        VStack(spacing: Spacing.md) {
            HStack {
                Button(action: { dismiss() }) {
                    Image(systemName: "chevron.left")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(CipherTheme.accent)
                        .frame(width: 40, height: 40)
                }

                Spacer()

                Text("Clone Your Voice")
                    .font(.system(size: 18, weight: .bold))
                    .foregroundColor(CipherTheme.textPrimary)

                Spacer()

                Color.clear.frame(width: 40, height: 40)
            }
            .padding(.horizontal, Spacing.lg)
            .padding(.vertical, Spacing.md)

            Divider().background(CipherTheme.border)
        }
    }

    // MARK: - Privacy Section

    private var privacySection: some View {
        VStack(alignment: .leading, spacing: Spacing.lg) {
            // Privacy badge
            HStack(spacing: Spacing.md) {
                Image(systemName: "shield.fill")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(CipherTheme.success)

                VStack(alignment: .leading, spacing: Spacing.xs) {
                    Text("Privacy First")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundColor(CipherTheme.textPrimary)

                    Text("Your voice stays on YOUR device")
                        .font(.system(size: 13, weight: .medium))
                        .foregroundColor(CipherTheme.textSecondary)
                }

                Spacer()
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

            VStack(alignment: .leading, spacing: Spacing.sm) {
                Text("Voice Cloning Process")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(CipherTheme.textPrimary)

                VStack(alignment: .leading, spacing: Spacing.md) {
                    privacyPoint(
                        number: "1",
                        title: "Record Locally",
                        description: "Your voice samples are processed entirely on your device"
                    )

                    privacyPoint(
                        number: "2",
                        title: "Secure Transmission",
                        description: "Encrypted samples sent to Cipher for neural voice cloning"
                    )

                    privacyPoint(
                        number: "3",
                        title: "Model Generation",
                        description: "Your unique voice model is created securely"
                    )

                    privacyPoint(
                        number: "4",
                        title: "Sovereign Control",
                        description: "You maintain complete control over your voice clone"
                    )
                }
            }
            .padding(Spacing.lg)
            .background(
                RoundedRectangle(cornerRadius: CornerRadius.md)
                    .fill(CipherTheme.surface)
                    .overlay(
                        RoundedRectangle(cornerRadius: CornerRadius.md)
                            .stroke(CipherTheme.border, lineWidth: 0.5)
                    )
            )
        }
    }

    private func privacyPoint(number: String, title: String, description: String) -> some View {
        HStack(spacing: Spacing.md) {
            Circle()
                .fill(CipherTheme.accent.opacity(0.2))
                .frame(width: 32, height: 32)
                .overlay(
                    Text(number)
                        .font(.system(size: 12, weight: .bold))
                        .foregroundColor(CipherTheme.accent)
                )

            VStack(alignment: .leading, spacing: Spacing.xs) {
                Text(title)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(CipherTheme.textPrimary)

                Text(description)
                    .font(.system(size: 12))
                    .foregroundColor(CipherTheme.textSecondary)
            }

            Spacer()
        }
    }

    // MARK: - Use Cases Section

    private var useCasesSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("What You Can Do")
                .font(.system(size: 14, weight: .bold))
                .foregroundColor(CipherTheme.textPrimary)

            VStack(spacing: Spacing.md) {
                useCase(
                    icon: "waveform.circle.fill",
                    title: "Create Voiceovers",
                    description: "Generate audio content in your own voice for videos and presentations"
                )

                useCase(
                    icon: "speaker.wave.2.fill",
                    title: "Personal Voice Assistant",
                    description: "Have Cipher respond in a voice that's uniquely yours"
                )

                useCase(
                    icon: "podcast.fill",
                    title: "Audio Content",
                    description: "Generate podcast episodes, audiobooks, and voice messages in your own voice"
                )

                useCase(
                    icon: "star.fill",
                    title: "Authentic Expression",
                    description: "Express yourself authentically with your genuine voice across platforms"
                )
            }
        }
    }

    private func useCase(icon: String, title: String, description: String) -> some View {
        HStack(spacing: Spacing.md) {
            Image(systemName: icon)
                .font(.system(size: 16, weight: .semibold))
                .foregroundColor(CipherTheme.accent)
                .frame(width: 32, alignment: .center)

            VStack(alignment: .leading, spacing: Spacing.xs) {
                Text(title)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(CipherTheme.textPrimary)

                Text(description)
                    .font(.system(size: 12))
                    .foregroundColor(CipherTheme.textSecondary)
                    .lineLimit(2)
            }

            Spacer()
        }
        .padding(Spacing.md)
        .background(
            RoundedRectangle(cornerRadius: CornerRadius.sm)
                .fill(CipherTheme.surfaceHover)
                .overlay(
                    RoundedRectangle(cornerRadius: CornerRadius.sm)
                        .stroke(CipherTheme.border, lineWidth: 0.5)
                )
        )
    }

    // MARK: - Recording Section

    private var recordingSection: some View {
        VStack(alignment: .center, spacing: Spacing.lg) {
            Text("Record Your Voice")
                .font(.system(size: 14, weight: .bold))
                .foregroundColor(CipherTheme.textPrimary)

            // Recording visualization
            ZStack {
                RoundedRectangle(cornerRadius: CornerRadius.lg)
                    .fill(CipherTheme.surface)
                    .overlay(
                        RoundedRectangle(cornerRadius: CornerRadius.lg)
                            .stroke(CipherTheme.border, lineWidth: 0.5)
                    )

                VStack(spacing: Spacing.lg) {
                    // Recording state indicator
                    ZStack {
                        Circle()
                            .fill(recordingState == .recording ? CipherTheme.error.opacity(0.1) : CipherTheme.accent.opacity(0.1))
                            .frame(width: 120, height: 120)

                        Circle()
                            .fill(recordingState == .recording ? CipherTheme.error : CipherTheme.accent)
                            .frame(width: 100, height: 100)

                        Image(systemName: recordingState == .recording ? "stop.fill" : "mic.fill")
                            .font(.system(size: 40, weight: .medium))
                            .foregroundColor(.white)
                    }
                    .scaleEffect(recordingState == .recording ? 1.05 : 1.0)
                    .animation(.easeInOut(duration: 0.5), value: recordingState)

                    // Duration display
                    if recordingState == .recording || (audioData != nil && recordingState != .idle) {
                        VStack(spacing: Spacing.xs) {
                            Text(formatDuration(recordingDuration))
                                .font(.system(size: 28, weight: .bold, design: .monospaced))
                                .foregroundColor(CipherTheme.textPrimary)

                            HStack(spacing: 4) {
                                Circle()
                                    .fill(CipherTheme.error)
                                    .frame(width: 8, height: 8)
                                    .opacity(recordingState == .recording ? 1 : 0)
                                    .animation(.easeInOut(duration: 0.5).repeatForever(), value: recordingState == .recording)

                                Text(recordingState == .recording ? "Recording..." : "Ready to review")
                                    .font(.system(size: 12, weight: .medium))
                                    .foregroundColor(CipherTheme.textSecondary)
                            }
                        }
                    } else {
                        Text("Minimum 30 seconds recommended")
                            .font(.system(size: 12, weight: .medium))
                            .foregroundColor(CipherTheme.textTertiary)
                    }

                    // Recording button
                    Button(action: toggleRecording) {
                        HStack(spacing: Spacing.sm) {
                            Image(systemName: recordingState == .recording ? "stop.circle.fill" : "circle.fill")
                                .font(.system(size: 14, weight: .semibold))

                            Text(recordingState == .recording ? "Stop Recording" : "Start Recording")
                                .font(.system(size: 14, weight: .semibold))
                        }
                        .frame(maxWidth: .infinity)
                        .padding(Spacing.md)
                        .background(
                            Capsule()
                                .fill(recordingState == .recording ? CipherTheme.error : CipherTheme.accent)
                        )
                        .foregroundColor(.white)
                    }
                    .disabled(isProcessing)
                }
                .padding(Spacing.xl)
            }

            // Quality indicator
            if recordingDuration > 0 {
                HStack(spacing: Spacing.md) {
                    VStack(alignment: .leading, spacing: Spacing.xs) {
                        HStack {
                            Text("Recording Quality")
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundColor(CipherTheme.textPrimary)

                            Spacer()

                            Text(recordingQualityText)
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundColor(recordingQualityColor)
                        }

                        ProgressView(value: min(recordingDuration / 30.0, 1.0))
                            .tint(recordingQualityColor)
                    }
                }
                .padding(Spacing.md)
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

    // MARK: - Consent Section

    private var consentSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            VStack(alignment: .leading, spacing: Spacing.md) {
                HStack(spacing: Spacing.md) {
                    Image(systemName: hasConsentedToCloning ? "checkmark.circle.fill" : "circle")
                        .font(.system(size: 20, weight: .semibold))
                        .foregroundColor(hasConsentedToCloning ? CipherTheme.success : CipherTheme.textTertiary)

                    VStack(alignment: .leading, spacing: Spacing.xs) {
                        Text("I understand and consent to voice cloning")
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundColor(CipherTheme.textPrimary)

                        Text("I agree to the processing of my voice samples for creating a personal voice model")
                            .font(.system(size: 11))
                            .foregroundColor(CipherTheme.textSecondary)
                    }

                    Spacer()
                }
                .onTapGesture {
                    hasConsentedToCloning.toggle()
                }

                Divider().background(CipherTheme.border)

                HStack(spacing: Spacing.md) {
                    Image(systemName: "lock.fill")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundColor(CipherTheme.info)

                    Text("Your data is encrypted and stored securely on your device")
                        .font(.system(size: 11))
                        .foregroundColor(CipherTheme.textTertiary)

                    Spacer()
                }
            }
            .padding(Spacing.md)
            .background(
                RoundedRectangle(cornerRadius: CornerRadius.md)
                    .fill(hasConsentedToCloning ? CipherTheme.success.opacity(0.08) : CipherTheme.surface)
                    .overlay(
                        RoundedRectangle(cornerRadius: CornerRadius.md)
                            .stroke(
                                hasConsentedToCloning ? CipherTheme.success.opacity(0.3) : CipherTheme.border,
                                lineWidth: 0.5
                            )
                    )
            )
        }
    }

    // MARK: - Action Button

    private var actionButton: some View {
        VStack(spacing: Spacing.md) {
            Button(action: cloneVoice) {
                HStack(spacing: Spacing.sm) {
                    if isProcessing {
                        ProgressView()
                            .tint(.white)
                            .scaleEffect(0.8)
                    } else {
                        Image(systemName: "waveform.badge.plus")
                            .font(.system(size: 16, weight: .semibold))
                    }

                    Text(isProcessing ? "Processing..." : "Clone My Voice")
                        .font(.system(size: 15, weight: .bold))
                }
                .frame(maxWidth: .infinity)
                .padding(Spacing.lg)
                .background(
                    Capsule()
                        .fill(CipherTheme.accentGradient)
                )
                .foregroundColor(.white)
            }
            .disabled(!isCloneButtonEnabled || isProcessing)
            .opacity(isCloneButtonEnabled && !isProcessing ? 1.0 : 0.5)

            if !isCloneButtonEnabled {
                HStack(spacing: Spacing.xs) {
                    Image(systemName: "info.circle.fill")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(CipherTheme.warning)

                    Text(cloneButtonDisabledReason)
                        .font(.system(size: 12, weight: .medium))
                        .foregroundColor(CipherTheme.warning)

                    Spacer()
                }
                .padding(Spacing.md)
                .background(
                    RoundedRectangle(cornerRadius: CornerRadius.sm)
                        .fill(CipherTheme.warning.opacity(0.08))
                        .overlay(
                            RoundedRectangle(cornerRadius: CornerRadius.sm)
                                .stroke(CipherTheme.warning.opacity(0.2), lineWidth: 0.5)
                        )
                )
            }
        }
    }

    // MARK: - Helper Methods

    private var isCloneButtonEnabled: Bool {
        audioData != nil && recordingDuration >= 10 && hasConsentedToCloning && !isProcessing
    }

    private var cloneButtonDisabledReason: String {
        if audioData == nil {
            return "Please record your voice first"
        } else if recordingDuration < 10 {
            return "Recording too short (minimum 10 seconds, 30+ recommended)"
        } else if !hasConsentedToCloning {
            return "Please consent to voice cloning"
        }
        return ""
    }

    private var recordingQualityText: String {
        if recordingDuration < 10 {
            return "Too short"
        } else if recordingDuration < 30 {
            return "Good"
        } else if recordingDuration < 60 {
            return "Excellent"
        } else {
            return "Perfect"
        }
    }

    private var recordingQualityColor: Color {
        if recordingDuration < 10 {
            return CipherTheme.error
        } else if recordingDuration < 30 {
            return CipherTheme.warning
        } else {
            return CipherTheme.success
        }
    }

    private func formatDuration(_ seconds: TimeInterval) -> String {
        let minutes = Int(seconds) / 60
        let secs = Int(seconds) % 60
        return String(format: "%02d:%02d", minutes, secs)
    }

    private func toggleRecording() {
        HapticsService.shared.mediumTap()

        switch recordingState {
        case .idle:
            recordingState = .recording
            recordingDuration = 0
            startRecordingTimer()
        case .recording:
            recordingState = .paused
            stopRecordingTimer()
        case .paused:
            recordingState = .recording
            startRecordingTimer()
        }
    }

    private func startRecordingTimer() {
        recordingTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { _ in
            recordingDuration += 0.1
        }
    }

    private func stopRecordingTimer() {
        recordingTimer?.invalidate()
        recordingTimer = nil
    }

    private func cloneVoice() {
        guard let audioData = audioData else { return }

        isProcessing = true

        Task {
            do {
                let voiceId = try await CipherAPI.shared.cloneVoice(
                    audioData: audioData,
                    name: "My Voice"
                )

                // Store the cloned voice ID
                VoiceService.shared.selectedVoiceId = voiceId

                successMessage = "Your voice has been successfully cloned! Cipher can now respond in your voice."
            } catch {
                errorMessage = "Failed to clone voice: \(error.localizedDescription)"
                isProcessing = false
            }
        }
    }
}

// MARK: - Recording State

enum RecordingState {
    case idle
    case recording
    case paused
}

// MARK: - Preview

#Preview {
    VoiceCloneView()
}

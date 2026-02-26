import SwiftUI

// MARK: - Settings View

struct SettingsView: View {
    @State private var viewModel = SettingsViewModel()
    @State private var showClearAlert = false
    @State private var showResetAlert = false

    var body: some View {
        NavigationStack {
            ZStack {
                CipherTheme.background.ignoresSafeArea()

                ScrollView {
                    VStack(spacing: Spacing.xxl) {
                        // Connection Section
                        connectionSection

                        // Model Section
                        modelSection

                        // Streaming Section
                        streamingSection

                        // Voice & Audio Section
                        voiceSection

                        // Privacy & Security
                        privacySection

                        // Data Management
                        dataSection

                        // About
                        aboutSection

                        Spacer(minLength: 40)
                    }
                    .padding(Spacing.lg)
                }
                .navigationTitle("Settings")
                .navigationBarTitleDisplayMode(.inline)
            }
        }
        .onAppear {
            Task { await viewModel.checkServerHealth() }
        }
        .alert("Clear All Data?", isPresented: $showClearAlert) {
            Button("Cancel", role: .cancel) {}
            Button("Clear Everything", role: .destructive) {
                viewModel.clearAllData()
            }
        } message: {
            Text("This will permanently delete all conversations and local data. This cannot be undone.")
        }
        .alert("Reset Settings?", isPresented: $showResetAlert) {
            Button("Cancel", role: .cancel) {}
            Button("Reset", role: .destructive) {
                viewModel.resetToDefaults()
            }
        } message: {
            Text("This will reset all settings to their default values.")
        }
    }

    // MARK: - Connection Section

    private var connectionSection: some View {
        SettingsSection(title: "Connection", icon: "network") {
            VStack(spacing: Spacing.md) {
                // Server URL
                VStack(alignment: .leading, spacing: Spacing.xs) {
                    Text("Orchid Server URL")
                        .font(.system(size: 13, weight: .medium))
                        .foregroundColor(CipherTheme.textSecondary)

                    TextField("http://localhost:8000", text: $viewModel.serverURL)
                        .textFieldStyle(.plain)
                        .font(.system(size: 14, design: .monospaced))
                        .foregroundColor(CipherTheme.textPrimary)
                        .padding(Spacing.md)
                        .background(
                            RoundedRectangle(cornerRadius: CornerRadius.sm)
                                .fill(CipherTheme.background)
                                .overlay(
                                    RoundedRectangle(cornerRadius: CornerRadius.sm)
                                        .stroke(CipherTheme.border, lineWidth: 0.5)
                                )
                        )
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                }

                // Status row
                HStack {
                    ConnectionIndicator(isConnected: viewModel.isConnected)

                    if let latency = viewModel.latencyMs {
                        Text("\(latency)ms")
                            .font(.system(size: 11, weight: .medium, design: .monospaced))
                            .foregroundColor(CipherTheme.textTertiary)
                    }

                    Spacer()

                    Button(action: {
                        Task { await viewModel.testConnection() }
                    }) {
                        HStack(spacing: 4) {
                            if viewModel.isTesting {
                                ProgressView()
                                    .tint(CipherTheme.accent)
                                    .scaleEffect(0.7)
                            } else {
                                Image(systemName: "arrow.clockwise")
                                    .font(.system(size: 12, weight: .semibold))
                            }
                            Text("Test")
                                .font(.system(size: 13, weight: .semibold))
                        }
                        .foregroundColor(CipherTheme.accent)
                        .padding(.horizontal, Spacing.md)
                        .padding(.vertical, Spacing.xs)
                        .background(
                            Capsule()
                                .fill(CipherTheme.accent.opacity(0.1))
                        )
                    }
                    .disabled(viewModel.isTesting)
                }
            }
        }
    }

    // MARK: - Model Section

    private var modelSection: some View {
        SettingsSection(title: "Model", icon: "brain") {
            VStack(spacing: Spacing.lg) {
                // Model tier picker
                VStack(alignment: .leading, spacing: Spacing.sm) {
                    Text("Intelligence Tier")
                        .font(.system(size: 13, weight: .medium))
                        .foregroundColor(CipherTheme.textSecondary)

                    ForEach(ModelTier.allCases, id: \.self) { tier in
                        tierRow(tier)
                    }
                }

                Divider().background(CipherTheme.border)

                // Memory toggle
                Toggle(isOn: $viewModel.includeMemory) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Contextual Memory")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(CipherTheme.textPrimary)
                        Text("Remember context across messages")
                            .font(.system(size: 12))
                            .foregroundColor(CipherTheme.textTertiary)
                    }
                }
                .tint(CipherTheme.accent)

                Divider().background(CipherTheme.border)

                // Max tokens
                VStack(alignment: .leading, spacing: Spacing.sm) {
                    HStack {
                        Text("Max Tokens")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(CipherTheme.textPrimary)
                        Spacer()
                        Text("\(Int(viewModel.maxTokens))")
                            .font(.system(size: 14, weight: .semibold, design: .monospaced))
                            .foregroundColor(CipherTheme.accent)
                    }
                    Slider(value: $viewModel.maxTokens, in: 256...8192, step: 256)
                        .tint(CipherTheme.accent)
                }

                // Temperature
                VStack(alignment: .leading, spacing: Spacing.sm) {
                    HStack {
                        Text("Temperature")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(CipherTheme.textPrimary)
                        Spacer()
                        Text(String(format: "%.1f", viewModel.temperature))
                            .font(.system(size: 14, weight: .semibold, design: .monospaced))
                            .foregroundColor(CipherTheme.accent)
                    }
                    Slider(value: $viewModel.temperature, in: 0...2, step: 0.1)
                        .tint(CipherTheme.accent)
                }
            }
        }
    }

    private func tierRow(_ tier: ModelTier) -> some View {
        Button(action: {
            viewModel.selectedTier = tier
            HapticsService.shared.selection()
        }) {
            HStack(spacing: Spacing.md) {
                Image(systemName: tier.icon)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(CipherTheme.tierColor(tier.rawValue))
                    .frame(width: 24)

                VStack(alignment: .leading, spacing: 1) {
                    Text(tier.displayName)
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(CipherTheme.textPrimary)
                    Text(tier.description)
                        .font(.system(size: 11))
                        .foregroundColor(CipherTheme.textTertiary)
                }

                Spacer()

                if viewModel.selectedTier == tier {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 18))
                        .foregroundColor(CipherTheme.accent)
                }
            }
            .padding(Spacing.md)
            .background(
                RoundedRectangle(cornerRadius: CornerRadius.sm)
                    .fill(viewModel.selectedTier == tier ? CipherTheme.accent.opacity(0.08) : Color.clear)
            )
        }
    }

    // MARK: - Streaming Section

    private var streamingSection: some View {
        SettingsSection(title: "Streaming", icon: "waveform") {
            Toggle(isOn: $viewModel.streamingEnabled) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Stream Responses")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(CipherTheme.textPrimary)
                    Text("See responses as they're generated")
                        .font(.system(size: 12))
                        .foregroundColor(CipherTheme.textTertiary)
                }
            }
            .tint(CipherTheme.accent)
        }
    }

    // MARK: - Voice & Audio Section

    private var voiceSection: some View {
        NavigationLink(destination: VoiceSettingsView()) {
            VStack(alignment: .leading, spacing: Spacing.md) {
                HStack(spacing: Spacing.sm) {
                    Image(systemName: "speaker.wave.2.fill")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(CipherTheme.accent)

                    Text("Voice & Audio")
                        .font(.system(size: 13, weight: .bold))
                        .foregroundColor(CipherTheme.accent)
                        .textCase(.uppercase)
                        .tracking(0.5)
                }

                VStack(alignment: .leading, spacing: 0) {
                    HStack(spacing: Spacing.md) {
                        VStack(alignment: .leading, spacing: Spacing.xs) {
                            Text("Voice Responses")
                                .font(.system(size: 14, weight: .medium))
                                .foregroundColor(CipherTheme.textPrimary)

                            Text(VoiceService.shared.voiceResponseEnabled ? "Enabled" : "Disabled")
                                .font(.system(size: 12))
                                .foregroundColor(CipherTheme.textTertiary)
                        }

                        Spacer()

                        HStack(spacing: Spacing.sm) {
                            if VoiceService.shared.voiceResponseEnabled {
                                Text("On")
                                    .font(.system(size: 11, weight: .semibold, design: .monospaced))
                                    .foregroundColor(CipherTheme.success)

                                Image(systemName: "checkmark.circle.fill")
                                    .font(.system(size: 14))
                                    .foregroundColor(CipherTheme.success)
                            }

                            Image(systemName: "chevron.right")
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundColor(CipherTheme.textTertiary)
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
        }
        .foregroundColor(CipherTheme.textPrimary)
    }

    // MARK: - Privacy Section

    private var privacySection: some View {
        SettingsSection(title: "Privacy & Security", icon: "lock.shield.fill") {
            VStack(spacing: Spacing.md) {
                Toggle(isOn: $viewModel.biometricEnabled) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(viewModel.biometricType)
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(CipherTheme.textPrimary)
                        Text("Require authentication to open Cipher")
                            .font(.system(size: 12))
                            .foregroundColor(CipherTheme.textTertiary)
                    }
                }
                .tint(CipherTheme.accent)

                Divider().background(CipherTheme.border)

                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Data Privacy")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(CipherTheme.textPrimary)
                        Text("All data stored locally on your device")
                            .font(.system(size: 12))
                            .foregroundColor(CipherTheme.textTertiary)
                    }

                    Spacer()

                    PrivacyBadge(compact: true)
                }
            }
        }
    }

    // MARK: - Data Section

    private var dataSection: some View {
        SettingsSection(title: "Data", icon: "internaldrive.fill") {
            VStack(spacing: Spacing.md) {
                HStack {
                    Text("Conversations")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(CipherTheme.textPrimary)
                    Spacer()
                    Text("\(viewModel.totalConversations)")
                        .font(.system(size: 14, weight: .semibold, design: .monospaced))
                        .foregroundColor(CipherTheme.textSecondary)
                }

                HStack {
                    Text("Storage Used")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(CipherTheme.textPrimary)
                    Spacer()
                    Text(viewModel.storageUsed)
                        .font(.system(size: 14, weight: .semibold, design: .monospaced))
                        .foregroundColor(CipherTheme.textSecondary)
                }

                Divider().background(CipherTheme.border)

                HStack(spacing: Spacing.md) {
                    Button(action: { showResetAlert = true }) {
                        Text("Reset Settings")
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundColor(CipherTheme.warning)
                    }

                    Spacer()

                    Button(action: { showClearAlert = true }) {
                        HStack(spacing: 4) {
                            Image(systemName: "trash")
                                .font(.system(size: 12))
                            Text("Clear All Data")
                                .font(.system(size: 13, weight: .semibold))
                        }
                        .foregroundColor(CipherTheme.error)
                    }
                }
            }
        }
    }

    // MARK: - About Section

    private var aboutSection: some View {
        SettingsSection(title: "About", icon: "info.circle") {
            HStack(spacing: Spacing.lg) {
                CipherLogo(size: 48)

                VStack(alignment: .leading, spacing: 3) {
                    Text(AppConstants.appName)
                        .font(.system(size: 18, weight: .bold))
                        .foregroundColor(CipherTheme.textPrimary)

                    Text("Version \(AppConstants.appVersion)")
                        .font(.system(size: 12, design: .monospaced))
                        .foregroundColor(CipherTheme.textTertiary)

                    Text("by \(AppConstants.publisherName)")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundColor(CipherTheme.accent)
                }

                Spacer()

                PrivacyBadge()
            }
        }
    }
}

// MARK: - Settings Section Container

struct SettingsSection<Content: View>: View {
    let title: String
    let icon: String
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            HStack(spacing: Spacing.sm) {
                Image(systemName: icon)
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(CipherTheme.accent)

                Text(title)
                    .font(.system(size: 13, weight: .bold))
                    .foregroundColor(CipherTheme.accent)
                    .textCase(.uppercase)
                    .tracking(0.5)
            }

            VStack(alignment: .leading, spacing: 0) {
                content
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
}

#Preview {
    SettingsView()
}

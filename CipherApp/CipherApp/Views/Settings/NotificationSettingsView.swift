import SwiftUI
import UserNotifications

// MARK: - Notification Settings View

struct NotificationSettingsView: View {
    @State private var pushEnabled = false
    @State private var smsEnabled = false
    @State private var phoneNumber = ""
    @State private var alertOnQuestions = true
    @State private var alertOnCompletions = true
    @State private var alertOnFailures = true
    @State private var isSendingTest = false
    @State private var testResult: String?
    @State private var permissionStatus: UNAuthorizationStatus = .notDetermined

    var body: some View {
        ZStack {
            CipherTheme.background.ignoresSafeArea()

            ScrollView {
                VStack(spacing: Spacing.xxl) {
                    // Push Notifications
                    pushSection

                    // SMS Alerts
                    smsSection

                    // Alert Types
                    alertTypesSection

                    // Test
                    testSection

                    Spacer(minLength: 40)
                }
                .padding(Spacing.lg)
            }
        }
        .navigationTitle("Notifications")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await checkPermissionStatus()
            loadPreferences()
        }
    }

    // MARK: - Push Section

    private var pushSection: some View {
        SettingsSection(title: "Push Notifications", icon: "bell.badge.fill") {
            VStack(spacing: Spacing.md) {
                Toggle(isOn: $pushEnabled) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Enable Push Notifications")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(CipherTheme.textPrimary)
                        Text("Get notified when agents need input or finish tasks")
                            .font(.system(size: 12))
                            .foregroundColor(CipherTheme.textTertiary)
                    }
                }
                .tint(CipherTheme.accent)
                .onChange(of: pushEnabled) { _, newValue in
                    if newValue {
                        Task { await requestPushPermission() }
                    }
                }

                // Permission status
                HStack {
                    Image(systemName: permissionStatusIcon)
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(permissionStatusColor)
                    Text(permissionStatusText)
                        .font(.system(size: 12))
                        .foregroundColor(CipherTheme.textTertiary)
                    Spacer()
                }
            }
        }
    }

    // MARK: - SMS Section

    private var smsSection: some View {
        SettingsSection(title: "SMS Alerts", icon: "message.fill") {
            VStack(spacing: Spacing.md) {
                Toggle(isOn: $smsEnabled) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Enable SMS Alerts")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(CipherTheme.textPrimary)
                        Text("Receive text messages for critical agent events")
                            .font(.system(size: 12))
                            .foregroundColor(CipherTheme.textTertiary)
                    }
                }
                .tint(CipherTheme.accent)

                if smsEnabled {
                    VStack(alignment: .leading, spacing: Spacing.xs) {
                        Text("Phone Number")
                            .font(.system(size: 13, weight: .medium))
                            .foregroundColor(CipherTheme.textSecondary)

                        TextField("+1 (555) 000-0000", text: $phoneNumber)
                            .textFieldStyle(.plain)
                            .font(.system(size: 14, design: .monospaced))
                            .foregroundColor(CipherTheme.textPrimary)
                            .keyboardType(.phonePad)
                            .padding(Spacing.md)
                            .background(
                                RoundedRectangle(cornerRadius: CornerRadius.sm)
                                    .fill(CipherTheme.background)
                                    .overlay(
                                        RoundedRectangle(cornerRadius: CornerRadius.sm)
                                            .stroke(CipherTheme.border, lineWidth: 0.5)
                                    )
                            )
                    }
                }
            }
        }
    }

    // MARK: - Alert Types

    private var alertTypesSection: some View {
        SettingsSection(title: "Alert Types", icon: "bell.and.waves.left.and.right") {
            VStack(spacing: Spacing.md) {
                Toggle(isOn: $alertOnQuestions) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Clarifying Questions")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(CipherTheme.textPrimary)
                        Text("When an agent needs your input to proceed")
                            .font(.system(size: 12))
                            .foregroundColor(CipherTheme.textTertiary)
                    }
                }
                .tint(CipherTheme.accent)

                Divider().background(CipherTheme.border)

                Toggle(isOn: $alertOnCompletions) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Task Completions")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(CipherTheme.textPrimary)
                        Text("When an agent finishes its work")
                            .font(.system(size: 12))
                            .foregroundColor(CipherTheme.textTertiary)
                    }
                }
                .tint(CipherTheme.accent)

                Divider().background(CipherTheme.border)

                Toggle(isOn: $alertOnFailures) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Failures & Errors")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(CipherTheme.textPrimary)
                        Text("When something goes wrong during execution")
                            .font(.system(size: 12))
                            .foregroundColor(CipherTheme.textTertiary)
                    }
                }
                .tint(CipherTheme.accent)
            }
        }
    }

    // MARK: - Test Section

    private var testSection: some View {
        SettingsSection(title: "Test", icon: "paperplane.fill") {
            VStack(spacing: Spacing.md) {
                Button(action: {
                    Task { await sendTestNotification() }
                }) {
                    HStack(spacing: Spacing.sm) {
                        if isSendingTest {
                            ProgressView()
                                .tint(CipherTheme.accent)
                                .scaleEffect(0.8)
                        } else {
                            Image(systemName: "bell.badge")
                                .font(.system(size: 14, weight: .semibold))
                        }
                        Text("Send Test Notification")
                            .font(.system(size: 14, weight: .semibold))
                    }
                    .foregroundColor(CipherTheme.accent)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Spacing.md)
                    .background(CipherTheme.accent.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
                }
                .disabled(isSendingTest)

                if let result = testResult {
                    Text(result)
                        .font(.system(size: 12))
                        .foregroundColor(CipherTheme.textTertiary)
                }
            }
        }
    }

    // MARK: - Helpers

    private func checkPermissionStatus() async {
        let settings = await UserNotificationManager.shared.getNotificationSettings()
        await MainActor.run {
            permissionStatus = settings.authorizationStatus
            pushEnabled = settings.authorizationStatus == .authorized
        }
    }

    private func requestPushPermission() async {
        await UserNotificationManager.shared.requestAuthorization()
        await checkPermissionStatus()
    }

    private func sendTestNotification() async {
        isSendingTest = true
        testResult = nil

        do {
            try await CipherAPI.shared.sendTestNotification()
            testResult = "Test notification sent successfully"
        } catch {
            testResult = "Failed: \(error.localizedDescription)"
        }

        isSendingTest = false
    }

    private func loadPreferences() {
        alertOnQuestions = UserDefaults.standard.object(forKey: "notify_questions") as? Bool ?? true
        alertOnCompletions = UserDefaults.standard.object(forKey: "notify_completions") as? Bool ?? true
        alertOnFailures = UserDefaults.standard.object(forKey: "notify_failures") as? Bool ?? true
        smsEnabled = UserDefaults.standard.bool(forKey: "sms_enabled")
        phoneNumber = UserDefaults.standard.string(forKey: "sms_phone") ?? ""
    }

    private var permissionStatusIcon: String {
        switch permissionStatus {
        case .authorized: return "checkmark.circle.fill"
        case .denied: return "xmark.circle.fill"
        case .provisional: return "checkmark.circle"
        default: return "questionmark.circle"
        }
    }

    private var permissionStatusColor: Color {
        switch permissionStatus {
        case .authorized, .provisional: return CipherTheme.success
        case .denied: return CipherTheme.error
        default: return CipherTheme.textTertiary
        }
    }

    private var permissionStatusText: String {
        switch permissionStatus {
        case .authorized: return "Notifications authorized"
        case .denied: return "Notifications denied — enable in Settings app"
        case .provisional: return "Provisional authorization"
        default: return "Permission not yet requested"
        }
    }
}

#Preview {
    NavigationStack {
        NotificationSettingsView()
    }
}

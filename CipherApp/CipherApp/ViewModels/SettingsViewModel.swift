import Foundation
import SwiftUI
import LocalAuthentication

// MARK: - Settings ViewModel

@Observable
class SettingsViewModel {
    var serverURL: String {
        get { CipherAPI.shared.serverURL }
        set { CipherAPI.shared.serverURL = newValue }
    }

    var isConnected: Bool { CipherAPI.shared.isHealthy }
    var latencyMs: Int? { CipherAPI.shared.latencyMs }
    var isTesting = false

    var selectedTier: ModelTier {
        get {
            let raw = UserDefaults.standard.string(forKey: "model_tier") ?? "auto"
            return ModelTier(rawValue: raw) ?? .auto
        }
        set {
            UserDefaults.standard.set(newValue.rawValue, forKey: "model_tier")
        }
    }

    var includeMemory: Bool {
        get { UserDefaults.standard.object(forKey: "include_memory") as? Bool ?? true }
        set { UserDefaults.standard.set(newValue, forKey: "include_memory") }
    }

    var maxTokens: Double {
        get { Double(UserDefaults.standard.object(forKey: "max_tokens") as? Int ?? 4096) }
        set { UserDefaults.standard.set(Int(newValue), forKey: "max_tokens") }
    }

    var temperature: Double {
        get { UserDefaults.standard.object(forKey: "temperature") as? Double ?? 0.7 }
        set { UserDefaults.standard.set(newValue, forKey: "temperature") }
    }

    var streamingEnabled: Bool {
        get { UserDefaults.standard.object(forKey: "streaming_enabled") as? Bool ?? true }
        set { UserDefaults.standard.set(newValue, forKey: "streaming_enabled") }
    }

    var biometricEnabled: Bool {
        get { UserDefaults.standard.bool(forKey: "biometric_enabled") }
        set { UserDefaults.standard.set(newValue, forKey: "biometric_enabled") }
    }

    var privacyMode: Bool {
        get { UserDefaults.standard.bool(forKey: "privacy_mode") }
        set { UserDefaults.standard.set(newValue, forKey: "privacy_mode") }
    }

    var hasCompletedOnboarding: Bool {
        get { UserDefaults.standard.bool(forKey: "has_completed_onboarding") }
        set { UserDefaults.standard.set(newValue, forKey: "has_completed_onboarding") }
    }

    // Legacy compatibility
    var isServerHealthy: Bool { isConnected }
    var selectedModelTier: String {
        get { selectedTier.rawValue }
        set { selectedTier = ModelTier(rawValue: newValue) ?? .auto }
    }

    // MARK: - Stats

    var totalConversations: Int { ConversationStorage.shared.totalConversations }
    var storageUsed: String { ConversationStorage.shared.storageUsedDisplay }

    // MARK: - Biometric Auth

    var biometricType: String {
        let context = LAContext()
        var error: NSError?
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            return "Passcode"
        }
        switch context.biometryType {
        case .none: return "Passcode"
        case .faceID: return "Face ID"
        case .touchID: return "Touch ID"
        case .opticID: return "Optic ID"
        @unknown default: return "Biometric"
        }
    }

    func authenticate() async -> Bool {
        let context = LAContext()
        context.localizedReason = "Unlock Cipher"

        do {
            return try await context.evaluatePolicy(
                .deviceOwnerAuthenticationWithBiometrics,
                localizedReason: "Authenticate to access Cipher"
            )
        } catch {
            return false
        }
    }

    // MARK: - Actions

    @MainActor
    func testConnection() async {
        isTesting = true
        _ = await CipherAPI.shared.checkHealth()
        isTesting = false
    }

    @MainActor
    func checkServerHealth() async {
        _ = await CipherAPI.shared.checkHealth()
    }

    func clearAllData() {
        ConversationStorage.shared.deleteAllConversations()
    }

    func resetToDefaults() {
        serverURL = AppConstants.defaultServerURL
        selectedTier = .auto
        includeMemory = true
        maxTokens = 4096
        temperature = 0.7
        streamingEnabled = true
    }

    func resetSettings() {
        resetToDefaults()
    }
}

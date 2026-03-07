import SwiftUI

@main
struct CipherApp: App {
    @State private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            Group {
                switch appState.phase {
                case .splash:
                    SplashScreenView {
                        appState.advanceFromSplash()
                    }
                case .onboarding:
                    OnboardingView(isComplete: Binding(
                        get: { false },
                        set: { _ in appState.completeOnboarding() }
                    ))
                case .locked:
                    LockScreenView {
                        appState.unlock()
                    }
                case .main:
                    MainTabView()
                }
            }
            .preferredColorScheme(.dark)
        }
    }
}

// MARK: - App State

@Observable
class AppState {
    enum Phase {
        case splash
        case onboarding
        case locked
        case main
    }

    var phase: Phase = .splash

    var hasCompletedOnboarding: Bool {
        UserDefaults.standard.bool(forKey: "has_completed_onboarding")
    }

    var biometricEnabled: Bool {
        UserDefaults.standard.bool(forKey: "biometric_enabled")
    }

    func advanceFromSplash() {
        withAnimation(.easeInOut(duration: 0.5)) {
            if !hasCompletedOnboarding {
                phase = .onboarding
            } else if biometricEnabled {
                phase = .locked
            } else {
                phase = .main
            }
        }
    }

    func completeOnboarding() {
        UserDefaults.standard.set(true, forKey: "has_completed_onboarding")
        withAnimation(.easeInOut(duration: 0.5)) {
            phase = .main
        }
    }

    func unlock() {
        withAnimation(.easeInOut(duration: 0.4)) {
            phase = .main
        }
    }
}

// MARK: - Splash Screen

struct SplashScreenView: View {
    let onComplete: () -> Void

    @State private var logoOpacity = 0.0
    @State private var logoScale = 0.8
    @State private var textOpacity = 0.0
    @State private var ringScale = 0.5
    @State private var ringOpacity = 0.0

    var body: some View {
        ZStack {
            CipherTheme.background.ignoresSafeArea()

            // Ambient gradient
            CipherTheme.meshGradient
                .ignoresSafeArea()
                .opacity(ringOpacity * 0.5)

            VStack(spacing: Spacing.xxl) {
                Spacer()

                // Logo with glow rings
                ZStack {
                    // Pulse rings
                    ForEach(0..<3, id: \.self) { i in
                        Circle()
                            .stroke(CipherTheme.accent.opacity(0.1), lineWidth: 1)
                            .frame(width: CGFloat(140 + i * 50), height: CGFloat(140 + i * 50))
                            .scaleEffect(ringScale)
                            .opacity(ringOpacity)
                    }

                    CipherLogo(size: 100, animated: false)
                        .scaleEffect(logoScale)
                }
                .opacity(logoOpacity)

                VStack(spacing: Spacing.sm) {
                    Text(AppConstants.appName)
                        .font(.system(size: 36, weight: .bold, design: .rounded))
                        .foregroundColor(CipherTheme.textPrimary)

                    Text(AppConstants.tagline)
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(CipherTheme.textSecondary)
                        .tracking(2)
                        .textCase(.uppercase)
                }
                .opacity(textOpacity)

                Spacer()

                Text(AppConstants.publisherName)
                    .font(.system(size: 12, weight: .medium))
                    .foregroundColor(CipherTheme.textTertiary)
                    .tracking(1)
                    .opacity(textOpacity)
                    .padding(.bottom, Spacing.xxxl)
            }
        }
        .onAppear {
            // Phase 1: Logo appears
            withAnimation(.easeOut(duration: 0.6)) {
                logoOpacity = 1.0
                logoScale = 1.0
            }

            // Phase 2: Rings expand
            withAnimation(.easeOut(duration: 0.8).delay(0.3)) {
                ringScale = 1.0
                ringOpacity = 1.0
            }

            // Phase 3: Text fades in
            withAnimation(.easeOut(duration: 0.5).delay(0.5)) {
                textOpacity = 1.0
            }

            // Phase 4: Transition out
            DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
                withAnimation(.easeInOut(duration: 0.4)) {
                    logoOpacity = 0
                    textOpacity = 0
                    ringOpacity = 0
                }

                DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
                    onComplete()
                }
            }
        }
    }
}

// MARK: - Lock Screen

struct LockScreenView: View {
    let onUnlock: () -> Void

    @State private var isAuthenticating = false
    @State private var authFailed = false

    var body: some View {
        ZStack {
            CipherTheme.background.ignoresSafeArea()

            VStack(spacing: Spacing.xxxl) {
                Spacer()

                CipherLogo(size: 80, animated: true)

                VStack(spacing: Spacing.md) {
                    Text("Cipher is Locked")
                        .font(.system(size: 22, weight: .bold))
                        .foregroundColor(CipherTheme.textPrimary)

                    Text("Authenticate to continue")
                        .font(.system(size: 15))
                        .foregroundColor(CipherTheme.textSecondary)
                }

                if authFailed {
                    Text("Authentication failed. Try again.")
                        .font(.system(size: 14))
                        .foregroundColor(CipherTheme.error)
                }

                Spacer()

                Button(action: authenticate) {
                    HStack(spacing: Spacing.sm) {
                        Image(systemName: "faceid")
                            .font(.system(size: 20, weight: .medium))
                        Text("Unlock")
                            .font(.system(size: 17, weight: .semibold))
                    }
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Spacing.lg)
                    .background(CipherTheme.accentGradient)
                    .clipShape(RoundedRectangle(cornerRadius: CornerRadius.lg))
                }
                .padding(.horizontal, Spacing.xxl)
                .padding(.bottom, Spacing.xxxl)
            }
        }
        .onAppear { authenticate() }
    }

    private func authenticate() {
        isAuthenticating = true
        authFailed = false

        Task {
            let settings = SettingsViewModel()
            let success = await settings.authenticate()
            await MainActor.run {
                isAuthenticating = false
                if success {
                    onUnlock()
                } else {
                    authFailed = true
                }
            }
        }
    }
}

#Preview("Splash") {
    SplashScreenView(onComplete: {})
}

#Preview("Lock") {
    LockScreenView(onUnlock: {})
}

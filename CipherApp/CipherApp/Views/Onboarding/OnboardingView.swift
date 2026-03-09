import SwiftUI

// MARK: - Onboarding View

struct OnboardingView: View {
    @Binding var isComplete: Bool
    @State private var currentPage = 0

    private let pages: [OnboardingPage] = [
        OnboardingPage(
            icon: "lock.shield.fill",
            iconColor: "34D399",
            title: "Sovereign Intelligence",
            subtitle: "Your AI runs on your terms. All conversations stay on your device. No data leaves without your permission.",
            accentText: "Built with love. Built for you."
        ),
        OnboardingPage(
            icon: "brain",
            iconColor: "6C63FF",
            title: "Multi-Model Power",
            subtitle: "Cipher automatically routes to the best AI model for each task — Claude for strategy, Groq for speed, DeepSeek for code.",
            accentText: "The best of every model, unified."
        ),
        OnboardingPage(
            icon: "waveform",
            iconColor: "A855F7",
            title: "Voice & Vision",
            subtitle: "Speak naturally with voice mode. Share images and documents for analysis. Cipher understands it all.",
            accentText: "Your thoughts, any format."
        ),
        OnboardingPage(
            icon: "network",
            iconColor: "60A5FA",
            title: "Connect to Server",
            subtitle: "Cipher works with your Elysian server for full AI power. You can set the server URL in Settings anytime — or just use the default.",
            accentText: "Smart routing. Seamless connection."
        ),
        OnboardingPage(
            icon: "sparkles",
            iconColor: "FBBF24",
            title: "Always Evolving",
            subtitle: "Cipher's intelligence scanner monitors the frontier 24/7, automatically discovering and integrating new capabilities.",
            accentText: "The future, delivered daily."
        )
    ]

    var body: some View {
        ZStack {
            CipherTheme.background.ignoresSafeArea()

            // Ambient gradient
            CipherTheme.meshGradient
                .ignoresSafeArea()
                .opacity(0.5)

            VStack(spacing: 0) {
                // Skip button
                HStack {
                    Spacer()
                    Button(action: complete) {
                        Text("Skip")
                            .font(.system(size: 15, weight: .medium))
                            .foregroundColor(CipherTheme.textTertiary)
                    }
                    .padding()
                }

                // Pages
                TabView(selection: $currentPage) {
                    ForEach(Array(pages.enumerated()), id: \.offset) { index, page in
                        onboardingPage(page)
                            .tag(index)
                    }
                }
                .tabViewStyle(.page(indexDisplayMode: .never))

                // Bottom controls
                VStack(spacing: Spacing.xl) {
                    // Page indicators
                    HStack(spacing: Spacing.sm) {
                        ForEach(0..<pages.count, id: \.self) { index in
                            Capsule()
                                .fill(index == currentPage ? CipherTheme.accent : CipherTheme.textTertiary.opacity(0.3))
                                .frame(width: index == currentPage ? 24 : 8, height: 8)
                                .animation(.spring(response: 0.3), value: currentPage)
                        }
                    }

                    // Action button
                    Button(action: {
                        if currentPage == pages.count - 1 {
                            complete()
                        } else {
                            withAnimation(.spring(response: 0.4)) {
                                currentPage += 1
                            }
                        }
                    }) {
                        HStack(spacing: Spacing.sm) {
                            Text(currentPage == pages.count - 1 ? "Get Started" : "Continue")
                                .font(.system(size: 17, weight: .bold))

                            Image(systemName: currentPage == pages.count - 1 ? "sparkles" : "arrow.right")
                                .font(.system(size: 15, weight: .bold))
                        }
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, Spacing.lg)
                        .background(CipherTheme.accentGradient)
                        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.lg))
                        .shadow(color: CipherTheme.accent.opacity(0.3), radius: 12, y: 4)
                    }
                    .pressable()
                }
                .padding(.horizontal, Spacing.xxl)
                .padding(.bottom, Spacing.xxxl)
            }
        }
    }

    private func onboardingPage(_ page: OnboardingPage) -> some View {
        VStack(spacing: Spacing.xxxl) {
            Spacer()

            // Icon — first page gets the animated Cipher logo, others keep SF Symbols
            if page.icon == "lock.shield.fill" {
                CipherLogo(size: 100, animated: true)
                    .shadow(color: CipherTheme.accent.opacity(0.3), radius: 20, y: 8)
            } else {
                ZStack {
                    Circle()
                        .fill(Color(hex: page.iconColor).opacity(0.12))
                        .frame(width: 120, height: 120)

                    Circle()
                        .fill(Color(hex: page.iconColor).opacity(0.06))
                        .frame(width: 160, height: 160)

                    Image(systemName: page.icon)
                        .font(.system(size: 48, weight: .medium))
                        .foregroundStyle(
                            LinearGradient(
                                colors: [Color(hex: page.iconColor), Color(hex: page.iconColor).opacity(0.7)],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                }
            }

            // Text
            VStack(spacing: Spacing.lg) {
                Text(page.title)
                    .font(.system(size: 28, weight: .bold))
                    .foregroundColor(CipherTheme.textPrimary)

                Text(page.subtitle)
                    .font(.system(size: 16, weight: .regular))
                    .foregroundColor(CipherTheme.textSecondary)
                    .multilineTextAlignment(.center)
                    .lineSpacing(4)
                    .padding(.horizontal, Spacing.xl)

                Text(page.accentText)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(CipherTheme.accent)
                    .tracking(0.3)
            }

            Spacer()
            Spacer()
        }
    }

    private func complete() {
        HapticsService.shared.success()
        withAnimation(.easeInOut(duration: 0.4)) {
            isComplete = true
        }
    }
}

struct OnboardingPage {
    let icon: String
    let iconColor: String
    let title: String
    let subtitle: String
    let accentText: String
}

#Preview {
    OnboardingView(isComplete: .constant(false))
}

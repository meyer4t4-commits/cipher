import SwiftUI

// MARK: - Cipher Logo

struct CipherLogo: View {
    var size: CGFloat = 64
    var animated: Bool = false
    @State private var glowPhase = false

    var body: some View {
        ZStack {
            // Outer glow
            if animated {
                RoundedRectangle(cornerRadius: size * 0.22)
                    .fill(CipherTheme.accent.opacity(0.2))
                    .frame(width: size + 8, height: size + 8)
                    .blur(radius: glowPhase ? 12 : 6)
            }

            // Main shape
            RoundedRectangle(cornerRadius: size * 0.22)
                .fill(CipherTheme.accentGradient)
                .shadow(color: CipherTheme.accent.opacity(0.4), radius: 12, y: 4)

            // Inner pattern — subtle geometric
            ZStack {
                // The "C" letterform
                Text("C")
                    .font(.system(size: size * 0.52, weight: .bold, design: .rounded))
                    .foregroundStyle(.white)

                // Subtle orbit ring
                Circle()
                    .trim(from: 0.1, to: 0.4)
                    .stroke(Color.white.opacity(0.3), style: StrokeStyle(lineWidth: size * 0.025, lineCap: .round))
                    .frame(width: size * 0.7, height: size * 0.7)
                    .rotationEffect(.degrees(animated && glowPhase ? 360 : 0))
            }
        }
        .frame(width: size, height: size)
        .onAppear {
            if animated {
                withAnimation(.easeInOut(duration: 2.5).repeatForever(autoreverses: true)) {
                    glowPhase = true
                }
            }
        }
    }
}

// MARK: - Logo Text

struct LogoText: View {
    var showTagline: Bool = true
    var titleSize: CGFloat = 32

    var body: some View {
        VStack(spacing: 4) {
            Text(AppConstants.appName)
                .font(.system(size: titleSize, weight: .bold, design: .rounded))
                .foregroundStyle(CipherTheme.textPrimary)

            if showTagline {
                Text(AppConstants.tagline)
                    .font(.system(size: 14, weight: .medium, design: .default))
                    .foregroundColor(CipherTheme.textSecondary)
                    .tracking(1.5)
                    .textCase(.uppercase)
            }
        }
    }
}

// MARK: - Privacy Badge

struct PrivacyBadge: View {
    var compact: Bool = false

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: "lock.shield.fill")
                .font(.system(size: compact ? 10 : 12, weight: .semibold))
                .foregroundColor(CipherTheme.success)

            if !compact {
                Text("Sovereign")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundColor(CipherTheme.success)
                    .tracking(0.5)
            }
        }
        .padding(.horizontal, compact ? 6 : 10)
        .padding(.vertical, compact ? 3 : 5)
        .background(
            Capsule()
                .fill(CipherTheme.success.opacity(0.12))
                .overlay(
                    Capsule()
                        .stroke(CipherTheme.success.opacity(0.2), lineWidth: 0.5)
                )
        )
    }
}

// MARK: - Connection Status Indicator

struct ConnectionIndicator: View {
    let isConnected: Bool
    var showLabel: Bool = true
    @State private var pulse = false

    var body: some View {
        HStack(spacing: 6) {
            ZStack {
                if isConnected && pulse {
                    Circle()
                        .fill(CipherTheme.success.opacity(0.3))
                        .frame(width: 10, height: 10)
                }

                Circle()
                    .fill(isConnected ? CipherTheme.success : CipherTheme.error)
                    .frame(width: 6, height: 6)
            }
            .frame(width: 10, height: 10)

            if showLabel {
                Text(isConnected ? "Connected" : "Offline")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundColor(CipherTheme.textTertiary)
            }
        }
        .onAppear {
            if isConnected {
                withAnimation(.easeInOut(duration: 1.5).repeatForever(autoreverses: true)) {
                    pulse = true
                }
            }
        }
    }
}

#Preview {
    ZStack {
        CipherTheme.background.ignoresSafeArea()

        VStack(spacing: 30) {
            CipherLogo(size: 80, animated: true)
            LogoText()
            PrivacyBadge()
            ConnectionIndicator(isConnected: true)
            ConnectionIndicator(isConnected: false)
        }
    }
}

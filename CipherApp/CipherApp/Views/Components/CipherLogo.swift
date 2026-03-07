import SwiftUI

// MARK: - Cipher Logo (Geometric Shield)

struct CipherLogo: View {
    var size: CGFloat = 64
    var animated: Bool = false
    @State private var glowPhase = false
    @State private var rotationAngle: Double = 0

    var body: some View {
        ZStack {
            // Outer glow
            if animated {
                Circle()
                    .fill(CipherTheme.accent.opacity(0.15))
                    .frame(width: size + 12, height: size + 12)
                    .blur(radius: glowPhase ? 14 : 8)
            }

            // Main shape — rounded square
            RoundedRectangle(cornerRadius: size * 0.22)
                .fill(CipherTheme.accentGradient)
                .shadow(color: CipherTheme.accent.opacity(0.4), radius: 12, y: 4)

            // Inner design — geometric cipher mark
            ZStack {
                // Outer orbit ring
                Circle()
                    .trim(from: 0.0, to: 0.35)
                    .stroke(
                        Color.white.opacity(0.5),
                        style: StrokeStyle(lineWidth: size * 0.03, lineCap: .round)
                    )
                    .frame(width: size * 0.72, height: size * 0.72)
                    .rotationEffect(.degrees(animated ? rotationAngle : 0))

                // Second orbit ring (opposite direction)
                Circle()
                    .trim(from: 0.5, to: 0.8)
                    .stroke(
                        Color.white.opacity(0.3),
                        style: StrokeStyle(lineWidth: size * 0.025, lineCap: .round)
                    )
                    .frame(width: size * 0.58, height: size * 0.58)
                    .rotationEffect(.degrees(animated ? -rotationAngle * 0.7 : 0))

                // Central shield shape
                CipherShieldShape()
                    .fill(Color.white)
                    .frame(width: size * 0.38, height: size * 0.44)

                // Inner dot — the "eye"
                Circle()
                    .fill(CipherTheme.accent)
                    .frame(width: size * 0.09, height: size * 0.09)
                    .offset(y: -size * 0.02)
            }
        }
        .frame(width: size, height: size)
        .onAppear {
            if animated {
                withAnimation(.easeInOut(duration: 2.5).repeatForever(autoreverses: true)) {
                    glowPhase = true
                }
                withAnimation(.linear(duration: 8).repeatForever(autoreverses: false)) {
                    rotationAngle = 360
                }
            }
        }
    }
}

// MARK: - Shield Shape

struct CipherShieldShape: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        let w = rect.width
        let h = rect.height
        let cx = rect.midX

        path.move(to: CGPoint(x: cx, y: 0))
        path.addCurve(
            to: CGPoint(x: w, y: h * 0.25),
            control1: CGPoint(x: w * 0.65, y: 0),
            control2: CGPoint(x: w, y: h * 0.1)
        )
        path.addCurve(
            to: CGPoint(x: cx, y: h),
            control1: CGPoint(x: w, y: h * 0.55),
            control2: CGPoint(x: cx, y: h * 0.85)
        )
        path.addCurve(
            to: CGPoint(x: 0, y: h * 0.25),
            control1: CGPoint(x: 0, y: h * 0.85),
            control2: CGPoint(x: 0, y: h * 0.55)
        )
        path.addCurve(
            to: CGPoint(x: cx, y: 0),
            control1: CGPoint(x: 0, y: h * 0.1),
            control2: CGPoint(x: w * 0.35, y: 0)
        )
        path.closeSubpath()
        return path
    }
}

// MARK: - Spinning Cipher Logo (Cowork-style)

struct SpinningCipherLogo: View {
    var size: CGFloat = 32
    var spinning: Bool = true
    @State private var rotation: Double = 0
    @State private var pulse: Bool = false

    var body: some View {
        ZStack {
            // Pulse ring
            if spinning {
                Circle()
                    .stroke(CipherTheme.accent.opacity(pulse ? 0.0 : 0.3), lineWidth: 1.5)
                    .frame(width: size + 8, height: size + 8)
                    .scaleEffect(pulse ? 1.4 : 1.0)
            }

            // Background circle
            Circle()
                .fill(CipherTheme.accentGradient)
                .frame(width: size, height: size)
                .shadow(color: CipherTheme.accent.opacity(0.3), radius: 6, y: 2)

            // Spinning orbit arcs
            ZStack {
                Circle()
                    .trim(from: 0, to: 0.3)
                    .stroke(Color.white.opacity(0.6), style: StrokeStyle(lineWidth: size * 0.04, lineCap: .round))
                    .frame(width: size * 0.75, height: size * 0.75)
                    .rotationEffect(.degrees(rotation))

                Circle()
                    .trim(from: 0.5, to: 0.75)
                    .stroke(Color.white.opacity(0.35), style: StrokeStyle(lineWidth: size * 0.035, lineCap: .round))
                    .frame(width: size * 0.55, height: size * 0.55)
                    .rotationEffect(.degrees(-rotation * 0.6))
            }

            // Central shield
            CipherShieldShape()
                .fill(Color.white)
                .frame(width: size * 0.3, height: size * 0.36)

            // Inner eye
            Circle()
                .fill(CipherTheme.accent)
                .frame(width: size * 0.07, height: size * 0.07)
                .offset(y: -size * 0.015)
        }
        .frame(width: size + 10, height: size + 10)
        .onAppear {
            startAnimations()
        }
        .onChange(of: spinning) { _, newValue in
            if newValue {
                startAnimations()
            }
        }
    }

    private func startAnimations() {
        guard spinning else { return }
        withAnimation(.linear(duration: 3).repeatForever(autoreverses: false)) {
            rotation = 360
        }
        withAnimation(.easeInOut(duration: 1.8).repeatForever(autoreverses: true)) {
            pulse = true
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
            SpinningCipherLogo(size: 40, spinning: true)
            LogoText()
            PrivacyBadge()
            ConnectionIndicator(isConnected: true)
            ConnectionIndicator(isConnected: false)
        }
    }
}

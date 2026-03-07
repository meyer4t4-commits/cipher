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

// MARK: - Spinning Cipher Logo (Premium Orrery Animation)

struct SpinningCipherLogo: View {
    var size: CGFloat = 32
    var spinning: Bool = true

    // Outer rings (fast, medium, slow rotations)
    @State private var outerRingRotation: Double = 0
    @State private var middleRingRotation: Double = 0
    @State private var innerRingRotation: Double = 0

    // Glow and breathing effects
    @State private var glowPhase: Double = 0
    @State private var breatheScale: CGFloat = 1.0
    @State private var glowOpacity: Double = 0.4

    // Subtle opacity breathing for intelligence effect
    @State private var centerOpacity: Double = 1.0

    var body: some View {
        ZStack {
            // Multi-layer ambient glow (breathing bloom effect)
            if spinning {
                // Outer bloom layer
                Circle()
                    .fill(CipherTheme.accent.opacity(0.08))
                    .frame(width: size + 20, height: size + 20)
                    .blur(radius: 12)
                    .scaleEffect(breatheScale + 0.15)
                    .opacity(glowOpacity * 0.6)

                // Middle bloom layer
                Circle()
                    .fill(CipherTheme.accent.opacity(0.12))
                    .frame(width: size + 14, height: size + 14)
                    .blur(radius: 8)
                    .scaleEffect(breatheScale + 0.08)
                    .opacity(glowOpacity * 0.8)
            }

            // Central background circle (subtle gradient)
            Circle()
                .fill(
                    RadialGradient(
                        gradient: Gradient(colors: [
                            CipherTheme.accent.opacity(0.2),
                            CipherTheme.accent.opacity(0.05)
                        ]),
                        center: .center,
                        startRadius: 0,
                        endRadius: size * 0.6
                    )
                )
                .frame(width: size + 4, height: size + 4)
                .shadow(color: CipherTheme.accent.opacity(0.25), radius: 8, x: 0, y: 2)

            // Premium multi-ring orrery effect
            ZStack {
                // OUTER RING - Fastest rotation (full orbit every 2.2s)
                Circle()
                    .trim(from: 0, to: 0.25)
                    .stroke(
                        LinearGradient(
                            gradient: Gradient(colors: [
                                Color.white.opacity(0.7),
                                Color.white.opacity(0.3)
                            ]),
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        ),
                        style: StrokeStyle(lineWidth: size * 0.032, lineCap: .round)
                    )
                    .frame(width: size * 0.8, height: size * 0.8)
                    .rotationEffect(.degrees(outerRingRotation))
                    .opacity(0.85)

                // MIDDLE RING - Medium rotation, opposite direction (full orbit every 3.5s)
                Circle()
                    .trim(from: 0.35, to: 0.65)
                    .stroke(
                        LinearGradient(
                            gradient: Gradient(colors: [
                                Color.white.opacity(0.5),
                                Color.white.opacity(0.2)
                            ]),
                            startPoint: .bottomLeading,
                            endPoint: .topTrailing
                        ),
                        style: StrokeStyle(lineWidth: size * 0.028, lineCap: .round)
                    )
                    .frame(width: size * 0.62, height: size * 0.62)
                    .rotationEffect(.degrees(-middleRingRotation * 0.75))
                    .opacity(0.7)

                // INNER RING - Slow rotation, same direction as outer (full orbit every 4.8s)
                Circle()
                    .trim(from: 0.1, to: 0.35)
                    .stroke(
                        LinearGradient(
                            gradient: Gradient(colors: [
                                Color.white.opacity(0.4),
                                Color.white.opacity(0.15)
                            ]),
                            startPoint: .topTrailing,
                            endPoint: .bottomLeading
                        ),
                        style: StrokeStyle(lineWidth: size * 0.024, lineCap: .round)
                    )
                    .frame(width: size * 0.45, height: size * 0.45)
                    .rotationEffect(.degrees(innerRingRotation * 0.55))
                    .opacity(0.6)
            }
            .scaleEffect(breatheScale)

            // Central shield (stable, breathing slightly)
            CipherShieldShape()
                .fill(
                    LinearGradient(
                        gradient: Gradient(colors: [
                            Color.white,
                            Color.white.opacity(0.95)
                        ]),
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .frame(width: size * 0.32, height: size * 0.38)
                .scaleEffect(breatheScale * 0.98 + 0.02)
                .opacity(centerOpacity)

            // Inner eye - glowing indicator (pulsing intelligence)
            ZStack {
                // Subtle glow around the eye
                Circle()
                    .fill(CipherTheme.accent.opacity(glowOpacity * 0.5))
                    .frame(width: size * 0.12, height: size * 0.12)
                    .blur(radius: 2)

                // Main eye
                Circle()
                    .fill(CipherTheme.accent)
                    .frame(width: size * 0.075, height: size * 0.075)
            }
            .offset(y: -size * 0.02)
            .opacity(centerOpacity)
        }
        .frame(width: size + 12, height: size + 12)
        .onAppear {
            startPremiumAnimations()
        }
        .onChange(of: spinning) { _, newValue in
            if newValue {
                startPremiumAnimations()
            }
        }
    }

    private func startPremiumAnimations() {
        guard spinning else { return }

        // Outer ring - smooth, fast rotation (2.2s full rotation)
        withAnimation(.linear(duration: 2.2).repeatForever(autoreverses: false)) {
            outerRingRotation = 360
        }

        // Middle ring - medium speed, opposite direction (3.5s full rotation)
        withAnimation(.linear(duration: 3.5).repeatForever(autoreverses: false)) {
            middleRingRotation = 360
        }

        // Inner ring - slow, subtle rotation (4.8s full rotation)
        withAnimation(.linear(duration: 4.8).repeatForever(autoreverses: false)) {
            innerRingRotation = 360
        }

        // Breathing scale effect - subtle expansion/contraction
        withAnimation(.easeInOut(duration: 2.0).repeatForever(autoreverses: true)) {
            breatheScale = 1.05
        }

        // Pulsing glow intensity - creates living AI sensation
        withAnimation(.easeInOut(duration: 1.6).repeatForever(autoreverses: true)) {
            glowOpacity = 0.7
        }

        // Subtle opacity breathing on center (feeling of thinking)
        withAnimation(.easeInOut(duration: 2.4).repeatForever(autoreverses: true)) {
            centerOpacity = 0.92
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

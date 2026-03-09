import SwiftUI
import Foundation

// MARK: - Shared Palette

private enum AlienPalette {
    static let violet = Color(hex: "7C3AED")
    static let cyan = Color(hex: "06B6D4")
    static let lavender = Color(hex: "A78BFA")
    static let brightCyan = Color(hex: "22D3EE")
    static let deepViolet = Color(hex: "4C1D95")
    static let electricBlue = Color(hex: "3B82F6")
}

// MARK: - Cipher Logo (Static/Ambient — for empty states, branding)

struct CipherLogo: View {
    var size: CGFloat = 64
    var animated: Bool = false
    @State private var phase: Double = 0
    @State private var breathe: CGFloat = 1.0
    @State private var glowPulse: Double = 0.4

    var body: some View {
        ZStack {
            if animated { ambientGlow }

            // Outer sacred geometry ring — rotates CLOCKWISE
            SacredRing(size: size, phase: phase, animated: animated, direction: 1.0)
                .scaleEffect(breathe)

            // Inner tessellation — rotates COUNTER-CLOCKWISE
            if size > 30 {
                TessellationWeb(size: size * 0.65, phase: phase, animated: animated, direction: -1.0)
                    .scaleEffect(breathe)
            }

            // Central diamond
            DiamondCore(size: size, phase: phase, animated: animated)
        }
        .frame(width: size, height: size)
        .onAppear {
            guard animated else { return }
            withAnimation(.easeInOut(duration: 3.0).repeatForever(autoreverses: true)) {
                breathe = 1.04
            }
            withAnimation(.easeInOut(duration: 2.0).repeatForever(autoreverses: true)) {
                glowPulse = 0.8
            }
            withAnimation(.linear(duration: 10).repeatForever(autoreverses: false)) {
                phase = .pi * 2
            }
        }
    }

    private var ambientGlow: some View {
        ZStack {
            Circle()
                .fill(
                    RadialGradient(
                        colors: [
                            AlienPalette.violet.opacity(glowPulse * 0.2),
                            AlienPalette.lavender.opacity(glowPulse * 0.08),
                            Color.clear
                        ],
                        center: .center,
                        startRadius: 0,
                        endRadius: size * 0.6
                    )
                )
                .frame(width: size * 1.4, height: size * 1.4)
                .blur(radius: size * 0.12)

            Circle()
                .fill(
                    RadialGradient(
                        colors: [
                            AlienPalette.brightCyan.opacity(glowPulse * 0.1),
                            Color.clear
                        ],
                        center: .center,
                        startRadius: 0,
                        endRadius: size * 0.3
                    )
                )
                .frame(width: size, height: size)
                .blur(radius: size * 0.08)
        }
    }
}

// MARK: - Spinning Cipher Logo (Thinking/Active State)
// The star of the show — COUNTER-ROTATING rings with orbital particles

struct SpinningCipherLogo: View {
    var size: CGFloat = 32
    var spinning: Bool = true

    @State private var phase: Double = 0
    @State private var breathe: CGFloat = 1.0
    @State private var glowIntensity: Double = 0.5
    @State private var orbitalAngle: Double = 0

    var body: some View {
        ZStack {
            // Orbital particles when spinning
            if spinning {
                OrbitalDots(size: size, angle: orbitalAngle, intensity: glowIntensity)
            }

            // Ambient glow
            if spinning {
                Circle()
                    .fill(
                        RadialGradient(
                            colors: [
                                AlienPalette.violet.opacity(glowIntensity * 0.2),
                                AlienPalette.brightCyan.opacity(glowIntensity * 0.05),
                                Color.clear
                            ],
                            center: .center,
                            startRadius: 0,
                            endRadius: size * 0.55
                        )
                    )
                    .frame(width: size * 1.3, height: size * 1.3)
                    .blur(radius: size * 0.1)
            }

            // Outer ring — spins CLOCKWISE
            SacredRing(size: size, phase: phase, animated: spinning, direction: 1.0)
                .scaleEffect(breathe)

            // Inner tessellation — spins COUNTER-CLOCKWISE
            if size > 20 {
                TessellationWeb(size: size * 0.6, phase: phase, animated: spinning, direction: -1.0)
                    .scaleEffect(breathe)
            }

            // Diamond core
            DiamondCore(size: size, phase: phase, animated: spinning)
        }
        .frame(width: size + 8, height: size + 8)
        .onAppear { startAnimations() }
        .onChange(of: spinning) { _, newValue in
            if newValue { startAnimations() }
        }
    }

    private func startAnimations() {
        guard spinning else { return }
        withAnimation(.linear(duration: 4).repeatForever(autoreverses: false)) {
            phase = .pi * 2
        }
        withAnimation(.easeInOut(duration: 2.0).repeatForever(autoreverses: true)) {
            breathe = 1.06
        }
        withAnimation(.easeInOut(duration: 1.4).repeatForever(autoreverses: true)) {
            glowIntensity = 0.9
        }
        withAnimation(.linear(duration: 2.5).repeatForever(autoreverses: false)) {
            orbitalAngle = 360
        }
    }
}

// MARK: - Sacred Geometry Ring (replaces the old square/hexagonal web)
// A complex multi-layered ring that looks nothing like a square.
// Inspired by sacred geometry, orbital mechanics, and sci-fi HUDs.

private struct SacredRing: View {
    let size: CGFloat
    let phase: Double
    let animated: Bool
    let direction: Double  // 1.0 = clockwise, -1.0 = counter-clockwise

    var body: some View {
        Canvas { context, canvasSize in
            let cx = canvasSize.width / 2
            let cy = canvasSize.height / 2
            let center = CGPoint(x: cx, y: cy)
            let t = animated ? phase * direction : 0
            let radius = min(canvasSize.width, canvasSize.height) * 0.42

            // Layer 1: Outer broken ring — segmented arc with gaps
            drawSegmentedRing(context: context, center: center, radius: radius, t: t, segments: 8, gapRatio: 0.15, alpha: 0.35, lineWidth: max(1.0, size * 0.014))

            // Layer 2: Mid ring — continuous but thinner, rotating opposite
            drawSegmentedRing(context: context, center: center, radius: radius * 0.82, t: -t * 0.7, segments: 6, gapRatio: 0.25, alpha: 0.2, lineWidth: max(0.5, size * 0.008))

            // Layer 3: Vertex nodes — pulsing dots at ring intersections
            drawRingNodes(context: context, center: center, radius: radius, t: t)

            // Layer 4: Arc connectors — small curved lines bridging the rings
            drawArcConnectors(context: context, center: center, innerR: radius * 0.82, outerR: radius, t: t)
        }
        .frame(width: size, height: size)
        .allowsHitTesting(false)
    }

    private func drawSegmentedRing(context: GraphicsContext, center: CGPoint, radius: Double, t: Double, segments: Int, gapRatio: Double, alpha: Double, lineWidth: CGFloat) {
        let segmentAngle = (.pi * 2) / Double(segments)
        let gapAngle = segmentAngle * gapRatio

        for i in 0..<segments {
            let startAngle = Double(i) * segmentAngle + t * 0.2
            let endAngle = startAngle + segmentAngle - gapAngle

            // Each segment warps slightly based on phase
            let warp = Foundation.sin(t * 1.8 + Double(i) * 2.1) * size * 0.004
            let r = radius + warp

            var path = Path()
            path.addArc(center: center, radius: r, startAngle: .radians(startAngle), endAngle: .radians(endAngle), clockwise: false)

            // Gradient alpha based on segment index for visual depth
            let segAlpha = alpha * (0.7 + 0.3 * Foundation.sin(t * 2.0 + Double(i) * 1.5))
            context.stroke(path, with: .color(Color.white.opacity(segAlpha)), lineWidth: lineWidth)

            // Glow on every other segment
            if i % 2 == 0 {
                context.stroke(path, with: .color(AlienPalette.brightCyan.opacity(segAlpha * 0.3)), style: StrokeStyle(lineWidth: lineWidth * 2.5))
            }
        }
    }

    private func drawRingNodes(context: GraphicsContext, center: CGPoint, radius: Double, t: Double) {
        let nodeCount = 8
        let dotR = max(1.2, size * 0.015)

        for i in 0..<nodeCount {
            let angle = (Double(i) / Double(nodeCount)) * .pi * 2 + t * 0.2
            let r = radius

            let px = center.x + Foundation.cos(angle) * r
            let py = center.y + Foundation.sin(angle) * r

            // Pulsing brightness
            let pulse = (Foundation.sin(t * 3.0 + Double(i) * 1.8) + 1.0) * 0.5
            let brightness = 0.3 + pulse * 0.6

            // Node dot
            let rect = CGRect(x: px - dotR, y: py - dotR, width: dotR * 2, height: dotR * 2)
            context.fill(Path(ellipseIn: rect), with: .color(Color.white.opacity(brightness)))

            // Glow halo
            let glowR = dotR * 2.5
            let glowRect = CGRect(x: px - glowR, y: py - glowR, width: glowR * 2, height: glowR * 2)
            context.fill(Path(ellipseIn: glowRect), with: .color(AlienPalette.lavender.opacity(brightness * 0.15)))
        }
    }

    private func drawArcConnectors(context: GraphicsContext, center: CGPoint, innerR: Double, outerR: Double, t: Double) {
        let count = 6
        for i in 0..<count {
            let angle = (Double(i) / Double(count)) * .pi * 2 + t * 0.15
            let nextAngle = angle + 0.12  // Small arc span

            // Inner to outer connector — a small radial line with slight curve
            var path = Path()
            let innerPt = CGPoint(
                x: center.x + Foundation.cos(angle) * innerR,
                y: center.y + Foundation.sin(angle) * innerR
            )
            let outerPt = CGPoint(
                x: center.x + Foundation.cos(nextAngle) * outerR,
                y: center.y + Foundation.sin(nextAngle) * outerR
            )
            // Curved connector using midpoint control
            let midAngle = (angle + nextAngle) / 2
            let midR = (innerR + outerR) / 2 + size * 0.02
            let controlPt = CGPoint(
                x: center.x + Foundation.cos(midAngle) * midR,
                y: center.y + Foundation.sin(midAngle) * midR
            )

            path.move(to: innerPt)
            path.addQuadCurve(to: outerPt, control: controlPt)

            let alpha = 0.12 + Foundation.sin(t * 2 + Double(i) * 1.5) * 0.06
            context.stroke(path, with: .color(Color.white.opacity(alpha)), lineWidth: max(0.4, size * 0.004))
        }
    }
}

// MARK: - Tessellation Web (inner structure — counter-rotates)

private struct TessellationWeb: View {
    let size: CGFloat
    let phase: Double
    let animated: Bool
    let direction: Double

    var body: some View {
        Canvas { context, canvasSize in
            let cx = canvasSize.width / 2
            let cy = canvasSize.height / 2
            let center = CGPoint(x: cx, y: cy)
            let t = animated ? phase * direction : 0
            let radius = min(canvasSize.width, canvasSize.height) * 0.4

            // Inner triangle with warping
            drawWeb(context: context, center: center, radius: radius, t: t, sides: 3, alpha: 0.2)

            // Connecting spokes
            drawSpokes(context: context, center: center, radius: radius, t: t)
        }
        .frame(width: size, height: size)
        .allowsHitTesting(false)
    }

    private func drawWeb(context: GraphicsContext, center: CGPoint, radius: Double, t: Double, sides: Int, alpha: Double) {
        var path = Path()
        var vertices: [CGPoint] = []

        for i in 0..<sides {
            let angle = (Double(i) / Double(sides)) * .pi * 2 + t * 0.2
            let warp = Foundation.sin(t * 1.5 + Double(i) * 1.3) * size * 0.008
            let r = radius + warp
            let pt = CGPoint(x: center.x + Foundation.cos(angle) * r, y: center.y + Foundation.sin(angle) * r)
            vertices.append(pt)
            if i == 0 { path.move(to: pt) } else { path.addLine(to: pt) }
        }
        path.closeSubpath()

        context.stroke(path, with: .color(Color.white.opacity(alpha)), lineWidth: max(0.5, size * 0.01))

        // Vertex dots
        let dotR = max(1.0, size * 0.015)
        for (i, v) in vertices.enumerated() {
            let brightness = (Foundation.sin(t * 2.5 + Double(i) * 1.8) + 1.0) * 0.5
            let rect = CGRect(x: v.x - dotR, y: v.y - dotR, width: dotR * 2, height: dotR * 2)
            context.fill(Path(ellipseIn: rect), with: .color(Color.white.opacity(0.3 + brightness * 0.4)))
        }
    }

    private func drawSpokes(context: GraphicsContext, center: CGPoint, radius: Double, t: Double) {
        let spokeCount = 3
        for i in 0..<spokeCount {
            let angle = (Double(i) / Double(spokeCount)) * .pi * 2 + t * 0.2
            let innerR = size * 0.08
            let outerR = radius * 0.9
            var line = Path()
            line.move(to: CGPoint(x: center.x + Foundation.cos(angle) * innerR, y: center.y + Foundation.sin(angle) * innerR))
            line.addLine(to: CGPoint(x: center.x + Foundation.cos(angle) * outerR, y: center.y + Foundation.sin(angle) * outerR))
            context.stroke(line, with: .color(Color.white.opacity(0.12)), lineWidth: max(0.4, size * 0.005))
        }
    }
}

// MARK: - Orbital Dots (particles orbit the core)

private struct OrbitalDots: View {
    let size: CGFloat
    let angle: Double
    let intensity: Double

    var body: some View {
        Canvas { context, canvasSize in
            let cx = canvasSize.width / 2
            let cy = canvasSize.height / 2
            let orbitR = Double(size) * 0.44
            let dotCount = 4
            let dotSize = max(1.5, Double(size) * 0.035)

            for i in 0..<dotCount {
                let baseAngle = (Double(i) / Double(dotCount)) * .pi * 2
                let a = baseAngle + angle * .pi / 180.0
                let px = cx + Foundation.cos(a) * orbitR
                let py = cy + Foundation.sin(a) * orbitR

                // Trail — 3 fading dots behind
                for trailIdx in 1...3 {
                    let trailA = a - Double(trailIdx) * 0.15
                    let trailX = cx + Foundation.cos(trailA) * orbitR
                    let trailY = cy + Foundation.sin(trailA) * orbitR
                    let trailSize = dotSize * (1.0 - Double(trailIdx) * 0.2)
                    let trailRect = CGRect(x: trailX - trailSize * 0.5, y: trailY - trailSize * 0.5, width: trailSize, height: trailSize)
                    context.fill(Path(ellipseIn: trailRect), with: .color(Color.white.opacity(intensity * 0.08 / Double(trailIdx))))
                }

                // Main dot
                let rect = CGRect(x: px - dotSize, y: py - dotSize, width: dotSize * 2, height: dotSize * 2)
                context.fill(Path(ellipseIn: rect), with: .color(Color.white.opacity(intensity * 0.55)))

                // Glow
                let glowRect = CGRect(x: px - dotSize * 2, y: py - dotSize * 2, width: dotSize * 4, height: dotSize * 4)
                context.fill(Path(ellipseIn: glowRect), with: .color(AlienPalette.brightCyan.opacity(intensity * 0.06)))
            }
        }
        .frame(width: size + 8, height: size + 8)
        .allowsHitTesting(false)
    }
}

// MARK: - Diamond Core

private struct DiamondCore: View {
    let size: CGFloat
    let phase: Double
    let animated: Bool

    private var coreSize: CGFloat { size * 0.2 }
    private var rotDeg: Double { animated ? phase * 180.0 / .pi * 0.15 : 0 }
    private var angularStart: Double { animated ? phase * 180.0 / .pi : 0 }

    var body: some View {
        ZStack {
            // Soft haze
            Diamond()
                .fill(
                    RadialGradient(
                        colors: [
                            Color.white.opacity(0.1),
                            AlienPalette.lavender.opacity(0.06),
                            Color.clear
                        ],
                        center: .center,
                        startRadius: 0,
                        endRadius: coreSize * 2
                    )
                )
                .frame(width: coreSize * 3, height: coreSize * 3)
                .blur(radius: 5)

            // Diamond body
            Diamond()
                .fill(
                    AngularGradient(
                        colors: [
                            Color.white,
                            AlienPalette.lavender,
                            AlienPalette.violet,
                            AlienPalette.cyan,
                            AlienPalette.brightCyan,
                            AlienPalette.lavender,
                            Color.white
                        ],
                        center: .center,
                        startAngle: .degrees(angularStart),
                        endAngle: .degrees(angularStart + 360)
                    )
                )
                .frame(width: coreSize, height: coreSize * 1.3)
                .overlay(
                    Diamond()
                        .fill(
                            LinearGradient(
                                colors: [Color.white.opacity(0.6), Color.white.opacity(0.05), Color.clear],
                                startPoint: .top,
                                endPoint: .center
                            )
                        )
                        .frame(width: coreSize, height: coreSize * 1.3)
                )
                .shadow(color: Color.white.opacity(0.3), radius: 3)
                .shadow(color: AlienPalette.violet.opacity(0.4), radius: 6)
                .shadow(color: AlienPalette.cyan.opacity(0.2), radius: 10)

            // Hot center dot
            Circle()
                .fill(Color.white)
                .frame(width: size * 0.025, height: size * 0.025)
                .shadow(color: Color.white.opacity(0.8), radius: 3)
        }
        .rotationEffect(.degrees(rotDeg))
    }
}

// MARK: - Diamond Shape

private struct Diamond: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        let cx = rect.midX
        let cy = rect.midY
        path.move(to: CGPoint(x: cx, y: rect.minY))
        path.addLine(to: CGPoint(x: rect.maxX, y: cy * 0.85))
        path.addLine(to: CGPoint(x: cx, y: rect.maxY))
        path.addLine(to: CGPoint(x: rect.minX, y: cy * 0.85))
        path.closeSubpath()
        return path
    }
}

// MARK: - Legacy Shield Shape (backward compat)

struct CipherShieldShape: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        let w = rect.width
        let h = rect.height
        let cx = rect.midX
        path.move(to: CGPoint(x: cx, y: 0))
        path.addCurve(to: CGPoint(x: w, y: h * 0.25), control1: CGPoint(x: w * 0.65, y: 0), control2: CGPoint(x: w, y: h * 0.1))
        path.addCurve(to: CGPoint(x: cx, y: h), control1: CGPoint(x: w, y: h * 0.55), control2: CGPoint(x: cx, y: h * 0.85))
        path.addCurve(to: CGPoint(x: 0, y: h * 0.25), control1: CGPoint(x: 0, y: h * 0.85), control2: CGPoint(x: 0, y: h * 0.55))
        path.addCurve(to: CGPoint(x: cx, y: 0), control1: CGPoint(x: 0, y: h * 0.1), control2: CGPoint(x: w * 0.35, y: 0))
        path.closeSubpath()
        return path
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
                        .frame(width: 8, height: 8)
                }
                Circle()
                    .fill(isConnected ? CipherTheme.success : CipherTheme.error)
                    .frame(width: 5, height: 5)
            }
            .frame(width: 8, height: 8)
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
            CipherLogo(size: 100, animated: true)
            SpinningCipherLogo(size: 48, spinning: true)
            SpinningCipherLogo(size: 28, spinning: true)
            LogoText()
            PrivacyBadge()
            ConnectionIndicator(isConnected: true)
        }
    }
}

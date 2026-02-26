import SwiftUI

// MARK: - Loading View

struct LoadingView: View {
    @State private var isAnimating = false

    var body: some View {
        VStack(spacing: 16) {
            ZStack {
                Circle()
                    .stroke(CipherTheme.surface, lineWidth: 2)
                    .frame(width: 40, height: 40)

                Circle()
                    .trim(from: 0, to: 0.7)
                    .stroke(CipherTheme.accent, style: StrokeStyle(lineWidth: 2, lineCap: .round))
                    .frame(width: 40, height: 40)
                    .rotationEffect(.degrees(isAnimating ? 360 : 0))
            }

            Text("Processing...")
                .font(.system(size: 14, weight: .medium))
                .foregroundColor(CipherTheme.textSecondary)
        }
        .onAppear {
            withAnimation(.linear(duration: 1.5).repeatForever(autoreverses: false)) {
                isAnimating = true
            }
        }
    }
}

// MARK: - Typing Indicator (Premium)

struct TypingIndicator: View {
    @State private var dotScales: [CGFloat] = [0.5, 0.5, 0.5]
    @State private var dotOpacities: [Double] = [0.3, 0.3, 0.3]

    var body: some View {
        HStack(spacing: Spacing.md) {
            // Cipher avatar mini
            ZStack {
                Circle()
                    .fill(CipherTheme.accentGradient)
                    .frame(width: 28, height: 28)

                Text("C")
                    .font(.system(size: 14, weight: .bold, design: .rounded))
                    .foregroundColor(.white)
            }

            // Animated dots
            HStack(spacing: 5) {
                ForEach(0..<3, id: \.self) { index in
                    Circle()
                        .fill(CipherTheme.accent)
                        .frame(width: 7, height: 7)
                        .scaleEffect(dotScales[index])
                        .opacity(dotOpacities[index])
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(
                Capsule()
                    .fill(CipherTheme.surfaceElevated)
                    .overlay(
                        Capsule()
                            .stroke(CipherTheme.border, lineWidth: 0.5)
                    )
            )

            Spacer()
        }
        .padding(.horizontal, Spacing.lg)
        .padding(.vertical, Spacing.sm)
        .onAppear {
            animateDots()
        }
    }

    private func animateDots() {
        for i in 0..<3 {
            withAnimation(
                .easeInOut(duration: 0.5)
                .repeatForever(autoreverses: true)
                .delay(Double(i) * 0.15)
            ) {
                dotScales[i] = 1.0
                dotOpacities[i] = 1.0
            }
        }
    }
}

// MARK: - Streaming Indicator

struct StreamingIndicator: View {
    @State private var cursorVisible = true

    var body: some View {
        Rectangle()
            .fill(CipherTheme.accent)
            .frame(width: 2, height: 18)
            .opacity(cursorVisible ? 1 : 0)
            .onAppear {
                withAnimation(.easeInOut(duration: 0.5).repeatForever(autoreverses: true)) {
                    cursorVisible = false
                }
            }
    }
}

// MARK: - Pulse Ring

struct PulseRing: View {
    let color: Color
    @State private var scale: CGFloat = 0.8
    @State private var opacity: Double = 0.8

    var body: some View {
        Circle()
            .stroke(color, lineWidth: 2)
            .scaleEffect(scale)
            .opacity(opacity)
            .onAppear {
                withAnimation(.easeOut(duration: 1.5).repeatForever(autoreverses: false)) {
                    scale = 1.5
                    opacity = 0
                }
            }
    }
}

#Preview {
    ZStack {
        CipherTheme.background.ignoresSafeArea()

        VStack(spacing: 40) {
            LoadingView()
            TypingIndicator()
            StreamingIndicator()
        }
    }
}

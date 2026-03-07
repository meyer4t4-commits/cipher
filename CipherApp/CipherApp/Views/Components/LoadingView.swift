import SwiftUI

// MARK: - Loading View

struct LoadingView: View {
    @State private var isAnimating = false

    var body: some View {
        VStack(spacing: 16) {
            SpinningCipherLogo(size: 40, spinning: true)

            Text("Processing...")
                .font(.system(size: 14, weight: .medium))
                .foregroundColor(CipherTheme.textSecondary)
        }
    }
}

// MARK: - Typing Indicator (with Thinking Status)

struct TypingIndicator: View {
    @State private var dotScales: [CGFloat] = [0.5, 0.5, 0.5]
    @State private var dotOpacities: [Double] = [0.3, 0.3, 0.3]
    @State private var thinkingPhase = 0
    @State private var showStatus = false

    private let thinkingStatuses = [
        "Analyzing your request...",
        "Routing to best model...",
        "Evaluating context...",
        "Composing response...",
        "Thinking deeply...",
        "Processing with agents...",
        "Synthesizing information...",
    ]

    var body: some View {
        HStack(spacing: Spacing.md) {
            // Cipher spinning avatar
            SpinningCipherLogo(size: 28, spinning: true)

            // Thinking bubble with status
            VStack(alignment: .leading, spacing: 4) {
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

                // Thinking status text
                if showStatus {
                    Text(thinkingStatuses[thinkingPhase % thinkingStatuses.count])
                        .font(.system(size: 11, weight: .medium))
                        .foregroundColor(CipherTheme.textTertiary)
                        .transition(.opacity.combined(with: .move(edge: .bottom)))
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(
                RoundedRectangle(cornerRadius: CornerRadius.lg)
                    .fill(CipherTheme.surfaceElevated)
                    .overlay(
                        RoundedRectangle(cornerRadius: CornerRadius.lg)
                            .stroke(CipherTheme.border, lineWidth: 0.5)
                    )
            )

            Spacer()
        }
        .padding(.horizontal, Spacing.lg)
        .padding(.vertical, Spacing.sm)
        .onAppear {
            animateDots()
            // Show status text after a short delay
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
                withAnimation(.easeIn(duration: 0.3)) {
                    showStatus = true
                }
            }
            // Cycle through thinking statuses
            Timer.scheduledTimer(withTimeInterval: 2.5, repeats: true) { _ in
                withAnimation(.easeInOut(duration: 0.3)) {
                    thinkingPhase += 1
                }
            }
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

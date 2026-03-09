import SwiftUI

// MARK: - Loading View

struct LoadingView: View {
    var body: some View {
        VStack(spacing: 16) {
            SpinningCipherLogo(size: 40, spinning: true)

            Text("Processing...")
                .font(.system(size: 14, weight: .medium))
                .foregroundColor(CipherTheme.textSecondary)
        }
    }
}

// MARK: - Typing Indicator (Premium thinking animation)
// Animated logo with cycling status + progressive brain check-in indicators.
// Inspired by the best: Claude's thinking bar, ChatGPT's streaming, Linear's UI.

struct TypingIndicator: View {
    @State private var thinkingPhase = 0
    @State private var statusOpacity: Double = 0
    @State private var showStatus = false
    @State private var timer: Timer?
    @State private var brainStates: [BrainState] = BrainState.initial

    private var currentStatus: String {
        thinkingStatuses[thinkingPhase % thinkingStatuses.count]
    }

    private let thinkingStatuses = [
        "Routing to optimal model",
        "Evaluating context",
        "Recalling memories",
        "Composing response",
        "Thinking deeply",
        "Synthesizing",
        "Cross-referencing",
        "Refining output",
    ]

    var body: some View {
        HStack(spacing: Spacing.sm) {
            // Animated Cipher logo
            SpinningCipherLogo(size: 28, spinning: true)

            if showStatus {
                VStack(alignment: .leading, spacing: 4) {
                    // Status text with smooth crossfade
                    Text(currentStatus)
                        .font(.system(size: 12, weight: .medium, design: .monospaced))
                        .foregroundColor(CipherTheme.accent)
                        .opacity(statusOpacity)
                        .transition(.asymmetric(
                            insertion: .move(edge: .top).combined(with: .opacity),
                            removal: .opacity
                        ))
                        .id("status-\(thinkingPhase)")

                    // Progressive brain indicators
                    HStack(spacing: 6) {
                        ForEach(brainStates) { brain in
                            BrainCheckIndicator(state: brain)
                        }
                    }

                    // Animated underline
                    CipherThinkingBar()
                }
                .transition(.move(edge: .leading).combined(with: .opacity))
            }

            Spacer()
        }
        .onAppear { startAnimation() }
        .onDisappear { timer?.invalidate(); timer = nil }
    }

    func startAnimation() {
        // Fade in status
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                showStatus = true
            }
            withAnimation(.easeIn(duration: 0.3)) {
                statusOpacity = 1.0
            }
        }

        // Progressive brain check-ins
        for (index, _) in brainStates.enumerated() {
            let delay = 0.8 + Double(index) * 0.6
            DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
                withAnimation(.spring(response: 0.35, dampingFraction: 0.7)) {
                    if index < brainStates.count {
                        brainStates[index].status = .active
                    }
                }
            }
        }

        // Cycle through statuses
        timer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { _ in
            withAnimation(.easeOut(duration: 0.15)) {
                statusOpacity = 0
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) {
                withAnimation(.easeIn(duration: 0.2)) {
                    thinkingPhase += 1
                    statusOpacity = 1.0
                }
            }
        }
    }
}

// MARK: - Brain State Model

struct BrainState: Identifiable {
    let id: String
    let label: String
    let icon: String
    var status: BrainStatus = .waiting

    enum BrainStatus {
        case waiting, active, done
    }

    static let initial: [BrainState] = [
        BrainState(id: "classify", label: "Classify", icon: "brain"),
        BrainState(id: "route", label: "Route", icon: "arrow.triangle.branch"),
        BrainState(id: "think", label: "Think", icon: "sparkles"),
    ]
}

// MARK: - Brain Check Indicator

private struct BrainCheckIndicator: View {
    let state: BrainState

    var body: some View {
        HStack(spacing: 2) {
            Image(systemName: state.icon)
                .font(.system(size: 8, weight: .semibold))

            Text(state.label)
                .font(.system(size: 9, weight: .medium, design: .monospaced))
        }
        .foregroundColor(color)
        .padding(.horizontal, 5)
        .padding(.vertical, 2)
        .background(
            Capsule()
                .fill(color.opacity(0.1))
        )
        .scaleEffect(state.status == .active ? 1.0 : 0.85)
        .opacity(state.status == .waiting ? 0.4 : 1.0)
    }

    private var color: Color {
        switch state.status {
        case .waiting: return CipherTheme.textTertiary
        case .active: return CipherTheme.accent
        case .done: return CipherTheme.success
        }
    }
}

// MARK: - Thinking Bar (animated gradient underline)

private struct CipherThinkingBar: View {
    @State private var progress: CGFloat = 0

    var body: some View {
        GeometryReader { geo in
            let barWidth: CGFloat = geo.size.width * 0.35
            RoundedRectangle(cornerRadius: 1)
                .fill(
                    LinearGradient(
                        colors: [
                            CipherTheme.accent.opacity(0.0),
                            CipherTheme.accent.opacity(0.5),
                            CipherTheme.accent.opacity(0.0),
                        ],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                )
                .frame(width: barWidth, height: 1.5)
                .offset(x: progress * (geo.size.width - barWidth))
        }
        .frame(height: 1.5)
        .padding(.top, 2)
        .onAppear {
            withAnimation(.easeInOut(duration: 1.2).repeatForever(autoreverses: true)) {
                progress = 1.0
            }
        }
    }
}

// MARK: - Streaming Indicator (blinking cursor)

struct StreamingIndicator: View {
    @State private var cursorVisible = true

    var body: some View {
        RoundedRectangle(cornerRadius: 1)
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

// MARK: - Streaming Text View
// Words appear one at a time with a smooth fade-in, mimicking the best streaming UX.
// Inspired by ChatGPT's word-by-word reveal and Linear's micro-animations.

struct StreamingTextView: View {
    let fullText: String
    let isStreaming: Bool

    @State private var visibleWordCount: Int = 0
    @State private var timer: Timer?
    @State private var lastKnownLength: Int = 0

    private var words: [String] {
        fullText.components(separatedBy: .whitespaces).filter { !$0.isEmpty }
    }

    var body: some View {
        if isStreaming && !fullText.isEmpty {
            // During streaming: reveal words with animation
            VStack(alignment: .leading, spacing: 0) {
                FlowingTextLayout(words: Array(words.prefix(visibleWordCount)), isUser: false)

                if visibleWordCount < words.count {
                    // Show cursor at the end during word reveal
                    StreamingIndicator()
                        .padding(.leading, 2)
                }
            }
            .onChange(of: fullText) { _, newValue in
                let newWords = newValue.components(separatedBy: .whitespaces).filter { !$0.isEmpty }
                let newCount = newWords.count

                // Batch reveal new words with staggered animation
                if newCount > visibleWordCount {
                    revealNewWords(target: newCount)
                }
            }
            .onAppear {
                // Initial reveal
                let wordCount = words.count
                if wordCount > 0 {
                    revealNewWords(target: wordCount)
                }
            }
            .onDisappear {
                timer?.invalidate()
                timer = nil
            }
        } else if !fullText.isEmpty {
            // After streaming: show full text normally
            MarkdownRenderer(text: fullText, isUser: false)
                .transition(.opacity.animation(.easeIn(duration: 0.2)))
        }
    }

    private func revealNewWords(target: Int) {
        timer?.invalidate()

        // Reveal words at a pace that feels natural
        // Fast for catching up (30ms), slower for real-time (60ms)
        let wordsToReveal = target - visibleWordCount
        let interval: TimeInterval = wordsToReveal > 10 ? 0.02 : 0.04

        timer = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { t in
            if visibleWordCount < target {
                withAnimation(.easeOut(duration: 0.15)) {
                    visibleWordCount += 1
                }
            } else {
                t.invalidate()
            }
        }
    }
}

// MARK: - Flowing Text Layout
// Renders words with individual fade-in animations, wrapping naturally.

private struct FlowingTextLayout: View {
    let words: [String]
    let isUser: Bool

    var body: some View {
        // Use Text concatenation for proper word wrapping
        words.enumerated().reduce(Text("")) { result, item in
            let (index, word) = item
            let separator = index == 0 ? "" : " "
            return result + Text(separator + word)
        }
        .font(.system(size: 15, weight: .regular))
        .foregroundColor(isUser ? .white : CipherTheme.textPrimary)
        .lineSpacing(3)
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

// MARK: - Agent Thinking View

struct AgentThinkingView: View {
    let agentName: String
    let status: String

    @State private var statusOpacity: Double = 0

    var body: some View {
        VStack(spacing: Spacing.lg) {
            SpinningCipherLogo(size: 56, spinning: true)

            Text(agentName)
                .font(.system(size: 16, weight: .semibold))
                .foregroundColor(CipherTheme.textPrimary)

            Text(status)
                .font(.system(size: 13, weight: .medium, design: .monospaced))
                .foregroundColor(CipherTheme.accent)
                .opacity(statusOpacity)
                .onAppear {
                    withAnimation(.easeIn(duration: 0.5)) {
                        statusOpacity = 1.0
                    }
                }

            CipherThinkingBar()
                .frame(width: 120)
        }
        .padding(Spacing.xl)
    }
}

#Preview {
    ZStack {
        CipherTheme.background.ignoresSafeArea()

        VStack(spacing: 40) {
            LoadingView()
            TypingIndicator()
            StreamingIndicator()
            StreamingTextView(fullText: "Hello Mark, I'm analyzing your request and routing it to the optimal model for this task.", isStreaming: true)
                .padding()
            AgentThinkingView(agentName: "Maverick", status: "Fetching TSLA price...")
        }
    }
}

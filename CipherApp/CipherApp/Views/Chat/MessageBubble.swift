import SwiftUI

// MARK: - Message Bubble

struct MessageBubble: View {
    let message: Message
    let onCopy: () -> Void
    let onDelete: () -> Void
    var onRetry: (() -> Void)? = nil

    @State private var showActions = false

    var body: some View {
        if message.isUser {
            userBubble
        } else {
            assistantBubble
        }
    }

    // MARK: - User Message

    private var userBubble: some View {
        HStack(alignment: .bottom, spacing: Spacing.sm) {
            Spacer(minLength: 60)

            VStack(alignment: .trailing, spacing: Spacing.xxs) {
                Text(message.content)
                    .font(.system(size: 15))
                    .foregroundColor(.white)
                    .lineSpacing(3)
                    .textSelection(.enabled)
                    .padding(.horizontal, Spacing.lg)
                    .padding(.vertical, Spacing.md)
                    .background(CipherTheme.userBubble)
                    .clipShape(RoundedRectangle(cornerRadius: CornerRadius.xl))
                    .clipShape(
                        BubbleShape(isUser: true)
                    )

                // Timestamp
                Text(message.timestamp.chatTimeFormat())
                    .font(.system(size: 10, weight: .medium))
                    .foregroundColor(CipherTheme.textTertiary)
                    .padding(.trailing, Spacing.xxs)
            }
        }
        .padding(.horizontal, Spacing.lg)
        .padding(.vertical, Spacing.xxs)
        .contextMenu {
            contextMenuItems
        }
    }

    // MARK: - Assistant Message

    private var assistantBubble: some View {
        HStack(alignment: .top, spacing: Spacing.sm) {
            // Avatar
            ZStack {
                Circle()
                    .fill(CipherTheme.accentGradient)
                    .frame(width: 30, height: 30)

                Text("C")
                    .font(.system(size: 14, weight: .bold, design: .rounded))
                    .foregroundColor(.white)
            }
            .padding(.top, 2)

            VStack(alignment: .leading, spacing: Spacing.xs) {
                // Content
                if message.isStreaming {
                    streamingContent
                } else if message.isFailed {
                    failedContent
                } else {
                    MarkdownRenderer(text: message.content, isUser: false)
                        .textSelection(.enabled)
                }

                // Metadata row
                if !message.isStreaming {
                    metadataRow
                }
            }

            Spacer(minLength: 40)
        }
        .padding(.horizontal, Spacing.lg)
        .padding(.vertical, Spacing.xs)
        .contextMenu {
            contextMenuItems
        }
    }

    // MARK: - Streaming Content

    private var streamingContent: some View {
        HStack(alignment: .bottom, spacing: 2) {
            if message.content.isEmpty {
                TypingIndicator()
            } else {
                MarkdownRenderer(text: message.content, isUser: false)
                StreamingIndicator()
            }
        }
    }

    // MARK: - Failed Content

    private var failedContent: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            HStack(spacing: Spacing.sm) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 14))
                    .foregroundColor(CipherTheme.error)

                Text("Failed to generate response")
                    .font(.system(size: 14))
                    .foregroundColor(CipherTheme.error)
            }

            if let onRetry = onRetry {
                Button(action: onRetry) {
                    HStack(spacing: 4) {
                        Image(systemName: "arrow.clockwise")
                            .font(.system(size: 12, weight: .semibold))
                        Text("Retry")
                            .font(.system(size: 13, weight: .semibold))
                    }
                    .foregroundColor(CipherTheme.accent)
                    .padding(.horizontal, Spacing.md)
                    .padding(.vertical, Spacing.xs)
                    .background(
                        Capsule()
                            .fill(CipherTheme.accent.opacity(0.12))
                    )
                }
            }
        }
    }

    // MARK: - Metadata

    private var metadataRow: some View {
        HStack(spacing: Spacing.sm) {
            if let model = message.modelUsed {
                HStack(spacing: 3) {
                    Image(systemName: "cpu")
                        .font(.system(size: 9))
                    Text(message.modelDisplayName)
                        .font(.system(size: 10, weight: .medium, design: .monospaced))
                }
                .foregroundColor(CipherTheme.textTertiary)
            }

            if let tokens = message.tokensUsed {
                Text("\(tokens) tokens")
                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                    .foregroundColor(CipherTheme.textTertiary)
            }

            Text(message.timestamp.chatTimeFormat())
                .font(.system(size: 10, weight: .medium))
                .foregroundColor(CipherTheme.textTertiary)
        }
        .padding(.leading, 2)
    }

    // MARK: - Context Menu

    @ViewBuilder
    private var contextMenuItems: some View {
        Button(action: onCopy) {
            Label("Copy", systemImage: "doc.on.doc")
        }

        if let onRetry = onRetry, message.isAssistant {
            Button(action: onRetry) {
                Label("Retry", systemImage: "arrow.clockwise")
            }
        }

        Divider()

        Button(role: .destructive, action: onDelete) {
            Label("Delete", systemImage: "trash")
        }
    }
}

// MARK: - Bubble Shape

struct BubbleShape: Shape {
    let isUser: Bool

    func path(in rect: CGRect) -> Path {
        let radius: CGFloat = 20
        var path = Path()

        if isUser {
            // User bubble — rounded except bottom-right
            path.addRoundedRect(
                in: rect,
                cornerSize: CGSize(width: radius, height: radius)
            )
        } else {
            path.addRoundedRect(
                in: rect,
                cornerSize: CGSize(width: radius, height: radius)
            )
        }

        return path
    }
}

#Preview {
    ScrollView {
        VStack(spacing: 0) {
            MessageBubble(
                message: .userSample,
                onCopy: {},
                onDelete: {}
            )

            MessageBubble(
                message: .sample,
                onCopy: {},
                onDelete: {}
            )

            MessageBubble(
                message: .codeSample,
                onCopy: {},
                onDelete: {}
            )

            MessageBubble(
                message: .streamingSample,
                onCopy: {},
                onDelete: {}
            )
        }
    }
    .background(CipherTheme.background)
}

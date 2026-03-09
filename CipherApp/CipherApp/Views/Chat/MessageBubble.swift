import SwiftUI

// MARK: - Message Bubble

struct MessageBubble: View {
    let message: Message
    let onCopy: () -> Void
    let onDelete: () -> Void
    var onRetry: (() -> Void)? = nil

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
                VStack(alignment: .trailing, spacing: Spacing.xs) {
                    // Show attached images in the bubble
                    let imageAttachments = message.attachments.filter { $0.isImage }
                    if !imageAttachments.isEmpty {
                        HStack(spacing: Spacing.xs) {
                            ForEach(Array(imageAttachments.prefix(3).enumerated()), id: \.offset) { _, attachment in
                                if let thumbData = attachment.thumbnailData,
                                   let uiImage = UIImage(data: thumbData) {
                                    Image(uiImage: uiImage)
                                        .resizable()
                                        .aspectRatio(contentMode: .fill)
                                        .frame(maxWidth: 140, maxHeight: 140)
                                        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
                                }
                            }
                        }
                    }

                    if message.content != "[Image attached]" {
                        CollapsibleText(
                            text: message.content,
                            lineLimit: 8,
                            font: .system(size: 15),
                            textColor: .white
                        )
                        .lineSpacing(3)
                    }
                }
                .padding(.horizontal, Spacing.lg)
                .padding(.vertical, Spacing.md)
                .background(CipherTheme.userBubble)
                .clipShape(RoundedRectangle(cornerRadius: CornerRadius.xl))
                .clipShape(BubbleShape(isUser: true))

                Text(message.timestamp.chatTimeFormat())
                    .font(.system(size: 10, weight: .medium))
                    .foregroundColor(CipherTheme.textTertiary)
                    .padding(.trailing, Spacing.xxs)
            }
        }
        .padding(.horizontal, Spacing.lg)
        .padding(.vertical, Spacing.xxs)
        .contextMenu {
            Button(action: onCopy) {
                Label("Copy", systemImage: "doc.on.doc")
            }
            Divider()
            Button(role: .destructive, action: onDelete) {
                Label("Delete", systemImage: "trash")
            }
        }
    }

    // MARK: - Assistant Message

    private var assistantBubble: some View {
        HStack(alignment: .top, spacing: Spacing.sm) {
            // Small logo — only show when streaming
            if message.isStreaming {
                SpinningCipherLogo(size: 24, spinning: true)
                    .padding(.top, 2)
            }

            VStack(alignment: .leading, spacing: Spacing.xs) {
                if message.isStreaming {
                    streamingContent
                } else if message.isFailed {
                    failedContent
                } else {
                    // Rendered markdown with native text selection
                    MarkdownRenderer(text: message.content, isUser: false)
                        .textSelection(.enabled)

                    // Display any image attachments from assistant (generated images)
                    let imageAttachments = message.attachments.filter { $0.isImage }
                    if !imageAttachments.isEmpty {
                        ForEach(Array(imageAttachments.enumerated()), id: \.offset) { _, attachment in
                            if let urlString = attachment.localPath,
                               let url = URL(string: urlString) {
                                AsyncImage(url: url) { phase in
                                    switch phase {
                                    case .success(let image):
                                        image
                                            .resizable()
                                            .aspectRatio(contentMode: .fit)
                                            .frame(maxWidth: 280)
                                            .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
                                    case .failure:
                                        HStack(spacing: 4) {
                                            Image(systemName: "photo.badge.exclamationmark")
                                            Text("Image failed to load")
                                        }
                                        .font(.system(size: 12))
                                        .foregroundColor(CipherTheme.textTertiary)
                                    case .empty:
                                        ProgressView()
                                            .frame(width: 200, height: 150)
                                    @unknown default:
                                        EmptyView()
                                    }
                                }
                            }
                        }
                    }
                }

                if !message.isStreaming {
                    MessageActionBar(
                        message: message,
                        onCopy: onCopy,
                        onRetry: onRetry,
                        onDelete: onDelete
                    )
                }
            }

            Spacer(minLength: 20)
        }
        .padding(.horizontal, Spacing.lg)
        .padding(.vertical, Spacing.xs)
    }

    // MARK: - Streaming Content (Word-by-word reveal)

    private var streamingContent: some View {
        VStack(alignment: .leading, spacing: 0) {
            if message.content.isEmpty {
                TypingIndicator()
            } else {
                // Word-by-word streaming — words fade in individually
                // instead of full text dump that scrolls to bottom
                StreamingTextView(
                    fullText: message.content,
                    isStreaming: message.isStreaming
                )
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
                    .background(Capsule().fill(CipherTheme.accent.opacity(0.12)))
                }
            }
        }
    }
}

// MARK: - Message Action Bar (Liquid Glass style)

struct MessageActionBar: View {
    let message: Message
    let onCopy: () -> Void
    var onRetry: (() -> Void)?
    var onDelete: (() -> Void)?

    @State private var copiedState: CopiedState = .idle

    private enum CopiedState {
        case idle, copied
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 2) {
                // Copy
                ActionBarButton(
                    icon: copiedState == .copied ? "checkmark" : "doc.on.doc",
                    label: copiedState == .copied ? "Copied" : "Copy",
                    activeColor: copiedState == .copied ? CipherTheme.success : nil
                ) {
                    UIPasteboard.general.string = message.content
                    HapticsService.shared.lightTap()
                    withAnimation(.easeInOut(duration: 0.2)) {
                        copiedState = .copied
                    }
                    DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            copiedState = .idle
                        }
                    }
                }

                // Retry
                if let onRetry {
                    ActionBarButton(icon: "arrow.clockwise", label: "Retry") {
                        onRetry()
                    }
                }

                // Share
                ActionBarButton(icon: "square.and.arrow.up", label: "Share") {
                    shareMessage()
                }

                Spacer()

                // Confidence indicator — only show for low-confidence responses
                if let score = message.confidenceScore, score < 0.7 {
                    HStack(spacing: 3) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(.system(size: 9))
                        Text("Unverified")
                            .font(.system(size: 10, weight: .medium))
                    }
                    .foregroundColor(CipherTheme.warning)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 3)
                    .background(
                        Capsule()
                            .fill(CipherTheme.warning.opacity(0.12))
                    )
                }

                // Model name only — clean, no token count
                if let model = message.modelUsed, !model.isEmpty {
                    Text(message.modelDisplayName)
                        .font(.system(size: 10, weight: .medium, design: .monospaced))
                        .foregroundColor(CipherTheme.textTertiary.opacity(0.7))
                }

                Text(message.timestamp.chatTimeFormat())
                    .font(.system(size: 10, weight: .medium))
                    .foregroundColor(CipherTheme.textTertiary.opacity(0.7))
            }

            // Validation warnings — shown inline below action bar
            if let warnings = message.validationWarnings, !warnings.isEmpty {
                VStack(alignment: .leading, spacing: 2) {
                    ForEach(warnings, id: \.self) { warning in
                        HStack(spacing: 4) {
                            Circle()
                                .fill(CipherTheme.warning)
                                .frame(width: 4, height: 4)
                            Text(warning)
                                .font(.system(size: 11))
                                .foregroundColor(CipherTheme.textTertiary)
                        }
                    }
                }
                .padding(.top, 2)
            }
        }
        .padding(.top, 4)
    }

    private func shareMessage() {
        let text = message.content
        let activityVC = UIActivityViewController(activityItems: [text], applicationActivities: nil)
        if let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
           let window = windowScene.windows.first,
           let rootVC = window.rootViewController {
            var topVC = rootVC
            while let presented = topVC.presentedViewController {
                topVC = presented
            }
            activityVC.popoverPresentationController?.sourceView = topVC.view
            activityVC.popoverPresentationController?.sourceRect = CGRect(x: topVC.view.bounds.midX, y: topVC.view.bounds.midY, width: 0, height: 0)
            topVC.present(activityVC, animated: true)
        }
        HapticsService.shared.lightTap()
    }
}

// MARK: - Action Bar Button (Liquid Glass pill)

private struct ActionBarButton: View {
    let icon: String
    let label: String
    var activeColor: Color? = nil
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 3) {
                Image(systemName: icon)
                    .font(.system(size: 11, weight: .medium))
                Text(label)
                    .font(.system(size: 11, weight: .medium))
            }
            .foregroundColor(activeColor ?? CipherTheme.textTertiary)
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .background(
                RoundedRectangle(cornerRadius: 7)
                    .fill(.ultraThinMaterial)
                    .opacity(0.6)
            )
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Collapsible Text

struct CollapsibleText: View {
    let text: String
    let lineLimit: Int
    var font: Font = .system(size: 15)
    var textColor: Color = .white

    @State private var isExpanded = false
    @State private var isTruncated = false

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.xs) {
            Text(text)
                .font(font)
                .foregroundColor(textColor)
                .lineLimit(isExpanded ? nil : lineLimit)
                .textSelection(.enabled)
                .background(
                    GeometryReader { visibleGeo in
                        Text(text)
                            .font(font)
                            .lineLimit(nil)
                            .fixedSize(horizontal: false, vertical: true)
                            .background(GeometryReader { fullGeo in
                                Color.clear.onAppear {
                                    isTruncated = fullGeo.size.height > visibleGeo.size.height + 4
                                }
                            })
                            .hidden()
                    }
                )

            if isTruncated {
                Button(action: {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        isExpanded.toggle()
                    }
                }) {
                    Text(isExpanded ? "See less" : "See more")
                        .font(.system(size: 13, weight: .medium))
                        .foregroundColor(CipherTheme.accent)
                }
            }
        }
    }
}

// MARK: - Agent Deploy Banner

struct AgentDeployBanner: View {
    let agentName: String
    let displayName: String
    let reason: String
    let onDeploy: () -> Void
    let onDismiss: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            HStack(spacing: Spacing.sm) {
                Image(systemName: "bolt.fill")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(CipherTheme.accent)

                Text("Deploy \(displayName)?")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(CipherTheme.textPrimary)

                Spacer()

                Button(action: onDismiss) {
                    Image(systemName: "xmark")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundColor(CipherTheme.textTertiary)
                }
            }

            Text(reason)
                .font(.system(size: 13))
                .foregroundColor(CipherTheme.textSecondary)
                .lineLimit(2)

            Button(action: onDeploy) {
                HStack(spacing: 6) {
                    Image(systemName: "paperplane.fill")
                        .font(.system(size: 12, weight: .semibold))
                    Text("Deploy Now")
                        .font(.system(size: 13, weight: .semibold))
                }
                .foregroundColor(CipherTheme.textOnAccent)
                .frame(maxWidth: .infinity)
                .padding(.vertical, Spacing.sm)
                .background(CipherTheme.accentGradient)
                .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
            }
        }
        .padding(Spacing.md)
        .background(
            RoundedRectangle(cornerRadius: CornerRadius.lg)
                .fill(.ultraThinMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: CornerRadius.lg)
                        .stroke(CipherTheme.accent.opacity(0.15), lineWidth: 0.5)
                )
        )
    }
}

// MARK: - Bubble Shape

struct BubbleShape: Shape {
    let isUser: Bool

    func path(in rect: CGRect) -> Path {
        var path = Path()
        path.addRoundedRect(
            in: rect,
            cornerSize: CGSize(width: 20, height: 20)
        )
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
                onDelete: {},
                onRetry: {}
            )
        }
    }
    .background(CipherTheme.background)
}

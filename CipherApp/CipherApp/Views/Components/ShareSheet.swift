import SwiftUI

// MARK: - Share Sheet

struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        let controller = UIActivityViewController(activityItems: items, applicationActivities: nil)
        return controller
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}

// MARK: - Conversation Export

struct ConversationExporter {
    static func exportAsText(_ conversation: Conversation) -> String {
        var output = "# \(conversation.title)\n"
        output += "Exported from Cipher by Elysian Protocol\n"
        output += "Date: \(conversation.createdAt.formatted())\n"
        output += "Messages: \(conversation.messages.count)\n"
        output += String(repeating: "-", count: 50) + "\n\n"

        for message in conversation.messages {
            let role = message.role == .user ? "You" : "Cipher"
            let time = message.timestamp.chatTimeFormat()
            output += "[\(role)] (\(time))\n"
            output += message.content + "\n\n"
        }

        return output
    }

    static func exportAsMarkdown(_ conversation: Conversation) -> String {
        var output = "# \(conversation.title)\n\n"
        output += "> Exported from **Cipher** by Elysian Protocol  \n"
        output += "> \(conversation.createdAt.formatted())  \n"
        output += "> \(conversation.messages.count) messages\n\n"
        output += "---\n\n"

        for message in conversation.messages {
            if message.role == .user {
                output += "### You\n\n"
            } else {
                let model = message.modelDisplayName
                output += "### Cipher" + (model.isEmpty ? "" : " (\(model))") + "\n\n"
            }
            output += message.content + "\n\n"
        }

        return output
    }
}

// MARK: - Quick Action Menu

struct QuickActionMenu: View {
    let message: Message
    let onCopy: () -> Void
    let onShare: () -> Void
    let onRetry: (() -> Void)?

    @State private var showShare = false

    var body: some View {
        HStack(spacing: Spacing.lg) {
            actionButton(icon: "doc.on.doc", label: "Copy", action: onCopy)

            actionButton(icon: "square.and.arrow.up", label: "Share") {
                showShare = true
            }

            if let onRetry = onRetry, message.isAssistant {
                actionButton(icon: "arrow.clockwise", label: "Retry", action: onRetry)
            }
        }
        .padding(.horizontal, Spacing.md)
        .padding(.vertical, Spacing.sm)
        .background(
            Capsule()
                .fill(CipherTheme.surfaceElevated)
                .overlay(
                    Capsule()
                        .stroke(CipherTheme.border, lineWidth: 0.5)
                )
                .shadow(color: Color.black.opacity(0.2), radius: 8, y: 2)
        )
        .sheet(isPresented: $showShare) {
            ShareSheet(items: [message.content])
        }
    }

    private func actionButton(icon: String, label: String, action: @escaping () -> Void) -> some View {
        Button(action: {
            action()
            HapticsService.shared.lightTap()
        }) {
            VStack(spacing: 2) {
                Image(systemName: icon)
                    .font(.system(size: 14, weight: .medium))
                Text(label)
                    .font(.system(size: 9, weight: .medium))
            }
            .foregroundColor(CipherTheme.textSecondary)
            .frame(width: 44, height: 36)
        }
    }
}

import SwiftUI

// MARK: - Conversation Row

struct ConversationRow: View {
    let conversation: Conversation
    let isSelected: Bool
    let onDelete: () -> Void
    var onPin: (() -> Void)? = nil

    var body: some View {
        HStack(spacing: Spacing.md) {
            // Icon
            ZStack {
                Circle()
                    .fill(CipherTheme.surfaceElevated)
                    .frame(width: 40, height: 40)

                Image(systemName: conversation.isPinned ? "pin.fill" : "bubble.left.fill")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundColor(conversation.isPinned ? CipherTheme.warning : CipherTheme.accent)
            }

            // Content
            VStack(alignment: .leading, spacing: 3) {
                HStack {
                    Text(conversation.title)
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundColor(CipherTheme.textPrimary)
                        .lineLimit(1)

                    Spacer()

                    Text(conversation.lastMessageTime.timeAgoDisplay())
                        .font(.system(size: 11, weight: .medium))
                        .foregroundColor(CipherTheme.textTertiary)
                }

                HStack {
                    Text(conversation.preview)
                        .font(.system(size: 13))
                        .foregroundColor(CipherTheme.textSecondary)
                        .lineLimit(1)

                    Spacer()

                    // Message count
                    let count = conversation.messageCount ?? conversation.messages.count
                    if count > 0 {
                        Text("\(count)")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(CipherTheme.textOnAccent)
                            .frame(minWidth: 18, minHeight: 18)
                            .background(
                                Circle()
                                    .fill(CipherTheme.accent.opacity(0.8))
                            )
                    }
                }

                // Model used indicator
                if let model = conversation.lastModelUsed {
                    HStack(spacing: 4) {
                        Image(systemName: "cpu")
                            .font(.system(size: 9))
                        Text(model)
                            .font(.system(size: 10, weight: .medium, design: .monospaced))
                    }
                    .foregroundColor(CipherTheme.textTertiary)
                }
            }
        }
        .padding(Spacing.md)
        .background(
            RoundedRectangle(cornerRadius: CornerRadius.md)
                .fill(isSelected ? CipherTheme.accent.opacity(0.08) : CipherTheme.surface)
                .overlay(
                    RoundedRectangle(cornerRadius: CornerRadius.md)
                        .stroke(
                            isSelected ? CipherTheme.accent.opacity(0.3) : CipherTheme.borderSubtle,
                            lineWidth: 0.5
                        )
                )
        )
        .contentShape(Rectangle())
        .contextMenu {
            if let onPin = onPin {
                Button(action: onPin) {
                    Label(conversation.isPinned ? "Unpin" : "Pin", systemImage: conversation.isPinned ? "pin.slash" : "pin")
                }
            }

            Button(action: {
                UIPasteboard.general.string = conversation.title
            }) {
                Label("Copy Title", systemImage: "doc.on.doc")
            }

            Divider()

            Button(role: .destructive, action: onDelete) {
                Label("Delete", systemImage: "trash")
            }
        }
    }
}

#Preview {
    ZStack {
        CipherTheme.background.ignoresSafeArea()

        VStack(spacing: Spacing.sm) {
            ConversationRow(
                conversation: .sample,
                isSelected: true,
                onDelete: {}
            )

            ConversationRow(
                conversation: Conversation(
                    title: "Swift Best Practices",
                    messages: [
                        Message(conversationId: UUID(), content: "What are the best practices?", role: .user)
                    ],
                    isPinned: true
                ),
                isSelected: false,
                onDelete: {}
            )
        }
        .padding()
    }
}

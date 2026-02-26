import Foundation

// MARK: - Conversation Model

struct Conversation: Identifiable, Codable {
    var id: UUID
    var title: String
    let createdAt: Date
    var messages: [Message]
    let messageCount: Int?
    var isPinned: Bool
    var projectId: UUID?
    var tags: [String]

    enum CodingKeys: String, CodingKey {
        case id, title, messages, tags
        case createdAt = "created_at"
        case messageCount = "message_count"
        case isPinned = "is_pinned"
        case projectId = "project_id"
    }

    init(
        id: UUID = UUID(),
        title: String = "New Conversation",
        createdAt: Date = Date(),
        messages: [Message] = [],
        messageCount: Int? = nil,
        isPinned: Bool = false,
        projectId: UUID? = nil,
        tags: [String] = []
    ) {
        self.id = id
        self.title = title
        self.createdAt = createdAt
        self.messages = messages
        self.messageCount = messageCount ?? messages.count
        self.isPinned = isPinned
        self.projectId = projectId
        self.tags = tags
    }

    var preview: String {
        guard let last = messages.last else { return "No messages yet" }
        let text = last.content.prefix(80).trimmingCharacters(in: .whitespacesAndNewlines)
        return text.isEmpty ? "No messages yet" : String(text)
    }

    var lastMessageTime: Date {
        messages.last?.timestamp ?? createdAt
    }

    var totalTokens: Int {
        messages.compactMap(\.tokensUsed).reduce(0, +)
    }

    var totalCost: Double {
        messages.compactMap(\.costUsd).reduce(0, +)
    }

    var lastModelUsed: String? {
        messages.last(where: { $0.role == .assistant })?.modelDisplayName
    }

    mutating func addMessage(_ message: Message) {
        messages.append(message)
    }
}

// MARK: - Project Model

struct Project: Identifiable, Codable {
    let id: UUID
    var name: String
    var description: String
    var icon: String
    var color: String
    let createdAt: Date
    var conversationIds: [UUID]

    init(
        id: UUID = UUID(),
        name: String,
        description: String = "",
        icon: String = "folder.fill",
        color: String = "6C63FF",
        createdAt: Date = Date(),
        conversationIds: [UUID] = []
    ) {
        self.id = id
        self.name = name
        self.description = description
        self.icon = icon
        self.color = color
        self.createdAt = createdAt
        self.conversationIds = conversationIds
    }
}

// MARK: - Preview Samples

extension Conversation {
    static let sample = Conversation(
        title: "Getting Started with Cipher",
        messages: [
            Message(
                conversationId: UUID(),
                content: "What can you help me with?",
                role: .user
            ),
            Message(
                conversationId: UUID(),
                content: "I'm Cipher, your sovereign AI assistant built on the Elysian Protocol. I can help with writing, analysis, coding, research, strategy, and much more. I operate with care and clarity — what would you like to explore?",
                role: .assistant,
                modelUsed: "anthropic/claude-sonnet-4-20250514"
            )
        ]
    )
}

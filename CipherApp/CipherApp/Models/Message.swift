import Foundation

// MARK: - Message Role

enum MessageRole: String, Codable {
    case user
    case assistant
    case system
}

// MARK: - Message Status

enum MessageStatus: String, Codable {
    case sending
    case streaming
    case delivered
    case failed
    case cancelled
}

// MARK: - Attachment

struct Attachment: Identifiable, Codable {
    let id: UUID
    let fileName: String
    let mimeType: String
    let fileSize: Int
    let localPath: String?
    let thumbnailData: Data?

    init(
        id: UUID = UUID(),
        fileName: String,
        mimeType: String,
        fileSize: Int = 0,
        localPath: String? = nil,
        thumbnailData: Data? = nil
    ) {
        self.id = id
        self.fileName = fileName
        self.mimeType = mimeType
        self.fileSize = fileSize
        self.localPath = localPath
        self.thumbnailData = thumbnailData
    }

    var isImage: Bool {
        mimeType.hasPrefix("image/")
    }

    var fileSizeDisplay: String {
        let formatter = ByteCountFormatter()
        formatter.allowedUnits = [.useKB, .useMB]
        formatter.countStyle = .file
        return formatter.string(fromByteCount: Int64(fileSize))
    }
}

// MARK: - Message Model

struct Message: Identifiable, Codable {
    let id: UUID
    var conversationId: UUID
    var content: String
    let role: MessageRole
    let timestamp: Date
    var status: MessageStatus
    let modelUsed: String?
    let tokensUsed: Int?
    let costUsd: Double?
    let attachments: [Attachment]
    let referenceSources: [String]?

    enum CodingKeys: String, CodingKey {
        case id
        case conversationId = "conversation_id"
        case content
        case role
        case timestamp
        case status
        case modelUsed = "model_used"
        case tokensUsed = "tokens_used"
        case costUsd = "cost_usd"
        case attachments
        case referenceSources = "reference_sources"
    }

    init(
        id: UUID = UUID(),
        conversationId: UUID,
        content: String,
        role: MessageRole,
        timestamp: Date = Date(),
        status: MessageStatus = .delivered,
        modelUsed: String? = nil,
        tokensUsed: Int? = nil,
        costUsd: Double? = nil,
        attachments: [Attachment] = [],
        referenceSources: [String]? = nil
    ) {
        self.id = id
        self.conversationId = conversationId
        self.content = content
        self.role = role
        self.timestamp = timestamp
        self.status = status
        self.modelUsed = modelUsed
        self.tokensUsed = tokensUsed
        self.costUsd = costUsd
        self.attachments = attachments
        self.referenceSources = referenceSources
    }

    var modelDisplayName: String {
        guard let model = modelUsed else { return "" }
        if model.contains("/") {
            return String(model.split(separator: "/").last ?? "")
        }
        return model
    }

    var isUser: Bool { role == .user }
    var isAssistant: Bool { role == .assistant }
    var isStreaming: Bool { status == .streaming }
    var isFailed: Bool { status == .failed }
}

// MARK: - Preview Samples

extension Message {
    static let sample = Message(
        conversationId: UUID(),
        content: "Hello! I'm Cipher, your sovereign AI assistant. I operate with care, clarity, and competence. How can I help you today?",
        role: .assistant,
        modelUsed: "anthropic/claude-sonnet-4-20250514"
    )

    static let userSample = Message(
        conversationId: UUID(),
        content: "Can you help me write a business plan?",
        role: .user
    )

    static let streamingSample = Message(
        conversationId: UUID(),
        content: "Let me think about that...",
        role: .assistant,
        status: .streaming
    )

    static let codeSample = Message(
        conversationId: UUID(),
        content: """
        Here's a Swift example:

        ```swift
        func fibonacci(_ n: Int) -> Int {
            guard n > 1 else { return n }
            return fibonacci(n - 1) + fibonacci(n - 2)
        }

        // Calculate first 10 numbers
        let results = (0..<10).map { fibonacci($0) }
        print(results) // [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
        ```

        This uses recursion, but for larger numbers you'd want memoization or an iterative approach.
        """,
        role: .assistant,
        modelUsed: "deepseek/deepseek-coder"
    )
}

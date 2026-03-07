import Foundation

// MARK: - Chat Request

struct ChatRequest: Codable {
    let message: String
    let conversationId: UUID?
    let modelTier: String
    let includeMemory: Bool
    let maxTokens: Int
    let temperature: Double
    let stream: Bool

    enum CodingKeys: String, CodingKey {
        case message
        case conversationId = "conversation_id"
        case modelTier = "model_tier"
        case includeMemory = "include_memory"
        case maxTokens = "max_tokens"
        case temperature
        case stream
    }

    init(
        message: String,
        conversationId: UUID? = nil,
        modelTier: String = "auto",
        includeMemory: Bool = true,
        maxTokens: Int = 4096,
        temperature: Double = 0.7,
        stream: Bool = false
    ) {
        self.message = message
        self.conversationId = conversationId
        self.modelTier = modelTier
        self.includeMemory = includeMemory
        self.maxTokens = maxTokens
        self.temperature = temperature
        self.stream = stream
    }
}

// MARK: - Chat Response

struct ChatResponse: Codable {
    let message: String
    let conversationId: UUID
    let modelUsed: String
    let tokensUsed: Int
    let costUsd: Double
    let timestamp: String?

    enum CodingKeys: String, CodingKey {
        case message
        case conversationId = "conversation_id"
        case modelUsed = "model_used"
        case tokensUsed = "tokens_used"
        case costUsd = "cost_usd"
        case timestamp
    }
}

// MARK: - Streaming Chunk

struct StreamChunk: Codable {
    let type: String            // "token", "metadata", "done", "error"
    let content: String?
    let conversationId: UUID?
    let modelUsed: String?
    let tokensUsed: Int?
    let costUsd: Double?

    enum CodingKeys: String, CodingKey {
        case type, content
        case conversationId = "conversation_id"
        case modelUsed = "model_used"
        case tokensUsed = "tokens_used"
        case costUsd = "cost_usd"
    }
}

// MARK: - Health Response

struct HealthResponse: Codable {
    let status: String
    let version: String?
    let uptimeSeconds: Double?
    let databaseConnected: Bool?
    let chromaConnected: Bool?

    enum CodingKeys: String, CodingKey {
        case status, version
        case uptimeSeconds = "uptime_seconds"
        case databaseConnected = "database_connected"
        case chromaConnected = "chroma_connected"
    }

    var isHealthy: Bool {
        status == "ok" || status == "healthy"
    }
}

// MARK: - Conversation List Response

struct ConversationListResponse: Codable {
    let conversations: [ConversationSummary]
}

struct ConversationSummary: Codable {
    let id: UUID
    let title: String
    let createdAt: Date
    let messageCount: Int

    enum CodingKeys: String, CodingKey {
        case id, title
        case createdAt = "created_at"
        case messageCount = "message_count"
    }

    func toConversation() -> Conversation {
        Conversation(
            id: id,
            title: title,
            createdAt: createdAt,
            messages: [],
            messageCount: messageCount
        )
    }
}

// MARK: - Model Tier

enum ModelTier: String, CaseIterable, Codable {
    case auto = "auto"
    case `default` = "default"
    case fast = "fast"
    case code = "code"
    case reasoning = "reasoning"

    var displayName: String {
        switch self {
        case .auto: return "Auto"
        case .default: return "Balanced"
        case .fast: return "Fast"
        case .code: return "Code"
        case .reasoning: return "Reasoning"
        }
    }

    var icon: String {
        switch self {
        case .auto: return "sparkles"
        case .default: return "brain"
        case .fast: return "bolt.fill"
        case .code: return "chevron.left.forwardslash.chevron.right"
        case .reasoning: return "lightbulb.fill"
        }
    }

    var description: String {
        switch self {
        case .auto: return "Cipher selects the best model"
        case .default: return "Balanced performance and quality"
        case .fast: return "Fastest responses via Groq"
        case .code: return "Optimized for coding via DeepSeek"
        case .reasoning: return "Deep reasoning via Claude"
        }
    }
}

// MARK: - Scanner Models

struct ScannerBriefing: Codable, Identifiable {
    let id: UUID
    let title: String
    let summary: String
    let source: String
    let url: String?
    let relevanceScore: Double
    let timestamp: Date

    enum CodingKeys: String, CodingKey {
        case id, title, summary, source, url, timestamp
        case relevanceScore = "relevance_score"
    }

    init(
        id: UUID = UUID(),
        title: String,
        summary: String,
        source: String,
        url: String? = nil,
        relevanceScore: Double = 0.5,
        timestamp: Date = Date()
    ) {
        self.id = id
        self.title = title
        self.summary = summary
        self.source = source
        self.url = url
        self.relevanceScore = relevanceScore
        self.timestamp = timestamp
    }

    var sourceIcon: String {
        switch source.lowercased() {
        case "news", "newsapi": return "newspaper.fill"
        case "reddit": return "bubble.left.and.bubble.right.fill"
        case "x", "twitter": return "at.circle.fill"
        case "github": return "chevron.left.forwardslash.chevron.right"
        case "huggingface", "models": return "cpu.fill"
        default: return "globe"
        }
    }
}

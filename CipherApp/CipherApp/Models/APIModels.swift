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
    let images: [String]  // base64-encoded images

    enum CodingKeys: String, CodingKey {
        case message
        case conversationId = "conversation_id"
        case modelTier = "model_tier"
        case includeMemory = "include_memory"
        case maxTokens = "max_tokens"
        case temperature
        case stream
        case images
    }

    init(
        message: String,
        conversationId: UUID? = nil,
        modelTier: String = "auto",
        includeMemory: Bool = true,
        maxTokens: Int = 4096,
        temperature: Double = 0.7,
        stream: Bool = false,
        images: [String] = []
    ) {
        self.message = message
        self.conversationId = conversationId
        self.modelTier = modelTier
        self.includeMemory = includeMemory
        self.maxTokens = maxTokens
        self.temperature = temperature
        self.stream = stream
        self.images = images
    }
}

// MARK: - Chat Response

struct ResponseImageAttachment: Codable {
    let url: String
    let mimeType: String?
    let analysis: String?

    enum CodingKeys: String, CodingKey {
        case url
        case mimeType = "mime_type"
        case analysis
    }
}

struct ChatResponse: Codable {
    let message: String
    let conversationId: UUID
    let modelUsed: String
    let tokensUsed: Int
    let costUsd: Double
    let timestamp: String?
    let recommendedAgent: RecommendedAgentInfo?
    let images: [ResponseImageAttachment]?
    let confidenceScore: Double?
    let validationWarnings: [String]?

    enum CodingKeys: String, CodingKey {
        case message
        case conversationId = "conversation_id"
        case modelUsed = "model_used"
        case tokensUsed = "tokens_used"
        case costUsd = "cost_usd"
        case timestamp
        case recommendedAgent = "recommended_agent"
        case images
        case confidenceScore = "confidence_score"
        case validationWarnings = "validation_warnings"
    }
}

// MARK: - Agent Recommendation (from chat response)

struct RecommendedAgentInfo: Codable {
    let agentName: String
    let displayName: String
    let reason: String
    let confidence: Double
    let suggestedInstruction: String

    enum CodingKeys: String, CodingKey {
        case agentName = "agent_name"
        case displayName = "display_name"
        case reason, confidence
        case suggestedInstruction = "suggested_instruction"
    }
}

// MARK: - Spawn Session Models

struct SpawnBatchRequest: Codable {
    let tasks: [SpawnTaskItem]
    let spawnSessionId: String?

    enum CodingKeys: String, CodingKey {
        case tasks
        case spawnSessionId = "spawn_session_id"
    }
}

struct SpawnTaskItem: Codable {
    let agentName: String
    let instruction: String

    enum CodingKeys: String, CodingKey {
        case agentName = "agent_name"
        case instruction
    }
}

struct SpawnBatchResponse: Codable {
    let spawnSessionId: String
    let taskIds: [String]
    let total: Int

    enum CodingKeys: String, CodingKey {
        case spawnSessionId = "spawn_session_id"
        case taskIds = "task_ids"
        case total
    }
}

struct RunningAgentStatus: Codable, Identifiable {
    let taskId: String
    let agentName: String
    let status: String
    let progress: Double
    let currentStep: String
    let error: String?
    let outputPreview: String?

    var id: String { taskId }

    enum CodingKeys: String, CodingKey {
        case taskId = "task_id"
        case agentName = "agent_name"
        case status, progress
        case currentStep = "current_step"
        case error
        case outputPreview = "output_preview"
    }
}

struct SpawnSessionSummary: Codable {
    let total: Int
    let running: Int
    let completed: Int
    let failed: Int
}

struct SpawnSessionStatusResponse: Codable {
    let spawnSessionId: String
    let createdAt: String
    let tasks: [RunningAgentStatus]
    let summary: SpawnSessionSummary

    enum CodingKeys: String, CodingKey {
        case spawnSessionId = "spawn_session_id"
        case createdAt = "created_at"
        case tasks, summary
    }
}

// MARK: - Agent Interaction Models

struct AgentInteractionAPI: Codable, Identifiable {
    let interactionId: String
    let taskId: String
    let agentName: String
    let question: String
    let options: [String]
    let status: String
    let createdAt: String
    let timeoutAt: String

    var id: String { interactionId }

    enum CodingKeys: String, CodingKey {
        case interactionId = "interaction_id"
        case taskId = "task_id"
        case agentName = "agent_name"
        case question, options, status
        case createdAt = "created_at"
        case timeoutAt = "timeout_at"
    }
}

struct PendingInteractionsResponse: Codable {
    let total: Int
    let interactions: [AgentInteractionAPI]
}

struct InteractionAnswerResponse: Codable {
    let success: Bool
    let interactionId: String
    let taskId: String?
    let resumed: Bool

    enum CodingKeys: String, CodingKey {
        case success
        case interactionId = "interaction_id"
        case taskId = "task_id"
        case resumed
    }
}

// MARK: - Streaming Chunk

struct StreamChunk: Codable {
    let type: String            // "token", "metadata", "done", "error", "image"
    let content: String?
    let conversationId: UUID?
    let modelUsed: String?
    let tokensUsed: Int?
    let costUsd: Double?
    // Metadata fields for confidence/validation
    let confidenceScore: Double?
    let hasImages: Int?
    // Image chunk fields (type == "image")
    let url: String?
    let mimeType: String?
    let analysis: String?

    enum CodingKeys: String, CodingKey {
        case type, content, url, analysis
        case conversationId = "conversation_id"
        case modelUsed = "model_used"
        case tokensUsed = "tokens_used"
        case costUsd = "cost_usd"
        case confidenceScore = "confidence_score"
        case hasImages = "has_images"
        case mimeType = "mime_type"
    }
}

// MARK: - Health Response

struct HealthResponse: Codable {
    let status: String
    let version: String?
    let uptimeSeconds: Double?
    let databaseConnected: Bool?
    let memoryConnected: Bool?

    enum CodingKeys: String, CodingKey {
        case status, version
        case uptimeSeconds = "uptime_seconds"
        case databaseConnected = "database_connected"
        case memoryConnected = "memory_connected"
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

// MARK: - Scanner Models

struct ScannerBriefingResponse: Codable {
    let briefings: [ScannerBriefing]?
    let generatedAt: String?
    let sourceCount: Int?

    enum CodingKeys: String, CodingKey {
        case briefings
        case generatedAt = "generated_at"
        case sourceCount = "source_count"
    }
}

struct ScannerStatusResponse: Codable {
    let running: Bool
    let lastScanAt: String?
    let activeScanners: [String]?
    let totalScans: Int?

    enum CodingKeys: String, CodingKey {
        case running
        case lastScanAt = "last_scan_at"
        case activeScanners = "active_scanners"
        case totalScans = "total_scans"
    }
}

// MARK: - Background Task Models

struct BackgroundTaskInfo: Codable, Identifiable {
    let taskId: String
    let name: String
    let status: String
    let description: String?
    let startedAt: String?
    let completedAt: String?

    var id: String { taskId }

    enum CodingKeys: String, CodingKey {
        case name, status, description
        case taskId = "task_id"
        case startedAt = "started_at"
        case completedAt = "completed_at"
    }
}

struct BackgroundTaskDetail: Codable {
    let taskId: String
    let name: String
    let status: String
    let description: String?
    let startedAt: String?
    let completedAt: String?
    let progress: [TaskProgressEntry]?

    enum CodingKeys: String, CodingKey {
        case name, status, description, progress
        case taskId = "task_id"
        case startedAt = "started_at"
        case completedAt = "completed_at"
    }
}

struct TaskProgressEntry: Codable {
    let message: String
    let timestamp: String?
    let percent: Double?
    let step: String?
}

// MARK: - Memory Models

struct MemoryRecallResponse: Codable {
    let results: [MemoryResult]?
    let query: String?
}

struct MemoryResult: Codable, Identifiable {
    let memoryId: String?
    let content: String
    let relevance: Double?
    let metadata: [String: String]?

    var id: String { memoryId ?? String(content.prefix(20)) }

    enum CodingKeys: String, CodingKey {
        case content, relevance, metadata
        case memoryId = "id"
    }
}

struct MemoryStatsResponse: Codable {
    let totalMemories: Int?
    let totalDocuments: Int?

    enum CodingKeys: String, CodingKey {
        case totalMemories = "total_memories"
        case totalDocuments = "total_documents"
    }
}

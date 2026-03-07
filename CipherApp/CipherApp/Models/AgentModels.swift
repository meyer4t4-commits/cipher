import Foundation

// MARK: - Agent Models for Dashboard

struct AgentInfo: Codable, Identifiable {
    let name: String
    let description: String
    let version: String
    let capabilities: [AgentCapabilityInfo]

    var id: String { name }
}

struct AgentCapabilityInfo: Codable, Identifiable {
    let name: String
    let description: String
    let category: String
    let requiresApproval: Bool
    let timeoutSeconds: Int

    var id: String { name }

    enum CodingKeys: String, CodingKey {
        case name, description, category
        case requiresApproval = "requires_approval"
        case timeoutSeconds = "timeout_seconds"
    }
}

struct AgentListResponse: Codable {
    let agents: [AgentInfo]
    let total: Int
}

struct AgentExecutionResult: Codable, Identifiable {
    let taskId: String
    let agentName: String
    let success: Bool
    let output: AnyCodable?
    let error: String?
    let executionTimeMs: Int?
    let verified: Bool?
    let startedAt: String?
    let completedAt: String?

    var id: String { taskId }

    enum CodingKeys: String, CodingKey {
        case taskId = "task_id"
        case agentName = "agent_name"
        case success, output, error
        case executionTimeMs = "execution_time_ms"
        case verified
        case startedAt = "started_at"
        case completedAt = "completed_at"
    }
}

struct PendingApproval: Codable, Identifiable {
    let taskId: String
    let agentName: String
    let instruction: String
    let createdAt: String?

    var id: String { taskId }

    enum CodingKeys: String, CodingKey {
        case taskId = "task_id"
        case agentName = "agent_name"
        case instruction
        case createdAt = "created_at"
    }
}

struct PendingApprovalsResponse: Codable {
    let pending: Int
    let tasks: [PendingApproval]
}

// MARK: - Cron Models

struct CronTaskInfo: Codable, Identifiable {
    let taskId: String
    let name: String
    let cronExpression: String
    let agentName: String
    let operation: String
    let enabled: Bool
    let description: String
    let lastRun: String?
    let nextRun: String?
    let runCount: Int
    let lastError: String?

    var id: String { taskId }

    enum CodingKeys: String, CodingKey {
        case taskId = "task_id"
        case name
        case cronExpression = "cron_expression"
        case agentName = "agent_name"
        case operation, enabled, description
        case lastRun = "last_run"
        case nextRun = "next_run"
        case runCount = "run_count"
        case lastError = "last_error"
    }
}

struct CronListResponse: Codable {
    let total: Int
    let enabled: Int
    let tasks: [CronTaskInfo]
}

// MARK: - Execution History

struct ExecutionHistoryResponse: Codable {
    let total: Int
    let entries: [AgentExecutionResult]
}

// MARK: - Executor Status

struct ExecutorStatusResponse: Codable {
    let executor: ExecutorInfo
    let registry: RegistryInfo

    struct ExecutorInfo: Codable {
        let maxConcurrent: Int
        let pendingApprovals: Int
        let historyEntries: Int

        enum CodingKeys: String, CodingKey {
            case maxConcurrent = "max_concurrent"
            case pendingApprovals = "pending_approvals"
            case historyEntries = "history_entries"
        }
    }

    struct RegistryInfo: Codable {
        let agents: Int
        let agentNames: [String]

        enum CodingKeys: String, CodingKey {
            case agents
            case agentNames = "agent_names"
        }
    }
}

// MARK: - AnyCodable helper for dynamic JSON

struct AnyCodable: Codable {
    let value: Any

    init(_ value: Any) {
        self.value = value
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let string = try? container.decode(String.self) {
            value = string
        } else if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = double
        } else if let bool = try? container.decode(Bool.self) {
            value = bool
        } else if let dict = try? container.decode([String: AnyCodable].self) {
            value = dict.mapValues { $0.value }
        } else if let array = try? container.decode([AnyCodable].self) {
            value = array.map { $0.value }
        } else {
            value = NSNull()
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        if let string = value as? String {
            try container.encode(string)
        } else if let int = value as? Int {
            try container.encode(int)
        } else if let double = value as? Double {
            try container.encode(double)
        } else if let bool = value as? Bool {
            try container.encode(bool)
        } else {
            try container.encodeNil()
        }
    }
}

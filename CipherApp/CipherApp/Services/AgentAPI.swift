import Foundation

// MARK: - Agent & Cron API Extensions

extension CipherAPI {

    // MARK: - Agents

    /// Fetch all registered agents with their capabilities
    func fetchAgents() async throws -> [AgentInfo] {
        let endpoint = serverURL + AppConstants.apiBasePath + "/agents/agents"
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        let result = try decoder.decode(AgentListResponse.self, from: data)
        return result.agents
    }

    /// Fetch executor status (agent count, pending approvals, history)
    func fetchExecutorStatus() async throws -> ExecutorStatusResponse {
        let endpoint = serverURL + AppConstants.apiBasePath + "/agents/status"
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        return try decoder.decode(ExecutorStatusResponse.self, from: data)
    }

    /// Fetch pending approvals
    func fetchPendingApprovals() async throws -> [PendingApproval] {
        let endpoint = serverURL + AppConstants.apiBasePath + "/agents/approvals"
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        let result = try decoder.decode(PendingApprovalsResponse.self, from: data)
        return result.tasks
    }

    /// Approve a pending task
    func approveTask(taskId: String, approvedBy: String = "Mark", notes: String? = nil) async throws {
        let endpoint = serverURL + AppConstants.apiBasePath + "/agents/approve/\(taskId)"
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "approved_by": approvedBy,
            "notes": notes ?? ""
        ]
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (_, response) = try await session.data(for: urlRequest)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
    }

    /// Reject a pending task
    func rejectTask(taskId: String, reason: String = "Rejected by operator") async throws {
        let endpoint = serverURL + AppConstants.apiBasePath + "/agents/reject/\(taskId)?approved_by=Mark&reason=\(reason.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")"
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"

        let (_, response) = try await session.data(for: urlRequest)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
    }

    /// Fetch execution history
    func fetchExecutionHistory(limit: Int = 50) async throws -> [AgentExecutionResult] {
        let endpoint = serverURL + AppConstants.apiBasePath + "/agents/history?limit=\(limit)"
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        let result = try decoder.decode(ExecutionHistoryResponse.self, from: data)
        return result.entries
    }

    /// Execute a task with the given agent and instruction
    func executeTask(agentName: String, instruction: String) async throws -> AgentExecutionResult {
        let endpoint = serverURL + AppConstants.apiBasePath + "/agents/execute"
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.timeoutInterval = 120 // 2 min for long-running tasks

        let request: [String: Any] = [
            "agent_name": agentName,
            "instruction": instruction,
            "params": [:] as [String: String],
            "timeout_seconds": 90,
            "priority": 0
        ]

        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: request)

        let (data, response) = try await session.data(for: urlRequest)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            let errorMessage = String(data: data, encoding: .utf8) ?? "Unknown error"
            let code = (response as? HTTPURLResponse)?.statusCode ?? 0
            throw APIError.serverError(code, errorMessage)
        }

        do {
            return try decoder.decode(AgentExecutionResult.self, from: data)
        } catch {
            throw APIError.decodingError
        }
    }

    /// Execute a task with real-time streaming progress updates (SSE)
    /// Calls onProgress for each progress event, returns final result
    func executeTaskStreaming(
        agentName: String,
        instruction: String,
        params: [String: String] = [:],
        onProgress: @escaping (AgentProgressEvent) -> Void
    ) async throws -> AgentExecutionResult {
        let endpoint = serverURL + AppConstants.apiBasePath + "/agents/execute/stream"
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        urlRequest.timeoutInterval = 180 // 3 min for streaming

        let requestBody: [String: Any] = [
            "agent_name": agentName,
            "instruction": instruction,
            "params": params,
            "timeout_seconds": 120,
            "priority": 0
        ]

        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: requestBody)

        let (bytes, response) = try await session.bytes(for: urlRequest)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        var finalResult: AgentExecutionResult?
        var currentEventType = "progress"

        for try await line in bytes.lines {
            if line.hasPrefix("event: ") {
                currentEventType = String(line.dropFirst(7))
                continue
            }

            if line.hasPrefix("data: ") {
                let jsonStr = String(line.dropFirst(6))
                guard let jsonData = jsonStr.data(using: .utf8) else { continue }

                if currentEventType == "result" {
                    // Final result
                    if let result = try? JSONDecoder().decode(StreamingAgentResult.self, from: jsonData) {
                        finalResult = AgentExecutionResult(
                            taskId: result.taskId,
                            agentName: result.agentName,
                            success: result.success,
                            output: result.output.map { AnyCodable($0) },
                            error: result.error,
                            executionTimeMs: result.executionTimeMs.map { Int($0) },
                            verified: result.verified,
                            startedAt: nil,
                            completedAt: nil
                        )
                    }
                } else if currentEventType == "heartbeat" {
                    continue
                } else {
                    // Progress event
                    if let event = try? JSONDecoder().decode(AgentProgressEvent.self, from: jsonData) {
                        onProgress(event)
                    }
                }
            }
        }

        if let result = finalResult {
            return result
        }

        throw APIError.streamingError("No result received from streaming execution")
    }

    // MARK: - Cron Tasks

    /// Fetch all cron tasks
    func fetchCronTasks() async throws -> [CronTaskInfo] {
        let endpoint = serverURL + AppConstants.apiBasePath + "/cron/tasks"
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        let result = try decoder.decode(CronListResponse.self, from: data)
        return result.tasks
    }

    /// Enable a cron task
    func enableCronTask(taskId: String) async throws {
        let endpoint = serverURL + AppConstants.apiBasePath + "/cron/tasks/\(taskId)/enable"
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"

        let (_, response) = try await session.data(for: urlRequest)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
    }

    /// Disable a cron task
    func disableCronTask(taskId: String) async throws {
        let endpoint = serverURL + AppConstants.apiBasePath + "/cron/tasks/\(taskId)/disable"
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"

        let (_, response) = try await session.data(for: urlRequest)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
    }

    /// Manually trigger a cron task
    func triggerCronTask(taskId: String) async throws {
        let endpoint = serverURL + AppConstants.apiBasePath + "/cron/tasks/\(taskId)/run"
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"

        let (_, response) = try await session.data(for: urlRequest)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
    }

    /// Delete a cron task
    func deleteCronTask(taskId: String) async throws {
        let endpoint = serverURL + AppConstants.apiBasePath + "/cron/tasks/\(taskId)"
        guard let url = URL(string: endpoint) else { throw APIError.invalidURL }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "DELETE"

        let (_, response) = try await session.data(for: urlRequest)
        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw APIError.invalidResponse
        }
    }

    /// Create a new cron task
    func createCronTask(_ task: CronTaskInfo) async throws {
        let endpoint = serverURL + AppConstants.apiBasePath + "/cron/tasks"
        guard let url = URL(string: endpoint) else { throw APIError.invalidURL }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = try encoder.encode(task)

        let (_, response) = try await session.data(for: urlRequest)
        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw APIError.invalidResponse
        }
    }

    // MARK: - Spawn Sessions (Multi-Agent)

    /// Spawn multiple agents concurrently
    func spawnBatch(tasks: [SpawnTaskItem]) async throws -> SpawnBatchResponse {
        let endpoint = serverURL + AppConstants.apiBasePath + "/agents/spawn-batch"
        guard let url = URL(string: endpoint) else { throw APIError.invalidURL }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let request = SpawnBatchRequest(tasks: tasks, spawnSessionId: nil)
        urlRequest.httpBody = try encoder.encode(request)

        let (data, response) = try await session.data(for: urlRequest)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        return try decoder.decode(SpawnBatchResponse.self, from: data)
    }

    /// Poll spawn session status
    func getSpawnSessionStatus(sessionId: String) async throws -> SpawnSessionStatusResponse {
        let endpoint = serverURL + AppConstants.apiBasePath + "/agents/spawn-session/\(sessionId)"
        guard let url = URL(string: endpoint) else { throw APIError.invalidURL }

        let (data, response) = try await session.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        return try decoder.decode(SpawnSessionStatusResponse.self, from: data)
    }

    /// Cancel a running task
    func cancelTask(taskId: String) async throws {
        let endpoint = serverURL + AppConstants.apiBasePath + "/agents/cancel/\(taskId)"
        guard let url = URL(string: endpoint) else { throw APIError.invalidURL }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"

        let (_, response) = try await session.data(for: urlRequest)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
    }

    // MARK: - Agent Interactions (Clarifying Questions)

    /// Get pending clarifying questions from agents
    func getPendingInteractions() async throws -> PendingInteractionsResponse {
        let endpoint = serverURL + AppConstants.apiBasePath + "/agents/interactions/pending"
        guard let url = URL(string: endpoint) else { throw APIError.invalidURL }

        let (data, response) = try await session.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        return try decoder.decode(PendingInteractionsResponse.self, from: data)
    }

    /// Answer an agent's clarifying question
    func answerInteraction(interactionId: String, userResponse: String) async throws -> InteractionAnswerResponse {
        let endpoint = serverURL + AppConstants.apiBasePath + "/agents/interactions/\(interactionId)/answer"
        guard let url = URL(string: endpoint) else { throw APIError.invalidURL }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: ["response": userResponse])

        let (data, response) = try await session.data(for: urlRequest)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        return try decoder.decode(InteractionAnswerResponse.self, from: data)
    }

    /// Dismiss an agent's question
    func dismissInteraction(interactionId: String) async throws {
        let endpoint = serverURL + AppConstants.apiBasePath + "/agents/interactions/\(interactionId)/dismiss"
        guard let url = URL(string: endpoint) else { throw APIError.invalidURL }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"

        let (_, response) = try await session.data(for: urlRequest)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
    }

    // MARK: - Notifications

    /// Register device for push notifications
    func registerNotificationDevice(deviceToken: String, deviceName: String, platform: String = "ios") async throws {
        let endpoint = serverURL + AppConstants.apiBasePath.replacingOccurrences(of: "/api/v1", with: "") + "/api/v1/notifications/register-device"
        guard let url = URL(string: endpoint) else { throw APIError.invalidURL }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "device_token": deviceToken,
            "user_id": "mark",
            "device_name": deviceName,
            "platform": platform,
        ]
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (_, response) = try await session.data(for: urlRequest)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
    }

    // MARK: - Scanner (Intelligence Briefings)

    /// Get the latest intelligence briefing
    func getLatestBriefing() async throws -> ScannerBriefingResponse {
        let endpoint = serverURL + "/api/v1/scanner/briefing"
        guard let url = URL(string: endpoint) else { throw APIError.invalidURL }

        let (data, response) = try await session.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        return try decoder.decode(ScannerBriefingResponse.self, from: data)
    }

    /// Get scanner status
    func getScannerStatus() async throws -> ScannerStatusResponse {
        let endpoint = serverURL + "/api/v1/scanner/status"
        guard let url = URL(string: endpoint) else { throw APIError.invalidURL }

        let (data, response) = try await session.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        return try decoder.decode(ScannerStatusResponse.self, from: data)
    }

    /// Trigger a full scan
    func triggerFullScan() async throws {
        let endpoint = serverURL + "/api/v1/scanner/scan"
        guard let url = URL(string: endpoint) else { throw APIError.invalidURL }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"

        let (_, response) = try await session.data(for: urlRequest)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
    }

    // MARK: - Background Tasks

    /// List all background tasks
    func getBackgroundTasks(status: String? = nil) async throws -> [BackgroundTaskInfo] {
        var endpoint = serverURL + "/api/v1/tasks/"
        if let status = status {
            endpoint += "?status=\(status)"
        }
        guard let url = URL(string: endpoint) else { throw APIError.invalidURL }

        let (data, response) = try await session.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        return try decoder.decode([BackgroundTaskInfo].self, from: data)
    }

    /// Get a single task status
    func getTaskStatus(taskId: String) async throws -> BackgroundTaskDetail {
        let endpoint = serverURL + "/api/v1/tasks/\(taskId)"
        guard let url = URL(string: endpoint) else { throw APIError.invalidURL }

        let (data, response) = try await session.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        return try decoder.decode(BackgroundTaskDetail.self, from: data)
    }

    /// Cancel a background task
    func cancelBackgroundTask(taskId: String) async throws {
        let endpoint = serverURL + "/api/v1/tasks/\(taskId)/cancel"
        guard let url = URL(string: endpoint) else { throw APIError.invalidURL }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"

        let (_, response) = try await session.data(for: urlRequest)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
    }

    // MARK: - Memory (Long-Term)

    /// Store a memory
    func storeMemory(content: String, tags: String? = nil) async throws {
        let endpoint = serverURL + "/api/v1/memory/store"
        guard let url = URL(string: endpoint) else { throw APIError.invalidURL }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = ["content": content]
        if let tags = tags { body["tags"] = tags }
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (_, response) = try await session.data(for: urlRequest)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
    }

    /// Recall memories by query
    func recallMemories(query: String, limit: Int = 5) async throws -> MemoryRecallResponse {
        let endpoint = serverURL + "/api/v1/memory/recall"
        guard let url = URL(string: endpoint) else { throw APIError.invalidURL }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: [
            "query": query,
            "n_results": limit,
        ] as [String: Any])

        let (data, response) = try await session.data(for: urlRequest)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        return try decoder.decode(MemoryRecallResponse.self, from: data)
    }

    /// Get memory stats
    func getMemoryStats() async throws -> MemoryStatsResponse {
        let endpoint = serverURL + "/api/v1/memory/stats"
        guard let url = URL(string: endpoint) else { throw APIError.invalidURL }

        let (data, response) = try await session.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        return try decoder.decode(MemoryStatsResponse.self, from: data)
    }

    /// Send test notification
    func sendTestNotification() async throws {
        let endpoint = serverURL + AppConstants.apiBasePath.replacingOccurrences(of: "/api/v1", with: "") + "/api/v1/notifications/test"
        guard let url = URL(string: endpoint) else { throw APIError.invalidURL }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: [
            "title": "Test from Cipher",
            "body": "Push notifications are working!",
        ])

        let (_, response) = try await session.data(for: urlRequest)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
    }
}

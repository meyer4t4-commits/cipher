import Foundation

// MARK: - Agent & Cron API Extensions

extension OrchidAPI {

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

        let request: [String: Any] = [
            "agent_name": agentName,
            "instruction": instruction,
            "params": [:],
            "timeout_seconds": 30,
            "priority": "normal"
        ]

        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: request)

        let (data, response) = try await session.data(for: urlRequest)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            let errorMessage = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw APIError.serverError(httpResponse.statusCode, errorMessage)
        }

        do {
            return try decoder.decode(AgentExecutionResult.self, from: data)
        } catch {
            throw APIError.decodingError
        }
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
}

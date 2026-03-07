import Foundation

// MARK: - Agents ViewModel

@Observable
@MainActor
class AgentsViewModel {
    var agents: [AgentInfo] = []
    var totalAgents = 0
    var isLoading = false
    var errorMessage: String?

    @ObservationIgnored let api = OrchidAPI.shared

    func loadAgents() async {
        isLoading = true
        errorMessage = nil

        do {
            agents = try await api.fetchAgents()
            totalAgents = agents.count
        } catch {
            agents = []
            errorMessage = "Failed to load agents: \(error.localizedDescription)"
        }

        isLoading = false
    }

    func executeTask(agentName: String, instruction: String) async throws -> AgentExecutionResult {
        return try await api.executeTask(agentName: agentName, instruction: instruction)
    }
}

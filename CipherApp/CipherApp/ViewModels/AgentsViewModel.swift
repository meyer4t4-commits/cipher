import Foundation

// MARK: - Agents ViewModel

@Observable
@MainActor
class AgentsViewModel {
    // All 29 agents from local catalog
    var agents: [AgentDefinition] = AgentDefinition.all
    var selectedCategory: AgentCategory?
    var searchText = ""
    var isLoading = false
    var errorMessage: String?
    var serverOnline = false

    // Execution state
    var executingAgentId: String?
    var executionInstruction = ""
    var lastResult: AgentExecutionResult?

    // Multi-select & spawn
    var isMultiSelectMode = false
    var selectedAgents: Set<String> = []
    var spawnInstruction = ""
    var showSpawnSheet = false

    // Active spawns
    var hasActiveSpawns = false
    var pendingInteractionCount = 0

    @ObservationIgnored let api = CipherAPI.shared

    var filteredAgents: [AgentDefinition] {
        var result = agents

        if let category = selectedCategory {
            result = result.filter { $0.category == category }
        }

        if !searchText.isEmpty {
            result = result.filter { agent in
                agent.displayName.localizedCaseInsensitiveContains(searchText) ||
                agent.description.localizedCaseInsensitiveContains(searchText) ||
                agent.category.rawValue.localizedCaseInsensitiveContains(searchText) ||
                agent.purpose.localizedCaseInsensitiveContains(searchText)
            }
        }

        return result
    }

    var categoryAgentCounts: [AgentCategory: Int] {
        var counts: [AgentCategory: Int] = [:]
        for cat in AgentCategory.allCases {
            counts[cat] = agents.filter { $0.category == cat }.count
        }
        return counts
    }

    func checkServerStatus() async {
        do {
            _ = try await api.fetchExecutorStatus()
            serverOnline = true
        } catch {
            serverOnline = false
        }
    }

    func executeAgent(_ agent: AgentDefinition, instruction: String) async {
        executingAgentId = agent.id
        errorMessage = nil

        do {
            lastResult = try await api.executeTask(agentName: agent.name, instruction: instruction)
        } catch {
            errorMessage = "Execution failed: \(error.localizedDescription)"
        }

        executingAgentId = nil
    }

    // MARK: - Multi-Select

    func toggleAgentSelection(_ agent: AgentDefinition) {
        if selectedAgents.contains(agent.id) {
            selectedAgents.remove(agent.id)
        } else {
            selectedAgents.insert(agent.id)
        }
    }

    func exitMultiSelect() {
        isMultiSelectMode = false
        selectedAgents.removeAll()
        spawnInstruction = ""
    }

    var selectedAgentDefinitions: [AgentDefinition] {
        agents.filter { selectedAgents.contains($0.id) }
    }

    // MARK: - Multi-Spawn

    func spawnSelected(instruction: String) async {
        guard !selectedAgents.isEmpty else { return }
        isLoading = true
        errorMessage = nil

        let tasks = selectedAgentDefinitions.map { agent in
            SpawnTaskItem(agentName: agent.name, instruction: instruction)
        }

        do {
            _ = try await api.spawnBatch(tasks: tasks)
            hasActiveSpawns = true
            exitMultiSelect()
        } catch {
            errorMessage = "Spawn failed: \(error.localizedDescription)"
        }

        isLoading = false
    }

    // MARK: - Interaction Badge

    func refreshInteractionCount() async {
        do {
            let response = try await api.getPendingInteractions()
            pendingInteractionCount = response.total
        } catch {
            // Silently fail
        }
    }
}

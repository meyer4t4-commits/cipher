import Foundation

// MARK: - Dashboard ViewModel

@Observable
@MainActor
class DashboardViewModel {
    var agents: [AgentInfo] = []
    var cronTasks: [CronTaskInfo] = []
    var pendingApprovals: [PendingApproval] = []
    var executionHistory: [AgentExecutionResult] = []
    var totalAgents = 0
    var isLoading = false
    var errorMessage: String?

    @ObservationIgnored let api = CipherAPI.shared

    func loadAll() async {
        isLoading = true
        errorMessage = nil

        async let agentsTask: () = loadAgents()
        async let cronTask: () = loadCronTasks()
        async let approvalsTask: () = loadPendingApprovals()
        async let historyTask: () = loadHistory()

        await agentsTask
        await cronTask
        await approvalsTask
        await historyTask

        isLoading = false
    }

    func loadAgents() async {
        do {
            agents = try await api.fetchAgents()
            totalAgents = agents.count
        } catch {
            agents = []
        }
    }

    func loadCronTasks() async {
        do {
            cronTasks = try await api.fetchCronTasks()
        } catch {
            cronTasks = []
        }
    }

    func loadPendingApprovals() async {
        do {
            pendingApprovals = try await api.fetchPendingApprovals()
        } catch {
            pendingApprovals = []
        }
    }

    func loadHistory() async {
        do {
            executionHistory = try await api.fetchExecutionHistory(limit: 20)
        } catch {
            executionHistory = []
        }
    }

    func approveTask(_ taskId: String) async {
        do {
            try await api.approveTask(taskId: taskId)
            await loadPendingApprovals()
        } catch {
            errorMessage = "Failed to approve: \(error.localizedDescription)"
        }
    }

    func rejectTask(_ taskId: String) async {
        do {
            try await api.rejectTask(taskId: taskId)
            await loadPendingApprovals()
        } catch {
            errorMessage = "Failed to reject: \(error.localizedDescription)"
        }
    }

    func toggleCronTask(_ taskId: String, enable: Bool) async {
        do {
            if enable {
                try await api.enableCronTask(taskId: taskId)
            } else {
                try await api.disableCronTask(taskId: taskId)
            }
            await loadCronTasks()
        } catch {
            errorMessage = "Failed to toggle task: \(error.localizedDescription)"
        }
    }

    func triggerCronTask(_ taskId: String) async {
        do {
            try await api.triggerCronTask(taskId: taskId)
            await loadCronTasks()
        } catch {
            errorMessage = "Failed to trigger: \(error.localizedDescription)"
        }
    }
}

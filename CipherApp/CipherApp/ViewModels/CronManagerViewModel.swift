import Foundation
import SwiftUI

// MARK: - Cron Manager ViewModel

@Observable
@MainActor
class CronManagerViewModel {
    var cronTasks: [CronTaskInfo] = []
    var isLoading = false
    var errorMessage: String?

    @ObservationIgnored let api = CipherAPI.shared

    // MARK: - Computed Properties

    /// Get all enabled cron tasks
    var activeTasks: [CronTaskInfo] {
        cronTasks.filter { $0.enabled }
    }

    /// Get all disabled cron tasks
    var pausedTasks: [CronTaskInfo] {
        cronTasks.filter { !$0.enabled }
    }

    // MARK: - Fetch Tasks

    /// Fetch all cron tasks from the server
    func fetchCronTasks() async {
        isLoading = true
        errorMessage = nil

        do {
            cronTasks = try await api.fetchCronTasks()
        } catch {
            errorMessage = "Failed to fetch cron tasks: \(error.localizedDescription)"
            cronTasks = []
        }

        isLoading = false
    }

    // MARK: - Task Management

    /// Toggle a cron task between enabled and disabled
    func toggleTask(taskId: String, enabled: Bool) async {
        do {
            if enabled {
                try await api.enableCronTask(taskId: taskId)
            } else {
                try await api.disableCronTask(taskId: taskId)
            }

            // Update local state
            if let index = cronTasks.firstIndex(where: { $0.taskId == taskId }) {
                cronTasks[index].enabled = enabled
            }
        } catch {
            errorMessage = "Failed to toggle task: \(error.localizedDescription)"
        }
    }

    /// Manually trigger a cron task to run immediately
    func triggerTask(taskId: String) async {
        do {
            try await api.triggerCronTask(taskId: taskId)
            await fetchCronTasks()
        } catch {
            errorMessage = "Failed to trigger task: \(error.localizedDescription)"
        }
    }

    /// Delete a cron task
    func deleteTask(taskId: String) async {
        do {
            try await api.deleteCronTask(taskId: taskId)
            cronTasks.removeAll { $0.taskId == taskId }
        } catch {
            errorMessage = "Failed to delete task: \(error.localizedDescription)"
        }
    }

    /// Create a new cron task
    func createTask(_ task: CronTaskInfo) async {
        do {
            try await api.createCronTask(task)
            await fetchCronTasks()
        } catch {
            errorMessage = "Failed to create task: \(error.localizedDescription)"
        }
    }
}

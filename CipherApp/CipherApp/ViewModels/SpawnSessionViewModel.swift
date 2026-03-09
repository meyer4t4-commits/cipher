import Foundation
import SwiftUI

// MARK: - Spawn Session ViewModel

@Observable
@MainActor
class SpawnSessionViewModel {
    var currentSessionId: String?
    var runningAgents: [RunningAgentStatus] = []
    var summary: SpawnSessionSummary?
    var isLoading = false
    var errorMessage: String?

    @ObservationIgnored let api = CipherAPI.shared
    @ObservationIgnored let haptics = HapticsService.shared
    @ObservationIgnored var pollTask: Task<Void, Never>?

    // MARK: - Computed Properties

    var isActive: Bool {
        summary?.running ?? 0 > 0
    }

    // MARK: - Spawn Multiple Agents

    /// Spawn multiple agents concurrently and start polling for status
    func spawnMultiple(tasks: [SpawnTaskItem]) async {
        isLoading = true
        errorMessage = nil

        do {
            let response = try await api.spawnBatch(tasks: tasks)
            self.currentSessionId = response.spawnSessionId
            haptics.success()

            // Start polling immediately
            startPolling()
        } catch {
            errorMessage = "Failed to spawn agents: \(error.localizedDescription)"
            haptics.error()
        }

        isLoading = false
    }

    // MARK: - Status Management

    /// Refresh spawn session status
    func refreshStatus() async {
        guard let sessionId = currentSessionId else {
            errorMessage = "No active session"
            return
        }

        do {
            let response = try await api.getSpawnSessionStatus(sessionId: sessionId)
            self.runningAgents = response.tasks
            self.summary = response.summary

            // Stop polling if no more running tasks
            if response.summary.running == 0 {
                stopPolling()
            }
        } catch {
            errorMessage = "Failed to refresh status: \(error.localizedDescription)"
        }
    }

    /// Cancel a specific agent task
    func cancelAgent(taskId: String) async {
        do {
            try await api.cancelTask(taskId: taskId)
            haptics.warning()
            // Refresh status after cancellation
            await refreshStatus()
        } catch {
            errorMessage = "Failed to cancel agent: \(error.localizedDescription)"
            haptics.error()
        }
    }

    // MARK: - Polling

    /// Start polling for status updates every 2 seconds
    func startPolling() {
        stopPolling()
        pollTask = Task { @MainActor [weak self] in
            while !Task.isCancelled {
                await self?.refreshStatus()
                try? await Task.sleep(nanoseconds: 2_000_000_000)
            }
        }
    }

    /// Stop polling for status updates
    func stopPolling() {
        pollTask?.cancel()
        pollTask = nil
    }

    deinit {
        pollTask?.cancel()
        pollTask = nil
    }
}

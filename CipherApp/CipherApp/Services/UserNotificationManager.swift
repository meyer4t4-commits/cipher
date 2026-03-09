import Foundation
import UserNotifications
import SwiftUI

// MARK: - User Notification Manager

@Observable
class UserNotificationManager: NSObject, UNUserNotificationCenterDelegate {
    static let shared = UserNotificationManager()

    var deviceToken: String?
    var lastNotification: [AnyHashable: Any]?

    override init() {
        super.init()
        UNUserNotificationCenter.current().delegate = self
    }

    // MARK: - Authorization

    /// Request notification permissions from the user
    func requestAuthorization() async {
        do {
            let granted = try await UNUserNotificationCenter.current()
                .requestAuthorization(options: [.alert, .sound, .badge])

            if granted {
                await MainActor.run {
                    UIApplication.shared.registerForRemoteNotifications()
                }
            }
        } catch {
            print("Failed to request notification authorization: \(error.localizedDescription)")
        }
    }

    // MARK: - Notification Settings

    /// Get current notification settings
    func getNotificationSettings() async -> UNNotificationSettings {
        return await UNUserNotificationCenter.current().notificationSettings()
    }

    // MARK: - UNUserNotificationCenterDelegate Methods

    /// Handle notifications when app is in foreground
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        let userInfo = notification.request.content.userInfo
        self.lastNotification = userInfo

        // Post notification to notify observers
        NotificationCenter.default.post(
            name: NSNotification.Name("AgentNotificationReceived"),
            object: nil,
            userInfo: userInfo
        )

        // Show banner and sound even in foreground
        completionHandler([.banner, .sound, .badge])
    }

    /// Handle notification tap
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        let userInfo = response.notification.request.content.userInfo
        self.lastNotification = userInfo

        // Extract task_id or interaction_id from userInfo
        let notificationData: [AnyHashable: Any] = userInfo

        // Post notification with interaction details
        NotificationCenter.default.post(
            name: NSNotification.Name("OpenAgentInteraction"),
            object: nil,
            userInfo: notificationData
        )

        completionHandler()
    }
}

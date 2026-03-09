import SwiftUI

// MARK: - Main Tab View

struct MainTabView: View {
    @State private var selectedTab = 0
    @State private var previousTab = 0
    @State private var pendingInteractions = 0
    @State private var newChatTrigger = UUID()

    init() {
        // Customize tab bar appearance
        let appearance = UITabBarAppearance()
        appearance.configureWithOpaqueBackground()
        appearance.backgroundColor = UIColor(CipherTheme.background)
        appearance.shadowColor = UIColor(CipherTheme.border)

        // Normal state
        appearance.stackedLayoutAppearance.normal.iconColor = UIColor(CipherTheme.textTertiary)
        appearance.stackedLayoutAppearance.normal.titleTextAttributes = [
            .foregroundColor: UIColor(CipherTheme.textTertiary),
            .font: UIFont.systemFont(ofSize: 10, weight: .medium)
        ]

        // Selected state
        appearance.stackedLayoutAppearance.selected.iconColor = UIColor(CipherTheme.accent)
        appearance.stackedLayoutAppearance.selected.titleTextAttributes = [
            .foregroundColor: UIColor(CipherTheme.accent),
            .font: UIFont.systemFont(ofSize: 10, weight: .bold)
        ]

        UITabBar.appearance().standardAppearance = appearance
        UITabBar.appearance().scrollEdgeAppearance = appearance
    }

    var body: some View {
        TabView(selection: $selectedTab) {
            ChatView()
                .id(newChatTrigger)
                .tabItem {
                    Image(systemName: selectedTab == 0 ? "bubble.left.and.bubble.right.fill" : "bubble.left.and.bubble.right")
                    Text("Chat")
                }
                .tag(0)

            AgentsView()
                .tabItem {
                    Image(systemName: selectedTab == 1 ? "cpu.fill" : "cpu")
                    Text("Brains")
                }
                .tag(1)
                .badge(pendingInteractions)

            ProjectsView()
                .tabItem {
                    Image(systemName: selectedTab == 2 ? "folder.fill" : "folder")
                    Text("My Projects")
                }
                .tag(2)

            ResearchView()
                .tabItem {
                    Image(systemName: selectedTab == 3 ? "brain.fill" : "brain")
                    Text("Research")
                }
                .tag(3)

            SettingsView()
                .tabItem {
                    Image(systemName: selectedTab == 4 ? "gearshape.fill" : "gearshape")
                    Text("Settings")
                }
                .tag(4)
        }
        .tint(CipherTheme.accent)
        .onChange(of: selectedTab) { oldValue, newValue in
            previousTab = oldValue
            HapticsService.shared.selection()
        }
        .task {
            await refreshInteractionBadge()
        }
        .onReceive(NotificationCenter.default.publisher(for: NSNotification.Name("AgentNotificationReceived"))) { _ in
            Task { await refreshInteractionBadge() }
        }
    }

    private func refreshInteractionBadge() async {
        do {
            let response = try await CipherAPI.shared.getPendingInteractions()
            await MainActor.run {
                pendingInteractions = response.total
            }
        } catch {
            // Silently fail
        }
    }
}

#Preview {
    MainTabView()
}

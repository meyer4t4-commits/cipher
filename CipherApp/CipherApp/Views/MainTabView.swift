import SwiftUI

// MARK: - Main Tab View

struct MainTabView: View {
    @State private var selectedTab = 0
    @State private var previousTab = 0

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
                .tabItem {
                    Image(systemName: selectedTab == 0 ? "bubble.left.and.bubble.right.fill" : "bubble.left.and.bubble.right")
                    Text("Chat")
                }
                .tag(0)

            AgentsView()
                .tabItem {
                    Image(systemName: selectedTab == 1 ? "cpu.fill" : "cpu")
                    Text("Agents")
                }
                .tag(1)

            ConversationListView()
                .tabItem {
                    Image(systemName: selectedTab == 2 ? "clock.fill" : "clock")
                    Text("History")
                }
                .tag(2)

            SettingsView()
                .tabItem {
                    Image(systemName: selectedTab == 3 ? "gearshape.fill" : "gearshape")
                    Text("Settings")
                }
                .tag(3)
        }
        .tint(CipherTheme.accent)
        .onChange(of: selectedTab) { oldValue, _ in
            previousTab = oldValue
            HapticsService.shared.selection()
        }
    }
}

#Preview {
    MainTabView()
}

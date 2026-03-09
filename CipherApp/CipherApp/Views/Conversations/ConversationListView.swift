import SwiftUI

// MARK: - Conversation List View

struct ConversationListView: View {
    @State private var conversations: [Conversation] = []
    @State private var selectedConversationId: UUID?
    @State private var searchText = ""
    @State private var isLoading = false
    @State private var showNewChat = false

    private var filteredConversations: [Conversation] {
        if searchText.isEmpty {
            return conversations
        }
        let lowered = searchText.lowercased()
        return conversations.filter {
            $0.title.lowercased().contains(lowered) ||
            $0.messages.contains { $0.content.lowercased().contains(lowered) }
        }
    }

    private var groupedConversations: [(String, [Conversation])] {
        let grouped = Dictionary(grouping: filteredConversations) { conversation in
            conversation.lastMessageTime.sectionHeader()
        }
        let order = ["Today", "Yesterday"]
        return grouped.sorted { a, b in
            let aIdx = order.firstIndex(of: a.key) ?? 100
            let bIdx = order.firstIndex(of: b.key) ?? 100
            if aIdx != bIdx { return aIdx < bIdx }
            return a.key < b.key
        }
    }

    var body: some View {
        NavigationStack {
            ZStack {
                CipherTheme.background.ignoresSafeArea()

                VStack(spacing: 0) {
                    // Header
                    conversationHeader

                    if isLoading {
                        Spacer()
                        LoadingView()
                        Spacer()
                    } else if conversations.isEmpty {
                        emptyState
                    } else {
                        // Search bar
                        searchBar

                        // Conversation list
                        ScrollView {
                            LazyVStack(spacing: 0, pinnedViews: [.sectionHeaders]) {
                                ForEach(groupedConversations, id: \.0) { section, convos in
                                    Section {
                                        ForEach(convos) { conversation in
                                            NavigationLink(destination: ChatView(conversation: conversation)) {
                                                ConversationRow(
                                                    conversation: conversation,
                                                    isSelected: selectedConversationId == conversation.id,
                                                    onDelete: {
                                                        deleteConversation(conversation)
                                                    },
                                                    onPin: {
                                                        togglePin(conversation)
                                                    }
                                                )
                                            }
                                            .simultaneousGesture(TapGesture().onEnded {
                                                selectedConversationId = conversation.id
                                                HapticsService.shared.lightTap()
                                            })
                                        }
                                    } header: {
                                        sectionHeader(section)
                                    }
                                }
                            }
                            .padding(.horizontal, Spacing.md)
                            // Extra bottom padding so FAB doesn't cover last row
                            Spacer(minLength: 80)
                        }
                    }
                }

                // Floating "New Chat" button — always visible when conversations exist
                if !conversations.isEmpty && !isLoading {
                    VStack {
                        Spacer()
                        HStack {
                            Spacer()
                            NavigationLink(destination: ChatView()) {
                                HStack(spacing: 8) {
                                    Image(systemName: "plus")
                                        .font(.system(size: 16, weight: .bold))
                                    Text("New Chat")
                                        .font(.system(size: 15, weight: .bold))
                                }
                                .foregroundColor(.white)
                                .padding(.horizontal, 20)
                                .padding(.vertical, 14)
                                .background(CipherTheme.accentGradient)
                                .clipShape(Capsule())
                                .shadow(color: CipherTheme.accent.opacity(0.4), radius: 12, y: 4)
                            }
                            .padding(.trailing, Spacing.lg)
                            .padding(.bottom, Spacing.lg)
                        }
                    }
                }
            }
        }
        .onAppear { loadConversations() }
        .onReceive(NotificationCenter.default.publisher(for: NSNotification.Name("ConversationUpdated"))) { _ in
            loadConversations()
        }
    }

    // MARK: - Header

    private var conversationHeader: some View {
        HStack(spacing: Spacing.md) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Conversations")
                    .font(.system(size: 22, weight: .bold))
                    .foregroundColor(CipherTheme.textPrimary)

                Text("\(conversations.count) total")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundColor(CipherTheme.textTertiary)
            }

            Spacer()

            NavigationLink(destination: ChatView()) {
                Image(systemName: "plus.circle.fill")
                    .font(.system(size: 24))
                    .foregroundStyle(CipherTheme.accentGradient)
            }
        }
        .padding(.horizontal, Spacing.lg)
        .padding(.vertical, Spacing.md)
    }

    // MARK: - Search

    private var searchBar: some View {
        HStack(spacing: Spacing.sm) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 14, weight: .medium))
                .foregroundColor(CipherTheme.textTertiary)

            TextField("Search conversations...", text: $searchText)
                .font(.system(size: 15))
                .foregroundColor(CipherTheme.textPrimary)

            if !searchText.isEmpty {
                Button(action: { searchText = "" }) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 14))
                        .foregroundColor(CipherTheme.textTertiary)
                }
            }
        }
        .padding(.horizontal, Spacing.md)
        .padding(.vertical, Spacing.sm)
        .background(
            RoundedRectangle(cornerRadius: CornerRadius.md)
                .fill(CipherTheme.surfaceElevated)
                .overlay(
                    RoundedRectangle(cornerRadius: CornerRadius.md)
                        .stroke(CipherTheme.border, lineWidth: 0.5)
                )
        )
        .padding(.horizontal, Spacing.lg)
        .padding(.bottom, Spacing.sm)
    }

    // MARK: - Section Header

    private func sectionHeader(_ title: String) -> some View {
        HStack {
            Text(title)
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(CipherTheme.textTertiary)
                .textCase(.uppercase)
                .tracking(0.5)

            Spacer()
        }
        .padding(.horizontal, Spacing.xxs)
        .padding(.vertical, Spacing.sm)
        .background(CipherTheme.background)
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: Spacing.xl) {
            Spacer()

            CipherLogo(size: 64, animated: true)

            Text("No Conversations Yet")
                .font(.system(size: 18, weight: .semibold))
                .foregroundColor(CipherTheme.textPrimary)

            Text("Start a new conversation with Cipher")
                .font(.system(size: 14))
                .foregroundColor(CipherTheme.textSecondary)

            NavigationLink(destination: ChatView()) {
                HStack(spacing: Spacing.sm) {
                    Image(systemName: "plus")
                        .font(.system(size: 14, weight: .bold))
                    Text("New Chat")
                        .font(.system(size: 15, weight: .semibold))
                }
                .foregroundColor(.white)
                .padding(.horizontal, Spacing.xl)
                .padding(.vertical, Spacing.md)
                .background(CipherTheme.accentGradient)
                .clipShape(Capsule())
            }

            Spacer()
        }
    }

    // MARK: - Actions

    private func loadConversations() {
        isLoading = true
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
            conversations = ConversationStorage.shared.loadAllConversations()
            isLoading = false
        }
    }

    private func deleteConversation(_ conversation: Conversation) {
        ConversationStorage.shared.deleteConversation(id: conversation.id)
        withAnimation {
            conversations.removeAll { $0.id == conversation.id }
        }
        if selectedConversationId == conversation.id {
            selectedConversationId = nil
        }
    }

    private func togglePin(_ conversation: Conversation) {
        if let index = conversations.firstIndex(where: { $0.id == conversation.id }) {
            conversations[index].isPinned.toggle()
            ConversationStorage.shared.saveConversation(conversations[index])
        }
    }
}

#Preview {
    ConversationListView()
}

import SwiftUI

// MARK: - Agents View

struct AgentsView: View {
    @State private var viewModel = AgentsViewModel()
    @State private var searchText = ""
    @State private var selectedAgent: AgentInfo?
    @State private var showDetailSheet = false
    @State private var gridLayout = [GridItem(.flexible()), GridItem(.flexible())]

    var filteredAgents: [AgentInfo] {
        if searchText.isEmpty {
            return viewModel.agents
        }
        return viewModel.agents.filter { agent in
            agent.name.localizedCaseInsensitiveContains(searchText) ||
            agent.description.localizedCaseInsensitiveContains(searchText)
        }
    }

    var body: some View {
        NavigationStack {
            ZStack {
                CipherTheme.background.ignoresSafeArea()

                ScrollView(.vertical, showsIndicators: false) {
                    VStack(spacing: Spacing.lg) {
                        // Stats Header
                        statsHeader

                        // Search Bar
                        HStack {
                            Image(systemName: "magnifyingglass")
                                .foregroundColor(CipherTheme.textTertiary)
                            TextField("Search agents...", text: $searchText)
                                .textFieldStyle(.plain)
                                .foregroundColor(CipherTheme.textPrimary)
                            if !searchText.isEmpty {
                                Button(action: { searchText = "" }) {
                                    Image(systemName: "xmark.circle.fill")
                                        .foregroundColor(CipherTheme.textTertiary)
                                }
                            }
                        }
                        .padding(Spacing.md)
                        .background(CipherTheme.surface)
                        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
                        .padding(.horizontal, Spacing.lg)

                        // Loading or Empty State
                        if viewModel.isLoading {
                            loadingView
                        } else if filteredAgents.isEmpty {
                            emptyState
                        } else {
                            // Agents Grid
                            LazyVGrid(columns: gridLayout, spacing: Spacing.lg) {
                                ForEach(filteredAgents) { agent in
                                    AgentGridCard(agent: agent) {
                                        selectedAgent = agent
                                        showDetailSheet = true
                                    }
                                }
                            }
                            .padding(.horizontal, Spacing.lg)
                        }

                        Spacer(minLength: Spacing.xxxl)
                    }
                    .padding(.vertical, Spacing.md)
                }
            }
            .navigationTitle("Agents")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        Task { await viewModel.loadAgents() }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                            .foregroundColor(CipherTheme.accent)
                    }
                }
            }
            .task {
                await viewModel.loadAgents()
            }
            .refreshable {
                await viewModel.loadAgents()
            }
            .sheet(isPresented: $showDetailSheet) {
                if let agent = selectedAgent {
                    AgentDetailView(agent: agent)
                }
            }
        }
    }

    // MARK: - Stats Header

    private var statsHeader: some View {
        HStack(spacing: Spacing.md) {
            StatCard(
                title: "Total Agents",
                value: "\(viewModel.totalAgents)",
                icon: "cpu",
                color: CipherTheme.accent
            )
            StatCard(
                title: "Active",
                value: "\(filteredAgents.count)",
                icon: "checkmark.circle",
                color: CipherTheme.success
            )
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Loading View

    private var loadingView: some View {
        VStack(spacing: Spacing.lg) {
            SpinningCipherLogo(size: 40, spinning: true)
            Text("Loading agents...")
                .font(.subheadline)
                .foregroundColor(CipherTheme.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Spacing.xxxl)
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: Spacing.md) {
            Image(systemName: "cpu")
                .font(.system(size: 48))
                .foregroundColor(CipherTheme.textTertiary)

            Text("No Agents Found")
                .font(.headline)
                .foregroundColor(CipherTheme.textPrimary)

            Text("Try adjusting your search or refresh the list")
                .font(.caption)
                .foregroundColor(CipherTheme.textSecondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Spacing.xxxl)
    }
}

// MARK: - Agent Grid Card

struct AgentGridCard: View {
    let agent: AgentInfo
    let onTap: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: Spacing.xs) {
                    HStack(spacing: Spacing.xs) {
                        Image(systemName: iconForAgent(agent.name))
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundColor(CipherTheme.accent)

                        Text(agent.name.replacingOccurrences(of: "_", with: " ").capitalized)
                            .font(.subheadline.bold())
                            .foregroundColor(CipherTheme.textPrimary)
                            .lineLimit(2)
                    }

                    Text(agent.description)
                        .font(.caption2)
                        .foregroundColor(CipherTheme.textSecondary)
                        .lineLimit(2)
                }

                Spacer()

                // Status indicator
                Circle()
                    .fill(CipherTheme.success)
                    .frame(width: 8, height: 8)
            }

            Spacer(minLength: 0)

            // Capabilities preview
            if !agent.capabilities.isEmpty {
                HStack(spacing: Spacing.xs) {
                    ForEach(agent.capabilities.prefix(2)) { cap in
                        Text(cap.name.replacingOccurrences(of: "_", with: " "))
                            .font(.caption2)
                            .foregroundColor(CipherTheme.accentLight)
                            .padding(.horizontal, Spacing.xs)
                            .padding(.vertical, 2)
                            .background(CipherTheme.accent.opacity(0.12))
                            .clipShape(Capsule())
                    }
                    if agent.capabilities.count > 2 {
                        Text("+\(agent.capabilities.count - 2)")
                            .font(.caption2)
                            .foregroundColor(CipherTheme.textTertiary)
                    }
                }
            }
        }
        .padding(Spacing.md)
        .frame(minHeight: 140)
        .background(
            LinearGradient(
                colors: [CipherTheme.surface, CipherTheme.surfaceHover.opacity(0.5)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
        .overlay(
            RoundedRectangle(cornerRadius: CornerRadius.md)
                .stroke(CipherTheme.border, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
        .onTapGesture(perform: onTap)
    }

    private func iconForAgent(_ name: String) -> String {
        let lowerName = name.lowercased()

        // Omni-Savant Organization
        if lowerName.contains("chronos") { return "clock.badge.checkmark" }
        if lowerName.contains("archivist") { return "archivebox" }
        if lowerName.contains("sentinel") { return "bell.badge" }
        if lowerName.contains("synthesis") { return "brain.head.profile" }

        // Apex Asset Hunter
        if lowerName.contains("market") { return "chart.line.uptrend.xyaxis" }
        if lowerName.contains("profitability") { return "dollarsign.circle" }
        if lowerName.contains("neighborhood") { return "map" }
        if lowerName.contains("deal") { return "building.2" }

        // Global Expansion Pulse
        if lowerName.contains("scout") { return "binoculars" }
        if lowerName.contains("analyst") { return "chart.bar.xaxis" }
        if lowerName.contains("outreach") { return "paperplane" }
        if lowerName.contains("provisioning") { return "server.rack" }

        // Core Agents
        if lowerName.contains("shell") { return "terminal" }
        if lowerName.contains("web") { return "globe" }
        if lowerName.contains("code") { return "chevron.left.forwardslash.chevron.right" }
        if lowerName.contains("trading") { return "chart.xyaxis.line" }
        if lowerName.contains("deploy") { return "icloud.and.arrow.up" }
        if lowerName.contains("research") { return "magnifyingglass" }
        if lowerName.contains("communication") { return "message" }
        if lowerName.contains("image") { return "photo" }
        if lowerName.contains("video") { return "film" }
        if lowerName.contains("legal") { return "scale.3d" }
        if lowerName.contains("apex") { return "crown" }
        if lowerName.contains("monitor") { return "waveform.path.ecg" }
        if lowerName.contains("brave") || lowerName.contains("search") { return "magnifyingglass.circle" }
        if lowerName.contains("file") { return "doc" }
        if lowerName.contains("data") { return "cylinder" }
        if lowerName.contains("scheduler") { return "calendar.badge.clock" }
        if lowerName.contains("skill") { return "hammer" }

        return "cpu"
    }
}

#Preview {
    AgentsView()
}

import SwiftUI

// MARK: - Agents View (Category-First Navigation)

struct AgentsView: View {
    @State private var viewModel = AgentsViewModel()
    @State private var spawnVM = SpawnSessionViewModel()
    @State private var searchText = ""
    @State private var showCronManager = false
    @State private var showSpawnInstruction = false
    @State private var multiSpawnInstruction = ""

    var body: some View {
        NavigationStack {
            ZStack {
                CipherTheme.background.ignoresSafeArea()

                ScrollView(.vertical, showsIndicators: false) {
                    VStack(spacing: Spacing.lg) {
                        // Header stats
                        headerStats

                        // Active spawns banner
                        if spawnVM.isActive {
                            NavigationLink(destination: ActiveSpawnsView(sessionId: spawnVM.currentSessionId ?? "")) {
                                activeSpawnsBanner
                            }
                            .buttonStyle(.plain)
                        }

                        // Search
                        searchBar

                        if searchText.isEmpty {
                            if viewModel.isMultiSelectMode {
                                multiSelectGrid
                            } else {
                                categorySections
                            }
                        } else {
                            searchResults
                        }

                        Spacer(minLength: 100)
                    }
                    .padding(.top, Spacing.sm)
                }

                // Floating multi-spawn bar
                if viewModel.isMultiSelectMode && !viewModel.selectedAgents.isEmpty {
                    VStack {
                        Spacer()
                        multiSpawnBar
                    }
                }
            }
            .navigationTitle("Agents")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(action: { showCronManager = true }) {
                        HStack(spacing: 4) {
                            Image(systemName: "clock.arrow.2.circlepath")
                                .font(.system(size: 13, weight: .semibold))
                            Text("Schedules")
                                .font(.system(size: 12, weight: .semibold))
                        }
                        .foregroundColor(CipherTheme.accent)
                    }
                }

                ToolbarItem(placement: .topBarTrailing) {
                    HStack(spacing: Spacing.md) {
                        Button(action: {
                            withAnimation(.easeInOut(duration: 0.2)) {
                                if viewModel.isMultiSelectMode {
                                    viewModel.exitMultiSelect()
                                } else {
                                    viewModel.isMultiSelectMode = true
                                }
                            }
                        }) {
                            Text(viewModel.isMultiSelectMode ? "Done" : "Multi")
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundColor(viewModel.isMultiSelectMode ? CipherTheme.warning : CipherTheme.accent)
                        }

                        HStack(spacing: 6) {
                            Circle()
                                .fill(viewModel.serverOnline ? CipherTheme.success : Color.red.opacity(0.6))
                                .frame(width: 8, height: 8)
                            Text(viewModel.serverOnline ? "Online" : "Offline")
                                .font(.caption2)
                                .foregroundColor(CipherTheme.textSecondary)
                        }
                    }
                }
            }
            .sheet(isPresented: $showCronManager) {
                NavigationStack {
                    CronManagerView()
                }
            }
            .sheet(isPresented: $showSpawnInstruction) {
                multiSpawnSheet
            }
            .task {
                await viewModel.checkServerStatus()
                await viewModel.refreshInteractionCount()
            }
        }
    }

    // MARK: - Active Spawns Banner

    private var activeSpawnsBanner: some View {
        HStack(spacing: Spacing.md) {
            ZStack {
                Circle()
                    .fill(CipherTheme.success.opacity(0.15))
                    .frame(width: 36, height: 36)
                Image(systemName: "bolt.horizontal.fill")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(CipherTheme.success)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text("Active Agents")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(CipherTheme.textPrimary)
                if let summary = spawnVM.summary {
                    Text("\(summary.running) running · \(summary.completed) done · \(summary.failed) failed")
                        .font(.system(size: 11))
                        .foregroundColor(CipherTheme.textSecondary)
                }
            }

            Spacer()

            Image(systemName: "chevron.right")
                .font(.system(size: 12, weight: .semibold))
                .foregroundColor(CipherTheme.textTertiary)
        }
        .padding(Spacing.md)
        .background(CipherTheme.success.opacity(0.05))
        .overlay(
            RoundedRectangle(cornerRadius: CornerRadius.md)
                .stroke(CipherTheme.success.opacity(0.2), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Multi-Select Grid

    private var multiSelectGrid: some View {
        let columns = [
            GridItem(.flexible(), spacing: 10),
            GridItem(.flexible(), spacing: 10)
        ]

        return LazyVGrid(columns: columns, spacing: 10) {
            ForEach(AgentDefinition.all) { agent in
                Button(action: { viewModel.toggleAgentSelection(agent) }) {
                    ZStack(alignment: .topTrailing) {
                        AgentGridTile(agent: agent)
                            .opacity(viewModel.selectedAgents.contains(agent.id) ? 1.0 : 0.6)

                        if viewModel.selectedAgents.contains(agent.id) {
                            Image(systemName: "checkmark.circle.fill")
                                .font(.system(size: 20))
                                .foregroundColor(CipherTheme.accent)
                                .background(Circle().fill(CipherTheme.background).padding(2))
                                .offset(x: 4, y: -4)
                        }
                    }
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Multi-Spawn Floating Bar

    private var multiSpawnBar: some View {
        Button(action: { showSpawnInstruction = true }) {
            HStack(spacing: Spacing.sm) {
                Image(systemName: "bolt.horizontal.fill")
                    .font(.system(size: 14, weight: .semibold))
                Text("Spawn \(viewModel.selectedAgents.count) Agents")
                    .font(.system(size: 15, weight: .bold))
            }
            .foregroundColor(CipherTheme.textOnAccent)
            .frame(maxWidth: .infinity)
            .padding(.vertical, Spacing.lg)
            .background(CipherTheme.accentGradient)
            .clipShape(RoundedRectangle(cornerRadius: CornerRadius.lg))
        }
        .padding(.horizontal, Spacing.lg)
        .padding(.bottom, Spacing.md)
        .transition(.move(edge: .bottom).combined(with: .opacity))
    }

    // MARK: - Multi-Spawn Instruction Sheet

    private var multiSpawnSheet: some View {
        NavigationStack {
            ZStack {
                CipherTheme.background.ignoresSafeArea()

                VStack(spacing: Spacing.lg) {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: Spacing.sm) {
                            ForEach(viewModel.selectedAgentDefinitions) { agent in
                                HStack(spacing: 4) {
                                    Image(systemName: agent.icon)
                                        .font(.system(size: 11, weight: .semibold))
                                    Text(agent.displayName)
                                        .font(.system(size: 12, weight: .semibold))
                                }
                                .foregroundColor(agent.category.color)
                                .padding(.horizontal, Spacing.sm)
                                .padding(.vertical, Spacing.xs)
                                .background(agent.category.color.opacity(0.1))
                                .clipShape(Capsule())
                            }
                        }
                        .padding(.horizontal, Spacing.lg)
                    }

                    VStack(alignment: .leading, spacing: Spacing.sm) {
                        Text("What should they do?")
                            .font(.system(size: 15, weight: .semibold))
                            .foregroundColor(CipherTheme.textPrimary)

                        TextField("Enter instruction for all agents...", text: $multiSpawnInstruction, axis: .vertical)
                            .lineLimit(3...6)
                            .font(.system(size: 15))
                            .foregroundColor(CipherTheme.textPrimary)
                            .padding(Spacing.md)
                            .background(CipherTheme.surface)
                            .overlay(
                                RoundedRectangle(cornerRadius: CornerRadius.md)
                                    .stroke(CipherTheme.border, lineWidth: 1)
                            )
                            .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
                    }
                    .padding(.horizontal, Spacing.lg)

                    Spacer()

                    Button(action: {
                        showSpawnInstruction = false
                        Task {
                            await viewModel.spawnSelected(instruction: multiSpawnInstruction)
                            multiSpawnInstruction = ""
                        }
                    }) {
                        HStack(spacing: Spacing.sm) {
                            Image(systemName: "bolt.horizontal.fill")
                            Text("Spawn All")
                                .font(.system(size: 16, weight: .bold))
                        }
                        .foregroundColor(CipherTheme.textOnAccent)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, Spacing.lg)
                        .background(CipherTheme.accentGradient)
                        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.lg))
                    }
                    .disabled(multiSpawnInstruction.trimmingCharacters(in: .whitespaces).isEmpty)
                    .padding(.horizontal, Spacing.lg)
                    .padding(.bottom, Spacing.lg)
                }
                .padding(.top, Spacing.lg)
            }
            .navigationTitle("Spawn \(viewModel.selectedAgents.count) Agents")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Cancel") { showSpawnInstruction = false }
                }
            }
        }
        .presentationDetents([.medium])
    }

    // MARK: - Header Stats

    private var headerStats: some View {
        HStack(spacing: Spacing.md) {
            SpinningCipherLogo(size: 28, spinning: spawnVM.isActive)

            statItem(value: "\(AgentDefinition.all.count)", label: "Agents", color: CipherTheme.textPrimary)
            Spacer()
            statItem(value: "\(AgentCategory.allCases.count)", label: "Squads", color: CipherTheme.accent)
            Spacer()
            HStack(spacing: 5) {
                Circle()
                    .fill(viewModel.serverOnline ? CipherTheme.success : Color.red.opacity(0.6))
                    .frame(width: 8, height: 8)
                Text(viewModel.serverOnline ? "Live" : "Off")
                    .font(.system(size: 18, weight: .bold, design: .rounded))
                    .foregroundColor(CipherTheme.textPrimary)
            }
            .frame(width: 70, alignment: .leading)
        }
        .padding(.horizontal, Spacing.lg)
    }

    private func statItem(value: String, label: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            Text(value)
                .font(.system(size: 22, weight: .bold, design: .rounded))
                .foregroundColor(color)
            Text(label)
                .font(.caption)
                .foregroundColor(CipherTheme.textSecondary)
        }
    }

    // MARK: - Search Bar

    private var searchBar: some View {
        HStack(spacing: Spacing.sm) {
            Image(systemName: "magnifyingglass")
                .foregroundColor(CipherTheme.textTertiary)
                .font(.caption)
            TextField("Search agents...", text: $searchText)
                .textFieldStyle(.plain)
                .foregroundColor(CipherTheme.textPrimary)
                .font(.subheadline)
            if !searchText.isEmpty {
                Button {
                    searchText = ""
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(CipherTheme.textTertiary)
                        .font(.caption)
                }
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(CipherTheme.surface)
        .overlay(
            RoundedRectangle(cornerRadius: CornerRadius.md)
                .stroke(CipherTheme.border, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Category Sections

    private var categorySections: some View {
        VStack(spacing: Spacing.md) {
            ForEach(AgentCategory.allCases) { category in
                NavigationLink(destination: CategoryAgentsView(category: category, serverOnline: viewModel.serverOnline)) {
                    CategoryCard(category: category)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Search Results

    private var searchResults: some View {
        let filtered = AgentDefinition.all.filter { agent in
            agent.displayName.localizedCaseInsensitiveContains(searchText) ||
            agent.description.localizedCaseInsensitiveContains(searchText) ||
            agent.purpose.localizedCaseInsensitiveContains(searchText) ||
            agent.category.rawValue.localizedCaseInsensitiveContains(searchText)
        }

        return VStack(spacing: Spacing.sm) {
            Text("\(filtered.count) results")
                .font(.caption)
                .foregroundColor(CipherTheme.textTertiary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, Spacing.lg)

            ForEach(filtered) { agent in
                NavigationLink(destination: AgentDetailView(agent: agent, serverOnline: viewModel.serverOnline)) {
                    AgentListRow(agent: agent)
                }
                .buttonStyle(.plain)
            }
        }
    }
}

// MARK: - Category Card

struct CategoryCard: View {
    let category: AgentCategory

    var body: some View {
        HStack(spacing: Spacing.md) {
            // Category icon
            ZStack {
                RoundedRectangle(cornerRadius: 12)
                    .fill(category.color.opacity(0.12))
                    .frame(width: 52, height: 52)
                Image(systemName: category.icon)
                    .font(.system(size: 22, weight: .semibold))
                    .foregroundColor(category.color)
            }

            VStack(alignment: .leading, spacing: 3) {
                Text(category.rawValue)
                    .font(.system(size: 16, weight: .bold))
                    .foregroundColor(CipherTheme.textPrimary)

                // Show agent names as subtitle
                Text(category.agents.map { $0.displayName }.joined(separator: " · "))
                    .font(.system(size: 11))
                    .foregroundColor(CipherTheme.textTertiary)
                    .lineLimit(1)
            }

            Spacer()

            // Count badge + chevron
            HStack(spacing: 6) {
                Text("\(category.agents.count)")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundColor(category.color)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(category.color.opacity(0.1))
                    .clipShape(Capsule())

                Image(systemName: "chevron.right")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(CipherTheme.textTertiary)
            }
        }
        .padding(Spacing.md)
        .background(CipherTheme.surface)
        .overlay(
            RoundedRectangle(cornerRadius: CornerRadius.md)
                .stroke(CipherTheme.border, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
    }
}

// MARK: - Agent List Row (for search results)

struct AgentListRow: View {
    let agent: AgentDefinition

    var body: some View {
        HStack(spacing: Spacing.md) {
            ZStack {
                Circle()
                    .fill(agent.category.color.opacity(0.12))
                    .frame(width: 38, height: 38)
                Image(systemName: agent.icon)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(agent.category.color)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(agent.displayName)
                    .font(.subheadline.bold())
                    .foregroundColor(CipherTheme.textPrimary)
                Text(agent.description)
                    .font(.caption)
                    .foregroundColor(CipherTheme.textSecondary)
                    .lineLimit(1)
            }

            Spacer()

            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundColor(CipherTheme.textTertiary)
        }
        .padding(.horizontal, Spacing.lg)
        .padding(.vertical, Spacing.sm)
    }
}

// MARK: - Category Agents View (drill-in)

struct CategoryAgentsView: View {
    let category: AgentCategory
    let serverOnline: Bool

    private let columns = [
        GridItem(.flexible(), spacing: 10),
        GridItem(.flexible(), spacing: 10)
    ]

    var body: some View {
        ZStack {
            CipherTheme.background.ignoresSafeArea()

            ScrollView(.vertical, showsIndicators: false) {
                VStack(spacing: Spacing.lg) {
                    // Category header
                    VStack(spacing: Spacing.sm) {
                        ZStack {
                            Circle()
                                .fill(category.color.opacity(0.15))
                                .frame(width: 56, height: 56)
                            Image(systemName: category.icon)
                                .font(.system(size: 24, weight: .semibold))
                                .foregroundColor(category.color)
                        }

                        Text("\(category.agents.count) Agents")
                            .font(.caption)
                            .foregroundColor(CipherTheme.textSecondary)
                    }
                    .padding(.top, Spacing.sm)

                    // Agent grid
                    LazyVGrid(columns: columns, spacing: 10) {
                        ForEach(category.agents) { agent in
                            NavigationLink(destination: AgentDetailView(agent: agent, serverOnline: serverOnline)) {
                                AgentGridTile(agent: agent)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.horizontal, Spacing.lg)

                    Spacer(minLength: 100)
                }
            }
        }
        .navigationTitle(category.rawValue)
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: - Agent Grid Tile

struct AgentGridTile: View {
    let agent: AgentDefinition

    var body: some View {
        VStack(spacing: 8) {
            ZStack {
                Circle()
                    .fill(agent.category.color.opacity(0.12))
                    .frame(width: 44, height: 44)
                Image(systemName: agent.icon)
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundColor(agent.category.color)
            }

            Text(agent.displayName)
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(CipherTheme.textPrimary)
                .lineLimit(1)

            Text(agent.description)
                .font(.system(size: 10))
                .foregroundColor(CipherTheme.textSecondary)
                .lineLimit(2)
                .multilineTextAlignment(.center)
                .frame(height: 26)

            HStack(spacing: 4) {
                ForEach(agent.actions) { action in
                    Circle()
                        .fill(action.color)
                        .frame(width: 6, height: 6)
                }
            }
        }
        .padding(.vertical, 14)
        .padding(.horizontal, 8)
        .frame(maxWidth: .infinity)
        .background(CipherTheme.surface)
        .overlay(
            RoundedRectangle(cornerRadius: CornerRadius.md)
                .stroke(CipherTheme.border, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
    }
}

#Preview {
    AgentsView()
}

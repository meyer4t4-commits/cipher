import SwiftUI

// MARK: - Projects View (App Hub)

struct ProjectsView: View {
    @State private var store = ProjectStore.shared
    @State private var showNewProject = false
    @State private var showVault = false

    var body: some View {
        NavigationStack {
            ZStack {
                CipherTheme.background.ignoresSafeArea()

                if store.projects.isEmpty {
                    emptyState
                } else {
                    projectsList
                }
            }
            .navigationTitle("Projects")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        showVault = true
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: "key.fill")
                                .font(.system(size: 12, weight: .semibold))
                            Text("Vault")
                                .font(.system(size: 12, weight: .semibold))
                        }
                        .foregroundColor(CipherTheme.accent)
                    }
                }

                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showNewProject = true
                    } label: {
                        Image(systemName: "plus.circle.fill")
                            .font(.system(size: 18))
                            .foregroundColor(CipherTheme.accent)
                    }
                }
            }
            .sheet(isPresented: $showNewProject) {
                NewProjectSheet(store: store)
            }
            .sheet(isPresented: $showVault) {
                NavigationStack {
                    ServiceVaultView(store: store)
                }
            }
        }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: Spacing.lg) {
            Spacer()

            CipherLogo(size: 64, animated: true)

            VStack(spacing: Spacing.sm) {
                Text("No projects yet")
                    .font(.system(size: 18, weight: .bold))
                    .foregroundColor(CipherTheme.textPrimary)

                Text("Add your apps and connect services so agents can deploy, monitor, and manage them autonomously.")
                    .font(.system(size: 14))
                    .foregroundColor(CipherTheme.textSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 40)
            }

            Button {
                showNewProject = true
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: "plus")
                        .font(.system(size: 14, weight: .semibold))
                    Text("Add Project")
                        .font(.system(size: 15, weight: .bold))
                }
                .foregroundColor(.white)
                .padding(.horizontal, 32)
                .padding(.vertical, 14)
                .background(CipherTheme.accent)
                .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
            }

            Button {
                showVault = true
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: "key.fill")
                        .font(.system(size: 12))
                    Text("Set up API keys first")
                        .font(.system(size: 13, weight: .semibold))
                }
                .foregroundColor(CipherTheme.textSecondary)
            }

            Spacer()
        }
    }

    // MARK: - Projects List

    private var projectsList: some View {
        ScrollView(.vertical, showsIndicators: false) {
            VStack(spacing: Spacing.md) {
                // Credential summary bar
                credentialBar

                ForEach(store.projects) { project in
                    NavigationLink(destination: ProjectDetailView(project: project, store: store)) {
                        ProjectCard(project: project)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, Spacing.lg)
            .padding(.top, Spacing.sm)
        }
    }

    // MARK: - Credential Bar

    private var credentialBar: some View {
        Button { showVault = true } label: {
            HStack(spacing: Spacing.sm) {
                Image(systemName: "key.fill")
                    .font(.system(size: 12))
                    .foregroundColor(CipherTheme.accent)

                Text("\(store.credentials.count) API keys stored")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(CipherTheme.textPrimary)

                Spacer()

                Text("Manage")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(CipherTheme.accent)
            }
            .padding(Spacing.md)
            .background(CipherTheme.surface)
            .overlay(
                RoundedRectangle(cornerRadius: CornerRadius.sm)
                    .stroke(CipherTheme.border, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))
        }
    }
}

// MARK: - Project Card

struct ProjectCard: View {
    let project: CipherProject

    var body: some View {
        HStack(spacing: Spacing.md) {
            ZStack {
                RoundedRectangle(cornerRadius: 12)
                    .fill(project.displayColor.opacity(0.12))
                    .frame(width: 52, height: 52)
                Image(systemName: project.icon)
                    .font(.system(size: 22, weight: .semibold))
                    .foregroundColor(project.displayColor)
            }

            VStack(alignment: .leading, spacing: 3) {
                Text(project.name)
                    .font(.system(size: 16, weight: .bold))
                    .foregroundColor(CipherTheme.textPrimary)

                Text(project.description)
                    .font(.system(size: 12))
                    .foregroundColor(CipherTheme.textSecondary)
                    .lineLimit(1)

                HStack(spacing: 6) {
                    HStack(spacing: 3) {
                        Image(systemName: project.platform.icon)
                            .font(.system(size: 9))
                        Text(project.platform.rawValue)
                            .font(.system(size: 10, weight: .semibold))
                    }
                    .foregroundColor(project.displayColor)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(project.displayColor.opacity(0.1))
                    .clipShape(Capsule())

                    if !project.services.isEmpty {
                        Text("\(project.services.count) services")
                            .font(.system(size: 10))
                            .foregroundColor(CipherTheme.textTertiary)
                    }
                }
            }

            Spacer()

            // Status indicator
            VStack(spacing: 4) {
                if project.deployURL != nil {
                    HStack(spacing: 3) {
                        Circle()
                            .fill(CipherTheme.success)
                            .frame(width: 6, height: 6)
                        Text("Live")
                            .font(.system(size: 10, weight: .semibold))
                            .foregroundColor(CipherTheme.success)
                    }
                }
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

// MARK: - Project Detail View

struct ProjectDetailView: View {
    let project: CipherProject
    let store: ProjectStore
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            CipherTheme.background.ignoresSafeArea()

            ScrollView(.vertical, showsIndicators: false) {
                VStack(spacing: Spacing.lg) {
                    projectHeader
                    quickActions
                    servicesSection
                    linksSection
                    dangerZone
                    Spacer(minLength: 40)
                }
                .padding(.top, Spacing.md)
            }
        }
        .navigationTitle(project.name)
        .navigationBarTitleDisplayMode(.inline)
    }

    private var projectHeader: some View {
        VStack(spacing: Spacing.md) {
            ZStack {
                Circle()
                    .fill(project.displayColor.opacity(0.15))
                    .frame(width: 72, height: 72)
                Image(systemName: project.icon)
                    .font(.system(size: 28, weight: .semibold))
                    .foregroundColor(project.displayColor)
            }

            Text(project.description)
                .font(.subheadline)
                .foregroundColor(CipherTheme.textSecondary)
                .multilineTextAlignment(.center)

            HStack(spacing: 8) {
                platformBadge
                if project.deployURL != nil {
                    liveBadge
                }
            }
        }
        .frame(maxWidth: .infinity)
        .padding(Spacing.lg)
    }

    private var platformBadge: some View {
        HStack(spacing: 4) {
            Image(systemName: project.platform.icon)
                .font(.system(size: 10))
            Text(project.platform.rawValue)
                .font(.system(size: 11, weight: .semibold))
        }
        .foregroundColor(project.displayColor)
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
        .background(project.displayColor.opacity(0.12))
        .clipShape(Capsule())
    }

    private var liveBadge: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(CipherTheme.success)
                .frame(width: 6, height: 6)
            Text("Live")
                .font(.system(size: 11, weight: .semibold))
        }
        .foregroundColor(CipherTheme.success)
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
        .background(CipherTheme.success.opacity(0.12))
        .clipShape(Capsule())
    }

    // MARK: - Quick Actions

    @State private var actionInProgress: String? = nil
    @State private var actionResult: String? = nil
    @State private var showActionResult = false

    private var quickActions: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            Text("Quick Actions")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(CipherTheme.textSecondary)
                .padding(.horizontal, Spacing.lg)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: Spacing.sm) {
                    quickActionButton(icon: "play.fill", label: "Deploy", color: .green) {
                        await executeProjectAction("Deploy project '\(project.name)' — run git push and deploy via Railway. Repo: \(project.repoURL ?? "unknown"). Railway ID: \(project.railwayProjectId ?? "not set").")
                    }
                    quickActionButton(icon: "waveform.path.ecg", label: "Health Check", color: .blue) {
                        await executeProjectAction("Run a health check on project '\(project.name)'. Check the deploy URL: \(project.deployURL ?? "not set"). Verify the service is responding and report status.")
                    }
                    quickActionButton(icon: "doc.text", label: "View Logs", color: .purple) {
                        await executeProjectAction("Show me the latest logs for project '\(project.name)'. Railway ID: \(project.railwayProjectId ?? "not set"). Check docker logs or railway logs.")
                    }
                    quickActionButton(icon: "wrench.fill", label: "Auto-Fix", color: .orange) {
                        await executeProjectAction("Analyze project '\(project.name)' for issues. Check the repo at \(project.repoURL ?? "unknown") for errors, failing tests, or common problems. Fix what you can.")
                    }
                    quickActionButton(icon: "terminal", label: "Run Script", color: .cyan) {
                        await executeProjectAction("Open a terminal session for project '\(project.name)'. Show me the project directory listing and git status. Repo: \(project.repoURL ?? "unknown").")
                    }
                }
                .padding(.horizontal, Spacing.lg)
            }

            // Inline result display
            if let result = actionResult, showActionResult {
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(CipherTheme.success)
                            .font(.system(size: 12))
                        Text("Cipher Response")
                            .font(.system(size: 11, weight: .bold))
                            .foregroundColor(CipherTheme.textSecondary)
                        Spacer()
                        Button { showActionResult = false } label: {
                            Image(systemName: "xmark")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundColor(CipherTheme.textTertiary)
                        }
                    }
                    Text(result)
                        .font(.system(size: 12, design: .monospaced))
                        .foregroundColor(CipherTheme.textPrimary)
                        .lineLimit(8)
                }
                .padding(Spacing.md)
                .background(CipherTheme.surface)
                .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))
                .overlay(
                    RoundedRectangle(cornerRadius: CornerRadius.sm)
                        .stroke(CipherTheme.success.opacity(0.3), lineWidth: 1)
                )
                .padding(.horizontal, Spacing.lg)
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
    }

    private func quickActionButton(icon: String, label: String, color: Color, action: @escaping () async -> Void) -> some View {
        Button {
            actionInProgress = label
            HapticsService.shared.mediumTap()
            Task { await action() }
        } label: {
            VStack(spacing: 6) {
                ZStack {
                    RoundedRectangle(cornerRadius: 10)
                        .fill(color.opacity(actionInProgress == label ? 0.25 : 0.12))
                        .frame(width: 48, height: 48)

                    if actionInProgress == label {
                        SpinningCipherLogo(size: 18, spinning: true)
                    } else {
                        Image(systemName: icon)
                            .font(.system(size: 18, weight: .semibold))
                            .foregroundColor(color)
                    }
                }
                Text(label)
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundColor(CipherTheme.textSecondary)
            }
        }
        .disabled(actionInProgress != nil)
        .opacity(actionInProgress != nil && actionInProgress != label ? 0.4 : 1.0)
    }

    private func executeProjectAction(_ prompt: String) async {
        let label = actionInProgress
        do {
            let response = try await CipherAPI.shared.sendMessage(
                message: prompt,
                modelTier: "reasoning"
            )
            await MainActor.run {
                actionResult = response.message
                showActionResult = true
                actionInProgress = nil
            }
        } catch {
            await MainActor.run {
                actionResult = "Error: \(error.localizedDescription)"
                showActionResult = true
                actionInProgress = nil
            }
        }
    }

    // MARK: - Services

    private var servicesSection: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            HStack {
                Text("Connected Services")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundColor(CipherTheme.textSecondary)
                Spacer()
                Button {
                    // TODO: Add service connection
                } label: {
                    Image(systemName: "plus.circle")
                        .font(.system(size: 16))
                        .foregroundColor(CipherTheme.accent)
                }
            }
            .padding(.horizontal, Spacing.lg)

            if project.services.isEmpty {
                HStack {
                    Image(systemName: "link.badge.plus")
                        .foregroundColor(CipherTheme.textTertiary)
                    Text("No services connected yet")
                        .font(.system(size: 13))
                        .foregroundColor(CipherTheme.textTertiary)
                }
                .padding(Spacing.md)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(CipherTheme.surface)
                .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))
                .padding(.horizontal, Spacing.lg)
            } else {
                VStack(spacing: 0) {
                    ForEach(project.services) { service in
                        HStack {
                            Image(systemName: service.serviceType.icon)
                                .font(.system(size: 14))
                                .foregroundColor(service.serviceType.color)
                                .frame(width: 24)
                            Text(service.serviceType.rawValue)
                                .font(.system(size: 14, weight: .medium))
                                .foregroundColor(CipherTheme.textPrimary)
                            Spacer()
                            if service.credentialId != nil {
                                Image(systemName: "checkmark.circle.fill")
                                    .font(.system(size: 14))
                                    .foregroundColor(CipherTheme.success)
                            }
                        }
                        .padding(.horizontal, Spacing.md)
                        .padding(.vertical, 10)
                    }
                }
                .background(CipherTheme.surface)
                .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
                .overlay(
                    RoundedRectangle(cornerRadius: CornerRadius.md)
                        .stroke(CipherTheme.border, lineWidth: 1)
                )
                .padding(.horizontal, Spacing.lg)
            }
        }
    }

    // MARK: - Links

    private var linksSection: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            Text("Links")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(CipherTheme.textSecondary)
                .padding(.horizontal, Spacing.lg)

            VStack(spacing: 0) {
                if let repo = project.repoURL, !repo.isEmpty {
                    linkRow(icon: "chevron.left.forwardslash.chevron.right", label: "Repository", value: repo)
                }
                if let deploy = project.deployURL, !deploy.isEmpty {
                    linkRow(icon: "globe", label: "Live URL", value: deploy)
                }
                if let railway = project.railwayProjectId, !railway.isEmpty {
                    linkRow(icon: "tram", label: "Railway ID", value: railway)
                }
            }
            .background(CipherTheme.surface)
            .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: CornerRadius.md)
                    .stroke(CipherTheme.border, lineWidth: 1)
            )
            .padding(.horizontal, Spacing.lg)
        }
    }

    private func linkRow(icon: String, label: String, value: String) -> some View {
        HStack {
            Image(systemName: icon)
                .font(.system(size: 12))
                .foregroundColor(CipherTheme.textTertiary)
                .frame(width: 20)
            Text(label)
                .font(.system(size: 13))
                .foregroundColor(CipherTheme.textSecondary)
            Spacer()
            Text(value)
                .font(.system(size: 12, design: .monospaced))
                .foregroundColor(CipherTheme.textPrimary)
                .lineLimit(1)
                .truncationMode(.middle)
                .frame(maxWidth: 180, alignment: .trailing)
        }
        .padding(.horizontal, Spacing.md)
        .padding(.vertical, 10)
    }

    // MARK: - Danger Zone

    private var dangerZone: some View {
        Button {
            store.deleteProject(project.id)
            dismiss()
        } label: {
            HStack {
                Image(systemName: "trash")
                    .font(.system(size: 13))
                Text("Delete Project")
                    .font(.system(size: 14, weight: .semibold))
            }
            .foregroundColor(CipherTheme.error)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .background(CipherTheme.error.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))
        }
        .padding(.horizontal, Spacing.lg)
        .padding(.top, Spacing.md)
    }
}

// MARK: - New Project Sheet

struct NewProjectSheet: View {
    let store: ProjectStore
    @Environment(\.dismiss) private var dismiss

    @State private var name = ""
    @State private var description = ""
    @State private var selectedPlatform = ProjectPlatform.fullStack
    @State private var selectedColor = "blue"
    @State private var selectedIcon = "folder.fill"
    @State private var repoURL = ""
    @State private var deployURL = ""
    @State private var railwayId = ""

    private let colors = ["blue", "red", "green", "purple", "orange", "cyan", "indigo", "pink"]
    private let icons = ["folder.fill", "app.fill", "globe", "iphone", "server.rack", "building.2", "cart.fill", "graduationcap.fill"]

    var body: some View {
        NavigationStack {
            ZStack {
                CipherTheme.background.ignoresSafeArea()

                ScrollView(.vertical, showsIndicators: false) {
                    VStack(alignment: .leading, spacing: Spacing.lg) {
                        nameSection
                        platformSection
                        appearanceSection
                        linksSection
                        createButton
                    }
                    .padding(Spacing.lg)
                }
            }
            .navigationTitle("New Project")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Cancel") { dismiss() }
                        .foregroundColor(CipherTheme.textSecondary)
                }
            }
        }
        .presentationDetents([.large])
        .presentationDragIndicator(.visible)
    }

    private var nameSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Name")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(CipherTheme.textSecondary)
            TextField("e.g. Rise Right", text: $name)
                .textFieldStyle(.plain)
                .font(.system(size: 16))
                .foregroundColor(CipherTheme.textPrimary)
                .padding(Spacing.md)
                .background(CipherTheme.surface)
                .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))

            Text("Description")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(CipherTheme.textSecondary)
                .padding(.top, Spacing.sm)
            TextField("What is this project?", text: $description, axis: .vertical)
                .textFieldStyle(.plain)
                .font(.system(size: 15))
                .foregroundColor(CipherTheme.textPrimary)
                .padding(Spacing.md)
                .background(CipherTheme.surface)
                .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))
                .lineLimit(2...3)
        }
    }

    private var platformSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Platform")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(CipherTheme.textSecondary)

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                ForEach(ProjectPlatform.allCases, id: \.rawValue) { platform in
                    Button {
                        selectedPlatform = platform
                    } label: {
                        VStack(spacing: 4) {
                            Image(systemName: platform.icon)
                                .font(.system(size: 16))
                            Text(platform.rawValue)
                                .font(.system(size: 11, weight: .semibold))
                        }
                        .foregroundColor(selectedPlatform == platform ? .white : CipherTheme.textSecondary)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
                        .background(selectedPlatform == platform ? CipherTheme.accent : CipherTheme.surface)
                        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))
                        .overlay(
                            RoundedRectangle(cornerRadius: CornerRadius.sm)
                                .stroke(selectedPlatform == platform ? Color.clear : CipherTheme.border, lineWidth: 1)
                        )
                    }
                }
            }
        }
    }

    private var appearanceSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Color & Icon")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(CipherTheme.textSecondary)

            HStack(spacing: 8) {
                ForEach(colors, id: \.self) { colorName in
                    let c = colorForName(colorName)
                    Button {
                        selectedColor = colorName
                    } label: {
                        Circle()
                            .fill(c)
                            .frame(width: 28, height: 28)
                            .overlay(
                                Circle()
                                    .stroke(Color.white, lineWidth: selectedColor == colorName ? 2 : 0)
                            )
                    }
                }
            }

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(icons, id: \.self) { iconName in
                        Button {
                            selectedIcon = iconName
                        } label: {
                            Image(systemName: iconName)
                                .font(.system(size: 16))
                                .foregroundColor(selectedIcon == iconName ? .white : CipherTheme.textSecondary)
                                .frame(width: 36, height: 36)
                                .background(selectedIcon == iconName ? CipherTheme.accent : CipherTheme.surface)
                                .clipShape(RoundedRectangle(cornerRadius: 8))
                        }
                    }
                }
            }
        }
    }

    private var linksSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Links (optional)")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(CipherTheme.textSecondary)

            linkField("GitHub / Repo URL", text: $repoURL, icon: "chevron.left.forwardslash.chevron.right")
            linkField("Deploy URL", text: $deployURL, icon: "globe")
            linkField("Railway Project ID", text: $railwayId, icon: "tram")
        }
    }

    private func linkField(_ placeholder: String, text: Binding<String>, icon: String) -> some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .font(.system(size: 12))
                .foregroundColor(CipherTheme.textTertiary)
                .frame(width: 20)
            TextField(placeholder, text: text)
                .textFieldStyle(.plain)
                .font(.system(size: 14))
                .foregroundColor(CipherTheme.textPrimary)
        }
        .padding(Spacing.sm)
        .background(CipherTheme.surface)
        .clipShape(RoundedRectangle(cornerRadius: CornerRadius.sm))
    }

    private var createButton: some View {
        Button {
            let project = CipherProject(
                id: UUID().uuidString,
                name: name,
                description: description,
                icon: selectedIcon,
                color: selectedColor,
                repoURL: repoURL.isEmpty ? nil : repoURL,
                deployURL: deployURL.isEmpty ? nil : deployURL,
                railwayProjectId: railwayId.isEmpty ? nil : railwayId,
                platform: selectedPlatform,
                services: [],
                createdAt: Date(),
                lastActiveAt: Date()
            )
            store.addProject(project)
            dismiss()
        } label: {
            Text("Create Project")
                .font(.system(size: 16, weight: .bold))
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(name.isEmpty ? Color.gray.opacity(0.5) : CipherTheme.accent)
                .clipShape(RoundedRectangle(cornerRadius: CornerRadius.md))
        }
        .disabled(name.isEmpty)
    }

    private func colorForName(_ name: String) -> Color {
        switch name {
        case "blue": return .blue
        case "red": return .red
        case "green": return .green
        case "purple": return .purple
        case "orange": return .orange
        case "cyan": return .cyan
        case "indigo": return .indigo
        case "pink": return .pink
        default: return .blue
        }
    }
}

#Preview {
    ProjectsView()
}

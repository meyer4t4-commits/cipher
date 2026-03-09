import SwiftUI
import PhotosUI

// MARK: - Chat View

struct ChatView: View {
    @State private var viewModel: ChatViewModel
    @State private var selectedPhotoItems: [PhotosPickerItem] = []
    @Environment(\.scenePhase) var scenePhase

    init(conversation: Conversation? = nil) {
        _viewModel = State(initialValue: ChatViewModel(conversation: conversation))
    }

    var body: some View {
        ZStack {
            CipherTheme.background.ignoresSafeArea()

            VStack(spacing: 0) {
                // Header — Liquid Glass style
                chatHeader

                // Messages or Empty State
                if viewModel.currentConversation.messages.isEmpty {
                    ChatEmptyState(
                        suggestions: viewModel.suggestions,
                        onSuggestionTap: { suggestion in
                            viewModel.inputText = suggestion.fullPrompt
                            Task { await viewModel.sendMessage() }
                        },
                        onRefresh: {
                            withAnimation(.easeInOut(duration: 0.25)) {
                                viewModel.refreshSuggestions()
                            }
                        }
                    )
                } else {
                    messagesList
                }

                // Error Banner
                if let errorMessage = viewModel.errorMessage {
                    ErrorBanner(message: errorMessage) {
                        viewModel.errorMessage = nil
                    }
                }

                // Agent Recommendation Card
                if viewModel.showRecommendation, let rec = viewModel.agentRecommendation {
                    AgentRecommendationCard(
                        recommendation: rec,
                        onSpawn: {
                            Task { await viewModel.spawnRecommendedAgent() }
                        },
                        onDismiss: {
                            viewModel.dismissRecommendation()
                        }
                    )
                    .padding(.horizontal, Spacing.md)
                    .padding(.bottom, Spacing.xxs)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                }

                // Input Bar — Liquid Glass style
                ChatInputBar(
                    text: $viewModel.inputText,
                    isLoading: viewModel.isLoading,
                    isStreaming: viewModel.isStreaming,
                    pendingImages: $viewModel.pendingImages,
                    onSend: {
                        Task { await viewModel.sendMessage() }
                    },
                    onStop: {
                        viewModel.cancelStreaming()
                    },
                    onVoice: {
                        viewModel.showVoiceMode = true
                    },
                    onAttach: {
                        viewModel.showImagePicker = true
                    },
                    onRemoveImage: { index in
                        viewModel.removeImage(at: index)
                    }
                )
            }
        }
        .sheet(isPresented: $viewModel.showVoiceMode) {
            VoiceModeView(onSend: { text in
                Task { await viewModel.sendVoiceMessage(text) }
            })
        }
        .sheet(isPresented: $viewModel.showModelPicker) {
            ModelPickerSheet(
                selected: $viewModel.selectedModelTier,
                onDismiss: { viewModel.showModelPicker = false }
            )
            .presentationDetents([.medium])
        }
        .sheet(isPresented: $viewModel.showInteractionSheet) {
            if let interaction = viewModel.pendingInteraction {
                AgentInteractionSheet(
                    interaction: interaction,
                    onAnswer: { response in
                        Task { await viewModel.answerInteraction(interaction.interactionId, response: response) }
                    },
                    onDismiss: {
                        Task { await viewModel.dismissInteraction(interaction.interactionId) }
                    }
                )
                .presentationDetents([.medium, .large])
            }
        }
        .photosPicker(
            isPresented: $viewModel.showImagePicker,
            selection: $selectedPhotoItems,
            maxSelectionCount: 10,
            matching: .images
        )
        .onChange(of: selectedPhotoItems) { _, newItems in
            Task {
                for item in newItems {
                    if let data = try? await item.loadTransferable(type: Data.self),
                       let image = UIImage(data: data) {
                        await MainActor.run {
                            viewModel.pendingImages.append(image)
                        }
                    }
                }
                await MainActor.run {
                    selectedPhotoItems = []
                }
            }
        }
        .onAppear {
            viewModel.reloadIfNeeded()
            Task { await viewModel.checkServerHealth() }
            viewModel.startInteractionPolling()
        }
        .onDisappear {
            viewModel.stopInteractionPolling()
        }
        .onChange(of: scenePhase) { _, newPhase in
            if newPhase == .active {
                Task { await viewModel.checkServerHealth() }
                viewModel.startInteractionPolling()
            } else if newPhase == .background {
                viewModel.stopInteractionPolling()
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: NSNotification.Name("OpenAgentInteraction"))) { _ in
            Task { await viewModel.fetchPendingInteractions() }
        }
    }

    // MARK: - Chat Header (Liquid Glass)

    private var chatHeader: some View {
        HStack(spacing: Spacing.sm) {
            // Cipher logo — spins when thinking
            SpinningCipherLogo(size: 24, spinning: viewModel.isLoading || viewModel.isStreaming)

            VStack(alignment: .leading, spacing: 1) {
                Text(viewModel.currentConversation.title == "New Conversation" ? "Cipher" : viewModel.currentConversation.title)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(CipherTheme.textPrimary)
                    .lineLimit(1)

                ConnectionIndicator(isConnected: viewModel.isConnected, showLabel: false)
            }

            Spacer()

            // Model tier — compact pill
            Button(action: { viewModel.showModelPicker = true }) {
                Text(viewModel.selectedModelTier.displayName)
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundColor(CipherTheme.accent)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(
                        Capsule()
                            .fill(.ultraThinMaterial)
                            .opacity(0.8)
                    )
                    .overlay(
                        Capsule()
                            .stroke(CipherTheme.accent.opacity(0.15), lineWidth: 0.5)
                    )
            }

            // New chat button
            Button(action: {
                HapticsService.shared.mediumTap()
                viewModel.startNewConversation()
            }) {
                Image(systemName: "plus")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(.white)
                    .frame(width: 32, height: 32)
                    .background(
                        Circle()
                            .fill(CipherTheme.accentGradient)
                    )
            }
        }
        .padding(.horizontal, Spacing.lg)
        .padding(.vertical, Spacing.sm)
        .background(
            // Liquid Glass header background
            Rectangle()
                .fill(.ultraThinMaterial)
                .opacity(0.7)
                .overlay(
                    Rectangle()
                        .fill(
                            LinearGradient(
                                colors: [
                                    CipherTheme.accent.opacity(0.03),
                                    Color.clear
                                ],
                                startPoint: .top,
                                endPoint: .bottom
                            )
                        )
                )
                .overlay(
                    Rectangle()
                        .fill(CipherTheme.border)
                        .frame(height: 0.5),
                    alignment: .bottom
                )
        )
    }

    // MARK: - Messages List

    private var messagesList: some View {
        ScrollViewReader { proxy in
            ScrollView(.vertical, showsIndicators: false) {
                LazyVStack(spacing: 0) {
                    ForEach(Array(viewModel.currentConversation.messages.enumerated()), id: \.element.id) { index, message in
                        MessageBubble(
                            message: message,
                            onCopy: {
                                viewModel.copyMessage(message)
                            },
                            onDelete: {
                                viewModel.deleteMessage(at: index)
                            },
                            onRetry: message.isFailed ? {
                                Task { await viewModel.retryLastMessage() }
                            } : nil
                        )
                        .id(message.id)
                        .transition(.asymmetric(
                            insertion: .opacity
                                .combined(with: .scale(scale: 0.96, anchor: .bottom))
                                .combined(with: .offset(y: 8))
                                .animation(.spring(response: 0.35, dampingFraction: 0.8)),
                            removal: .opacity.animation(.easeIn(duration: 0.12))
                        ))
                    }

                    // Loading indicator — premium thinking state
                    if viewModel.isLoading && !viewModel.isStreaming {
                        HStack(spacing: Spacing.sm) {
                            TypingIndicator()
                        }
                        .padding(.horizontal, Spacing.lg)
                        .padding(.vertical, Spacing.sm)
                        .transition(.asymmetric(
                            insertion: .opacity
                                .combined(with: .move(edge: .bottom))
                                .combined(with: .scale(scale: 0.95, anchor: .bottomLeading))
                                .animation(.spring(response: 0.4, dampingFraction: 0.75)),
                            removal: .opacity.animation(.easeIn(duration: 0.12))
                        ))
                        .id("typing")
                    }

                    // Bottom anchor
                    Color.clear
                        .frame(height: 1)
                        .id("bottomAnchor")
                }
                .padding(.top, Spacing.sm)
                .animation(.spring(response: 0.3, dampingFraction: 0.85), value: viewModel.currentConversation.messages.count)
            }
            .onChange(of: viewModel.currentConversation.messages.count) {
                let messages = viewModel.currentConversation.messages
                guard let lastMessage = messages.last else { return }

                if lastMessage.role == .user {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
                        withAnimation(.easeOut(duration: 0.3)) {
                            proxy.scrollTo(lastMessage.id, anchor: .bottom)
                        }
                    }
                } else {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                        withAnimation(.easeOut(duration: 0.3)) {
                            proxy.scrollTo("bottomAnchor", anchor: .bottom)
                        }
                    }
                }
            }
            .onChange(of: viewModel.isLoading) {
                if viewModel.isLoading && !viewModel.isStreaming {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
                        withAnimation(.easeOut(duration: 0.2)) {
                            proxy.scrollTo("bottomAnchor", anchor: .bottom)
                        }
                    }
                }
            }
            .onChange(of: viewModel.streamingText) {
                withAnimation(.easeOut(duration: 0.1)) {
                    proxy.scrollTo("bottomAnchor", anchor: .bottom)
                }
            }
            .scrollDismissesKeyboard(.interactively)
        }
    }
}

// MARK: - Empty State (centered logo, smooth fade)

struct ChatEmptyState: View {
    let suggestions: [SuggestedPrompt]
    let onSuggestionTap: (SuggestedPrompt) -> Void
    var onRefresh: (() -> Void)?

    @State private var appeared = false

    private var timeGreeting: String {
        let hour = Calendar.current.component(.hour, from: Date())
        switch hour {
        case 5..<12: return "Good morning, Mark"
        case 12..<17: return "Good afternoon, Mark"
        case 17..<22: return "Good evening, Mark"
        default: return "Burning the midnight oil, Mark?"
        }
    }

    var body: some View {
        ScrollView {
            VStack(spacing: Spacing.xxl) {
                Spacer(minLength: 60)

                // Logo — centered, breathing, no box
                VStack(spacing: Spacing.md) {
                    CipherLogo(size: 80, animated: true)
                        .scaleEffect(appeared ? 1.0 : 0.8)
                        .opacity(appeared ? 1.0 : 0.0)

                    LogoText(titleSize: 26)
                        .opacity(appeared ? 1.0 : 0.0)
                }

                // Greeting + suggestions
                VStack(spacing: Spacing.md) {
                    Text(timeGreeting)
                        .font(.system(size: 18, weight: .semibold))
                        .foregroundColor(CipherTheme.textPrimary)
                        .opacity(appeared ? 1.0 : 0.0)

                    HStack(spacing: Spacing.sm) {
                        Text("How can I help?")
                            .font(.system(size: 15, weight: .medium))
                            .foregroundColor(CipherTheme.textSecondary)

                        if let onRefresh {
                            Button(action: onRefresh) {
                                Image(systemName: "arrow.triangle.2.circlepath")
                                    .font(.system(size: 12, weight: .medium))
                                    .foregroundColor(CipherTheme.textTertiary)
                            }
                        }
                    }
                    .opacity(appeared ? 1.0 : 0.0)

                    LazyVGrid(columns: [
                        GridItem(.flexible(), spacing: Spacing.sm),
                        GridItem(.flexible(), spacing: Spacing.sm)
                    ], spacing: Spacing.sm) {
                        ForEach(suggestions) { suggestion in
                            SuggestionChip(prompt: suggestion) {
                                onSuggestionTap(suggestion)
                            }
                        }
                    }
                    .opacity(appeared ? 1.0 : 0.0)
                }
                .padding(.horizontal, Spacing.lg)

                Spacer(minLength: 40)
            }
        }
        .onAppear {
            withAnimation(.easeOut(duration: 0.6)) {
                appeared = true
            }
        }
    }
}

// MARK: - Error Banner

struct ErrorBanner: View {
    let message: String
    var onDismiss: (() -> Void)?

    var body: some View {
        HStack(spacing: Spacing.sm) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 14, weight: .medium))
                .foregroundColor(CipherTheme.error)

            Text(message)
                .font(.system(size: 13))
                .foregroundColor(CipherTheme.textPrimary)
                .lineLimit(2)

            Spacer()

            if let onDismiss = onDismiss {
                Button(action: onDismiss) {
                    Image(systemName: "xmark")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundColor(CipherTheme.textTertiary)
                }
            }
        }
        .padding(Spacing.md)
        .background(
            RoundedRectangle(cornerRadius: CornerRadius.sm)
                .fill(.ultraThinMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: CornerRadius.sm)
                        .stroke(CipherTheme.error.opacity(0.2), lineWidth: 0.5)
                )
        )
        .padding(.horizontal, Spacing.md)
        .padding(.bottom, Spacing.xxs)
    }
}

// MARK: - Model Picker Sheet

struct ModelPickerSheet: View {
    @Binding var selected: ModelTier
    var onDismiss: () -> Void

    var body: some View {
        NavigationStack {
            List {
                ForEach(ModelTier.allCases, id: \.self) { tier in
                    Button(action: {
                        selected = tier
                        HapticsService.shared.selection()
                        onDismiss()
                    }) {
                        HStack(spacing: Spacing.md) {
                            Image(systemName: tier.icon)
                                .font(.system(size: 16, weight: .semibold))
                                .foregroundColor(CipherTheme.tierColor(tier.rawValue))
                                .frame(width: 32)

                            VStack(alignment: .leading, spacing: 2) {
                                Text(tier.displayName)
                                    .font(.system(size: 16, weight: .semibold))
                                    .foregroundColor(CipherTheme.textPrimary)

                                Text(tier.description)
                                    .font(.system(size: 13))
                                    .foregroundColor(CipherTheme.textSecondary)
                            }

                            Spacer()

                            if selected == tier {
                                Image(systemName: "checkmark.circle.fill")
                                    .font(.system(size: 20))
                                    .foregroundColor(CipherTheme.accent)
                            }
                        }
                        .padding(.vertical, Spacing.xxs)
                    }
                }
            }
            .navigationTitle("Select Model")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done", action: onDismiss)
                }
            }
        }
    }
}

// MARK: - Border Extensions

extension View {
    func borderTop(height: CGFloat, color: Color) -> some View {
        VStack(spacing: 0) {
            Divider()
                .background(color)
                .frame(height: height)
            self
        }
    }

    func borderBottom(height: CGFloat, color: Color) -> some View {
        VStack(spacing: 0) {
            self
            Divider()
                .background(color)
                .frame(height: height)
        }
    }
}

#Preview {
    ChatView()
}

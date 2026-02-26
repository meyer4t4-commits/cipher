import SwiftUI

// MARK: - Chat View

struct ChatView: View {
    @State private var viewModel: ChatViewModel
    @Environment(\.scenePhase) var scenePhase

    init(conversation: Conversation? = nil) {
        _viewModel = State(initialValue: ChatViewModel(conversation: conversation))
    }

    var body: some View {
        ZStack {
            CipherTheme.background.ignoresSafeArea()

            VStack(spacing: 0) {
                // Header
                chatHeader

                // Messages or Empty State
                if viewModel.currentConversation.messages.isEmpty {
                    ChatEmptyState(
                        suggestions: viewModel.suggestions,
                        onSuggestionTap: { suggestion in
                            viewModel.inputText = suggestion.fullPrompt
                            Task { await viewModel.sendMessage() }
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

                // Input Bar
                ChatInputBar(
                    text: $viewModel.inputText,
                    isLoading: viewModel.isLoading,
                    isStreaming: viewModel.isStreaming,
                    onSend: {
                        Task { await viewModel.sendMessage() }
                    },
                    onStop: {
                        viewModel.cancelStreaming()
                    },
                    onVoice: {
                        viewModel.showVoiceMode = true
                    },
                    onAttach: nil // Phase 2
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
        .onAppear {
            Task { await viewModel.checkServerHealth() }
        }
        .onChange(of: scenePhase) { _, newPhase in
            if newPhase == .active {
                Task { await viewModel.checkServerHealth() }
            }
        }
    }

    // MARK: - Chat Header

    private var chatHeader: some View {
        HStack(spacing: Spacing.md) {
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: Spacing.sm) {
                    Text(viewModel.currentConversation.title == "New Conversation" ? "Cipher" : viewModel.currentConversation.title)
                        .font(.system(size: 17, weight: .semibold))
                        .foregroundColor(CipherTheme.textPrimary)
                        .lineLimit(1)
                }

                ConnectionIndicator(isConnected: viewModel.isConnected, showLabel: true)
            }

            Spacer()

            // Model tier indicator
            Button(action: { viewModel.showModelPicker = true }) {
                HStack(spacing: 4) {
                    Image(systemName: viewModel.selectedModelTier.icon)
                        .font(.system(size: 11, weight: .semibold))
                    Text(viewModel.selectedModelTier.displayName)
                        .font(.system(size: 11, weight: .semibold))
                }
                .foregroundColor(CipherTheme.accent)
                .padding(.horizontal, 10)
                .padding(.vertical, 5)
                .background(
                    Capsule()
                        .fill(CipherTheme.accent.opacity(0.1))
                        .overlay(
                            Capsule()
                                .stroke(CipherTheme.accent.opacity(0.2), lineWidth: 0.5)
                        )
                )
            }

            // New chat button
            Button(action: { viewModel.startNewConversation() }) {
                Image(systemName: "square.and.pencil")
                    .font(.system(size: 18, weight: .medium))
                    .foregroundColor(CipherTheme.textSecondary)
            }
        }
        .padding(.horizontal, Spacing.lg)
        .padding(.vertical, Spacing.md)
        .background(
            CipherTheme.background
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
                        .transition(.opacity.combined(with: .move(edge: .bottom)))
                    }

                    if viewModel.isLoading && !viewModel.isStreaming {
                        TypingIndicator()
                            .padding(.horizontal, Spacing.lg)
                            .padding(.vertical, Spacing.sm)
                            .transition(.opacity)
                    }

                    // Bottom anchor
                    Color.clear
                        .frame(height: 1)
                        .id("bottom")
                }
                .padding(.top, Spacing.sm)
            }
            .onChange(of: viewModel.currentConversation.messages.count) {
                withAnimation(.easeOut(duration: 0.3)) {
                    proxy.scrollTo("bottom", anchor: .bottom)
                }
            }
            .onChange(of: viewModel.streamingText) {
                withAnimation(.easeOut(duration: 0.1)) {
                    proxy.scrollTo("bottom", anchor: .bottom)
                }
            }
        }
    }
}

// MARK: - Empty State

struct ChatEmptyState: View {
    let suggestions: [SuggestedPrompt]
    let onSuggestionTap: (SuggestedPrompt) -> Void

    var body: some View {
        ScrollView {
            VStack(spacing: Spacing.xxxl) {
                Spacer(minLength: 40)

                // Logo
                VStack(spacing: Spacing.lg) {
                    CipherLogo(size: 72, animated: true)
                    LogoText(titleSize: 28)
                    PrivacyBadge()
                }

                // Suggestions grid
                VStack(spacing: Spacing.md) {
                    Text("How can I help you?")
                        .font(.system(size: 16, weight: .medium))
                        .foregroundColor(CipherTheme.textSecondary)

                    LazyVGrid(columns: [
                        GridItem(.flexible(), spacing: Spacing.md),
                        GridItem(.flexible(), spacing: Spacing.md)
                    ], spacing: Spacing.md) {
                        ForEach(suggestions) { suggestion in
                            SuggestionChip(prompt: suggestion) {
                                onSuggestionTap(suggestion)
                            }
                        }
                    }
                }
                .padding(.horizontal, Spacing.lg)

                Spacer(minLength: 40)
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
                .fill(CipherTheme.error.opacity(0.1))
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

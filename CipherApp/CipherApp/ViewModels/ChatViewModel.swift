import Foundation
import SwiftUI
import UIKit

// MARK: - Chat ViewModel

@Observable
class ChatViewModel {
    var currentConversation: Conversation
    var isLoading = false
    var isStreaming = false

    /// Minimum time the thinking animation stays visible AFTER the response arrives.
    /// This guarantees the Cipher logo spin is always seen, even on instant responses.
    private let minimumThinkingDuration: TimeInterval = 1.5
    private var thinkingStartTime: Date?
    var errorMessage: String?
    var inputText = ""
    var isConnected = false
    var streamingText = ""
    var showModelPicker = false
    var showVoiceMode = false
    var showImagePicker = false
    var selectedSuggestion: String?

    // MARK: - Image Attachments
    var pendingImages: [UIImage] = []

    // MARK: - Agent Recommendation & Interaction
    var agentRecommendation: RecommendedAgentInfo?
    var showRecommendation = false
    var pendingInteraction: AgentInteractionAPI?
    var showInteractionSheet = false
    var pendingInteractionCount = 0

    @ObservationIgnored let api = CipherAPI.shared
    @ObservationIgnored let haptics = HapticsService.shared
    @ObservationIgnored let storage = ConversationStorage.shared
    @ObservationIgnored var currentStreamTask: Task<Void, Never>?
    @ObservationIgnored var interactionPollTask: Task<Void, Never>?

    // MARK: - Settings

    var selectedModelTier: ModelTier {
        get {
            let raw = UserDefaults.standard.string(forKey: "model_tier") ?? "auto"
            return ModelTier(rawValue: raw) ?? .auto
        }
        set {
            UserDefaults.standard.set(newValue.rawValue, forKey: "model_tier")
        }
    }

    var includeMemory: Bool {
        get { UserDefaults.standard.object(forKey: "include_memory") as? Bool ?? true }
        set { UserDefaults.standard.set(newValue, forKey: "include_memory") }
    }

    var maxTokens: Int {
        get { UserDefaults.standard.object(forKey: "max_tokens") as? Int ?? 4096 }
        set { UserDefaults.standard.set(newValue, forKey: "max_tokens") }
    }

    var temperature: Double {
        get { UserDefaults.standard.object(forKey: "temperature") as? Double ?? 0.7 }
        set { UserDefaults.standard.set(newValue, forKey: "temperature") }
    }

    var streamingEnabled: Bool {
        get { UserDefaults.standard.object(forKey: "streaming_enabled") as? Bool ?? true }
        set { UserDefaults.standard.set(newValue, forKey: "streaming_enabled") }
    }

    // MARK: - Suggested Prompts (random 4 from pool each session)

    var suggestions: [SuggestedPrompt] = Array(SuggestedPrompt.pool.shuffled().prefix(4))

    /// Refresh with 4 new random suggestions
    func refreshSuggestions() {
        suggestions = Array(SuggestedPrompt.pool.shuffled().prefix(4))
    }

    // MARK: - Active Conversation Persistence Key
    private static let activeConversationKey = "active_conversation_id"

    // MARK: - Init

    init(conversation: Conversation? = nil) {
        if let conversation = conversation {
            self.currentConversation = conversation
        } else if let savedId = UserDefaults.standard.string(forKey: Self.activeConversationKey),
                  let uuid = UUID(uuidString: savedId),
                  let saved = ConversationStorage.shared.loadConversation(id: uuid) {
            self.currentConversation = saved
        } else {
            self.currentConversation = Conversation(id: UUID(), title: "New Conversation")
        }
    }

    /// Reload the current conversation from disk (called on tab reappear)
    @MainActor
    func reloadIfNeeded() {
        // Don't reload while actively sending/streaming
        guard !isLoading, !isStreaming else { return }

        let convId = currentConversation.id
        if let fresh = storage.loadConversation(id: convId) {
            currentConversation = fresh
        }
    }

    /// Persist which conversation is active so it survives tab switches
    private func saveActiveConversationId() {
        UserDefaults.standard.set(currentConversation.id.uuidString, forKey: Self.activeConversationKey)
    }

    // MARK: - Send Message

    @MainActor
    func sendMessage() async {
        let messageText = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        let hasImages = !pendingImages.isEmpty
        guard !messageText.isEmpty || hasImages else { return }

        // Compress images to base64
        let imageStrings = pendingImages.compactMap { image -> String? in
            // Resize large images and compress to JPEG
            let maxDimension: CGFloat = 1920
            let resized: UIImage
            if max(image.size.width, image.size.height) > maxDimension {
                let scale = maxDimension / max(image.size.width, image.size.height)
                let newSize = CGSize(width: image.size.width * scale, height: image.size.height * scale)
                UIGraphicsBeginImageContextWithOptions(newSize, false, 1.0)
                image.draw(in: CGRect(origin: .zero, size: newSize))
                resized = UIGraphicsGetImageFromCurrentImageContext() ?? image
                UIGraphicsEndImageContext()
            } else {
                resized = image
            }
            return resized.jpegData(compressionQuality: 0.7)?.base64EncodedString()
        }

        // Build user message with attachments
        let attachments: [Attachment] = pendingImages.enumerated().map { index, image in
            Attachment(
                fileName: "image_\(index + 1).jpg",
                mimeType: "image/jpeg",
                fileSize: Int(image.jpegData(compressionQuality: 0.7)?.count ?? 0),
                thumbnailData: image.jpegData(compressionQuality: 0.3)
            )
        }

        let effectiveText = messageText.isEmpty ? "[Image attached]" : messageText
        inputText = ""
        pendingImages = []
        isLoading = true
        errorMessage = nil
        haptics.mediumTap()

        let userMessage = Message(
            conversationId: currentConversation.id,
            content: effectiveText,
            role: .user,
            status: .delivered,
            attachments: attachments
        )
        currentConversation.addMessage(userMessage)

        if streamingEnabled {
            await sendStreamingMessage(effectiveText, images: imageStrings)
        } else {
            await sendStandardMessage(effectiveText, images: imageStrings)
        }
    }

    @MainActor
    func removeImage(at index: Int) {
        guard index < pendingImages.count else { return }
        pendingImages.remove(at: index)
    }

    // MARK: - Standard Send

    @MainActor
    private func sendStandardMessage(_ text: String, images: [String] = []) async {
        do {
            let response = try await api.sendMessage(
                message: text,
                conversationId: currentConversation.id,
                modelTier: selectedModelTier.rawValue,
                includeMemory: includeMemory,
                maxTokens: maxTokens,
                temperature: temperature,
                images: images
            )

            // Start the thinking timer NOW — when response arrives, not when user sent.
            // This ensures the logo animation plays for at least minimumThinkingDuration
            // from this point forward, so the user always sees it.
            thinkingStartTime = Date()

            let assistantMessage = Message(
                conversationId: response.conversationId,
                content: response.message,
                role: .assistant,
                timestamp: Date(),
                status: .delivered,
                modelUsed: response.modelUsed,
                tokensUsed: response.tokensUsed,
                costUsd: response.costUsd
            )

            currentConversation.id = response.conversationId
            currentConversation.addMessage(assistantMessage)
            updateTitle(from: text)
            storage.saveConversation(currentConversation)
            saveActiveConversationId()
            haptics.success()

            // Check for agent recommendation — auto-deploy at very high confidence
            if let rec = response.recommendedAgent {
                if rec.confidence > 0.85 {
                    // High confidence — deploy immediately, notify in chat
                    agentRecommendation = rec
                    showRecommendation = true
                } else if rec.confidence > 0.5 {
                    // Medium confidence — show deploy banner
                    agentRecommendation = rec
                    showRecommendation = true
                }
            }
        } catch {
            handleSendError(error)
        }

        await finishThinking()
    }

    /// Ensures the thinking animation stays visible for at least `minimumThinkingDuration`.
    /// This guarantees the Cipher logo always gets screen time, even on fast responses.
    @MainActor
    private func finishThinking() async {
        if let start = thinkingStartTime {
            let elapsed = Date().timeIntervalSince(start)
            if elapsed < minimumThinkingDuration {
                try? await Task.sleep(nanoseconds: UInt64((minimumThinkingDuration - elapsed) * 1_000_000_000))
            }
        }
        isLoading = false
        thinkingStartTime = nil
    }

    // MARK: - Streaming Send

    @MainActor
    private func sendStreamingMessage(_ text: String, images: [String] = []) async {
        isStreaming = true
        streamingText = ""

        // Add placeholder assistant message
        let placeholderMessage = Message(
            conversationId: currentConversation.id,
            content: "",
            role: .assistant,
            status: .streaming
        )
        currentConversation.addMessage(placeholderMessage)
        let messageIndex = currentConversation.messages.count - 1

        let stream = api.streamMessage(
            message: text,
            conversationId: currentConversation.id,
            modelTier: selectedModelTier.rawValue,
            includeMemory: includeMemory,
            maxTokens: maxTokens,
            temperature: temperature,
            images: images
        )

        var fullContent = ""
        var finalModel: String?
        var finalTokens: Int?
        var finalCost: Double?
        var finalConversationId: UUID?

        do {
            for try await chunk in stream {
                switch chunk.type {
                case "token":
                    if let content = chunk.content {
                        // Start thinking timer on first token so logo always gets screen time
                        if thinkingStartTime == nil {
                            thinkingStartTime = Date()
                        }
                        fullContent += content
                        streamingText = fullContent
                        // Update the message in place
                        if messageIndex < currentConversation.messages.count {
                            currentConversation.messages[messageIndex].content = fullContent
                        }
                    }
                case "metadata":
                    finalModel = chunk.modelUsed
                    finalTokens = chunk.tokensUsed
                    finalCost = chunk.costUsd
                    finalConversationId = chunk.conversationId
                case "done":
                    break
                case "error":
                    throw APIError.streamingError(chunk.content ?? "Unknown streaming error")
                default:
                    break
                }
            }

            // BLANK MESSAGE GUARD: detect empty responses and show retry option
            let trimmedContent = fullContent.trimmingCharacters(in: .whitespacesAndNewlines)
            let effectiveContent = trimmedContent.isEmpty
                ? "Response was empty — tap Retry or try a different model."
                : fullContent
            let effectiveStatus: MessageStatus = trimmedContent.isEmpty ? .failed : .delivered

            // Finalize the message
            if messageIndex < currentConversation.messages.count {
                currentConversation.messages[messageIndex] = Message(
                    id: currentConversation.messages[messageIndex].id,
                    conversationId: finalConversationId ?? currentConversation.id,
                    content: effectiveContent,
                    role: .assistant,
                    timestamp: Date(),
                    status: effectiveStatus,
                    modelUsed: finalModel,
                    tokensUsed: finalTokens,
                    costUsd: finalCost
                )
            }

            if let convId = finalConversationId {
                currentConversation.id = convId
            }

            updateTitle(from: text)
            storage.saveConversation(currentConversation)
            saveActiveConversationId()
            if effectiveStatus == .delivered {
                haptics.success()
            } else {
                haptics.error()
            }
        } catch {
            // If streaming failed, show error inline instead of falling back silently
            let errorText = "Connection error: \(error.localizedDescription). Tap Retry to try again."
            if messageIndex < currentConversation.messages.count {
                currentConversation.messages[messageIndex] = Message(
                    id: currentConversation.messages[messageIndex].id,
                    conversationId: currentConversation.id,
                    content: errorText,
                    role: .assistant,
                    timestamp: Date(),
                    status: .failed,
                    modelUsed: nil,
                    tokensUsed: nil,
                    costUsd: nil
                )
            }
            haptics.error()
        }

        isStreaming = false
        await finishThinking()
        streamingText = ""
    }

    // MARK: - Cancel Streaming

    @MainActor
    func cancelStreaming() {
        currentStreamTask?.cancel()
        currentStreamTask = nil
        isStreaming = false
        isLoading = false

        // Mark last message as cancelled if it was streaming
        if let lastIndex = currentConversation.messages.indices.last,
           currentConversation.messages[lastIndex].status == .streaming {
            currentConversation.messages[lastIndex].status = .cancelled
        }
    }

    // MARK: - Voice Input

    @MainActor
    func sendVoiceMessage(_ text: String) async {
        inputText = text
        await sendMessage()
    }

    // MARK: - Helpers

    @MainActor
    func startNewConversation() {
        currentConversation = Conversation(id: UUID(), title: "New Conversation")
        inputText = ""
        errorMessage = nil
        isLoading = false
        isStreaming = false
        saveActiveConversationId()
    }

    @MainActor
    func checkServerHealth() async {
        self.isConnected = await api.checkHealth()
    }

    func deleteMessage(at index: Int) {
        guard index < currentConversation.messages.count else { return }
        currentConversation.messages.remove(at: index)
        storage.saveConversation(currentConversation)
    }

    func copyMessage(_ message: Message) {
        UIPasteboard.general.string = message.content
        haptics.lightTap()
    }

    func retryLastMessage() async {
        guard let lastUserMessage = currentConversation.messages.last(where: { $0.role == .user }) else { return }

        // Remove failed assistant message if it exists
        if let last = currentConversation.messages.last, last.role == .assistant && last.isFailed {
            currentConversation.messages.removeLast()
        }

        inputText = lastUserMessage.content
        // Remove the user message too so it gets re-sent
        if let idx = currentConversation.messages.lastIndex(where: { $0.id == lastUserMessage.id }) {
            currentConversation.messages.remove(at: idx)
        }
        await sendMessage()
    }

    @MainActor
    func clearConversationHistory() {
        storage.deleteAllConversations()
        currentConversation = Conversation(id: UUID(), title: "New Conversation")
    }

    private func updateTitle(from message: String) {
        if currentConversation.title == "New Conversation" {
            let words = message.split(separator: " ").prefix(6).joined(separator: " ")
            currentConversation.title = words.isEmpty ? "New Conversation" : String(words)
        }
    }

    private func handleSendError(_ error: Error) {
        errorMessage = error.localizedDescription
        haptics.error()
        // Mark last user message for potential retry
        if let lastIndex = currentConversation.messages.indices.last,
           currentConversation.messages[lastIndex].role == .user {
            // Keep user message but show error
        }
    }

    // MARK: - Agent Recommendation

    @MainActor
    func spawnRecommendedAgent() async {
        guard let rec = agentRecommendation else { return }
        dismissRecommendation()

        do {
            let tasks = [SpawnTaskItem(agentName: rec.agentName, instruction: rec.suggestedInstruction)]
            _ = try await api.spawnBatch(tasks: tasks)
            haptics.success()

            // Add system message about spawn
            let systemMsg = Message(
                conversationId: currentConversation.id,
                content: "Spawned **\(rec.displayName)** to handle: \(rec.suggestedInstruction)",
                role: .assistant,
                status: .delivered
            )
            currentConversation.addMessage(systemMsg)
        } catch {
            errorMessage = "Failed to spawn agent: \(error.localizedDescription)"
            haptics.error()
        }
    }

    @MainActor
    func dismissRecommendation() {
        withAnimation(.easeOut(duration: 0.25)) {
            showRecommendation = false
            agentRecommendation = nil
        }
    }

    // MARK: - Interaction Polling

    @MainActor
    func startInteractionPolling() {
        stopInteractionPolling()
        // Immediate first check, then poll every 10 seconds
        interactionPollTask = Task { @MainActor [weak self] in
            await self?.fetchPendingInteractions()
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 10_000_000_000)
                await self?.fetchPendingInteractions()
            }
        }
    }

    @MainActor
    func stopInteractionPolling() {
        interactionPollTask?.cancel()
        interactionPollTask = nil
    }

    @MainActor
    func fetchPendingInteractions() async {
        do {
            let response = try await api.getPendingInteractions()
            pendingInteractionCount = response.total

            // Show the first pending interaction if we don't already have one open
            if let first = response.interactions.first, !showInteractionSheet {
                pendingInteraction = first
                showInteractionSheet = true
                haptics.success()
            }
        } catch {
            // Silently fail — this is background polling
        }
    }

    @MainActor
    func answerInteraction(_ interactionId: String, response: String) async {
        do {
            _ = try await api.answerInteraction(interactionId: interactionId, userResponse: response)
            showInteractionSheet = false
            pendingInteraction = nil
            haptics.success()

            // Re-fetch to show next interaction if any
            await fetchPendingInteractions()
        } catch {
            errorMessage = "Failed to submit response: \(error.localizedDescription)"
            haptics.error()
        }
    }

    @MainActor
    func dismissInteraction(_ interactionId: String) async {
        do {
            try await api.dismissInteraction(interactionId: interactionId)
            showInteractionSheet = false
            pendingInteraction = nil
        } catch {
            // Silently dismiss locally even if server fails
            showInteractionSheet = false
            pendingInteraction = nil
        }
    }
}

// MARK: - Suggested Prompt

struct SuggestedPrompt: Identifiable {
    let id = UUID()
    let icon: String
    let title: String
    let subtitle: String

    var fullPrompt: String { "\(title) \(subtitle)" }

    // Large rotating pool — 4 are randomly chosen each session
    static let pool: [SuggestedPrompt] = [
        // Writing & Communication
        SuggestedPrompt(icon: "pencil.line", title: "Help me write", subtitle: "a compelling cover letter"),
        SuggestedPrompt(icon: "envelope.fill", title: "Draft an email", subtitle: "that sounds professional but warm"),
        SuggestedPrompt(icon: "doc.text.fill", title: "Write a proposal", subtitle: "for a new business idea"),
        SuggestedPrompt(icon: "text.quote", title: "Rewrite this", subtitle: "in a more persuasive tone"),
        SuggestedPrompt(icon: "textformat.abc", title: "Proofread and edit", subtitle: "my writing for clarity"),
        SuggestedPrompt(icon: "bubble.left.fill", title: "Help me respond", subtitle: "to a tricky message diplomatically"),
        SuggestedPrompt(icon: "newspaper.fill", title: "Write a blog post", subtitle: "about an industry trend"),

        // Brainstorming & Ideas
        SuggestedPrompt(icon: "lightbulb.fill", title: "Brainstorm names", subtitle: "for a new product or brand"),
        SuggestedPrompt(icon: "sparkles", title: "Generate ideas", subtitle: "for a side project that makes money"),
        SuggestedPrompt(icon: "puzzlepiece.fill", title: "Solve a problem", subtitle: "I've been stuck on for days"),
        SuggestedPrompt(icon: "target", title: "Help me plan", subtitle: "my goals for the next quarter"),
        SuggestedPrompt(icon: "brain", title: "Think through", subtitle: "the pros and cons of a decision"),
        SuggestedPrompt(icon: "theatermasks.fill", title: "Play devil's advocate", subtitle: "on my business strategy"),
        SuggestedPrompt(icon: "bolt.fill", title: "Give me a quick", subtitle: "creative breakthrough for a stuck project"),

        // Code & Technical
        SuggestedPrompt(icon: "chevron.left.forwardslash.chevron.right", title: "Write a script", subtitle: "to automate something tedious"),
        SuggestedPrompt(icon: "ladybug.fill", title: "Debug this code", subtitle: "I can't figure out what's wrong"),
        SuggestedPrompt(icon: "terminal.fill", title: "Explain this error", subtitle: "in plain English"),
        SuggestedPrompt(icon: "hammer.fill", title: "Build an API", subtitle: "endpoint for my app"),
        SuggestedPrompt(icon: "cpu.fill", title: "Optimize this", subtitle: "function for better performance"),
        SuggestedPrompt(icon: "externaldrive.connected.to.line.below.fill", title: "Design a database", subtitle: "schema for my project"),
        SuggestedPrompt(icon: "swift", title: "Help me with Swift", subtitle: "patterns and best practices"),

        // Analysis & Research
        SuggestedPrompt(icon: "chart.bar.fill", title: "Analyze trends", subtitle: "in my industry this quarter"),
        SuggestedPrompt(icon: "magnifyingglass", title: "Research the market", subtitle: "for a new product opportunity"),
        SuggestedPrompt(icon: "chart.pie.fill", title: "Break down the data", subtitle: "and tell me what matters"),
        SuggestedPrompt(icon: "doc.text.magnifyingglass", title: "Summarize this article", subtitle: "and pull out the key takeaways"),
        SuggestedPrompt(icon: "globe", title: "What's happening in", subtitle: "AI and tech this week"),
        SuggestedPrompt(icon: "building.2.fill", title: "Compare companies", subtitle: "and their competitive advantages"),

        // Business & Strategy
        SuggestedPrompt(icon: "dollarsign.circle.fill", title: "Model the financials", subtitle: "for a new venture"),
        SuggestedPrompt(icon: "chart.line.uptrend.xyaxis", title: "Help me forecast", subtitle: "revenue for next quarter"),
        SuggestedPrompt(icon: "person.3.fill", title: "Plan a pitch", subtitle: "for investors or partners"),
        SuggestedPrompt(icon: "building.columns.fill", title: "Evaluate a deal", subtitle: "and flag the risks"),
        SuggestedPrompt(icon: "briefcase.fill", title: "Create a strategy", subtitle: "for scaling my business"),
        SuggestedPrompt(icon: "arrow.triangle.branch", title: "Map out a workflow", subtitle: "for my team's process"),

        // Personal & Productivity
        SuggestedPrompt(icon: "calendar", title: "Plan my week", subtitle: "with priorities and time blocks"),
        SuggestedPrompt(icon: "list.bullet.clipboard.fill", title: "Create a checklist", subtitle: "for launching something new"),
        SuggestedPrompt(icon: "book.fill", title: "Recommend books", subtitle: "on leadership and growth"),
        SuggestedPrompt(icon: "figure.run", title: "Design a routine", subtitle: "for peak performance and focus"),
        SuggestedPrompt(icon: "fork.knife", title: "Plan meals", subtitle: "that are healthy and easy to prep"),

        // Creative & Content
        SuggestedPrompt(icon: "paintbrush.fill", title: "Design a concept", subtitle: "for a new app feature"),
        SuggestedPrompt(icon: "film.fill", title: "Write a script", subtitle: "for a short video or ad"),
        SuggestedPrompt(icon: "music.note", title: "Write song lyrics", subtitle: "about a feeling or experience"),
        SuggestedPrompt(icon: "camera.fill", title: "Plan a content series", subtitle: "for social media growth"),
        SuggestedPrompt(icon: "megaphone.fill", title: "Craft a tagline", subtitle: "that's memorable and sharp"),

        // Learning & Explanation
        SuggestedPrompt(icon: "graduationcap.fill", title: "Explain like I'm 10", subtitle: "how neural networks work"),
        SuggestedPrompt(icon: "questionmark.circle.fill", title: "Walk me through", subtitle: "how to read a balance sheet"),
        SuggestedPrompt(icon: "flame.fill", title: "What's the hottest", subtitle: "technology I should learn next"),
        SuggestedPrompt(icon: "map.fill", title: "Create a roadmap", subtitle: "for learning a new skill"),

        // Real Estate & Property (Apex)
        SuggestedPrompt(icon: "house.fill", title: "Analyze a property", subtitle: "for investment potential"),
        SuggestedPrompt(icon: "building.fill", title: "Compare neighborhoods", subtitle: "for growth and rental yield"),
        SuggestedPrompt(icon: "key.fill", title: "Draft a lease", subtitle: "or review rental terms"),
        SuggestedPrompt(icon: "banknote.fill", title: "Calculate ROI", subtitle: "on a real estate deal"),
    ]
}

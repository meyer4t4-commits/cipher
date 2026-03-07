import Foundation
import SwiftUI

// MARK: - Chat ViewModel

@Observable
class ChatViewModel {
    var currentConversation: Conversation
    var isLoading = false
    var isStreaming = false
    var errorMessage: String?
    var inputText = ""
    var isConnected = false
    var streamingText = ""
    var showModelPicker = false
    var showVoiceMode = false
    var selectedSuggestion: String?

    @ObservationIgnored let api = OrchidAPI.shared
    @ObservationIgnored let haptics = HapticsService.shared
    @ObservationIgnored let storage = ConversationStorage.shared
    @ObservationIgnored var currentStreamTask: Task<Void, Never>?

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

    // MARK: - Suggested Prompts

    let suggestions = [
        SuggestedPrompt(icon: "pencil.line", title: "Help me write", subtitle: "an email, essay, or report"),
        SuggestedPrompt(icon: "lightbulb.fill", title: "Brainstorm ideas", subtitle: "for a project or problem"),
        SuggestedPrompt(icon: "chevron.left.forwardslash.chevron.right", title: "Write code", subtitle: "in any programming language"),
        SuggestedPrompt(icon: "chart.bar.fill", title: "Analyze data", subtitle: "and find insights"),
    ]

    // MARK: - Init

    init(conversation: Conversation? = nil) {
        if let conversation = conversation {
            self.currentConversation = conversation
        } else {
            self.currentConversation = Conversation(id: UUID(), title: "New Conversation")
        }
    }

    // MARK: - Send Message

    @MainActor
    func sendMessage() async {
        let messageText = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !messageText.isEmpty else { return }

        inputText = ""
        isLoading = true
        errorMessage = nil
        haptics.mediumTap()

        let userMessage = Message(
            conversationId: currentConversation.id,
            content: messageText,
            role: .user,
            status: .delivered
        )
        currentConversation.addMessage(userMessage)

        if streamingEnabled {
            await sendStreamingMessage(messageText)
        } else {
            await sendStandardMessage(messageText)
        }
    }

    // MARK: - Standard Send

    @MainActor
    private func sendStandardMessage(_ text: String) async {
        do {
            let response = try await api.sendMessage(
                message: text,
                conversationId: currentConversation.id,
                modelTier: selectedModelTier.rawValue,
                includeMemory: includeMemory,
                maxTokens: maxTokens,
                temperature: temperature
            )

            let assistantMessage = Message(
                conversationId: response.conversationId,
                content: response.message,
                role: .assistant,
                timestamp: response.timestamp,
                status: .delivered,
                modelUsed: response.modelUsed,
                tokensUsed: response.tokensUsed,
                costUsd: response.costUsd
            )

            currentConversation.id = response.conversationId
            currentConversation.addMessage(assistantMessage)
            updateTitle(from: text)
            storage.saveConversation(currentConversation)
            haptics.success()
        } catch {
            handleSendError(error)
        }

        isLoading = false
    }

    // MARK: - Streaming Send

    @MainActor
    private func sendStreamingMessage(_ text: String) async {
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
            temperature: temperature
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

            // Finalize the message
            if messageIndex < currentConversation.messages.count {
                currentConversation.messages[messageIndex] = Message(
                    id: currentConversation.messages[messageIndex].id,
                    conversationId: finalConversationId ?? currentConversation.id,
                    content: fullContent,
                    role: .assistant,
                    timestamp: Date(),
                    status: .delivered,
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
            haptics.success()
        } catch {
            // If streaming failed, fall back to standard
            if messageIndex < currentConversation.messages.count {
                currentConversation.messages.remove(at: messageIndex)
            }
            await sendStandardMessage(text)
        }

        isStreaming = false
        isLoading = false
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
}

// MARK: - Suggested Prompt

struct SuggestedPrompt: Identifiable {
    let id = UUID()
    let icon: String
    let title: String
    let subtitle: String

    var fullPrompt: String { "\(title) \(subtitle)" }
}

import Foundation

// MARK: - API Error

enum APIError: LocalizedError {
    case invalidURL
    case invalidRequest
    case invalidResponse
    case decodingError
    case networkError(String)
    case serverError(Int, String)
    case streamingError(String)
    case timeout
    case cancelled
    case unknown

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid server URL. Check your settings."
        case .invalidRequest:
            return "Failed to prepare request"
        case .invalidResponse:
            return "Invalid response from Orchid"
        case .decodingError:
            return "Failed to decode response"
        case .networkError(let message):
            return "Network error: \(message)"
        case .serverError(let code, let message):
            return "Server error (\(code)): \(message)"
        case .streamingError(let message):
            return "Streaming error: \(message)"
        case .timeout:
            return "Request timed out. Is Orchid running?"
        case .cancelled:
            return "Request was cancelled"
        case .unknown:
            return "An unknown error occurred"
        }
    }
}

// MARK: - Orchid API Client

@Observable
class OrchidAPI {
    static let shared = OrchidAPI()

    var serverURL: String {
        get {
            UserDefaults.standard.string(forKey: "orchid_server_url") ?? AppConstants.defaultServerURL
        }
        set {
            UserDefaults.standard.set(newValue, forKey: "orchid_server_url")
        }
    }

    var isHealthy = false
    var lastHealthCheck: Date?
    var latencyMs: Int?

    @ObservationIgnored let session: URLSession
    @ObservationIgnored let decoder: JSONDecoder
    @ObservationIgnored let encoder: JSONEncoder

    init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 300
        config.waitsForConnectivity = true
        self.session = URLSession(configuration: config)

        self.decoder = JSONDecoder()
        self.decoder.dateDecodingStrategy = .iso8601

        self.encoder = JSONEncoder()
        self.encoder.dateEncodingStrategy = .iso8601
    }

    // MARK: - Health Check

    @MainActor
    func checkHealth() async -> Bool {
        let start = Date()
        do {
            guard let url = URL(string: serverURL + AppConstants.apiBasePath + AppConstants.healthEndpoint) else {
                throw APIError.invalidURL
            }

            let (data, response) = try await session.data(from: url)

            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200 else {
                throw APIError.invalidResponse
            }

            let healthResponse = try decoder.decode(HealthResponse.self, from: data)
            self.isHealthy = healthResponse.status == "ok"
            self.lastHealthCheck = Date()
            self.latencyMs = Int(Date().timeIntervalSince(start) * 1000)
            return isHealthy
        } catch {
            self.isHealthy = false
            self.latencyMs = nil
            return false
        }
    }

    // MARK: - Send Message (Standard)

    func sendMessage(
        message: String,
        conversationId: UUID? = nil,
        modelTier: String = AppConstants.defaultModelTier,
        includeMemory: Bool = AppConstants.defaultIncludeMemory,
        maxTokens: Int = AppConstants.defaultMaxTokens,
        temperature: Double = AppConstants.defaultTemperature
    ) async throws -> ChatResponse {
        let request = ChatRequest(
            message: message,
            conversationId: conversationId,
            modelTier: modelTier,
            includeMemory: includeMemory,
            maxTokens: maxTokens,
            temperature: temperature,
            stream: false
        )

        guard let url = URL(string: serverURL + AppConstants.apiBasePath + AppConstants.chatEndpoint) else {
            throw APIError.invalidURL
        }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")

        do {
            urlRequest.httpBody = try encoder.encode(request)
        } catch {
            throw APIError.invalidRequest
        }

        let (data, response) = try await session.data(for: urlRequest)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            let errorMessage = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw APIError.serverError(httpResponse.statusCode, errorMessage)
        }

        do {
            return try decoder.decode(ChatResponse.self, from: data)
        } catch {
            throw APIError.decodingError
        }
    }

    // MARK: - Stream Message (SSE)

    func streamMessage(
        message: String,
        conversationId: UUID? = nil,
        modelTier: String = AppConstants.defaultModelTier,
        includeMemory: Bool = AppConstants.defaultIncludeMemory,
        maxTokens: Int = AppConstants.defaultMaxTokens,
        temperature: Double = AppConstants.defaultTemperature
    ) -> AsyncThrowingStream<StreamChunk, Error> {
        AsyncThrowingStream { continuation in
            Task {
                do {
                    let request = ChatRequest(
                        message: message,
                        conversationId: conversationId,
                        modelTier: modelTier,
                        includeMemory: includeMemory,
                        maxTokens: maxTokens,
                        temperature: temperature,
                        stream: true
                    )

                    guard let url = URL(string: serverURL + AppConstants.apiBasePath + AppConstants.chatEndpoint) else {
                        throw APIError.invalidURL
                    }

                    var urlRequest = URLRequest(url: url)
                    urlRequest.httpMethod = "POST"
                    urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
                    urlRequest.setValue("text/event-stream", forHTTPHeaderField: "Accept")
                    urlRequest.httpBody = try self.encoder.encode(request)

                    let (bytes, response) = try await self.session.bytes(for: urlRequest)

                    guard let httpResponse = response as? HTTPURLResponse,
                          httpResponse.statusCode == 200 else {
                        throw APIError.invalidResponse
                    }

                    for try await line in bytes.lines {
                        if line.hasPrefix("data: ") {
                            let jsonStr = String(line.dropFirst(6))
                            if jsonStr == "[DONE]" {
                                continuation.finish()
                                return
                            }
                            if let data = jsonStr.data(using: .utf8),
                               let chunk = try? self.decoder.decode(StreamChunk.self, from: data) {
                                continuation.yield(chunk)
                            }
                        }
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }

    // MARK: - Fetch Conversations

    func fetchConversations() async throws -> [Conversation] {
        guard let url = URL(string: serverURL + AppConstants.apiBasePath + AppConstants.conversationsEndpoint) else {
            throw APIError.invalidURL
        }

        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        do {
            let listResponse = try decoder.decode(ConversationListResponse.self, from: data)
            return listResponse.conversations.map { $0.toConversation() }
        } catch {
            throw APIError.decodingError
        }
    }

    // MARK: - Voice Synthesis

    func synthesizeSpeech(text: String, voiceId: String?) async throws -> Data {
        let endpoint = serverURL + AppConstants.apiBasePath + "/voice/synthesize"
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        let request = SynthesizeSpeechRequest(
            text: text,
            voiceId: voiceId ?? "default"
        )

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")

        do {
            urlRequest.httpBody = try encoder.encode(request)
        } catch {
            throw APIError.invalidRequest
        }

        let (data, response) = try await session.data(for: urlRequest)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            let errorMessage = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw APIError.serverError(httpResponse.statusCode, errorMessage)
        }

        return data
    }

    // MARK: - Voice Cloning

    func cloneVoice(audioData: Data, name: String) async throws -> String {
        let endpoint = serverURL + AppConstants.apiBasePath + "/voice/clone"
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"

        let boundary = UUID().uuidString
        urlRequest.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()

        // Add name field
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"name\"\r\n\r\n".data(using: .utf8)!)
        body.append("\(name)\r\n".data(using: .utf8)!)

        // Add audio file
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"audio\"; filename=\"voice.wav\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: audio/wav\r\n\r\n".data(using: .utf8)!)
        body.append(audioData)
        body.append("\r\n".data(using: .utf8)!)
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)

        urlRequest.httpBody = body

        let (data, response) = try await session.data(for: urlRequest)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            let errorMessage = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw APIError.serverError(httpResponse.statusCode, errorMessage)
        }

        do {
            let result = try decoder.decode(CloneVoiceResponse.self, from: data)
            return result.voiceId
        } catch {
            throw APIError.decodingError
        }
    }

    // MARK: - List Voices

    func listVoices() async throws -> [VoiceInfo] {
        let endpoint = serverURL + AppConstants.apiBasePath + "/voice/list"
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        do {
            let response = try decoder.decode(ListVoicesResponse.self, from: data)
            return response.voices
        } catch {
            throw APIError.decodingError
        }
    }

    // MARK: - Voice Usage

    func getVoiceUsage() async throws -> VoiceUsage {
        let endpoint = serverURL + AppConstants.apiBasePath + "/voice/usage"
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        do {
            return try decoder.decode(VoiceUsage.self, from: data)
        } catch {
            throw APIError.decodingError
        }
    }
}

// MARK: - Voice API Models

struct SynthesizeSpeechRequest: Codable {
    let text: String
    let voiceId: String

    enum CodingKeys: String, CodingKey {
        case text
        case voiceId = "voice_id"
    }
}

struct CloneVoiceResponse: Codable {
    let voiceId: String
    let name: String

    enum CodingKeys: String, CodingKey {
        case voiceId = "voice_id"
        case name
    }
}

struct ListVoicesResponse: Codable {
    let voices: [VoiceInfo]
}

struct VoiceInfo: Codable, Identifiable {
    let id: String
    let name: String
    let isCloned: Bool

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case isCloned = "is_cloned"
    }
}

struct VoiceUsage: Codable {
    let charactersUsed: Int
    let charactersRemaining: Int
    let totalCharacters: Int

    enum CodingKeys: String, CodingKey {
        case charactersUsed = "characters_used"
        case charactersRemaining = "characters_remaining"
        case totalCharacters = "total_characters"
    }
}

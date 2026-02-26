import Foundation

// MARK: - Conversation Storage (Local Persistence)

final class ConversationStorage {
    static let shared = ConversationStorage()

    private let fileManager = FileManager.default
    private let documentsPath: URL
    private let projectsPath: URL
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    private init() {
        let docs = fileManager.urls(for: .documentDirectory, in: .userDomainMask)[0]
        documentsPath = docs.appendingPathComponent("Cipher/conversations")
        projectsPath = docs.appendingPathComponent("Cipher/projects")

        try? fileManager.createDirectory(at: documentsPath, withIntermediateDirectories: true)
        try? fileManager.createDirectory(at: projectsPath, withIntermediateDirectories: true)

        encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = .prettyPrinted

        decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
    }

    // MARK: - Conversations

    func saveConversation(_ conversation: Conversation) {
        do {
            let data = try encoder.encode(conversation)
            let url = documentsPath.appendingPathComponent("\(conversation.id.uuidString).json")
            try data.write(to: url)
        } catch {
            print("[ConversationStorage] Save failed: \(error)")
        }
    }

    func loadConversation(id: UUID) -> Conversation? {
        do {
            let url = documentsPath.appendingPathComponent("\(id.uuidString).json")
            let data = try Data(contentsOf: url)
            return try decoder.decode(Conversation.self, from: data)
        } catch {
            return nil
        }
    }

    func loadAllConversations() -> [Conversation] {
        guard let files = try? fileManager.contentsOfDirectory(at: documentsPath, includingPropertiesForKeys: [.contentModificationDateKey]) else {
            return []
        }

        return files
            .filter { $0.pathExtension == "json" }
            .compactMap { url in
                guard let data = try? Data(contentsOf: url) else { return nil }
                return try? decoder.decode(Conversation.self, from: data)
            }
            .sorted { $0.lastMessageTime > $1.lastMessageTime }
    }

    func deleteConversation(id: UUID) {
        do {
            let url = documentsPath.appendingPathComponent("\(id.uuidString).json")
            try fileManager.removeItem(at: url)
        } catch {
            print("[ConversationStorage] Delete failed: \(error)")
        }
    }

    func deleteAllConversations() {
        do {
            let files = try fileManager.contentsOfDirectory(at: documentsPath, includingPropertiesForKeys: nil)
            for file in files where file.pathExtension == "json" {
                try fileManager.removeItem(at: file)
            }
        } catch {
            print("[ConversationStorage] Delete all failed: \(error)")
        }
    }

    func searchConversations(query: String) -> [Conversation] {
        let lowered = query.lowercased()
        return loadAllConversations().filter { conversation in
            conversation.title.lowercased().contains(lowered) ||
            conversation.messages.contains { $0.content.lowercased().contains(lowered) }
        }
    }

    // MARK: - Projects

    func saveProject(_ project: Project) {
        do {
            let data = try encoder.encode(project)
            let url = projectsPath.appendingPathComponent("\(project.id.uuidString).json")
            try data.write(to: url)
        } catch {
            print("[ConversationStorage] Save project failed: \(error)")
        }
    }

    func loadAllProjects() -> [Project] {
        guard let files = try? fileManager.contentsOfDirectory(at: projectsPath, includingPropertiesForKeys: nil) else {
            return []
        }

        return files
            .filter { $0.pathExtension == "json" }
            .compactMap { url in
                guard let data = try? Data(contentsOf: url) else { return nil }
                return try? decoder.decode(Project.self, from: data)
            }
            .sorted { $0.createdAt > $1.createdAt }
    }

    func deleteProject(id: UUID) {
        do {
            let url = projectsPath.appendingPathComponent("\(id.uuidString).json")
            try fileManager.removeItem(at: url)
        } catch {
            print("[ConversationStorage] Delete project failed: \(error)")
        }
    }

    // MARK: - Stats

    var totalConversations: Int {
        (try? fileManager.contentsOfDirectory(at: documentsPath, includingPropertiesForKeys: nil))?
            .filter { $0.pathExtension == "json" }.count ?? 0
    }

    var storageUsedBytes: Int {
        let urls = (try? fileManager.contentsOfDirectory(at: documentsPath, includingPropertiesForKeys: [.fileSizeKey])) ?? []
        return urls.compactMap { try? $0.resourceValues(forKeys: [.fileSizeKey]).fileSize }.reduce(0, +)
    }

    var storageUsedDisplay: String {
        ByteCountFormatter.string(fromByteCount: Int64(storageUsedBytes), countStyle: .file)
    }
}

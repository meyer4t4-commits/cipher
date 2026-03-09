import Foundation
import SwiftUI

// MARK: - Project (App you're building)

struct CipherProject: Identifiable, Codable {
    let id: String
    var name: String
    var description: String
    var icon: String              // SF Symbol name
    var color: String             // Color name (blue, red, green, etc.)
    var repoURL: String?          // GitHub/GitLab URL
    var deployURL: String?        // Live app URL
    var railwayProjectId: String? // Railway project ID
    var platform: ProjectPlatform
    var services: [ProjectService] // Connected services for this project
    var createdAt: Date
    var lastActiveAt: Date

    var displayColor: Color {
        switch color {
        case "blue": return .blue
        case "red": return .red
        case "green": return .green
        case "purple": return .purple
        case "orange": return .orange
        case "cyan": return .cyan
        case "indigo": return .indigo
        case "pink": return .pink
        case "yellow": return .yellow
        default: return .blue
        }
    }
}

enum ProjectPlatform: String, Codable, CaseIterable {
    case ios = "iOS"
    case web = "Web"
    case backend = "Backend"
    case fullStack = "Full Stack"
    case mobile = "Mobile"
    case other = "Other"

    var icon: String {
        switch self {
        case .ios: return "iphone"
        case .web: return "globe"
        case .backend: return "server.rack"
        case .fullStack: return "square.stack.3d.up"
        case .mobile: return "apps.iphone"
        case .other: return "cube"
        }
    }
}

struct ProjectService: Identifiable, Codable {
    let id: String
    var serviceType: ServiceType
    var credentialId: String?     // References a ServiceCredential
    var config: [String: String]  // Service-specific config
}

// MARK: - Service Credential (Stored tokens/keys)

struct ServiceCredential: Identifiable, Codable {
    let id: String
    var name: String              // User-friendly name ("My ElevenLabs Key")
    var serviceType: ServiceType
    var tokenValue: String        // The actual API key/token (encrypted at rest)
    var additionalFields: [String: String] // Extra fields (e.g., "voice_id", "project_id")
    var createdAt: Date
    var lastUsedAt: Date?

    var maskedToken: String {
        guard tokenValue.count > 8 else { return "••••••••" }
        let prefix = String(tokenValue.prefix(4))
        let suffix = String(tokenValue.suffix(4))
        return "\(prefix)••••••••\(suffix)"
    }
}

enum ServiceType: String, Codable, CaseIterable, Identifiable {
    // AI & Generation
    case openai = "OpenAI"
    case anthropic = "Anthropic"
    case stabilityai = "Stability AI"
    case replicate = "Replicate"
    case elevenlabs = "ElevenLabs"
    case suno = "Suno"
    case runway = "Runway"
    case heygen = "HeyGen"

    // Infrastructure & Deploy
    case railway = "Railway"
    case vercel = "Vercel"
    case supabase = "Supabase"
    case cloudflare = "Cloudflare"
    case aws = "AWS"

    // Code & Dev
    case github = "GitHub"
    case figma = "Figma"
    case notion = "Notion"

    // Communication
    case twilio = "Twilio"
    case sendgrid = "SendGrid"
    case slack = "Slack"

    // Social & Content
    case youtube = "YouTube"
    case tiktok = "TikTok"
    case instagram = "Instagram"
    case twitter = "X / Twitter"

    // Commerce & Finance
    case stripe = "Stripe"
    case shopify = "Shopify"

    // Search
    case brave = "Brave Search"

    // Other
    case custom = "Custom"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .openai: return "brain"
        case .anthropic: return "brain.head.profile"
        case .stabilityai: return "paintbrush"
        case .replicate: return "cpu"
        case .elevenlabs: return "waveform"
        case .suno: return "music.note"
        case .runway: return "film"
        case .heygen: return "person.crop.rectangle"
        case .railway: return "tram"
        case .vercel: return "arrow.up.right.circle"
        case .supabase: return "cylinder"
        case .cloudflare: return "cloud.fill"
        case .aws: return "server.rack"
        case .github: return "chevron.left.forwardslash.chevron.right"
        case .figma: return "pencil.and.ruler"
        case .notion: return "doc.text"
        case .twilio: return "phone"
        case .sendgrid: return "envelope"
        case .slack: return "number"
        case .youtube: return "play.rectangle.fill"
        case .tiktok: return "music.note.list"
        case .instagram: return "camera"
        case .twitter: return "at"
        case .stripe: return "creditcard"
        case .shopify: return "bag"
        case .brave: return "magnifyingglass.circle"
        case .custom: return "key"
        }
    }

    var color: Color {
        switch self {
        case .openai: return .green
        case .anthropic: return Color(red: 0.82, green: 0.55, blue: 0.28)
        case .stabilityai: return .purple
        case .replicate: return .blue
        case .elevenlabs: return .purple
        case .suno: return .pink
        case .runway: return .cyan
        case .heygen: return .teal
        case .railway: return .pink
        case .vercel: return .white
        case .supabase: return .green
        case .cloudflare: return .orange
        case .aws: return Color(red: 1.0, green: 0.6, blue: 0.0)
        case .github: return .white
        case .figma: return Color(red: 0.63, green: 0.30, blue: 1.0)
        case .notion: return .white
        case .twilio: return .red
        case .sendgrid: return .blue
        case .slack: return Color(red: 0.38, green: 0.15, blue: 0.55)
        case .youtube: return .red
        case .tiktok: return .cyan
        case .instagram: return Color(red: 0.88, green: 0.19, blue: 0.49)
        case .twitter: return .blue
        case .stripe: return .indigo
        case .shopify: return Color(red: 0.58, green: 0.80, blue: 0.09)
        case .brave: return .orange
        case .custom: return .gray
        }
    }

    var tokenLabel: String {
        switch self {
        case .openai: return "API Key"
        case .anthropic: return "API Key"
        case .stabilityai: return "API Key"
        case .replicate: return "API Token"
        case .elevenlabs: return "API Key"
        case .suno: return "API Key"
        case .runway: return "API Key"
        case .heygen: return "API Key"
        case .railway: return "API Token"
        case .vercel: return "API Token"
        case .supabase: return "Service Key"
        case .cloudflare: return "API Token"
        case .aws: return "Access Key ID"
        case .github: return "Personal Access Token"
        case .figma: return "Access Token"
        case .notion: return "Integration Token"
        case .twilio: return "Auth Token"
        case .sendgrid: return "API Key"
        case .slack: return "Bot Token"
        case .youtube: return "API Key"
        case .tiktok: return "Access Token"
        case .instagram: return "Access Token"
        case .twitter: return "Bearer Token"
        case .stripe: return "Secret Key"
        case .shopify: return "Admin API Token"
        case .brave: return "API Key"
        case .custom: return "Token / Key"
        }
    }

    /// Category for grouping in the vault UI
    var category: String {
        switch self {
        case .openai, .anthropic, .stabilityai, .replicate, .elevenlabs, .suno, .runway, .heygen:
            return "AI & Generation"
        case .railway, .vercel, .supabase, .cloudflare, .aws:
            return "Infrastructure"
        case .github, .figma, .notion:
            return "Dev Tools"
        case .twilio, .sendgrid, .slack:
            return "Communication"
        case .youtube, .tiktok, .instagram, .twitter:
            return "Social & Content"
        case .stripe, .shopify:
            return "Commerce"
        case .brave:
            return "Search"
        case .custom:
            return "Other"
        }
    }
}

// MARK: - Project Storage

@Observable
@MainActor
class ProjectStore {
    static let shared = ProjectStore()

    var projects: [CipherProject] = []
    var credentials: [ServiceCredential] = []

    private let projectsKey = "cipher_projects"
    private let credentialsKey = "cipher_credentials"

    init() {
        loadFromDisk()
    }

    // MARK: - Projects

    func addProject(_ project: CipherProject) {
        projects.append(project)
        saveToDisk()
    }

    func updateProject(_ project: CipherProject) {
        if let index = projects.firstIndex(where: { $0.id == project.id }) {
            projects[index] = project
            saveToDisk()
        }
    }

    func deleteProject(_ id: String) {
        projects.removeAll { $0.id == id }
        saveToDisk()
    }

    // MARK: - Credentials

    func addCredential(_ credential: ServiceCredential) {
        credentials.append(credential)
        saveToDisk()
    }

    func updateCredential(_ credential: ServiceCredential) {
        if let index = credentials.firstIndex(where: { $0.id == credential.id }) {
            credentials[index] = credential
            saveToDisk()
        }
    }

    func deleteCredential(_ id: String) {
        credentials.removeAll { $0.id == id }
        saveToDisk()
    }

    func credential(for id: String) -> ServiceCredential? {
        credentials.first { $0.id == id }
    }

    func credentials(for serviceType: ServiceType) -> [ServiceCredential] {
        credentials.filter { $0.serviceType == serviceType }
    }

    // MARK: - Persistence

    private func saveToDisk() {
        let encoder = JSONEncoder()
        if let projectData = try? encoder.encode(projects) {
            UserDefaults.standard.set(projectData, forKey: projectsKey)
        }
        if let credData = try? encoder.encode(credentials) {
            UserDefaults.standard.set(credData, forKey: credentialsKey)
        }
    }

    private func loadFromDisk() {
        let decoder = JSONDecoder()
        if let data = UserDefaults.standard.data(forKey: projectsKey),
           let loaded = try? decoder.decode([CipherProject].self, from: data) {
            projects = loaded
        }
        if let data = UserDefaults.standard.data(forKey: credentialsKey),
           let loaded = try? decoder.decode([ServiceCredential].self, from: data) {
            credentials = loaded
        }
    }
}

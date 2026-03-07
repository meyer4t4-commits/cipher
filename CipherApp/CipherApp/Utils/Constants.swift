import SwiftUI

// MARK: - App Constants

struct AppConstants {
    static let appName = "Cipher"
    static let tagline = "Sovereign Intelligence"
    static let appVersion = "2.0.0"
    static let publisherName = "Elysian Protocol"

    static let defaultServerURL = "https://cipher-elysian-production-b6a8.up.railway.app"
    static let apiBasePath = "/api/v1"
    static let chatEndpoint = "/chat/"
    static let streamEndpoint = "/chat/stream"
    static let conversationsEndpoint = "/chat/conversations"
    static let healthEndpoint = "/system/health"
    static let scannerEndpoint = "/scanner"

    static let defaultModelTier = "auto"
    static let defaultTemperature = 0.7
    static let defaultMaxTokens = 4096
    static let defaultIncludeMemory = true

    static let maxAttachmentSizeMB = 25
    static let maxInputLines = 12
    static let messagePageSize = 50
    static let typingDebounceMs = 150
}

// MARK: - Design System

struct CipherTheme {
    // Core palette — deep navy/indigo with electric accents
    static let background = Color(hex: "08090F")
    static let backgroundSecondary = Color(hex: "0D0F18")
    static let surface = Color(hex: "131521")
    static let surfaceElevated = Color(hex: "1A1D2E")
    static let surfaceHover = Color(hex: "21243A")

    // Accent colors
    static let accent = Color(hex: "6C63FF")       // Primary indigo-violet
    static let accentLight = Color(hex: "8B83FF")
    static let accentDark = Color(hex: "4F46E5")
    static let accentGlow = Color(hex: "6C63FF").opacity(0.3)

    // Semantic colors
    static let success = Color(hex: "34D399")
    static let warning = Color(hex: "FBBF24")
    static let error = Color(hex: "F87171")
    static let info = Color(hex: "60A5FA")

    // Text
    static let textPrimary = Color.white
    static let textSecondary = Color(hex: "9CA3AF")
    static let textTertiary = Color(hex: "6B7280")
    static let textOnAccent = Color.white

    // Borders
    static let border = Color.white.opacity(0.08)
    static let borderSubtle = Color.white.opacity(0.04)
    static let borderFocus = Color(hex: "6C63FF").opacity(0.5)

    // Gradients
    static let accentGradient = LinearGradient(
        colors: [Color(hex: "6C63FF"), Color(hex: "A855F7")],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )

    static let surfaceGradient = LinearGradient(
        colors: [Color(hex: "13152180"), Color(hex: "1A1D2E40")],
        startPoint: .top,
        endPoint: .bottom
    )

    static let meshGradient = LinearGradient(
        colors: [
            Color(hex: "6C63FF").opacity(0.15),
            Color(hex: "A855F7").opacity(0.08),
            Color(hex: "08090F").opacity(0.0)
        ],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )

    // Message bubbles
    static let userBubble = LinearGradient(
        colors: [Color(hex: "6C63FF"), Color(hex: "5B54E8")],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )
    static let assistantBubble = Color(hex: "1A1D2E")

    // Model tier colors
    static func tierColor(_ tier: String) -> Color {
        switch tier.lowercased() {
        case "fast": return Color(hex: "34D399")
        case "code": return Color(hex: "60A5FA")
        case "reasoning": return Color(hex: "A855F7")
        default: return Color(hex: "6C63FF")
        }
    }
}

// MARK: - Spacing & Layout

struct Spacing {
    static let xxxs: CGFloat = 2
    static let xxs: CGFloat = 4
    static let xs: CGFloat = 6
    static let sm: CGFloat = 8
    static let md: CGFloat = 12
    static let lg: CGFloat = 16
    static let xl: CGFloat = 20
    static let xxl: CGFloat = 24
    static let xxxl: CGFloat = 32
    static let huge: CGFloat = 48
    static let massive: CGFloat = 64
}

struct CornerRadius {
    static let xs: CGFloat = 4
    static let sm: CGFloat = 8
    static let md: CGFloat = 12
    static let lg: CGFloat = 16
    static let xl: CGFloat = 20
    static let xxl: CGFloat = 24
    static let full: CGFloat = 100
}

// Legacy compatibility
struct AppColors {
    static let primary = CipherTheme.accent
    static let accent = CipherTheme.accent
    static let background = CipherTheme.background
    static let surface = CipherTheme.surface
    static let text = CipherTheme.textPrimary
    static let secondaryText = CipherTheme.textSecondary
}

struct AppSpacing {
    static let xs = Spacing.xxs
    static let sm = Spacing.sm
    static let md = Spacing.md
    static let lg = Spacing.lg
    static let xl = Spacing.xl
    static let xxl = Spacing.xxxl
}

struct AppCornerRadius {
    static let sm = CornerRadius.sm
    static let md = CornerRadius.md
    static let lg = CornerRadius.lg
}

// MARK: - Color Hex Extension

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3:
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6:
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8:
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}

import Foundation
import SwiftUI

// MARK: - Agent Catalog (Hardcoded Source of Truth)

struct AgentDefinition: Identifiable, Hashable {
    static func == (lhs: AgentDefinition, rhs: AgentDefinition) -> Bool {
        lhs.id == rhs.id
    }
    func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }

    let id: String
    let name: String
    let displayName: String
    let emoji: String
    let icon: String
    let category: AgentCategory
    let description: String
    let purpose: String
    let useCases: [String]
    let actions: [AgentAction]
    let isAvailable: Bool

    static let all: [AgentDefinition] = [
        // ── Core Operations ──
        AgentDefinition(
            id: "shell_agent", name: "shell_agent", displayName: "Bolt",
            emoji: "⚡", icon: "terminal",
            category: .coreOps,
            description: "Your command line muscle",
            purpose: "Bolt runs anything you'd type into a terminal. Need to restart a server, clean up old files, run a script, or check what's eating your disk space? Just tell Bolt what to do and it handles it.",
            useCases: ["\"Restart my Railway service\"", "\"Find all files over 100MB and list them\"", "\"Run my test suite and tell me what failed\"", "\"Kill whatever's using port 3000\""],
            actions: [.spawn, .cron],
            isAvailable: true
        ),
        AgentDefinition(
            id: "web_agent", name: "web_agent", displayName: "Crawler",
            emoji: "🕷️", icon: "globe",
            category: .coreOps,
            description: "Scrapes, browses, and extracts from any website",
            purpose: "Crawler logs into your accounts, pulls data from any website, watches pages for changes, and grabs exactly what you need. Point it at a URL and tell it what you want.",
            useCases: ["\"Log into my ElevenLabs and check my usage\"", "\"Scrape all product prices from this page\"", "\"Watch this listing and alert me if the price drops\"", "\"Pull my analytics from Stripe dashboard\""],
            actions: [.spawn, .cron],
            isAvailable: true
        ),
        AgentDefinition(
            id: "code_agent", name: "code_agent", displayName: "Forge",
            emoji: "🔥", icon: "chevron.left.forwardslash.chevron.right",
            category: .coreOps,
            description: "Writes, fixes, and ships code",
            purpose: "Forge is your developer on call. It writes code from scratch, fixes bugs, reviews pull requests, and can refactor messy code into something clean. Any language, any framework.",
            useCases: ["\"Write a Python script that sorts my CSVs by date\"", "\"Fix the crash in my login screen\"", "\"Review this code and tell me what's wrong\"", "\"Convert this JavaScript to TypeScript\""],
            actions: [.spawn],
            isAvailable: true
        ),
        AgentDefinition(
            id: "file_agent", name: "file_agent", displayName: "Vault",
            emoji: "📁", icon: "doc",
            category: .coreOps,
            description: "Organizes, converts, and manages your files",
            purpose: "Vault handles everything file-related. Rename hundreds of files at once, convert between formats, organize messy folders, or find that document you lost somewhere in your system.",
            useCases: ["\"Organize my Downloads folder by file type\"", "\"Convert all my PNGs to WebP\"", "\"Find every PDF that mentions 'contract' in my docs\"", "\"Rename these files to match YYYY-MM-DD format\""],
            actions: [.spawn, .cron],
            isAvailable: true
        ),
        AgentDefinition(
            id: "deploy_agent", name: "deploy_agent", displayName: "Launchpad",
            emoji: "🚀", icon: "icloud.and.arrow.up",
            category: .coreOps,
            description: "Ships your apps live in minutes",
            purpose: "Launchpad takes your code and puts it on the internet. It handles Railway, Vercel, Docker, and cloud deployments so you don't have to wrestle with configs and build errors.",
            useCases: ["\"Deploy my latest changes to Railway\"", "\"Set up a new Vercel project for my frontend\"", "\"Build and push my Docker image\"", "\"Roll back to yesterday's deployment\""],
            actions: [.spawn, .deploy],
            isAvailable: true
        ),
        AgentDefinition(
            id: "monitor_agent", name: "monitor_agent", displayName: "Watchtower",
            emoji: "🗼", icon: "waveform.path.ecg",
            category: .coreOps,
            description: "Keeps an eye on everything 24/7",
            purpose: "Watchtower never sleeps. It checks if your servers are up, tracks error spikes, monitors your APIs, and pings you the moment something goes wrong before your users notice.",
            useCases: ["\"Check if my Railway app is healthy right now\"", "\"Alert me if my API response time exceeds 2 seconds\"", "\"Monitor my server's memory usage every hour\"", "\"Watch my Stripe webhooks for failures\""],
            actions: [.spawn, .cron, .deploy],
            isAvailable: true
        ),

        // ── Automation & Infrastructure ──
        AgentDefinition(
            id: "ghost", name: "ghost", displayName: "Ghost",
            emoji: "👻", icon: "computermouse",
            category: .intelligence,
            description: "Takes over your browser and does the work",
            purpose: "Ghost is your hands-free browser pilot. It navigates websites, fills out forms, clicks through flows, takes screenshots, and completes multi-step web tasks you'd waste hours doing manually. Like having someone sitting at your computer.",
            useCases: ["\"Fill out this insurance quote form with my info\"", "\"Go to Zillow, search Nashville 37209, screenshot the top 5\"", "\"Navigate my bank dashboard and download last month's statement\"", "\"Apply to these 10 job listings with my resume\""],
            actions: [.spawn],
            isAvailable: false
        ),
        AgentDefinition(
            id: "pipeline", name: "pipeline", displayName: "Pipeline",
            emoji: "🔗", icon: "arrow.triangle.branch",
            category: .intelligence,
            description: "Chains tasks into automated workflows",
            purpose: "Pipeline connects your agents into multi-step workflows. Instead of running agents one at a time, describe a chain: when this happens, do that, then do this. It's Zapier but you just describe what you want in plain English.",
            useCases: ["\"When a new lead comes in, research them, draft an email, and add to my CRM\"", "\"Every morning: check server health, pull analytics, send me a summary\"", "\"Scrape competitor prices, compare to mine, alert me if I'm undercut\"", "\"Download new invoices, extract totals, update my spreadsheet\""],
            actions: [.spawn, .cron],
            isAvailable: false
        ),
        AgentDefinition(
            id: "provisioning_agent", name: "provisioning_agent", displayName: "Terraform",
            emoji: "🖥️", icon: "server.rack",
            category: .intelligence,
            description: "Spins up infrastructure on demand",
            purpose: "Terraform builds your digital foundation. Need a new server, database, or cloud environment? It provisions everything, configures it properly, and gets you up and running fast.",
            useCases: ["\"Set up a new staging environment for my app\"", "\"Spin up a PostgreSQL database on Railway\"", "\"Configure a new server with Node.js and Redis\"", "\"Clone my production setup for testing\""],
            actions: [.spawn, .deploy],
            isAvailable: true
        ),
        AgentDefinition(
            id: "sentinel_agent", name: "sentinel_agent", displayName: "Sentinel",
            emoji: "🛡️", icon: "shield.checkered",
            category: .intelligence,
            description: "Scans for threats and locks things down",
            purpose: "Sentinel actively hunts for security issues. It scans your apps for vulnerabilities, checks if your API keys are exposed, monitors for unauthorized access, and hardens your infrastructure.",
            useCases: ["\"Scan my app for security vulnerabilities\"", "\"Are any of my API keys exposed publicly?\"", "\"Check if my SSL certificates are about to expire\"", "\"Monitor my server for unauthorized access attempts\""],
            actions: [.spawn, .cron, .deploy],
            isAvailable: true
        ),
        AgentDefinition(
            id: "scheduler_agent", name: "scheduler_agent", displayName: "Clockwork",
            emoji: "⏰", icon: "clock.arrow.2.circlepath",
            category: .intelligence,
            description: "Schedules and manages recurring tasks",
            purpose: "Clockwork is your task scheduler. It creates one-time and recurring jobs, manages cron expressions, handles delays, and makes sure your automated workflows fire on time every time.",
            useCases: ["\"Schedule a server health check every 6 hours\"", "\"Run my lead scanner every weekday at 9am\"", "\"Set a one-time reminder to check deployment tomorrow at noon\"", "\"Show me all my active scheduled tasks\""],
            actions: [.spawn, .cron],
            isAvailable: true
        ),

        // ── Creative & Communication ──
        AgentDefinition(
            id: "communication_agent", name: "communication_agent", displayName: "Mercury",
            emoji: "💬", icon: "message",
            category: .communication,
            description: "Sends messages everywhere for you",
            purpose: "Mercury handles all your messaging. It drafts and sends emails, Slack messages, texts, and notifications. Tell it what to say and who should hear it, and it takes care of the rest.",
            useCases: ["\"Email the team that the deploy is live\"", "\"Text my contractor that we're meeting at 3\"", "\"Send a Slack update to #general about the launch\"", "\"Draft a follow-up email to everyone from yesterday's meeting\""],
            actions: [.spawn, .cron],
            isAvailable: true
        ),
        AgentDefinition(
            id: "image_agent", name: "image_agent", displayName: "Canvas",
            emoji: "🎨", icon: "photo",
            category: .communication,
            description: "Creates and edits images with AI",
            purpose: "Canvas generates images from your descriptions, edits existing photos, creates thumbnails and social media graphics. Just describe what you want and it makes it happen.",
            useCases: ["\"Generate a hero image for my landing page\"", "\"Create Instagram-sized versions of these product photos\"", "\"Make me a logo concept with blue and gold tones\"", "\"Remove the background from all these headshots\""],
            actions: [.spawn],
            isAvailable: true
        ),
        AgentDefinition(
            id: "video_agent", name: "video_agent", displayName: "Director",
            emoji: "🎬", icon: "film",
            category: .communication,
            description: "Produces and edits video content",
            purpose: "Director creates video clips, adds captions, generates animations, and transcribes footage. From social media reels to presentation videos, it handles the production so you don't need a studio.",
            useCases: ["\"Generate a 30-second promo clip for my product\"", "\"Transcribe this meeting recording\"", "\"Add captions to my TikTok video\"", "\"Create an animated explainer for the new feature\""],
            actions: [.spawn],
            isAvailable: true
        ),
        AgentDefinition(
            id: "scribe", name: "scribe", displayName: "Scribe",
            emoji: "📝", icon: "doc.richtext",
            category: .communication,
            description: "Creates polished documents, decks, and reports",
            purpose: "Scribe produces professional deliverables. It builds pitch decks, writes formatted reports, creates spreadsheets with charts, generates PDFs, and outputs publication-ready documents. Not a chatbot response — an actual file you can send.",
            useCases: ["\"Build a pitch deck for my Series A raise\"", "\"Create a PDF report of this month's property performance\"", "\"Make me a one-pager for this investment opportunity\"", "\"Generate a formatted spreadsheet comparing these 5 deals\""],
            actions: [.spawn],
            isAvailable: false
        ),
        AgentDefinition(
            id: "echo", name: "echo", displayName: "Echo",
            emoji: "🎙️", icon: "waveform",
            category: .communication,
            description: "Voice cloning, transcription, and audio content",
            purpose: "Echo handles everything audio. It transcribes recordings, generates voice memos in your cloned voice, creates podcast intros, and turns text into natural speech. Built on your existing voice clone.",
            useCases: ["\"Transcribe this meeting recording and pull out action items\"", "\"Read this report back to me in my voice\"", "\"Generate a voice memo summarizing today's deals\"", "\"Create an audio walkthrough of this property listing\""],
            actions: [.spawn],
            isAvailable: false
        ),

        // ── Research & Intelligence ──
        AgentDefinition(
            id: "research_agent", name: "research_agent", displayName: "Oracle",
            emoji: "🔍", icon: "magnifyingglass",
            category: .intelligence,
            description: "Deep web research and market intelligence",
            purpose: "Oracle digs deep. It searches the web, aggregates news, pulls market data, and compiles research reports so you get the full picture on any topic without spending hours in browser tabs.",
            useCases: ["\"Research the top competitors in Nashville property management\"", "\"What's the latest news on interest rate changes?\"", "\"Find everything published about this company in the last month\"", "\"Compile a market report on short-term rental regulations\""],
            actions: [.spawn, .cron],
            isAvailable: true
        ),
        AgentDefinition(
            id: "brave_search_agent", name: "brave_search_agent", displayName: "Recon",
            emoji: "🦁", icon: "safari",
            category: .intelligence,
            description: "Fast web and news search powered by Brave",
            purpose: "Recon is your rapid search specialist. Powered by Brave Search with DuckDuckGo fallback, it finds what you need across the web and news instantly — no tracking, no noise, just results.",
            useCases: ["\"Search for recent articles about AI in real estate\"", "\"Find the latest news on Stripe pricing changes\"", "\"Look up Nashville zoning laws for multifamily\"", "\"What are people saying about this company online?\""],
            actions: [.spawn],
            isAvailable: true
        ),
        AgentDefinition(
            id: "synthesis_agent", name: "synthesis_agent", displayName: "Synthesis",
            emoji: "🧬", icon: "brain",
            category: .intelligence,
            description: "Deep scoping and executive research briefs",
            purpose: "Synthesis runs autonomous multi-step research and delivers executive-ready briefs. It deep-scopes topics, compares options, analyzes trends, and gives you actionable intelligence — not just raw data.",
            useCases: ["\"Deep scope the Nashville multifamily market and give me a brief\"", "\"Compare Stripe vs Square vs PayPal for my business\"", "\"What are the emerging trends in AI-powered property management?\"", "\"Quick intel on this company before my meeting tomorrow\""],
            actions: [.spawn],
            isAvailable: true
        ),
        AgentDefinition(
            id: "data_agent", name: "data_agent", displayName: "Prism",
            emoji: "💎", icon: "chart.bar.doc.horizontal",
            category: .intelligence,
            description: "Data analysis, SQL queries, and visualizations",
            purpose: "Prism crunches your numbers. It runs SQL queries, analyzes CSVs, builds visualizations, and turns raw data into insights you can actually use to make decisions.",
            useCases: ["\"Query my database for all tenants with overdue rent\"", "\"Analyze this CSV and show me the trends\"", "\"Build a chart comparing revenue across my properties\"", "\"Run a pivot table on my sales data by region\""],
            actions: [.spawn],
            isAvailable: true
        ),
        AgentDefinition(
            id: "analyst_agent", name: "analyst_agent", displayName: "Analyst",
            emoji: "🔬", icon: "scope",
            category: .globalExpansion,
            description: "Technical auditor for automation gaps",
            purpose: "Analyst audits target companies for automation opportunities. It scans tech stacks, evaluates social presence, analyzes SEO, and identifies exactly where Cipher can plug in to save time and money.",
            useCases: ["\"Audit this company's tech stack for automation gaps\"", "\"Analyze their social media presence and engagement\"", "\"Run a full SEO audit on this website\"", "\"Score this prospect's readiness for Cipher integration\""],
            actions: [.spawn, .cron],
            isAvailable: true
        ),
        AgentDefinition(
            id: "scout_agent", name: "scout_agent", displayName: "Scout",
            emoji: "🎯", icon: "binoculars",
            category: .globalExpansion,
            description: "Finds companies ripe for automation",
            purpose: "Scout hunts for leads at high velocity. It scans industries, discovers companies still running manual processes, and feeds qualified prospects straight into your pipeline before competitors find them.",
            useCases: ["\"Scan Nashville businesses that still use manual invoicing\"", "\"Find 20 property managers without automated tenant screening\"", "\"Identify companies in my niche with outdated tech stacks\"", "\"Build a prospect list of businesses spending on Zapier\""],
            actions: [.spawn, .cron],
            isAvailable: true
        ),

        // ── Finance & Trading ──
        AgentDefinition(
            id: "trading_agent", name: "trading_agent", displayName: "Maverick",
            emoji: "📈", icon: "chart.xyaxis.line",
            category: .finance,
            description: "Tracks markets and tests strategies",
            purpose: "Maverick watches the markets for you. It runs paper trades to test your strategies risk-free, tracks your watchlist, does technical analysis, and alerts you to moves that match your criteria.",
            useCases: ["\"Paper trade $1000 in Tesla and track it for a week\"", "\"What's the technical analysis on Bitcoin today?\"", "\"Alert me when AAPL drops below $180\"", "\"Backtest this moving average strategy on SPY\""],
            actions: [.spawn, .cron],
            isAvailable: true
        ),

        // ── Apex Property ──
        AgentDefinition(
            id: "apex_architect_agent", name: "apex_architect_agent", displayName: "Apex",
            emoji: "👑", icon: "crown",
            category: .apexAsset,
            description: "The brain behind your real estate deals",
            purpose: "Apex is the mastermind. It coordinates all the property agents, scores investment opportunities, manages your deal pipeline, and gives you clear buy/pass recommendations with real numbers.",
            useCases: ["\"Run a full analysis on this 4-unit in Nashville\"", "\"Score my top 5 deals and rank them by ROI\"", "\"What should my next investment move be?\"", "\"Compare these three properties side by side\""],
            actions: [.spawn],
            isAvailable: true
        ),
        AgentDefinition(
            id: "market_pulse_agent", name: "market_pulse_agent", displayName: "Pulse",
            emoji: "📊", icon: "chart.line.uptrend.xyaxis",
            category: .apexAsset,
            description: "Tracks real estate market moves in real time",
            purpose: "Pulse keeps its finger on the market. It watches pricing trends, inventory levels, interest rates, and local conditions so you always know whether it's a buyer's or seller's market.",
            useCases: ["\"What's the Austin rental market doing this month?\"", "\"How have home prices changed in my target area?\"", "\"Show me inventory trends for Nashville multifamily\"", "\"What's the average cap rate in this zip code?\""],
            actions: [.spawn, .cron],
            isAvailable: true
        ),
        AgentDefinition(
            id: "profitability_analyst_agent", name: "profitability_analyst_agent", displayName: "Ledger",
            emoji: "💰", icon: "dollarsign.circle",
            category: .apexAsset,
            description: "Tells you exactly how much you'll make",
            purpose: "Ledger runs the numbers that matter. Plug in a property and it calculates your cash flow, cap rate, return on investment, and builds a full financial model so you know if a deal is worth it.",
            useCases: ["\"What's the cash-on-cash return on this duplex?\"", "\"Build me a 5-year pro forma for this property\"", "\"Will this deal cash flow with 25% down?\"", "\"Compare financing options: 20% vs 25% down\""],
            actions: [.spawn],
            isAvailable: true
        ),
        AgentDefinition(
            id: "neighborhood_growth_agent", name: "neighborhood_growth_agent", displayName: "Atlas",
            emoji: "🗺️", icon: "map",
            category: .apexAsset,
            description: "Scores neighborhoods before you invest",
            purpose: "Atlas knows the ground truth. It scores neighborhoods on growth potential by analyzing population trends, school ratings, crime data, new developments, and job growth so you invest in the right areas.",
            useCases: ["\"Score this neighborhood for investment potential\"", "\"What's the growth trend for this zip code?\"", "\"Compare these three neighborhoods side by side\"", "\"Are there any new developments planned near this address?\""],
            actions: [.spawn, .cron],
            isAvailable: true
        ),
        AgentDefinition(
            id: "deal_flow_agent", name: "deal_flow_agent", displayName: "Prospector",
            emoji: "⛏️", icon: "building.2",
            category: .apexAsset,
            description: "Finds deals before anyone else",
            purpose: "Prospector hunts for properties that match your criteria. It sources off-market deals, scans new listings, evaluates opportunities, and alerts you the moment something worth looking at hits the market.",
            useCases: ["\"Find me multifamily properties under $500K in Nashville\"", "\"Alert me when new off-market deals pop up in my area\"", "\"What properties match my investment criteria right now?\"", "\"Show me distressed properties with value-add potential\""],
            actions: [.spawn, .cron],
            isAvailable: true
        ),

        // ── Growth & Outreach ──
        AgentDefinition(
            id: "outreach_agent", name: "outreach_agent", displayName: "Piper",
            emoji: "✉️", icon: "paperplane",
            category: .globalExpansion,
            description: "Runs outreach campaigns that get responses",
            purpose: "Piper handles cold outreach at scale. It personalizes emails, manages follow-up sequences, tracks who opened and replied, and keeps your pipeline full without you writing the same email 100 times.",
            useCases: ["\"Email 50 property managers in Nashville with my pitch\"", "\"Follow up with everyone who didn't reply last week\"", "\"Create a 3-email drip campaign for new leads\"", "\"Who opened my last outreach batch?\""],
            actions: [.spawn, .cron],
            isAvailable: true
        ),
        AgentDefinition(
            id: "legal_agent", name: "legal_agent", displayName: "Juris",
            emoji: "⚖️", icon: "building.columns",
            category: .globalExpansion,
            description: "Patents, contracts, LLC formation, and legal research",
            purpose: "Juris handles the legal heavy lifting. It searches patents, drafts provisional applications, researches case law, reviews contracts, and helps with LLC formation so you stay protected without billable hours.",
            useCases: ["\"Search for prior art related to my AI scheduling patent\"", "\"Draft a provisional patent application for my algorithm\"", "\"Review this contractor agreement and flag risks\"", "\"What do I need to form an LLC in Tennessee?\""],
            actions: [.spawn],
            isAvailable: true
        ),

        // ── Memory & Scheduling ──
        AgentDefinition(
            id: "archivist_agent", name: "archivist_agent", displayName: "Archivist",
            emoji: "📚", icon: "books.vertical",
            category: .omniSavant,
            description: "Your contextual memory and knowledge base",
            purpose: "Archivist indexes every conversation, document, and thought across all your agents. It provides instant context retrieval, maintains a searchable knowledge base with semantic organization, so nothing you've ever discussed is lost.",
            useCases: ["\"What did we discuss about the Nashville deal last week?\"", "\"Find every mention of TallowRoots across all conversations\"", "\"What were the action items from my Monday planning session?\"", "\"Search my knowledge base for competitor pricing notes\""],
            actions: [.spawn, .cron],
            isAvailable: true
        ),
        AgentDefinition(
            id: "chronos_agent", name: "chronos_agent", displayName: "Chronos",
            emoji: "⏳", icon: "hourglass",
            category: .omniSavant,
            description: "Energy-aware scheduling and time blocking",
            purpose: "Chronos optimizes your schedule around your energy levels. It handles time blocking, resolves conflicts, protects deep work sessions, and manages cognitive load so you work on the right things at the right time.",
            useCases: ["\"Block 2 hours of deep work tomorrow morning\"", "\"Reschedule my afternoon — I need to handle an emergency\"", "\"Plan my week around my peak energy hours\"", "\"What's my schedule look like and where are the gaps?\""],
            actions: [.spawn, .cron],
            isAvailable: true
        ),

        // ── Meta / System ──
        AgentDefinition(
            id: "skill_creator_agent", name: "skill_creator_agent", displayName: "Architect",
            emoji: "🔧", icon: "hammer",
            category: .omniSavant,
            description: "Builds new abilities for your agents",
            purpose: "Architect expands what your agents can do. Need a custom capability that doesn't exist yet? Architect creates it, tests it, and plugs it into the system so your agents get smarter over time.",
            useCases: ["\"Build a skill that checks my Shopify orders daily\"", "\"Create a custom scraper for this real estate site\"", "\"Add a new capability to Crawler for login flows\"", "\"Make an agent that monitors my competitor's pricing\""],
            actions: [.spawn],
            isAvailable: true
        ),
        AgentDefinition(
            id: "new_agent", name: "new_agent", displayName: "Genesis",
            emoji: "✨", icon: "sparkles",
            category: .omniSavant,
            description: "Subscription management and onboarding",
            purpose: "Genesis handles subscription management — checking tiers, creating checkout sessions, processing webhooks, and onboarding new users into the Cipher ecosystem.",
            useCases: ["\"Check my current subscription tier\"", "\"Create a checkout session for the pro plan\"", "\"Process the latest webhook events\"", "\"What features does my current plan include?\""],
            actions: [.spawn],
            isAvailable: true
        ),
    ]
}

// MARK: - Agent Category

enum AgentCategory: String, CaseIterable, Identifiable {
    case coreOps = "Core Ops"
    case intelligence = "Automation"
    case communication = "Creative"
    case finance = "Finance"
    case apexAsset = "Apex Property"
    case globalExpansion = "Outreach"
    case omniSavant = "System"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .coreOps: return "gearshape.2"
        case .intelligence: return "arrow.triangle.branch"
        case .communication: return "bubble.left.and.bubble.right"
        case .finance: return "chart.line.uptrend.xyaxis"
        case .apexAsset: return "crown"
        case .globalExpansion: return "paperplane"
        case .omniSavant: return "hammer"
        }
    }

    var color: Color {
        switch self {
        case .coreOps: return .blue
        case .intelligence: return .purple
        case .communication: return .green
        case .finance: return .orange
        case .apexAsset: return .red
        case .globalExpansion: return .cyan
        case .omniSavant: return .indigo
        }
    }

    var agents: [AgentDefinition] {
        AgentDefinition.all.filter { $0.category == self }
    }
}

// MARK: - Agent Actions

enum AgentAction: String, Identifiable {
    case spawn = "Spawn"
    case cron = "Set Cron"
    case deploy = "Deploy"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .spawn: return "play.circle.fill"
        case .cron: return "clock.arrow.2.circlepath"
        case .deploy: return "arrow.up.circle.fill"
        }
    }

    var color: Color {
        switch self {
        case .spawn: return .green
        case .cron: return .orange
        case .deploy: return .blue
        }
    }

    var description: String {
        switch self {
        case .spawn: return "Run once now"
        case .cron: return "Schedule recurring"
        case .deploy: return "Deploy as service"
        }
    }
}

// MARK: - API Response Models (for enrichment from server)

struct AgentInfo: Codable, Identifiable {
    let name: String
    let description: String
    let version: String
    let capabilities: [AgentCapabilityInfo]

    var id: String { name }
}

struct AgentCapabilityInfo: Codable, Identifiable {
    let name: String
    let description: String
    let category: String
    let requiresApproval: Bool
    let timeoutSeconds: Int

    var id: String { name }

    enum CodingKeys: String, CodingKey {
        case name, description, category
        case requiresApproval = "requires_approval"
        case timeoutSeconds = "timeout_seconds"
    }
}

struct AgentListResponse: Codable {
    let agents: [AgentInfo]
    let total: Int
}

struct AgentExecutionResult: Codable, Identifiable {
    let taskId: String
    let agentName: String
    let success: Bool
    let output: AnyCodable?
    let error: String?
    let executionTimeMs: Int?
    let verified: Bool?
    let startedAt: String?
    let completedAt: String?

    var id: String { taskId }

    enum CodingKeys: String, CodingKey {
        case taskId = "task_id"
        case agentName = "agent_name"
        case success, output, error
        case executionTimeMs = "execution_time_ms"
        case verified
        case startedAt = "started_at"
        case completedAt = "completed_at"
    }
}

struct PendingApproval: Codable, Identifiable {
    let taskId: String
    let agentName: String
    let instruction: String
    let createdAt: String?

    var id: String { taskId }

    enum CodingKeys: String, CodingKey {
        case taskId = "task_id"
        case agentName = "agent_name"
        case instruction
        case createdAt = "created_at"
    }
}

struct PendingApprovalsResponse: Codable {
    let pending: Int
    let tasks: [PendingApproval]
}

// MARK: - Cron Models

struct CronTaskInfo: Codable, Identifiable {
    let taskId: String
    let name: String
    let cronExpression: String
    let agentName: String
    let operation: String
    var enabled: Bool
    let description: String
    let lastRun: String?
    let nextRun: String?
    let runCount: Int
    let lastError: String?

    var id: String { taskId }

    enum CodingKeys: String, CodingKey {
        case taskId = "task_id"
        case name
        case cronExpression = "cron_expression"
        case agentName = "agent_name"
        case operation, enabled, description
        case lastRun = "last_run"
        case nextRun = "next_run"
        case runCount = "run_count"
        case lastError = "last_error"
    }
}

struct CronListResponse: Codable {
    let total: Int
    let enabled: Int
    let tasks: [CronTaskInfo]
}

// MARK: - Execution History

struct ExecutionHistoryResponse: Codable {
    let total: Int
    let entries: [AgentExecutionResult]
}

// MARK: - Executor Status

struct ExecutorStatusResponse: Codable {
    let executor: ExecutorInfo
    let registry: RegistryInfo

    struct ExecutorInfo: Codable {
        let maxConcurrent: Int
        let pendingApprovals: Int
        let historyEntries: Int

        enum CodingKeys: String, CodingKey {
            case maxConcurrent = "max_concurrent"
            case pendingApprovals = "pending_approvals"
            case historyEntries = "history_entries"
        }
    }

    struct RegistryInfo: Codable {
        let agents: Int
        let agentNames: [String]

        enum CodingKeys: String, CodingKey {
            case agents
            case agentNames = "agent_names"
        }
    }
}

// MARK: - Streaming Progress Models

/// Real-time progress event from agent execution stream
struct AgentProgressEvent: Codable {
    let type: String        // "progress", "bash", "chain"
    let message: String

    var isBash: Bool { type == "bash" }
    var isChain: Bool { type == "chain" }
}

/// Result format from streaming endpoint (snake_case)
struct StreamingAgentResult: Codable {
    let taskId: String
    let agentName: String
    let success: Bool
    let output: String?
    let error: String?
    let executionTimeMs: Double?
    let verified: Bool?

    enum CodingKeys: String, CodingKey {
        case taskId = "task_id"
        case agentName = "agent_name"
        case success, output, error
        case executionTimeMs = "execution_time_ms"
        case verified
    }
}

// MARK: - AnyCodable helper for dynamic JSON

struct AnyCodable: Codable {
    let value: Any

    init(_ value: Any) {
        self.value = value
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let string = try? container.decode(String.self) {
            value = string
        } else if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = double
        } else if let bool = try? container.decode(Bool.self) {
            value = bool
        } else if let dict = try? container.decode([String: AnyCodable].self) {
            value = dict.mapValues { $0.value }
        } else if let array = try? container.decode([AnyCodable].self) {
            value = array.map { $0.value }
        } else {
            value = NSNull()
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        if let string = value as? String {
            try container.encode(string)
        } else if let int = value as? Int {
            try container.encode(int)
        } else if let double = value as? Double {
            try container.encode(double)
        } else if let bool = value as? Bool {
            try container.encode(bool)
        } else {
            try container.encodeNil()
        }
    }

    var stringValue: String? {
        value as? String
    }

    var intValue: Int? {
        if let i = value as? Int { return i }
        if let d = value as? Double { return Int(d) }
        return nil
    }

    var doubleValue: Double? {
        if let d = value as? Double { return d }
        if let i = value as? Int { return Double(i) }
        return nil
    }

    var boolValue: Bool? {
        value as? Bool
    }
}

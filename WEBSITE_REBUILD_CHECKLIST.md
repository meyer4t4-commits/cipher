# CIPHER Website — Full Rebuild Checklist
## What CIPHER is supposed to be vs. what the website currently shows

**Date:** March 10, 2026

---

## WHAT THE WEBSITE CURRENTLY HAS (and that's basically it)

1. Chat interface (send messages, stream responses)
2. Sidebar with conversation list
3. Sidebar with agent divisions (collapsible, emoji-based)
4. Right panel showing "Agent Activity" (no real data feeding in)
5. Model tier selector (Auto/Reasoning/Fast/Code/Default)
6. Voice mode selector (8 modes)
7. Health status indicator (Online/Offline)
8. Quick action chips (Search web, Generate image, Analyze data, Write code)
9. Image upload in chat
10. Welcome screen with 6 capability cards (emoji icons, no real functionality)

**What's wrong with all of it:**
- Logo is just a "◆" unicode character, not the actual CIPHER logo
- Capability cards do nothing when clicked (just focus the input)
- Agent Activity panel shows "Waiting for agents..." with no live feed
- No navigation — everything is crammed into one chat page
- No dashboard, no settings, no dedicated views for any subsystem
- Looks like a basic ChatGPT clone with a dark theme
- No access to any of the 29 agents' actual capabilities
- No cron/scheduling UI
- No memory system UI
- No trading UI
- No scanner UI
- No real estate pipeline UI
- No education/voice platform UI
- No self-training section

---

## WHAT'S MISSING — THE FULL CHECKLIST

### A. BRANDING & IDENTITY
- [ ] Replace "◆" with actual CIPHER SVG logo in header and welcome screen
- [ ] Use the real app icon (1024px PNG) as favicon
- [ ] Professional typography — current Inter font is fine but layout is amateur
- [ ] Consistent color system (purple/gold from the brand, not random)
- [ ] "Elysian Protocol" branding with tier badge (Free/Pro/Business/Enterprise)
- [ ] Loading/splash screen with logo animation

### B. NAVIGATION & LAYOUT
- [ ] Proper navigation system (not just a chat window)
- [ ] Dashboard as the main landing page (not a chat)
- [ ] Sidebar navigation with sections for each major area:
  - Dashboard
  - Chat (Cipher conversation)
  - Agents (29 agents, browse/invoke/monitor)
  - Trading (Flux)
  - Real Estate (Apex Asset Hunter pipeline)
  - Intelligence Scanner
  - Cron/Scheduler
  - Memory System
  - Education Platform (voices/self-training)
  - Settings
  - Deployment Status

### C. DASHBOARD (Home Screen)
- [ ] System health overview (backend status, uptime, last health check)
- [ ] Active agents count / status
- [ ] Cron task status (next run times, last results)
- [ ] Quick stats: total conversations, total agent executions, memory entries
- [ ] Recent activity feed (real, from the API)
- [ ] Cost tracker (LLM spend across providers)
- [ ] Scanner latest intel summary
- [ ] Morning briefing preview
- [ ] Sentinel alert count / priority items

### D. CHAT INTERFACE (Upgrade Existing)
- [ ] Markdown rendering for Cipher responses (currently plain text)
- [ ] Code syntax highlighting (highlight.js is loaded but never used)
- [ ] Agent attribution on responses (which agent handled it)
- [ ] Confidence score display that actually works
- [ ] Voice mode visual indicator (show which personality is active)
- [ ] Conversation search
- [ ] Conversation export
- [ ] Proper message timestamps
- [ ] Copy message button
- [ ] Retry/regenerate button

### E. AGENT MANAGEMENT
- [ ] Agent browser — grid/list of all 29 agents with descriptions
- [ ] Agent detail view — capabilities, last execution, status
- [ ] Invoke agent directly (not just through chat)
- [ ] Agent execution history with results
- [ ] Agent status (idle/running/error)
- [ ] Agent divisions view matching the 6 divisions:
  - Intelligence (7 agents)
  - Real Estate (6 agents)
  - Engineering (6 agents)
  - Creative (2 agents)
  - Communications (2 agents)
  - Operations (6 agents)
- [ ] Spawn session management (start/stop/monitor)

### F. TRADING DASHBOARD (Flux)
- [ ] Paper portfolio overview (positions, P&L)
- [ ] Real-time quotes (via yfinance)
- [ ] Watchlist display
- [ ] Order history
- [ ] Technical analysis display (RSI, MACD, SMA)
- [ ] Trade execution form (with approval gate)
- [ ] Position sizing calculator
- [ ] Daily loss limit tracker
- [ ] Charts (price history, portfolio performance)

### G. REAL ESTATE PIPELINE (Apex Asset Hunter)
- [ ] Daily High-Upside Report display
- [ ] Property pipeline view (scan → analyze → filter → shortlist)
- [ ] Deal cards with MAO, ARV, repair estimates, ROI, grade
- [ ] Neighborhood growth scores
- [ ] Market pulse feed
- [ ] Investor PDF download
- [ ] Seller inquiry draft review/approve
- [ ] Target market settings (counties, price ceiling, margin floor)
- [ ] Map view (if feasible)

### H. INTELLIGENCE SCANNER
- [ ] Scanner status (running/stopped, last scan times)
- [ ] Per-source status: News, Web, Twitter, GitHub, Models
- [ ] Scan interval settings (15min for fast, 30-60 for slow)
- [ ] Intel feed — latest discoveries/alerts
- [ ] Filter by source/topic
- [ ] Scanner results history

### I. CRON / SCHEDULER
- [ ] List all 14+ registered cron tasks
- [ ] Enable/disable tasks
- [ ] Manual trigger button
- [ ] Last run time and result
- [ ] Next scheduled run
- [ ] Task execution log
- [ ] Create new cron task form
- [ ] Schedule visualization (calendar or timeline)

### J. MEMORY SYSTEM
- [ ] Memory browser — search/browse stored memories
- [ ] Memory count and stats
- [ ] Add/edit/delete memories
- [ ] Memory categories (conversations, preferences, decisions, contacts, market insights)
- [ ] Search with keyword matching (Phase 1)
- [ ] Memory export

### K. SELF-TRAINING / OVERNIGHT AUTONOMOUS OPERATIONS
- [ ] Self-training configuration panel
- [ ] Schedule overnight training runs (what to learn, what to research)
- [ ] Training queue — list of pending training tasks
- [ ] Training results — what Cipher learned while you slept
- [ ] Skill acquisition log — new capabilities gained
- [ ] Nightly brief integration (7 AM morning briefing result display)
- [ ] Evening work sprint config (Mon-Sat 8 PM priorities)
- [ ] Life audit display (9 PM nightly reconciliation output)
- [ ] Archivist index sweep results (11 PM)
- [ ] Chronos daily plan review (6:30 AM generated plan)
- [ ] Sentinel digest review (8 PM alert digest)
- [ ] Synthesis weekly briefing (Monday 6 AM)
- [ ] "What CIPHER did overnight" summary view
- [ ] Toggle which overnight tasks are active
- [ ] Set priorities and focus areas for overnight work

### L. EDUCATION PLATFORM (Voice Characters)
- [ ] 10 voice character profiles (Nonna Maria, Teacher Lin, The Sage, Blues, Dr. Nova, Professor Clarity, The Chronicler, The Muse, The Founder, Profesora Sofia)
- [ ] Voice preview/playback per character
- [ ] ElevenLabs voice settings per character (stability, similarity, style)
- [ ] Lesson interface per subject
- [ ] Subject categories: Italian, Mandarin, Philosophy, Music/Harmonica, Science/Physics, Mathematics, History, Writing/Creative, Business/Entrepreneurship, Spanish
- [ ] Progress tracking per subject
- [ ] Voice reference clips management

### M. EXPANSION PULSE (B2B Growth Engine)
- [ ] Weekly pipeline view (Scout → Analyst → Report → Outreach → Provisioning)
- [ ] Target industry settings
- [ ] Lead list with scores
- [ ] Audit results per target (tech stack, social, SEO)
- [ ] Outreach drafts review/approve
- [ ] Engagement tracking (open rate, reply rate, meeting rate)
- [ ] Client provisioning status

### N. COMMUNICATION HUB
- [ ] Email management (connected accounts)
- [ ] Telegram bot status
- [ ] Slack integration status
- [ ] SMS/Twilio status
- [ ] Notification preferences
- [ ] Message drafts awaiting approval

### O. SETTINGS / CONFIGURATION
- [ ] API key status (configured/missing — never show actual keys)
- [ ] LLM provider status (Anthropic, Groq, OpenAI, DeepSeek, Ollama)
- [ ] Model routing configuration (tier assignments)
- [ ] Cascade routing toggle
- [ ] Cache settings (semantic threshold, TTL)
- [ ] Voice mode configuration
- [ ] Operator profile editor (preferences, communication style)
- [ ] Deployment status (local vs Railway)
- [ ] System logs viewer

### P. OMNI-SAVANT (Central Nervous System)
- [ ] Chronos: Today's energy-optimized schedule
- [ ] Chronos: Deep work guard settings
- [ ] Chronos: Calendar sync status
- [ ] Chronos: Friction log (skipped items, adaptations)
- [ ] Archivist: Index status, total documents indexed
- [ ] Archivist: Cross-agent search interface
- [ ] Sentinel: Active monitoring status
- [ ] Sentinel: Alert feed (urgency-sorted)
- [ ] Sentinel: Predictions (48-hour need forecast)
- [ ] Sentinel: Auto-response drafts awaiting approval
- [ ] Synthesis: Research sessions and briefs

---

## SUMMARY COUNT

| Category | Missing Items |
|----------|--------------|
| A. Branding | 6 |
| B. Navigation | 11 |
| C. Dashboard | 9 |
| D. Chat Upgrades | 10 |
| E. Agents | 7 |
| F. Trading (Flux) | 9 |
| G. Real Estate | 9 |
| H. Scanner | 6 |
| I. Cron/Scheduler | 8 |
| J. Memory | 6 |
| K. Self-Training/Overnight | 15 |
| L. Education Platform | 7 |
| M. Expansion Pulse | 7 |
| N. Communications | 6 |
| O. Settings | 9 |
| P. Omni-Savant | 11 |
| **TOTAL** | **~136 items** |

---

## WHAT THE WEBSITE CURRENTLY COVERS

Out of ~136 items that CIPHER is supposed to have, the website currently covers approximately **5-10** in a basic/broken form (chat, agent list, model selector, voice selector, health check).

**That's roughly 5-7% of what it should be.**

# CIPHER / Elysian Protocol — Session Context Summary
**Date:** March 10, 2026

## Project Overview
CIPHER is a sovereign AI daemon / multi-agent system built with:
- **Backend:** Python FastAPI deployed on Railway (`cipher-elysian-production-b6a8.up.railway.app`)
- **Frontend Web:** Single-page HTML app at `web/index.html` (Elysian Protocol dashboard)
- **iOS App:** Swift app in `CipherApp/` folder
- **Logo:** SVG at `frontend/public/cipher-logo.svg` + PNG app icon at `CipherApp/CipherApp/Assets.xcassets/AppIcon.appiconset/icon-appstore-1024.png`

## Agent Divisions
- INTELLIGENCE: research, search, analyst, data, synthesis, chronos, archivist
- REAL_ESTATE: apex_architect, scout, market_pulse, profitability_analyst, neighborhood_growth, deal_flow
- ENGINEERING: code, deploy, shell, monitor, provisioning, sentinel
- CREATIVE: image, video
- COMMUNICATIONS: communication, outreach
- OPERATIONS: scheduler, legal, trading, file, web

## Voice Modes
CIPHER_CORE, MOTIVATOR, ANCHOR, PHILOSOPHER, CREATIVE, STRATEGIST, COACH, EDUCATOR

## Current Website Issues (as of March 10)
- Looks juvenile and unprofessional
- Functionality is broken/not working properly
- Missing self-training overnight section (was discussed, needs to be built)
- Welcome screen uses basic emoji icons instead of polished design
- No actual logo displayed (just a "◆" unicode character)

## Key Files
- `web/index.html` — Main website (2051 lines, single HTML file)
- `app/main.py` — FastAPI backend entry
- `app/api/` — API endpoints
- `app/agents/` — Agent implementations
- `app/services/` — Service layer
- `.env` — Environment config
- `BIBLE_CIPHER_ELYSIAN.md` — Core project documentation

## What Needs To Be Done
1. Add self-training overnight section to the website
2. Make the website look professional (not juvenile)
3. Ensure all sections are functional
4. Use the actual CIPHER logo (not placeholder characters)
5. Overall UI/UX overhaul

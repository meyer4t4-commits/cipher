# Prompt for Perplexity Computer Use Agent

## Context

You are helping Mark Meyer deploy and build out the CIPHER / Elysian Protocol website. CIPHER is a sovereign AI intelligence daemon with 30+ specialized agents, deployed as a Python FastAPI backend on Railway and a single-page web app served via Cloudflare Workers.

**Read `CIPHER_BIBLE.md` in this project folder first** — it contains the complete architecture, API endpoints, agent roster, design system, and deployment instructions.

**Read `WEBSITE_REBUILD_CHECKLIST.md`** — it has the full 136-item checklist of what needs to be built.

---

## TASK 1: Deploy the Current Website (URGENT)

The file `web/index.html` (3,180 lines, 123KB) needs to be deployed to Cloudflare Workers so it's live at `elysianprotocol.io`.

### Credentials
- **Cloudflare Account ID:** `85d2891e296d3c6931050919a06319ca`
- **Cloudflare API Token:** `zQleInZLfr7FzBhQPkbP-BgpbBlKAsXa9WLsmfM6`
- **Worker name:** `cipher`

### Approach A: Wrangler CLI (Best)

```bash
npm install -g wrangler
export CLOUDFLARE_API_TOKEN="zQleInZLfr7FzBhQPkbP-BgpbBlKAsXa9WLsmfM6"
```

Create `wrangler.toml` in the project root:
```toml
name = "cipher"
main = "worker.js"
compatibility_date = "2024-01-01"
account_id = "85d2891e296d3c6931050919a06319ca"
```

Create `worker.js` that wraps the HTML:
```javascript
// Read web/index.html content and embed it
const HTML = `... contents of web/index.html ...`;

export default {
  async fetch(request) {
    return new Response(HTML, {
      headers: {
        "content-type": "text/html;charset=UTF-8",
        "cache-control": "no-cache"
      }
    });
  }
};
```

**Important:** The HTML contains 98 backticks and 67 `${` sequences that MUST be escaped. Use this Python script to build the worker:
```python
html = open('web/index.html').read()
escaped = html.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')
worker = f'const HTML = `{escaped}`;\n\nexport default {{\n  async fetch(request) {{\n    return new Response(HTML, {{\n      headers: {{ "content-type": "text/html;charset=UTF-8", "cache-control": "no-cache" }}\n    }});\n  }}\n}};'
open('worker.js', 'w').write(worker)
```
Or just deploy the pre-built `deploy_worker.js` which is already properly escaped.

Then deploy:
```bash
wrangler deploy
```

### Approach B: Cloudflare API (curl)

If wrangler isn't available, use the REST API directly. Write a script that:

1. Reads `web/index.html`
2. Creates a worker.js that embeds it as a template literal
3. Uploads via the CF API:

```bash
# Create the worker file
cat > /tmp/worker_deploy.js << 'EOF'
const HTML = `HTMLPLACEHOLDER`;
export default {
  async fetch(request) {
    return new Response(HTML, {
      headers: { "content-type": "text/html;charset=UTF-8", "cache-control": "no-cache" }
    });
  }
};
EOF

# Use Python/Node to properly embed the HTML (handles escaping)
python3 -c "
import re
html = open('web/index.html').read()
html_escaped = html.replace('\\\\', '\\\\\\\\').replace('\`', '\\\\\`').replace('\${', '\\\\\${')
worker = open('/tmp/worker_deploy.js').read().replace('HTMLPLACEHOLDER', html_escaped)
open('/tmp/worker_final.js', 'w').write(worker)
"

# Deploy via API
curl -X PUT \
  "https://api.cloudflare.com/client/v4/accounts/85d2891e296d3c6931050919a06319ca/workers/scripts/cipher" \
  -H "Authorization: Bearer zQleInZLfr7FzBhQPkbP-BgpbBlKAsXa9WLsmfM6" \
  -F 'metadata={"main_module":"worker.js","compatibility_date":"2024-01-01"};type=application/json' \
  -F 'worker.js=@/tmp/worker_final.js;type=application/javascript+module'
```

### Approach C: CF Dashboard (Manual Paste)

1. Open https://dash.cloudflare.com/85d2891e296d3c6931050919a06319ca/workers/services/edit/cipher/production
2. Select all code in the editor
3. Paste the worker script (from `deploy_worker.js` in the repo, which already has the HTML inlined)
4. Click "Deploy"

### Verification

After deployment, verify:
- https://elysianprotocol.io loads the site
- https://cipher.meyer4t4.workers.dev loads the site
- The dashboard view loads (it fetches from the Railway backend)
- Navigation between views works (sidebar links)

---

## TASK 2: Build Remaining Website Sections (D through P)

After deployment is confirmed, continue building the website by adding sections D through P to `web/index.html`.

### How the SPA Works

The site is a single HTML file with:
- A sidebar with nav links
- View containers (`<div id="XXX-view" class="view-container">`)
- A `navigateTo(viewId)` function that shows/hides views
- JavaScript at the bottom that fetches data from the backend API

### Backend API Base URL
```javascript
const BACKEND_URL = 'https://cipher-elysian-production-b6a8.up.railway.app';
```

All API endpoints are listed in CIPHER_BIBLE.md Section 3.

### Build Order (Priority)

#### D. Chat Interface Upgrades
The chat view exists but needs:
- Markdown rendering for responses (use marked.js or similar)
- Code syntax highlighting (highlight.js is already loaded but unused)
- Agent attribution badges on responses (which agent handled it)
- Confidence score display
- Message timestamps
- Copy message / retry buttons
- Conversation search and export

**Key API:** `POST /chat/stream` for streaming, `GET /chat/conversations` for history

#### E. Agent Management
Build a grid/list view of all 30+ agents with:
- Agent cards showing name, division, description, status
- Agent detail view (click a card to expand)
- Direct invoke button (calls `POST /agents/execute`)
- Execution history (`GET /agents/history`)
- Division tabs matching the 6 divisions
- Real-time status indicators

**Key APIs:** `GET /agents/agents`, `POST /agents/execute`, `GET /agents/history`, `GET /agents/capabilities`

#### I. Cron/Scheduler
- List all 14 cron tasks with status
- Enable/disable toggles
- Manual trigger buttons
- Last run time and next scheduled run
- Task execution logs

**Key APIs:** `GET /cron/tasks`, `POST /cron/tasks/{id}/enable`, `POST /cron/tasks/{id}/run`

#### F. Trading Dashboard (Flux)
- Paper portfolio overview
- Watchlist with live quotes
- Technical analysis display
- Order history
- Trade execution form

**Key API:** `POST /agents/execute` with `agent_name: "trading_agent"`

#### G. Real Estate Pipeline
- Property pipeline view
- Deal cards with financials (MAO, ARV, ROI)
- Market pulse feed
- Neighborhood growth scores

**Key APIs:** Various agent executions (apex_architect, scout, market_pulse, neighborhood_growth, deal_flow)

Continue with H through P following the checklist.

### Design Principles

- **Dark theme** — all backgrounds use the CSS variables defined in `:root`
- **Cards everywhere** — use `background: var(--bg-tertiary); border: 1px solid var(--border-color); border-radius: var(--radius-md);`
- **Lucide icons** — already loaded, use `<i data-lucide="icon-name"></i>` then call `lucide.createIcons()`
- **Responsive** — sidebar collapses on mobile
- **Live data** — every view should fetch real data from the backend API on load
- **Loading states** — show skeleton/spinner while fetching
- **Error handling** — gracefully handle API errors (backend may be restarting)

### Style Patterns (from existing code)

```css
/* Card */
.widget-card {
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 20px;
    transition: all 0.3s ease;
}
.widget-card:hover {
    border-color: var(--accent-primary);
    transform: translateY(-2px);
}

/* Status indicators */
.status-online { color: var(--success); }
.status-warning { color: var(--warning); }
.status-error { color: var(--danger); }
```

### After Each Section

After building each section, redeploy to Cloudflare Workers using whichever approach worked in Task 1. The goal is for Mark to see live updates at elysianprotocol.io after each section is complete.

---

## IMPORTANT NOTES

1. **The backend is LIVE and has REAL data.** The APIs work. Test them:
   ```bash
   curl https://cipher-elysian-production-b6a8.up.railway.app/system/health
   curl https://cipher-elysian-production-b6a8.up.railway.app/agents/agents
   ```

2. **Everything is one HTML file.** All CSS, JS, and HTML are in `web/index.html`. No build tools, no bundler, no framework. Just vanilla HTML/CSS/JS.

3. **The iOS app exists separately** — don't modify it unless asked. Focus on the web interface.

4. **Deploy early and often.** Don't build all sections before deploying. Build one, deploy, verify, repeat.

5. **The HTML has 98 backticks and 67 `${` sequences** (template literals in JS). The `deploy_worker.js` file has these properly escaped. When building new sections, you can use template literals in the HTML — just re-run the escape script before deploying. Or better: use wrangler with a build step that auto-escapes.

6. **Mark's vision:** CIPHER should feel like a command center, not a chat app. The dashboard is the home screen. Every subsystem has its own dedicated view with real data. The chat is ONE view among many, not the whole app.

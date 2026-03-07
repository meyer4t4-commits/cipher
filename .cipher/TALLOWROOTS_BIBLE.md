# TALLOWROOTS — PROJECT CONTEXT FOR CIPHER
## Last Updated: March 3, 2026
## Owner: Mark & Rose Mannino (meyer4t4@gmail.com)
## Website: tallowroots.co
## Shopify Store: tallowroots.myshopify.com

---

# 1. WHAT IS TALLOWROOTS

TallowRoots is a family-owned, DTC tallow skincare brand based in Mantua, NJ. The brand was born when Mark and Rose's daughter Silvana had severe eczema — they made tallow balm at home and her skin cleared up overnight. That moment is the brand's origin story and marketing anchor.

**Family name: Mannino** (Mark goes by Meyer professionally)

---

# 2. PRODUCT LINES

| Product | Target | Landed Cost | Retail Price | Handle |
|---------|--------|-------------|-------------|--------|
| **Tallow Glow** | Women | ~$4-5 | $30 | `tallow-glow` |
| **Balm Butta** | Men | ~$4-5 | $30 | `balm-butta` |

Both are grass-fed tallow skincare. Ingredients: grass-fed tallow, olive oil, beeswax, essential oils. 5 clean ingredients total.

---

# 3. CURRENT STATUS

- **Sales**: 10-20 orders/month
- **Distribution**: Shopify DTC + 3 salons
- **Email list**: Small (needs growth)
- **Social**: Active on Instagram, starting TikTok
- **Revenue target**: $5K/month by Month 3, $10K/month by Month 6

---

# 4. MISSION FILES

All TallowRoots website overhaul files are at: `data/tallowroots/`

### Master Mission File
`data/tallowroots/CIPHER_MISSION_TALLOWROOTS.md` — 9 missions to be run in order

### Mission Summary
| # | Mission | What It Does |
|---|---------|-------------|
| 1 | Push Shopify Pages | Creates 6 new pages (FAQ, Shipping, Returns, Ingredients, Wholesale, About) |
| 2 | Update Products & SEO | Rewrites product descriptions + SEO meta tags for Tallow Glow & Balm Butta |
| 3 | Create Blog Posts | 4 SEO-targeted blog drafts in a "Journal" blog |
| 4 | Trust Badges | Pushes homepage trust bar + product page trust badges as Liquid snippets |
| 5 | Navigation Menu | Restructures main menu + footer menu |
| 6 | Email Sequences | Sets up 12 emails across 3 Klaviyo flows + 2 Shopify discount codes |
| 7 | Checkout Optimization | Free shipping threshold, payment methods, abandoned cart recovery |
| 8 | Analytics Pixels | GA4, Meta Pixel, TikTok Pixel, Google Search Console |
| 9 | Full Site Verification | Tests all changes with GREEN/YELLOW/RED status report |

### File Inventory
| File | Purpose |
|------|---------|
| `cipher_tallowroots_website_fix.py` | Master script — 8 modules, full Shopify API integration |
| `CIPHER_MISSION_TALLOWROOTS.md` | 9 mission prompts formatted for Cipher |
| `HUMAN_CHECKLIST.txt` | Manual tasks for Mark (technical) and Rose (creative) |
| `analytics_install_guide.md` | Step-by-step pixel installation guide |
| `blog_post_1.html` — `blog_post_4.html` | 4 blog post drafts |
| `email_sequence_welcome.txt` | 5-email welcome flow |
| `email_sequence_abandoned_cart.txt` | 3-email cart recovery flow |
| `email_sequence_post_purchase.txt` | 4-email post-purchase flow |
| `trust_bar_homepage.html` | Homepage trust badge bar HTML/CSS |
| `trust_badges_product.html` | Product page trust badges HTML/CSS |
| `product_description_tallow-glow.html` | Tallow Glow rewritten description |
| `product_description_balm-butta.html` | Balm Butta rewritten description |
| `navigation_structure.json` | New main menu + footer menu structure |
| `seo_meta_tags.json` | Homepage & collection SEO tags |
| `TallowRoots_Website_Audit_TodoList.pdf` | Full website audit reference |

---

# 5. API REQUIREMENTS

The master script (`cipher_tallowroots_website_fix.py`) needs:
- `SHOPIFY_STORE` = `tallowroots.myshopify.com`
- `SHOPIFY_ACCESS_TOKEN` = (Shopify Admin API private app token — check .env)

Optional (for Mission 6):
- `KLAVIYO_API_KEY` = (if configured)

Optional (for Mission 8):
- `GA4_MEASUREMENT_ID`
- `META_PIXEL_ID`
- `TIKTOK_PIXEL_ID`

If API tokens aren't available, the script runs in FILE-GENERATION mode and outputs all content as local files that can be manually uploaded.

---

# 6. HOW TO RUN

**Option A: Paste missions into Cipher dashboard (localhost:8000)**
Open `data/tallowroots/CIPHER_MISSION_TALLOWROOTS.md`, paste each mission prompt one at a time.

**Option B: Run the master script directly**
```bash
cd data/tallowroots
python cipher_tallowroots_website_fix.py
```
Without a Shopify token it generates all files locally. With a token it pushes directly to Shopify.

---

# 7. HUMAN CHECKLIST (AFTER MISSIONS)

After all 9 missions complete, Mark needs to:
1. Add Shopify Admin API token to .env if not already there
2. Add `{% render 'trust-bar' %}` in theme editor (homepage, below header)
3. Add `{% render 'product-trust-badges' %}` in theme editor (product page, below add-to-cart)
4. Connect Klaviyo account and set API key
5. Enable Shop Pay, Apple Pay, Google Pay in Shopify Payments settings
6. Set up Google Search Console and verify domain
7. Review and publish the 4 blog draft posts

Rose needs to:
1. Review all 6 new pages for voice/tone
2. Review product descriptions
3. Review and approve blog posts before publishing
4. Review email sequences for brand voice
5. Add real product photos where placeholders exist

---

# 8. BRAND VOICE NOTES

- Origin story is the #1 marketing asset — "Silvana's skin cleared up overnight"
- Tone: warm, family-first, clean-ingredient focused, NOT clinical
- Competitor benchmarks: Toups & Co ($3M/yr), Primally Pure (25% from influencer affiliates)
- Key differentiator: family story + handmade in NJ + only 5 ingredients

# Part 1: What You're Getting

A Claude Code skill that operates your Meta (Facebook + Instagram) ad account end-to-end via the **official Meta CLI** plus the Marketing API SDK. Create, scale, pause, analyze campaigns directly from Claude Code chat. No clicking through Ads Manager.

I walk through this skill in the Meta Ads + Claude Code video here: https://youtu.be/_TODO_VIDEO_URL_

This skill replaces Ads Manager for most operational work. You give Claude a brief - "launch a $50/day cold campaign for X to US business owners 30-55 with these 5 creatives, optimization toward webinar registration" - and Claude scaffolds the campaign, ad set, creatives, and ads, patches detailed targeting via the Marketing API SDK, and reports back the IDs and Ads Manager URL. Everything starts PAUSED for your review before going live.

## What It Does

- **Create campaigns + ad sets + ads** via official Meta CLI with structured naming (`[OBJECTIVE]_[AUDIENCE]_[DATE]`)
- **Upload statics + videos** with auto-thumbnail generation
- **Apply detailed targeting** (interests, behaviors, lookalikes, custom audiences, age, placements) via the Marketing API SDK
- **Set custom-conversion optimization** (e.g. `WebinarRegistration` event)
- **Pause, scale, duplicate** existing campaigns/ad sets/ads
- **Pull insights** (spend, CPM, CTR, CPL, ROAS) via CLI for any date range
- **Find interest/behavior IDs** by keyword (`targeting.py search "small business owners"`)
- **Create custom audiences** from pixel events (`targeting.py audience ...`)

## Why CLI + SDK Hybrid

The official Meta CLI handles 80% of operations cleanly (campaigns, ad sets, creatives, uploads). But the CLI doesn't expose detailed targeting (interests, behaviors, lookalikes, placements, custom audiences). So the skill scaffolds with CLI, then patches targeting via the Marketing API SDK Python helper.

You don't need to know any of this - just give Claude a brief. The skill knows which tool to call when.

## Iron Rules Baked In

- **PAUSED on creation.** Nothing goes live until you say so. The skill literally refuses to add `--status ACTIVE` to any create command.
- **Budgets in cents.** $50 = `5000`. The skill triple-checks the conversion before submitting.
- **Confirm ambiguous briefs.** If creative file path, landing URL, or audience criteria are unclear, the skill asks before creating.

## v25 Quirks Pre-Solved

The Meta Marketing API has a long list of v25 gotchas that bite you in production. The skill has them all pre-solved:

- Custom audience `subtype` parameter dropped
- `targeting_optimization` field replaced with `targeting_automation.advantage_audience`
- `promoted_object` is immutable after ad set creation (set on creation via SDK)
- CLI `--link-url` for video creatives is broken (bypass via SDK)
- Video creative requires thumbnail URL (auto-fetched from `AdVideo.get_thumbnails`)
- 4K video uploads frequently fail at publishing phase (auto-transcode to 1080p before upload)
- And many more (see the SKILL.md `## Marketing API v25 quirks` section)

## What You Need

- **Meta Business account** with ad account access - https://business.facebook.com
- **System User token** with `ads_management` + `ads_read` + `pages_read_engagement` scopes - generated in Business Suite > Settings > Users > System Users
- **Python 3.10+** (already on Mac/Linux)
- **uv** (modern Python package manager) - https://docs.astral.sh/uv/getting-started/installation/
- **Claude Code** - https://claude.ai/code

## Cost

Meta API is free. Your only spend is the actual ad budget (which you set).

## Heads Up

- AI agents + Meta ads used to get accounts BANNED for using third-party automation. That changed when Meta released the official CLI + MCP in late April 2026. The official CLI is now the supported way. The skill ONLY uses the official tooling - no third-party scrapers, no unofficial wrappers.
- **The Meta MCP at `mcp.facebook.com/ads` does NOT work in Claude Code yet.** Meta is rolling it out gradually and most ad accounts don't have access. If you want to use the MCP, use Claude Cowork (desktop app). For Claude Code, this skill uses the official CLI directly.
- **Test your token first.** Before launching real campaigns, the install prompt runs `meta auth status` and `meta ads page list` to confirm everything is wired correctly.

---

# Part 2: Copy-Paste This Into Claude Code

```
I want you to install the meta-ads Claude Code skill from https://github.com/bosar-academy/cc-meta-ads and walk me through full setup including the official Meta CLI + Marketing API SDK.

Step 1 - Install the skill:

Run:
  git clone https://github.com/bosar-academy/cc-meta-ads ~/.claude/skills/meta-ads

Confirm ~/.claude/skills/meta-ads/SKILL.md exists.

Step 2 - Install the official Meta CLI:

The official Meta CLI install docs are at:
  https://developers.facebook.com/documentation/ads-commerce/ads-ai-connectors/ads-cli/setup/get-started

Open that page and follow Meta's CURRENT install instructions for my OS (Meta updates the installer regularly, so always use the version on the docs page rather than a cached command).

After install, verify:
  meta --version

If `meta` is not on my PATH, add the installer's bin directory (typically `~/.local/bin/` or `/usr/local/bin/`) to my PATH.

Step 3 - Authenticate the CLI:

Run:
  meta auth login

This opens a browser window. Tell me to sign in with my Meta Business account and authorize the CLI for ads_management.

After the browser flow completes, verify:
  meta auth status

Should print "Authenticated as: <my name>". If it says "opens browser, can't automate" - just open the URL it printed manually in my browser, complete the flow, then re-check status.

Step 4 - Install the SDK Python:

The CLI handles 80% of operations but doesn't expose detailed targeting. The skill needs the Marketing API SDK for that. Install via uv:

  uv tool install meta-ads

(If the package name differs in current uv registry, search with `uv tool list` or fall back to `pip install --user facebook-business` and update META_PY in SKILL.md accordingly.)

Confirm the SDK Python is available:
  ls ~/.local/share/uv/tools/meta-ads/bin/python

This path is what helpers/targeting.py expects.

Step 5 - Write credentials to ~/.config/meta/credentials:

The targeting.py helper reads the System User token from ~/.config/meta/credentials (RAW token only, no KEY= prefix).

If `meta auth login` saved the token somewhere different, find it via:
  meta auth token --show

Then write the raw token:
  mkdir -p ~/.config/meta
  echo 'RAW_TOKEN_HERE' > ~/.config/meta/credentials
  chmod 600 ~/.config/meta/credentials

Verify the file has ONLY the token (no `KEY=` prefix, no quotes, no whitespace at end).

Step 6 - Capture my account defaults:

Ask me one at a time and write to ~/.claude/skills/meta-ads/.env:

1. My ad account ID (format: act_XXXXXXXXXX) - find at business.facebook.com/adsmanager → look at URL
2. My default Page ID (the Facebook Page ads should run from) - find via `meta ads page list`
3. My pixel ID - find at business.facebook.com/events_manager
4. My default landing URL (the page traffic should go to by default)

Write as:
  META_AD_ACCOUNT_ID=act_...
  META_DEFAULT_PAGE_ID=...
  META_PIXEL_ID=...
  META_DEFAULT_LANDING_URL=https://...

Step 7 - Smoke test:

Run these to confirm everything is wired:

  meta auth status
  meta ads page list
  meta --output json ads insights get --date-preset last_7d --fields spend,impressions,clicks,ctr --ad-account-id "$(grep META_AD_ACCOUNT_ID ~/.claude/skills/meta-ads/.env | cut -d= -f2)"

Then test the SDK helper:
  META_PY=~/.local/share/uv/tools/meta-ads/bin/python
  $META_PY ~/.claude/skills/meta-ads/helpers/targeting.py search "Entrepreneurship"

Should print at least 3 interest IDs with names. If yes, the SDK Python + token are working.

Step 8 - Confirm I'm ready:

Tell me the skill is installed and remind me of the trigger phrases:
- "Create a Meta campaign for X targeting Y with $X/day"
- "Pull insights for my last 7 days"
- "Pause campaign <name>"
- "Scale ad set <name> by 25%"
- "Find interest IDs for 'B2B SaaS'"
- "/meta-ads launch --strategy <path-to-strategy.md>" (if I have /ad-strategy installed)

Iron rules I should know:
- Everything launches PAUSED by default. The skill never adds --status ACTIVE without my explicit confirmation.
- Budgets are in CENTS internally ($50 = 5000). The skill handles conversion but always shows me both for review.
- For complex campaigns, run /ad-strategy first - the YAML handoff block in its output feeds directly into /meta-ads.

That's it - ready to operate Meta ads from Claude Code.
```

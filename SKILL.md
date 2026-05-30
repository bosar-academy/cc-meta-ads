---
name: meta-ads
description: Use when the user mentions running, creating, pausing, scaling, or analyzing Meta (Facebook/Instagram) ad campaigns, ad sets, or creatives. Triggers on briefs like "run a $X/day ad", "pause the X campaign", "create a campaign for X targeting Y", uploading video/image ads, pulling ad performance/insights, or any reference to the Meta Marketing API or Ads Manager.
---

# Meta Ads

Run Meta ads via the **official `meta` CLI** plus the Marketing API SDK. The Meta MCP at `mcp.facebook.com/ads` does NOT work in Claude Code — never try it.

## Setup (handled by install prompt)

The install prompt at `INSTALL.md` walks the user through:

- Installing the official Meta CLI (the `meta` binary on PATH)
- Generating a System User token and writing it to `~/.config/meta/credentials` (raw token, no `KEY=` prefix)
- Installing a Python with `facebook-business` SDK via `uv tool install meta-ads`
- Writing the user's defaults to `~/.claude/skills/meta-ads/.env`:
  - `META_AD_ACCOUNT_ID=act_...`
  - `META_DEFAULT_PAGE_ID=...`
  - `META_PIXEL_ID=...`
  - `META_DEFAULT_LANDING_URL=https://...`

Read those env vars when running CLI/SDK commands. If any are missing, ask the user where to find them or run the install prompt again.

## Iron rules

- **Everything starts PAUSED.** Never include `--status ACTIVE` in create commands. Activate only after the user explicitly confirms.
- **Budgets are CENTS.** `2000` = $20.00. `5000` = $50.00. Triple-check before submitting.
- **Confirm ambiguous briefs.** If creative file path, landing URL, or audience criteria are unclear, ask before creating.
- **Use the user's default Page** (`META_DEFAULT_PAGE_ID` from `.env`). If a different Page is requested, run `meta ads page list` to discover. If that returns empty, assets need re-assignment in Business Suite > Settings > Users > System Users.
- **The user's `META_AD_ACCOUNT_ID` won't auto-load from random working directories** (project-local `.env` files may shadow it). Pass `--ad-account-id "$META_AD_ACCOUNT_ID"` explicitly when working in unfamiliar directories.

## Hybrid pattern (CLI scaffold + SDK targeting)

The CLI doesn't expose detailed targeting. Use this 3-stage flow:

1. **CLI scaffold** — campaign → adset → creative (uploads media) → ad. All PAUSED.
2. **SDK patch targeting** — interests, behaviors, age, placements via `helpers/targeting.py`.
3. **CLI activate** — flip status to ACTIVE only after the user reviews.

## Execution flow for "run an ad" briefs

For a brief like *"run the sunglasses ad to US business owners 30-55, $20/day"*:

1. Pre-flight: `meta auth status` → `meta ads page list` (capture PAGE_ID)
2. Confirm with the user: video/image file path, landing URL, exact audience, budget→cents conversion
3. Search interest/behavior IDs: `targeting.py search "<keyword>"` (see helper below)
4. Build `targeting.json` (shape below)
5. Run CLI scaffold (capture each returned ID):
   ```
   meta ads campaign create --name "..." --objective OUTCOME_TRAFFIC --daily-budget 2000
   meta ads adset create <CAMPAIGN_ID> --name "..." --optimization-goal LINK_CLICKS --billing-event IMPRESSIONS --targeting-countries US
   meta ads creative create --name "..." --page-id <PAGE_ID> --video ./file.mp4 --body "..." --title "..." --link-url ... --call-to-action SHOP_NOW
   meta ads ad create <ADSET_ID> --name "..." --creative-id <CREATIVE_ID>
   ```
6. SDK patch: `targeting.py patch <ADSET_ID> targeting.json`
7. Report to the user: all 4 IDs, summary of what was created, Ads Manager URL: `https://business.facebook.com/adsmanager/manage/campaigns?act=<AD_ACCOUNT_NUMERIC_ID>`
8. **Wait for explicit "go live"** before running the three `--status ACTIVE` updates.

## Quick reference

| Operation | Command |
|---|---|
| Auth check | `meta auth status` |
| List Pages | `meta ads page list` |
| List campaigns | `meta ads campaign list` |
| Insights | `meta ads insights get --date-preset last_7d --fields spend,impressions,clicks,ctr,cpc,conversions,purchase_roas` |
| Pause | `meta ads campaign update <ID> --status PAUSED` |
| JSON output | prepend `meta --output json ...` |

Objectives: `OUTCOME_SALES`, `OUTCOME_TRAFFIC`, `OUTCOME_LEADS`, `OUTCOME_AWARENESS`, `OUTCOME_ENGAGEMENT`, `OUTCOME_APP_PROMOTION`
CTAs: `SHOP_NOW`, `LEARN_MORE`, `SIGN_UP`, `SUBSCRIBE`, `BOOK_TRAVEL`, `GET_OFFER`, `APPLY_NOW`, `DOWNLOAD`, `CONTACT_US`, `WATCH_MORE`

## Targeting helper

`helpers/targeting.py` is a self-contained Python script. Run via the SDK-capable interpreter:

```bash
META_PY=~/.local/share/uv/tools/meta-ads/bin/python

# Find interest/behavior IDs (use this anytime the user names categories not IDs)
$META_PY ~/.claude/skills/meta-ads/helpers/targeting.py search "small business owners"

# Patch detailed targeting onto an adset (must be PAUSED — script enforces this)
$META_PY ~/.claude/skills/meta-ads/helpers/targeting.py patch <ADSET_ID> targeting.json
```

`targeting.json` shape:
```json
{
  "geo_locations": {"countries": ["US", "CA"]},
  "age_min": 30, "age_max": 55,
  "interests": [{"id": "6003107902433", "name": "Entrepreneurship"}],
  "behaviors": [{"id": "6002714895372", "name": "Small business owners"}],
  "publisher_platforms": ["facebook", "instagram"],
  "facebook_positions": ["feed", "reels", "story"],
  "instagram_positions": ["stream", "reels", "story", "explore"]
}
```

For complex AND/OR audience logic use `flexible_spec`: a list where each item is intersected (OR within, AND across).

## Common gotchas

- **"Malformed access token"** → credentials file has `KEY=value` somewhere. Must be raw token only.
- **Page list empty** → fix in Business Suite (asset assignment to system user).
- **Budget seems 100x off** → cents.
- **Targeting patch fails on ACTIVE adset** → helper refuses. Pause first.
- **"Black screen" in Ads Manager preview for some placements (especially IG)** → 90% of the time this is **a browser-side ad blocker** overlaying black on Meta's preview iframe, NOT a real creative or delivery issue. Before debugging: ask the user to (1) try incognito mode, (2) disable ad blockers on business.facebook.com, (3) try a different browser. Don't waste hours transcoding/upscaling/reuploading images — check the browser FIRST.

## Marketing API v25 quirks (verified in production launches)

These bite when building real campaigns. Skip the trial-and-error:

### Custom Audience creation
- **`subtype` parameter dropped.** Don't include it — Meta now infers type from the rule structure. Helper already updated.
- Modern call: `AdAccount(id).create_custom_audience(params={"name", "rule": json.dumps(...), "retention_days", "prefill"})`

### Targeting JSON
- **`targeting_optimization` field removed.** Replaced with `targeting_automation.advantage_audience: 0` (or 1 to enable). If you submit `targeting_optimization`, Meta rejects with error 1870197.
- **Advantage audience is now mandatory.** You MUST set `targeting_automation.advantage_audience` explicitly to 0 or 1 — error 1870227 if missing.
- **Excluded audiences syntax:** `"excluded_custom_audiences": [{"id": "..."}]`
- **Mobile-only:** `"device_platforms": ["mobile"]`
- **No Audience Network:** stick to `"publisher_platforms": ["facebook", "instagram"]` and explicit positions.

### Promoted object (custom conversion optimization)
- **`promoted_object` is IMMUTABLE after ad set creation.** You cannot patch it later — error 3260011 ("Can't Make Edits to Published Ad Set"). Set it on creation via SDK.
- **Custom conversion optimization:** use `{"custom_conversion_id": "<ID>"}` ALONE. Adding `pixel_id` or `custom_event_type` next to it triggers error 1885014 ("Promoted Object Invalid"). The custom conversion already encodes the pixel and rule.
- Example for OFFSITE_CONVERSIONS optimization toward custom conversion:
  ```python
  {"custom_conversion_id": "YOUR_CUSTOM_CONVERSION_ID"}
  ```

### Ad set creation via CLI
- Default bid strategy requires `--bid-amount` cents. For LOWEST_COST_WITHOUT_CAP (no bid cap), the CLI doesn't expose it — go via SDK with `"bid_strategy": "LOWEST_COST_WITHOUT_CAP"`.
- ABO mode = omit campaign-level `--daily-budget`. Don't combine with `--adset-budget-sharing` (errors).
- Required for custom-conversion ad sets: create via SDK directly to set `promoted_object` on creation, since the CLI's `--pixel-id`/`--custom-event-type` don't support `custom_conversion_id`.

### Video creatives
- **CLI's `--link-url` for video is broken.** Meta v25 rejects: "field link_url is not supported in video_data of object_story_spec." Bypass the CLI for video creatives — build via SDK directly.
- **Correct video creative shape (SDK):**
  ```python
  {
    "name": "...",
    "object_story_spec": {
      "page_id": "...",
      "video_data": {
        "video_id": "...",
        "image_url": "https://...",  # REQUIRED - thumbnail
        "title": "...",
        "message": "...",
        "call_to_action": {
          "type": "SIGN_UP",
          "value": {"link": "https://..."}  # link goes HERE, not in video_data
        }
      }
    }
  }
  ```
- **Thumbnail is required.** Error 1443226 if missing. Fetch auto-generated thumb from `AdVideo(video_id).get_thumbnails(fields=["uri", "is_preferred"])` and use the preferred one's `uri`.
- **`description` field NOT supported on video creatives.** Only on image (link_data). Pass description only for image creatives.

### Video uploads
- **4K source files (2160x3840) at high bitrate (~30 Mbps) frequently fail Meta's publishing phase** — uploading_phase completes, processing_phase completes, then publishing_phase goes to "error" with no useful message. **Fix:** transcode to 1080x1920 at 6-8 Mbps before upload. ffmpeg one-liner: `ffmpeg -i input.mp4 -vf scale=1080:1920 -c:v libx264 -preset fast -b:v 6M -c:a aac -b:a 128k output.mp4`. Meta downsamples to 1080p for display anyway, so no quality loss in the feed.
- **Files >100MB return 413** on `create_ad_video(source=...)`. Use chunked upload:
  ```python
  video = AdVideo(parent_id=AD_ACCOUNT)
  video[AdVideo.Field.filepath] = path
  video.remote_create()
  video_id = video.get_id()
  ```
- **Status check after upload:** `AdVideo(video_id).api_get(fields=["status"])` returns a `VideoStatus` object (not dict). Access via `info.get("status")["video_status"]`. Wait for `"ready"` before creating the creative. Processing time: 30-180s typical, up to 5-10 min for large files.
- **Cache video_ids** if iterating, since uploads are slow. Same video file uploaded twice creates two separate video objects.

### Image creatives (link_data)
- Standard `link_data` shape works fine via SDK or CLI. CLI is OK for image-only ads.
- For images, `description` IS supported.
- **`AdAccount.create_ad_image()` returns a flat AdImage object** with `hash` directly on it (`response["hash"]`). NOT wrapped in `{"images": {filename: {hash: ...}}}` like older SDK docs suggest. Just access `image["hash"]`.

### Multi-format creatives (NOT WORKING reliably — needs more research)

**Status: do not use for production.** `asset_feed_spec` with `optimization_type: "PLACEMENT"` and 2 assets (1:1 + 9:16) expecting Meta to auto-pick by aspect ratio does NOT work. Meta requires explicit `asset_customization_rules` mapping each placement to a specific labeled asset — but the labeling mechanism is poorly documented:
- `image_label: {"name": "..."}` on the rule must match a label on the image asset
- The image asset does NOT accept a `name` field (Meta rejects with error 100)
- Could not find which property serves as the matching label

**Recommended for now:** stick with single-format creatives via `object_story_spec.link_data` (image) or `object_story_spec.video_data` (video). Meta auto-letterboxes/auto-crops in non-native placements. Acceptable for normal campaigns, suboptimal for performance.

### Rate limits
- Heavy session (50+ creates) can hit ad-account API rate limit (error 17, subcode 2446079). Wait 5-10 min. Use bulk operations or batch via SDK to reduce call count.

### Helper extensions
- `targeting.py audience <ad_account> <name> <pixel_id> <event_name> <retention_days>` — create custom audience from pixel events filtered by content_name
- `targeting.py promote <adset_id> <json>` — patch promoted_object (refuses ACTIVE adsets)
- `targeting.py show <adset_id>` — returns full targeting + `promoted_object`

### Anti-overspend defaults
Always include in targeting JSON:
```json
{
  "device_platforms": ["mobile"],
  "publisher_platforms": ["facebook", "instagram"],
  "facebook_positions": ["feed", "facebook_reels", "story"],
  "instagram_positions": ["stream", "reels", "story"],
  "targeting_automation": {"advantage_audience": 0}
}
```
Skip: Audience Network, Marketplace, Search, In-stream Video, Threads, Explore, Right Column, Messenger.

### Strategic gotchas (campaign architecture)
- **Two ad sets with identical targeting in same ABO campaign cannibalize each other** in Meta's auction. Either: separate campaigns, OR single ad set with mixed creatives, OR differentiated audiences. Don't run identical-targeting parallel ad sets in one campaign.
- **Learning phase exit requires 50 events per ad set per 7 days.** Below this, signal is noise. Plan budget accordingly (e.g., $1.5K/week per ad set at $30 target CPR).
- **CTA A/B testing requires same creative on both CTAs** to isolate signal. Don't mix different creatives across CTA variants — confounded.
- **URL UTMs** for Meta dynamic params: `{{ad.name}}`, `{{adset.name}}`, `{{campaign.name}}`, `{{ad.id}}`, `{{site_source_name}}`. Meta substitutes at click time.

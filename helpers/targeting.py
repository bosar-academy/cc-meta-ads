#!/usr/bin/env python3
"""Meta Ads targeting helper (SDK-only operations).

Usage:
  targeting.py search <keyword>                       Find interest/behavior IDs by keyword
  targeting.py patch  <adset_id> <json>               Replace adset targeting with JSON file (or '-' for stdin)
  targeting.py show   <adset_id>                      Print current targeting on an adset
  targeting.py promote <adset_id> <json>              Set promoted_object on adset (e.g., custom_conversion_id)
  targeting.py audience <ad_account_id> <name> <pixel_id> <event_name> <retention_days>
                                                       Create custom audience from pixel events

The CLI does not expose interests/behaviors/age/placements/promoted_object/custom audiences — this fills that gap.
"""

import json
import sys
from pathlib import Path

from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.targetingsearch import TargetingSearch
from facebook_business.adobjects.adaccount import AdAccount


CRED_PATH = Path("~/.config/meta/credentials").expanduser()


def init() -> None:
    if not CRED_PATH.exists():
        sys.exit(f"No token at {CRED_PATH}. Generate a System User token in Meta Business Suite.")
    token = CRED_PATH.read_text().strip()
    if "=" in token.splitlines()[0]:
        sys.exit("Credentials file looks like dotenv. It must contain ONLY the raw token.")
    FacebookAdsApi.init(access_token=token)


def cmd_search(query: str) -> None:
    init()
    seen = set()
    for type_ in ("adinterest", "adTargetingCategory"):
        try:
            results = TargetingSearch.search(params={"q": query, "type": type_, "limit": 20})
        except Exception:
            continue
        if not results:
            continue
        printed_header = False
        for r in results:
            rid = r.get("id")
            if not rid or rid in seen:
                continue
            seen.add(rid)
            if not printed_header:
                print(f"\n# {type_}")
                printed_header = True
            size = r.get("audience_size_lower_bound") or r.get("audience_size") or "?"
            path = " > ".join(r.get("path", [])) if r.get("path") else ""
            sub = f"  [{r.get('type','')}]" if r.get("type") else ""
            print(f"  {rid:<20} {r.get('name','')}{sub}  size={size}  {path}")


def _load_targeting(json_arg: str) -> dict:
    if json_arg == "-":
        return json.load(sys.stdin)
    return json.loads(Path(json_arg).read_text())


def cmd_patch(adset_id: str, json_arg: str) -> None:
    init()
    targeting = _load_targeting(json_arg)
    adset = AdSet(adset_id).api_get(fields=["status", "effective_status", "name"])
    if adset.get("effective_status") == "ACTIVE" or adset.get("status") == "ACTIVE":
        sys.exit(
            f"REFUSED: adset '{adset.get('name')}' is ACTIVE. "
            "Pause it before patching targeting (avoids mid-flight delivery changes)."
        )
    AdSet(adset_id).api_update(params={"targeting": targeting})
    print(f"OK: patched targeting on {adset_id} ({adset.get('name')})")


def cmd_show(adset_id: str) -> None:
    init()
    adset = AdSet(adset_id).api_get(fields=["name", "effective_status", "targeting", "promoted_object"])
    print(json.dumps(dict(adset), indent=2, default=str))


def cmd_promote(adset_id: str, json_arg: str) -> None:
    """Patch promoted_object on an adset (used for custom_conversion_id, custom_event_str, etc.)."""
    init()
    promoted = _load_targeting(json_arg)
    adset = AdSet(adset_id).api_get(fields=["status", "effective_status", "name"])
    if adset.get("effective_status") == "ACTIVE" or adset.get("status") == "ACTIVE":
        sys.exit(
            f"REFUSED: adset '{adset.get('name')}' is ACTIVE. "
            "Pause it before patching promoted_object (avoids mid-flight delivery changes)."
        )
    AdSet(adset_id).api_update(params={"promoted_object": promoted})
    print(f"OK: patched promoted_object on {adset_id} ({adset.get('name')}): {promoted}")


def cmd_audience(ad_account_id: str, name: str, pixel_id: str, event_name: str, retention_days: str) -> None:
    """Create a Custom Audience from a pixel Lead event filtered by content_name.

    Args:
      ad_account_id: e.g. "act_<YOUR_AD_ACCOUNT_NUMERIC_ID>"
      name: human-readable audience name
      pixel_id: e.g. "<YOUR_PIXEL_ID>"
      event_name: matches pixel content_name (e.g. "Webinar Registration")
      retention_days: e.g. "30"
    """
    init()
    ad_account_id = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"
    rule = {
        "inclusions": {
            "operator": "or",
            "rules": [{
                "event_sources": [{"id": pixel_id, "type": "pixel"}],
                "retention_seconds": int(retention_days) * 86400,
                "filter": {
                    "operator": "and",
                    "filters": [
                        {"field": "event", "operator": "eq", "value": "Lead"},
                        {"field": "content_name", "operator": "contains", "value": event_name},
                    ],
                },
            }],
        },
    }
    audience = AdAccount(ad_account_id).create_custom_audience(params={
        "name": name,
        "rule": json.dumps(rule),
        "retention_days": int(retention_days),
        "prefill": True,
    })
    print(f"OK: created custom audience id={audience['id']} name='{name}'")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    cmd, rest = args[0], args[1:]
    if cmd == "search" and len(rest) == 1:
        cmd_search(rest[0])
    elif cmd == "patch" and len(rest) == 2:
        cmd_patch(rest[0], rest[1])
    elif cmd == "show" and len(rest) == 1:
        cmd_show(rest[0])
    elif cmd == "promote" and len(rest) == 2:
        cmd_promote(rest[0], rest[1])
    elif cmd == "audience" and len(rest) == 5:
        cmd_audience(*rest)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()

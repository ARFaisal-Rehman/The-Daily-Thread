"""Headlines archive and brand mentions.

Each refresh merges the latest feed items with the archive from the previous snapshot, so the
record grows beyond the 10 to 100 items a feed shows at once. A brand is mentioned when its name
appears in a headline as a whole word, ignoring case and accents (Chloe = Chloé), unless the
headline contains one of the brand's exclusions (Celine Dion is not Celine). Matching is by name,
so a headline can still be about something else with the same name; the page shows the headlines
so readers can judge.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta
from typing import Dict, List


def _plain(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def merge_items(old: List[Dict], new: List[Dict], today: str, keep_days: int = 90) -> List[Dict]:
    """Union by link (new wins), newest first, without items older than keep_days."""
    cutoff = (date.fromisoformat(today) - timedelta(days=keep_days)).isoformat()
    by_link = {i["link"]: i for i in old}
    by_link.update({i["link"]: i for i in new})
    return sorted((i for i in by_link.values() if i["published"] >= cutoff),
                  key=lambda i: (i["published"], i["title"]), reverse=True)


def mentions(items: List[Dict], brands: List[Dict], today: str, days: int = 30) -> Dict[str, List[Dict]]:
    """Headlines from the last `days` days that name each brand, newest first; [] when none."""
    cutoff = (date.fromisoformat(today) - timedelta(days=days)).isoformat()
    recent = sorted((i for i in items if i["published"] >= cutoff), key=lambda i: i["published"], reverse=True)
    out = {}
    for b in brands:
        name = re.compile(rf"\b{re.escape(_plain(b['name']))}\b")
        skip = [_plain(x) for x in b.get("news_exclude", [])]
        out[b["slug"]] = [i for i in recent if name.search(_plain(i["title"]))
                          and not any(x in _plain(i["title"]) for x in skip)]
    return out

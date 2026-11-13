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
from typing import Dict, List, Optional


def _plain(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def merge_items(old: List[Dict], new: List[Dict], today: str, keep_days: int = 90) -> List[Dict]:
    """Union by link (new wins), newest first, without items older than keep_days."""
    cutoff = (date.fromisoformat(today) - timedelta(days=keep_days)).isoformat()
    by_link = {i["link"]: i for i in old}
    by_link.update({i["link"]: i for i in new})
    return sorted((i for i in by_link.values() if i["published"] >= cutoff),
                  key=lambda i: (i["published"], i["title"]), reverse=True)


def _matcher(names: List[str], exclude: List[str] = ()):
    """True when a headline names any of `names` as whole words (plural allowed), and none of `exclude`."""
    pats = [re.compile(r"\b" + re.escape(_plain(n)) + r"(s|es)?\b") for n in names]
    skip = [_plain(x) for x in exclude]
    return lambda title: (any(p.search(_plain(title)) for p in pats)
                          and not any(x in _plain(title) for x in skip))


def mentions(items: List[Dict], brands: List[Dict], today: str, days: int = 30) -> Dict[str, List[Dict]]:
    """Headlines from the last `days` days that name each brand, newest first; [] when none."""
    cutoff = (date.fromisoformat(today) - timedelta(days=days)).isoformat()
    recent = sorted((i for i in items if i["published"] >= cutoff), key=lambda i: i["published"], reverse=True)
    out = {}
    for b in brands:
        hit = _matcher([b["name"]], b.get("news_exclude", []))
        out[b["slug"]] = [i for i in recent if hit(i["title"])]
    return out


def _key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _plain(title)).strip()


def dedupe(items: List[Dict]) -> List[Dict]:
    """One entry per headline: the first copy is kept, other feeds that ran it go in also_in."""
    seen: Dict[str, Dict] = {}
    for i in items:
        k = _key(i["title"])
        if k in seen:
            if i["feed"] != seen[k]["feed"] and i["feed"] not in seen[k]["also_in"]:
                seen[k]["also_in"].append(i["feed"])
        else:
            seen[k] = {**i, "also_in": []}
    return list(seen.values())


def desk(items: List[Dict], tags: List[Dict], today: str, tag: Optional[str] = None,
         feed: Optional[str] = None, days: int = 30) -> Dict:
    """The news desk: deduplicated headlines grouped by day, each with its brand, group and term tags.

    tags: [{slug, name, kind ('brand' | 'group' | 'term'), names, exclude?}]. 'top' counts tagged
    headlines over the last `days` days, before any filter, so it describes the whole desk.
    """
    matchers = [(t, _matcher(t["names"], t.get("exclude", []))) for t in tags]
    stories = dedupe(sorted(items, key=lambda i: i["published"], reverse=True))
    for s in stories:
        s["tags"] = [{"slug": t["slug"], "name": t["name"], "kind": t["kind"]} for t, hit in matchers if hit(s["title"])]
    cutoff = (date.fromisoformat(today) - timedelta(days=days)).isoformat()
    counts: Dict[tuple, int] = {}
    for s in stories:
        if s["published"] >= cutoff:
            for t in s["tags"]:
                counts[(t["slug"], t["name"])] = counts.get((t["slug"], t["name"]), 0) + 1
    top = sorted(((slug, name, n) for (slug, name), n in counts.items()), key=lambda x: (-x[2], x[1]))[:10]
    shown = [s for s in stories if (not tag or any(t["slug"] == tag for t in s["tags"]))
             and (not feed or s["feed"] == feed or feed in s["also_in"])]
    grouped: Dict[str, List[Dict]] = {}
    for s in shown:
        grouped.setdefault(s["published"], []).append(s)
    return {"days": list(grouped.items()), "top": top, "count": len(stories), "shown": len(shown),
            "feeds": sorted({s["feed"] for s in stories}), "tag_names": {t["slug"]: t["name"] for t in tags}}

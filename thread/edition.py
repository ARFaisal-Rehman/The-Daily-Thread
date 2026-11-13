"""An edition: one published snapshot day, written up as a newspaper front page.

Everything comes from that day's snapshot, so an old edition shows what the site knew then.
Hand-entered facts (the Lyst ranking) live in current files rather than in snapshots, so an
edition only shows a fact entered on or before its own date.
"""
from __future__ import annotations

from typing import Dict, List, Optional


def build(day: str, items: List[Dict], brand_rows: List[Dict], lyst: Dict, stories: List[Dict],
          picks: int = 3, headlines: int = 6) -> Dict:
    solid = [i for i in items if not i["low_volume"] and i["yoy"] is not None]
    lead = max(solid, key=lambda x: x["yoy"], default=None)
    faller = min(solid, key=lambda x: x["yoy"], default=None)
    if faller is not None and lead is not None and faller["yoy"] >= 0:
        faller = None                                  # nothing is actually falling: don't invent a faller
    if lead is not None and lead["yoy"] <= 0:
        lead = None
    risers = sorted((i for i in solid if i is not lead and i["label"] in ("Rising", "Emerging")),
                    key=lambda x: x["yoy"], reverse=True)[:picks]
    labelled = [r for r in brand_rows if r["label"] is not None and r["yoy"] is not None]
    lyst_ok = bool(lyst) and lyst.get("retrieved", "9999") <= day
    return {
        "day": day, "lead": lead, "faller": faller, "risers": risers,
        "brands_up": sorted((r for r in labelled if r["yoy"] > 0), key=lambda r: r["yoy"], reverse=True)[:picks],
        "brands_down": sorted((r for r in labelled if r["yoy"] < 0), key=lambda r: r["yoy"])[:picks],
        "lyst": {"edition": lyst["edition"], "url": lyst["url"],
                 "top": sorted((r for r in brand_rows if r["lyst_rank"]), key=lambda r: r["lyst_rank"])[:picks]}
                if lyst_ok else None,
        "headlines": [s for s in stories if s["tags"]][:headlines],
        "stats": {"terms": len(items), "brands": len(labelled), "stories": len(stories)},
    }

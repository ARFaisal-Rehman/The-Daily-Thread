"""Build the page data from the newest snapshot: trend labels, sparklines and the colour story."""
from __future__ import annotations

import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from .colours import FAMILIES, nearest_family, palette_profile
from .snapshots import latest_published
from .trends import LABELS, classify, wiki_yoy, window_change

DATA = Path(__file__).resolve().parents[1] / "data"


def slug(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")


def sparkline(values: List[float], w: int = 120, h: int = 32) -> str:
    """SVG path for the values, scaled to a w x h box."""
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    step = w / max(1, len(values) - 1)
    pts = [f"{i * step:.1f},{h - (v - lo) / span * (h - 2) - 1:.1f}" for i, v in enumerate(values)]
    return "M" + " L".join(pts)


def season_now(today: date) -> str:
    """Pantone season id for a date: Sep-Feb is autumn/winter, Mar-Aug is spring/summer."""
    if today.month >= 9:
        return f"aw{today.year % 100}"
    if today.month <= 2:
        return f"aw{(today.year - 1) % 100}"
    return f"ss{today.year % 100}"


def _season_dates(sid: str, window: List[str]) -> tuple[str, str]:
    year = 2000 + int(sid[2:])
    start = f"{year}-{window[0]}"
    end = f"{year + (1 if sid.startswith('aw') else 0)}-{window[1]}"
    return start, end


class Radar:
    def __init__(self, snapshot: Path, terms_file: Path = DATA / "terms.json", palettes_file: Path = DATA / "palettes.json"):
        self.snapshot_path = snapshot
        self.snap = json.loads(snapshot.read_text(encoding="utf-8"))
        self.terms = json.loads(terms_file.read_text(encoding="utf-8"))["terms"]
        self.palettes = json.loads(palettes_file.read_text(encoding="utf-8"))
        self.as_of = snapshot.stem          # the day the snapshot was published
        self.items = self._items()
        ends = [s["dates"][-1] for s in self.snap["google"].values() if s.get("dates")]
        self.data_to = max(ends) if ends else self.as_of   # last complete week of search data
        self.missing = [t["term"] for t in self.terms if t["term"] not in self.snap["google"]]

    # ------------------------------------------------------------------ terms
    def _items(self) -> List[Dict]:
        out = []
        for t in self.terms:
            s = self.snap["google"].get(t["term"])
            if not s:
                continue
            sig = classify(s["values"])
            wiki = self.snap["wiki"].get(t.get("wiki", ""), None)
            w_yoy = wiki_yoy(wiki["months"], wiki["views"]) if wiki else None
            agrees = None
            if w_yoy is not None and sig.yoy is not None:
                agrees = (w_yoy > 0) == (sig.yoy > 0)
            out.append({**t, "slug": slug(t["term"]), **sig.as_dict(), "wiki_yoy": w_yoy, "wiki_agrees": agrees,
                        "spark": sparkline(s["values"][-104:]), "last_week": s["dates"][-1],
                        "collected_at": s.get("collected_at"), "carried_from": s.get("carried_from")})
        order = {name: i for i, name in enumerate(LABELS)}
        return sorted(out, key=lambda x: (order[x["label"]], -(x["yoy"] or 0)))

    def item(self, term_slug: str) -> Optional[Dict]:
        return next((i for i in self.items if i["slug"] == term_slug), None)

    def series(self, term: str) -> Dict:
        return self.snap["google"][term]

    def by_label(self) -> Dict[str, List[Dict]]:
        return {lab: [i for i in self.items if i["label"] == lab] for lab in LABELS}

    def categories(self) -> List[str]:
        return list(dict.fromkeys(t["category"] for t in self.terms))

    # ---------------------------------------------------------------- colours
    def season(self, sid: str) -> Optional[Dict]:
        return next((s for s in self.palettes["seasons"] if s["id"] == sid), None)

    def colour_story(self, today: Optional[date] = None) -> Dict:
        today = today or date.fromisoformat(self.data_to)
        now = season_now(today)
        kind, yy = now[:2], int(now[2:])
        last = f"{'ss' if kind == 'aw' else 'aw'}{yy if kind == 'aw' else yy - 1}"
        year_ago = f"{kind}{yy - 1}"
        nxt = f"{'ss' if kind == 'aw' else 'aw'}{yy + 1 if kind == 'aw' else yy}"

        def colours_for(sid: str) -> Optional[Dict]:
            s = self.season(sid)
            if not s:
                return None
            start, end = _season_dates(sid, s["window"])
            rows = []
            for c in s["colours"]:
                fam, de = nearest_family(c["hex"])
                series = self.snap["colours"].get(fam)
                ch = None
                if series:
                    last_date = series["dates"][-1]
                    ch = window_change(series["dates"], series["values"], start, min(end, last_date))
                rows.append({**c, "family": fam, "family_hex": FAMILIES[fam], "delta_e": de, "interest": ch})
            return {**s, "start": start, "end": end, "rows": rows, "profile": palette_profile(s["colours"])}

        story = {"now": colours_for(now), "last": colours_for(last), "year_ago": colours_for(year_ago),
                 "next": colours_for(nxt)}
        story["timeline"] = [colours_for(s["id"]) for s in self.palettes["seasons"]]
        story["carried"] = self._carried(story["last"], story["now"])
        story["movers"] = self._movers(story["now"])
        story["shift"] = self._shift(story["year_ago"], story["now"])
        return story

    @staticmethod
    def _movers(season: Optional[Dict]) -> List[Dict]:
        """One row per colour word with a measured change, biggest gain first."""
        if not season:
            return []
        seen, out = set(), []
        for r in season["rows"]:
            if r["family"] in seen or not r["interest"] or r["interest"]["change"] is None:
                continue
            seen.add(r["family"])
            out.append(r)
        return sorted(out, key=lambda r: -r["interest"]["change"])

    @staticmethod
    def _shift(before: Optional[Dict], after: Optional[Dict]) -> Optional[Dict]:
        """How this season's palette differs from the same season a year earlier."""
        if not before or not after:
            return None
        a, b = before["profile"], after["profile"]
        return {"from": before["label"], **{k: round(b[k] - a[k], 3) for k in a}}

    @staticmethod
    def _carried(last: Optional[Dict], now: Optional[Dict]) -> Dict[str, List[str]]:
        """Colour words that stayed, arrived or left between last season and this one."""
        if not last or not now:
            return {"stayed": [], "new": [], "gone": []}
        a = {r["family"] for r in last["rows"]}
        b = {r["family"] for r in now["rows"]}
        return {"stayed": sorted(a & b), "new": sorted(b - a), "gone": sorted(a - b)}


@lru_cache(maxsize=4)
def _load(path: str, mtime: float) -> Radar:
    return Radar(Path(path))


def get_radar(folder: Path = DATA / "snapshots") -> Optional[Radar]:
    snap = latest_published(folder)
    if snap is None:
        return None
    return _load(str(snap), snap.stat().st_mtime)

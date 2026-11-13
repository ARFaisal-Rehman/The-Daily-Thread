"""Brand Watch: attention signals for fashion brands, with company money kept separate and scoped.

data/brands.json is the registry (brand, Google Trends topic id, Wikipedia article, owning group).
data/brand_facts.json holds hand-entered facts with sources: the Lyst Index ranking and figures
from company releases. load() validates both and refuses to run on a broken file.

Rules this module keeps:
  - missing is missing: a brand with no series has label None, not "Stable"; an unranked brand has
    lyst_rank None, not 0; a private company has no figures, and none are estimated.
  - group, segment and brand figures are different things and always carry their scope. A group's
    growth is never shown as a brand's growth.
"""
from __future__ import annotations

import json
import re
from statistics import median
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .news import mentions
from .radar import sparkline
from .trends import assess, wiki_yoy

DATA = Path(__file__).resolve().parents[1] / "data"
SCOPES = {"group", "segment", "brand"}
GROWTH_KINDS = {"reported", "organic", "comparable", "constant_fx"}


@dataclass
class Brand:
    id: str
    name: str
    slug: str
    search: str
    search_title: str
    wiki: Optional[str]
    group: str
    news_exclude: List[str] = field(default_factory=list)
    search_hold: Optional[str] = None


@dataclass
class BrandData:
    brands: List[Brand]
    groups: Dict[str, Dict]
    lyst: Dict
    financials: List[Dict]

    def __post_init__(self):
        self.by_id = {b.id: b for b in self.brands}
        self.by_slug = {b.slug: b for b in self.brands}


def load(registry: Path = DATA / "brands.json", facts: Path = DATA / "brand_facts.json") -> BrandData:
    reg = json.loads(Path(registry).read_text(encoding="utf-8"))
    fx = json.loads(Path(facts).read_text(encoding="utf-8"))
    groups = {g["id"]: g for g in reg["groups"]}
    problems: List[str] = []
    brands, seen = [], {"id": set(), "slug": set(), "search": set()}
    for entry in reg["brands"]:
        b = Brand(**entry)
        where = f"brand {b.id} ({b.name})"
        for key in seen:
            if getattr(b, key) in seen[key]:
                problems.append(f"{where}: duplicate {key}")
            seen[key].add(getattr(b, key))
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", b.slug):
            problems.append(f"{where}: slug must be lower-case words joined by hyphens")
        if b.group not in groups:
            problems.append(f"{where}: unknown group {b.group}")
        brands.append(b)

    ids = {b.id for b in brands}
    lyst = sorted(fx.get("lyst", []), key=lambda e: e["edition"])[-1] if fx.get("lyst") else {}
    for edition in fx.get("lyst", []):
        for r in edition["ranks"]:
            if r["brand"] not in ids:
                problems.append(f"Lyst {edition['edition']} rank {r['rank']}: unknown brand {r['brand']}")
    for i, f in enumerate(fx.get("financials", [])):
        where = f"financial figure {i} ({f.get('label')})"
        if f.get("scope") not in SCOPES:
            problems.append(f"{where}: scope must be one of {sorted(SCOPES)}")
        if f.get("scope") == "brand" and f.get("brand") not in ids:
            problems.append(f"{where}: brand-scope figures need a brand from the registry")
        if f.get("group") not in groups:
            problems.append(f"{where}: unknown group {f.get('group')}")
        if not str(f.get("source", "")).startswith("https://"):
            problems.append(f"{where}: every figure needs an https source")
        growth = f.get("growth") or {}
        if not growth or set(growth) - GROWTH_KINDS:
            problems.append(f"{where}: growth needs at least one of {sorted(GROWTH_KINDS)} and nothing else")
    if problems:
        raise ValueError("Brand Watch data is invalid:\n  " + "\n  ".join(problems))
    return BrandData(brands, groups, lyst, fx.get("financials", []))


def level_break(values: List[float], ratio: float = 2.5) -> Optional[str]:
    """Why a search series can't be trusted, or None.

    Google sometimes remaps a topic to a different entity, which shows up as a sudden permanent
    jump or drop. Compare each 13-week mean with the one before it; a change of 2.5 times or more
    is a break unless the same jump happens a year earlier or later (a season, like coats in
    winter). Real overnight surges are also caught; that is the safe side to err on.
    """
    if sum(1 for v in values if v > 0) < len(values) / 2:
        return "no search data for most of the five years"
    q = [sum(values[i - 13:i]) / 13 for i in range(len(values), 12, -13)][::-1]
    step = [max(b, 1) / max(a, 1) for a, b in zip(q, q[1:])]
    for i, r in enumerate(step):
        if 1 / ratio < r < ratio:
            continue
        same_season = [step[j] for j in (i - 4, i + 4) if 0 <= j < len(step)]
        if any((s >= ratio ** 0.5) if r > 1 else (s <= ratio ** -0.5) for s in same_season):
            continue
        return f"search level {'jumped' if r > 1 else 'dropped'} {max(r, 1 / r):.1f} times between two quarters"
    return None


class BrandWatch:
    def __init__(self, snapshot: Dict, data: Optional[BrandData] = None, today: Optional[str] = None,
                 news_days: int = 30):
        self.data = data or load()
        self.snap = snapshot
        self.ranks = {r["brand"]: r for r in self.data.lyst.get("ranks", [])}
        self.news_days = news_days
        feeds = snapshot.get("news", {})
        items = [i for f in feeds.values() for i in f.get("items", [])]
        day = today or (snapshot.get("fetched") or "")[:10] or None
        self.news = (mentions(items, [{"slug": b.slug, "name": b.name, "news_exclude": b.news_exclude}
                                      for b in self.data.brands], today=day, days=news_days)
                     if feeds and day else None)          # None: no archive yet, so counts are unknown
        self._rows = {b.slug: self._row(b) for b in self.data.brands}
        wiki = sorted(r["wiki_yoy"] for r in self._rows.values() if r["wiki_yoy"] is not None)
        self.wiki_median = median(wiki) if wiki else None   # context: is everyone down, or just this brand?

    def _row(self, b: Brand) -> Dict:
        s = self.snap.get("brands", {}).get(b.search)
        problem = (b.search_hold or level_break(s["values"])) if s else None
        sig = assess(s["values"]) if s and not problem else None
        wiki = self.snap.get("wiki", {}).get(b.wiki or "")
        rank = self.ranks.get(b.id)
        return {"id": b.id, "name": b.name, "slug": b.slug, "group": b.group,
                "group_name": self.data.groups[b.group]["name"],
                "label": sig.label if sig else None, "yoy": sig.yoy if sig else None,
                "confidence": sig.confidence if sig else None, "low_volume": sig.low_volume if sig else None,
                "spark": sparkline(s["values"][-104:]) if s else "",
                "wiki_yoy": wiki_yoy(wiki["months"], wiki["views"]) if wiki else None,
                "lyst_rank": rank["rank"] if rank else None, "lyst_move": rank["move"] if rank else None,
                "collected_at": s.get("collected_at") if s else None,
                "carried_from": s.get("carried_from") if s else None,
                "unreliable": problem,
                "news_count": len(self.news[b.slug]) if self.news is not None else None,
                "headlines": self.news[b.slug][:3] if self.news is not None else []}

    def row(self, slug: str) -> Optional[Dict]:
        return self._rows.get(slug)

    def rows(self) -> List[Dict]:
        return sorted(self._rows.values(),
                      key=lambda r: (r["lyst_rank"] is None, r["lyst_rank"] or 0, r["name"]))

    def financials_for(self, slug: str) -> List[Dict]:
        """The brand's own figures plus its owner's group and segment figures, each with its scope."""
        b = self.data.by_slug[slug]
        return [f for f in self.data.financials
                if (f["scope"] == "brand" and f.get("brand") == b.id)
                or (f["scope"] != "brand" and f["group"] == b.group)]

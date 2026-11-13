"""The Fashion Dictionary: canonical terms with stable ids, aliases, definitions and a category tree.

data/dictionary.json is the source of truth. It is curated by hand and kept in git so every edit is
reviewable; load() validates it and refuses to run on a broken file. Each term's 'query' is the
Google Trends search phrase and the key its series is stored under in a snapshot, so renaming a
term's display name never breaks its history.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

PATH = Path(__file__).resolve().parents[1] / "data" / "dictionary.json"
STATUSES = {"proposed", "active", "deprecated", "merged"}


def norm(text: str) -> str:
    """Lower-case, hyphens as spaces, single spaces: 'Barrel-Leg  Jeans' -> 'barrel leg jeans'."""
    return re.sub(r"\s+", " ", re.sub(r"[-_]", " ", text.lower())).strip()


@dataclass
class Term:
    id: str
    name: str
    slug: str
    query: str
    category: str
    definition: str
    aliases: List[str] = field(default_factory=list)
    related: List[str] = field(default_factory=list)
    notes: str = ""
    status: str = "active"
    added: str = ""
    language: str = "en"
    region: str = "worldwide"
    verified: bool = False
    wiki: Optional[str] = None
    merged_into: Optional[str] = None
    sources: List[Dict] = field(default_factory=list)


class Dictionary:
    def __init__(self, categories: Dict[str, Dict], terms: List[Term]):
        self.categories = categories
        self.terms = terms
        self.by_id = {t.id: t for t in terms}
        self.by_slug = {t.slug: t for t in terms}
        self._names = {}
        for t in terms:
            for n in [t.name, t.query, *t.aliases]:
                self._names.setdefault(norm(n), t)

    def path(self, category: str) -> List[str]:
        out, cur = [], category
        while cur:
            out.append(self.categories[cur]["name"])
            cur = self.categories[cur].get("parent")
        return out[::-1]

    def section(self, category: str) -> str:
        """Top-level category name, used for the front-page filter."""
        return self.path(category)[0]

    def find(self, text: str) -> Optional[Term]:
        return self._names.get(norm(text))

    def search(self, text: str) -> List[Term]:
        q = norm(text)
        return [t for t in self.terms if q and any(q in norm(n) for n in [t.name, *t.aliases])]

    def children(self, category: Optional[str]) -> List[str]:
        return [cid for cid, c in self.categories.items() if c.get("parent") == category]

    def tracked(self) -> List[Dict]:
        """Active terms in the shape the radar and refresh use (term = snapshot key)."""
        return [{"id": t.id, "term": t.query, "name": t.name, "slug": t.slug, "category": self.section(t.category),
                 "category_id": t.category, "wiki": t.wiki} for t in self.terms if t.status == "active"]


def load(path: Path = PATH) -> Dictionary:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    defaults = raw.get("defaults", {})
    categories = {c["id"]: c for c in raw["categories"]}
    problems: List[str] = []
    for c in raw["categories"]:
        if c.get("parent") and c["parent"] not in categories:
            problems.append(f"category {c['id']}: unknown parent {c['parent']}")

    terms, seen_ids, seen_slugs, seen_names = [], set(), set(), {}
    for entry in raw["terms"]:
        t = Term(**{**defaults, **entry})
        where = f"term {t.id} ({t.name})"
        if t.id in seen_ids:
            problems.append(f"{where}: duplicate id")
        if t.slug in seen_slugs:
            problems.append(f"{where}: duplicate slug {t.slug}")
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", t.slug):
            problems.append(f"{where}: slug must be lower-case words joined by hyphens")
        if t.category not in categories:
            problems.append(f"{where}: unknown category {t.category}")
        if t.status not in STATUSES:
            problems.append(f"{where}: status must be one of {sorted(STATUSES)}")
        if t.status == "merged" and not t.merged_into:
            problems.append(f"{where}: merged terms need merged_into")
        if t.status == "active" and not t.definition.strip():
            problems.append(f"{where}: active terms need a definition")
        if t.id not in seen_ids:                      # a duplicate entry is already reported above
            for n in {norm(x) for x in [t.name, t.query, *t.aliases]}:
                owner = seen_names.setdefault(n, t.id)
                if owner != t.id:
                    problems.append(f"{where}: name or alias '{n}' already belongs to {owner}")
        seen_ids.add(t.id)
        seen_slugs.add(t.slug)
        terms.append(t)

    ids = {t.id for t in terms}
    for t in terms:
        for r in t.related + ([t.merged_into] if t.merged_into else []):
            if r not in ids:
                problems.append(f"term {t.id} ({t.name}): unknown related or merged term {r}")
    if problems:
        raise ValueError("Fashion Dictionary is invalid:\n  " + "\n  ".join(problems))
    return Dictionary(categories, terms)

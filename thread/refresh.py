"""One refresh run: fetch every tracked series into today's draft, then publish.

Kept separate from scripts/refresh_trends.py so it can be tested with fake providers.
The draft carries a "run" manifest: when it started and finished, how many series were
attempted and fetched, and why each failure happened.
"""
from __future__ import annotations

import random
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List

import json

from .news import merge_items
from .providers import google_trends, rss, wikipedia
from .snapshots import latest_published, load_draft, publish, save_draft
from .trends import METHODOLOGY_VERSION


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="minutes")


def run(folder: Path, terms: List[Dict], families: Iterable[str], brands: List[Dict] = (),
        feeds: Dict[str, str] | None = None, news: Callable = rss.fetch, google: Callable = google_trends.fetch,
        wiki: Callable = wikipedia.fetch, today: str | None = None, pause: float = 3.0,
        publish_at_end: bool = True, log: Callable[[str], None] = print) -> Dict:
    today = today or date.today().isoformat()
    snap = load_draft(folder, today)
    meta = snap.setdefault("run", {"started": _now(), "methodology_version": METHODOLOGY_VERSION,
                                   "attempted": 0, "ok": 0, "failed": {}})

    jobs = ([("google", t["term"], t["term"], google, google_trends.SOURCE) for t in terms]
            + [("colours", f, f"{f} outfit", google, google_trends.SOURCE) for f in families]
            + [("wiki", t["wiki"], t["wiki"], wiki, wikipedia.SOURCE) for t in terms if t.get("wiki")]
            + [("brands", b["topic"], b["topic"], google, google_trends.SOURCE) for b in brands]
            + [("wiki", b["wiki"], b["wiki"], wiki, wikipedia.SOURCE) for b in brands if b.get("wiki")]
            + [("news", name, url, lambda u, n=name: news(n, u), rss.SOURCE) for name, url in (feeds or {}).items()])
    prev_path = latest_published(folder)
    prev = json.loads(prev_path.read_text(encoding="utf-8")) if prev_path else {}
    prev_news = prev.get("news", {})
    done_today = {(b, k) for b in ("google", "colours", "wiki", "brands", "news")
                  for k, v in prev.get(b, {}).items() if v.get("collected_at") == today}
    for bucket, key, query, fn, source in jobs:
        if key in snap.setdefault(bucket, {}) or (bucket, key) in done_today:
            continue                                  # fetched earlier today: resume, don't repeat
        log(f"{bucket}: {query}")
        res = fn(query)
        meta["attempted"] += 1
        tag = f"{bucket}:{key}"
        if res.status == "ok":
            series = res.series
            if bucket == "news":                      # keep the archive growing across refreshes
                series = {"items": merge_items(prev_news.get(key, {}).get("items", []), res.series["items"], today)}
            snap[bucket][key] = {**series, **res.params, "source": source, "collected_at": today}
            meta["ok"] += 1
            meta["failed"].pop(tag, None)
        else:
            meta["failed"][tag] = f"{res.status}: {res.detail}".rstrip(": ")
            log(f"  {meta['failed'][tag]}")
        snap["fetched"] = _now()
        save_draft(folder, today, snap)
        if pause and source == google_trends.SOURCE:
            time.sleep(random.uniform(pause, pause * 2))
        elif pause and source == wikipedia.SOURCE:
            time.sleep(1.0)                           # Wikimedia answers 429 to back-to-back requests

    meta["finished"] = _now()
    save_draft(folder, today, snap)
    if not publish_at_end:
        return {"day": today, "published": False, "run": meta}
    report = publish(folder, today, snap)
    return {**report, "published": True, "run": meta}

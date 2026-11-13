"""Draft and published trend snapshots.

A refresh writes to data/snapshots/drafts/<day>.json while it runs. Only publish() writes
data/snapshots/<day>.json, which is what the site reads. publish() merges the draft with the
latest published snapshot: anything the refresh failed to fetch is carried forward and marked
with the date it came from, so a blocked or half-finished refresh never makes the site worse.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

BUCKETS = ("google", "colours", "wiki")


def draft_path(folder: Path, day: str) -> Path:
    return Path(folder) / "drafts" / f"{day}.json"


def latest_published(folder: Path) -> Optional[Path]:
    files = sorted(Path(folder).glob("*.json"))  # non-recursive: drafts/ is never included
    return files[-1] if files else None


def empty_snapshot() -> Dict:
    return {"fetched": None, "geo": "worldwide", **{b: {} for b in BUCKETS}}


def load_draft(folder: Path, day: str) -> Dict:
    p = draft_path(folder, day)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else empty_snapshot()


def save_draft(folder: Path, day: str, snap: Dict) -> None:
    p = draft_path(folder, day)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(snap, separators=(",", ":")), encoding="utf-8")


def publish(folder: Path, day: str, draft: Dict) -> Dict:
    """Merge the draft over the latest published snapshot, write <day>.json, delete the draft."""
    folder = Path(folder)
    prev_path = latest_published(folder)
    prev = json.loads(prev_path.read_text(encoding="utf-8")) if prev_path else empty_snapshot()
    prev_day = prev_path.stem if prev_path else None
    prev_fetched = (prev.get("fetched") or prev_day or "")[:10]

    out = {**prev, **{k: v for k, v in draft.items() if k not in BUCKETS}}
    fresh = carried = 0
    for bucket in BUCKETS:
        merged = {}
        for key, s in prev.get(bucket, {}).items():
            s = {**s, "collected_at": s.get("collected_at") or prev_fetched}
            if prev_day != day and "carried_from" not in s:
                s["carried_from"] = prev_day     # first time it is carried: remember where from
            merged[key] = s
        for key, s in draft.get(bucket, {}).items():
            merged[key] = {k: v for k, v in s.items() if k != "carried_from"}
        out[bucket] = merged
        fresh += len(draft.get(bucket, {}))
        carried += sum(1 for k in merged if k not in draft.get(bucket, {}) and "carried_from" in merged[k])

    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{day}.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    draft_path(folder, day).unlink(missing_ok=True)
    return {"day": day, "fresh": fresh, "carried": carried, "previous": prev_day}

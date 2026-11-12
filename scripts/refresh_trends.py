"""Fetch fresh trend data and save it as data/snapshots/<today>.json.

Run weekly:  python scripts/refresh_trends.py
Resumable: terms already in today's snapshot are skipped, so a rate-limited run can be re-run.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from thread.colours import nearest_family  # noqa: E402
from thread.sources import google_series, wiki_monthly  # noqa: E402

DATA = ROOT / "data"
PAUSE = float(os.environ.get("TRENDS_PAUSE", 3))  # seconds between Google queries; raise it if rate-limited


def main() -> None:
    terms = json.loads((DATA / "terms.json").read_text(encoding="utf-8"))["terms"]
    palettes = json.loads((DATA / "palettes.json").read_text(encoding="utf-8"))
    families = sorted({nearest_family(c["hex"])[0] for s in palettes["seasons"] for c in s["colours"]})

    out_path = DATA / "snapshots" / f"{date.today().isoformat()}.json"
    snap = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {
        "fetched": None, "geo": "worldwide", "google": {}, "colours": {}, "wiki": {}}

    def save() -> None:
        snap["fetched"] = datetime.now(timezone.utc).isoformat(timespec="minutes")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(snap, separators=(",", ":")), encoding="utf-8")

    jobs = [("google", t["term"], t["term"]) for t in terms] + [("colours", f, f"{f} outfit") for f in families]
    for bucket, key, query in jobs:
        if key in snap[bucket]:
            continue
        print(f"{bucket}: {query}")
        series = google_series(query)
        if series is None:
            print("  no data")
            continue
        snap[bucket][key] = series
        save()
        time.sleep(random.uniform(PAUSE, PAUSE * 2))

    for t in terms:
        art = t.get("wiki")
        if art and art not in snap["wiki"]:
            w = wiki_monthly(art)
            if w:
                snap["wiki"][art] = w
    save()
    missing = [t["term"] for t in terms if t["term"] not in snap["google"]]
    print(f"saved {out_path.name}: {len(snap['google'])} terms, {len(snap['colours'])} colour words, "
          f"{len(snap['wiki'])} wiki articles; missing {missing}")


if __name__ == "__main__":
    main()

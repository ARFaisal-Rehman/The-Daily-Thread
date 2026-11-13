"""Fetch fresh trend data and publish it as data/snapshots/<today>.json.

Run weekly:  python scripts/refresh_trends.py
While it runs, results go to data/snapshots/drafts/<today>.json (resumable: an interrupted run
picks up where it stopped). At the end the draft is published, merged with the last good
snapshot, so anything Google refused this time is carried forward and marked as older data.
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
from thread.snapshots import load_draft, publish, save_draft  # noqa: E402
from thread.sources import google_series, wiki_monthly  # noqa: E402

DATA = ROOT / "data"
PAUSE = float(os.environ.get("TRENDS_PAUSE", 3))  # seconds between Google queries; raise it if rate-limited


def main() -> None:
    terms = json.loads((DATA / "terms.json").read_text(encoding="utf-8"))["terms"]
    palettes = json.loads((DATA / "palettes.json").read_text(encoding="utf-8"))
    families = sorted({nearest_family(c["hex"])[0] for s in palettes["seasons"] for c in s["colours"]})

    folder, today = DATA / "snapshots", date.today().isoformat()
    snap = load_draft(folder, today)    # resume today's unfinished run, if any

    def save() -> None:
        snap["fetched"] = datetime.now(timezone.utc).isoformat(timespec="minutes")
        save_draft(folder, today, snap)

    jobs = [("google", t["term"], t["term"]) for t in terms] + [("colours", f, f"{f} outfit") for f in families]
    for bucket, key, query in jobs:
        if key in snap[bucket]:
            continue
        print(f"{bucket}: {query}")
        series = google_series(query)
        if series is None:
            print("  no data")
            continue
        snap[bucket][key] = {**series, "collected_at": today}
        save()
        time.sleep(random.uniform(PAUSE, PAUSE * 2))

    for t in terms:
        art = t.get("wiki")
        if art and art not in snap["wiki"]:
            w = wiki_monthly(art)
            if w:
                snap["wiki"][art] = {**w, "collected_at": today}
    save()
    report = publish(folder, today, snap)     # merge with the last good snapshot; misses are carried forward
    missing = [t["term"] for t in terms if t["term"] not in snap["google"]]
    print(f"published {today}.json: {report['fresh']} fresh series, {report['carried']} carried forward "
          f"from {report['previous']}; terms not fetched this run: {missing}")


if __name__ == "__main__":
    main()

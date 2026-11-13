"""Fetch fresh trend data and publish it as data/snapshots/<today>.json.

Run weekly:  python scripts/refresh_trends.py
While it runs, results go to data/snapshots/drafts/<today>.json (resumable: an interrupted run
picks up where it stopped). At the end the draft is published, merged with the last good
snapshot, so anything Google refused this time is carried forward and marked as older data.
The published snapshot includes a "run" manifest listing every failure and its reason.
All of the logic lives in thread/refresh.py so it can be tested without the network.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from thread.colours import nearest_family  # noqa: E402
from thread.refresh import run  # noqa: E402

DATA = ROOT / "data"
PAUSE = float(os.environ.get("TRENDS_PAUSE", 3))  # seconds between Google queries; raise it if rate-limited


def main() -> None:
    terms = json.loads((DATA / "terms.json").read_text(encoding="utf-8"))["terms"]
    palettes = json.loads((DATA / "palettes.json").read_text(encoding="utf-8"))
    families = sorted({nearest_family(c["hex"])[0] for s in palettes["seasons"] for c in s["colours"]})
    report = run(DATA / "snapshots", terms, families, pause=PAUSE)
    m = report["run"]
    print(f"\npublished {report['day']}.json: {m['ok']} of {m['attempted']} fetched this run, "
          f"{report['carried']} series carried forward from {report['previous']}")
    for tag, why in sorted(m["failed"].items()):
        print(f"  not fetched  {tag:32s} {why}")


if __name__ == "__main__":
    main()

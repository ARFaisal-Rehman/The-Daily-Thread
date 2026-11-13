"""Backtest the trend labels on the newest published snapshot; writes data/backtest.json.

Run after each refresh:  python scripts/backtest_labels.py
The How It Works page reads data/backtest.json. See thread/backtest.py for the method.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from thread.backtest import backtest  # noqa: E402
from thread.snapshots import latest_published  # noqa: E402

DATA = ROOT / "data"


def main() -> None:
    snap_path = latest_published(DATA / "snapshots")
    if snap_path is None:
        sys.exit("No published snapshot. Run scripts/refresh_trends.py first.")
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    res = backtest({term: s["values"] for term, s in snap["google"].items()})
    res.update({"snapshot": snap_path.stem, "generated": date.today().isoformat()})
    (DATA / "backtest.json").write_text(json.dumps(res, indent=1), encoding="utf-8")

    print(f"{res['terms']} terms, {res['observations']} label-weeks, horizon {res['horizon_weeks']} weeks")
    print(f"{'label':8s} {'n':>6s} {'up 12 wk later':>15s} {'median YoY then':>16s}")
    for lab, s in res["labels"].items():
        print(f"{lab:8s} {s['n']:6d} {s['still_up_share']:15.0%} {s['median_future_yoy']:+16.0%}")
    print(f"Rising -> still +25%: {res['rising_precision']:.0%} vs base rate {res['base_rate_rising']:.0%} "
          f"(lift {res['rising_lift']})")
    print(f"Fading/Out -> still -10%: {res['falling_precision']:.0%} vs base rate {res['base_rate_falling']:.0%} "
          f"(lift {res['falling_lift']})")
    print(f"Label changes week to week: {res['flip_rate']:.1%}")


if __name__ == "__main__":
    main()

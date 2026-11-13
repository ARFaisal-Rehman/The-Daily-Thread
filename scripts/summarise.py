"""Print the newest snapshot's results as Markdown tables (used for the README).

Run: python scripts/summarise.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thread.radar import get_radar  # noqa: E402


def pct(v):
    return "n/a" if v is None else f"{v:+.0%}"


def main() -> None:
    r = get_radar()
    if r is None:
        sys.exit("No snapshot. Run scripts/refresh_trends.py first.")
    print(f"Snapshot {r.as_of}: {len(r.items)} of {len(r.terms)} terms\n")
    counts = {lab: len(v) for lab, v in r.by_label().items()}
    print(" | ".join(f"{k}: {v}" for k, v in counts.items()), "\n")
    print("| Term | Label | Year on year | Share of 5-year high | Wikipedia YoY |\n|---|---|---|---|---|")
    for i in r.items:
        flag = " (low volume)" if i["low_volume"] else ""
        print(f"| {i['name']}{flag} | {i['label']} | {pct(i['yoy'])} | {i['vs_peak']:.0%} | {pct(i['wiki_yoy'])} |")
    with_wiki = [i for i in r.items if i["wiki_agrees"] is not None]
    if with_wiki:
        agree = sum(i["wiki_agrees"] for i in with_wiki)
        print(f"\nWikipedia direction agrees with Google for {agree} of {len(with_wiki)} terms with an article.")

    story = r.colour_story()
    for key in ("now", "last"):
        s = story[key]
        print(f"\n{s['label']} ({s['start']} to {s['end']}), colour word searches vs a year earlier")
        print("| Pantone colour | Hex | Reads as | Change |\n|---|---|---|---|")
        for row in s["rows"]:
            ch = row["interest"]["change"] if row["interest"] else None
            print(f"| {row['name']} | {row['hex']} | {row['family']} | {pct(ch)} |")
    print("\nPalette profiles")
    print("| Season | Lightness | Saturation | Warm | Cool | Neutral |\n|---|---|---|---|---|---|")
    for s in story["timeline"]:
        p = s["profile"]
        print(f"| {s['label']} | {p['lightness']:.2f} | {p['saturation']:.2f} | {p['warm']:.0%} | {p['cool']:.0%} | {p['neutral']:.0%} |")
    print("\nCarried over:", story["carried"])


if __name__ == "__main__":
    main()

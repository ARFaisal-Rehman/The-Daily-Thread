"""Build data/palettes.json from Pantone's public NYFW Fashion Color Trend Reports.

Stores facts only: colour name, Pantone TCX code, the hex value Pantone shows on its
chip, which group it belongs to (top 10 or seasonless core), and the source URL.
Run: python scripts/build_palettes.py
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parents[1] / "data" / "palettes.json"
BASE = "https://www.pantone.com/na/en-us"
SEASONS = [  # (id, label, season window used for search interest, url)
    ("aw25", "Autumn/Winter 2025/26", ("09-01", "02-28"), BASE + "/articles/fashion-color-trend-report/new-york-fashion-week-autumn-winter-2025-2026"),
    ("ss26", "Spring/Summer 2026", ("03-01", "08-31"), BASE + "/articles/fashion-color-trend-report/new-york-fashion-week-spring-summer-2026"),
    ("aw26", "Autumn/Winter 2026/27", ("09-01", "02-28"), BASE + "/articles/fashion-color-trend-report/new-york-fashion-week-autumn-winter-2026"),
    ("ss27", "Spring/Summer 2027", ("03-01", "08-31"), BASE + "/fashion-color-trend-report/new-york-fashion-week-spring-summer-2027"),
]
CHIP = re.compile(r'background-color:\s*(#[0-9A-Fa-f]{6}).{0,400}?(\d\d-\d{4}) TCX ([^<]+?)\s*</span', re.S)


def parse(page: str) -> list[dict]:
    # The page embeds its HTML as an escaped JSON string.
    page = page.replace("\\u003c", "<").replace("\\u003e", ">").replace('\\"', '"').replace("\\n", "\n")
    colours, seen = [], set()
    for sec in re.split(r'class="palette ', page)[1:]:
        group = "core" if not sec.startswith("top-ten") else "top10"
        for hx, code, name in CHIP.findall(sec.split('class="palette ')[0]):
            if code in seen:
                continue
            seen.add(code)
            colours.append({"name": name.strip(), "code": f"{code} TCX", "hex": hx.upper(), "group": group})
    if not colours:  # newer pages hold the chips in a script: var COLORS = {"top-ten": [...], ...}
        for key, body in re.findall(r'"(top-ten|seasonless-shades)"\s*:\s*\[(.*?)\]', page, re.S):
            for code, name, hx in re.findall(r'"code":\s*"([^"]+)",\s*"name":\s*"([^"]+)",\s*"hex":\s*"(#[0-9A-Fa-f]{6})"', body):
                colours.append({"name": name, "code": code, "hex": hx.upper(),
                                "group": "top10" if key == "top-ten" else "core"})
    return colours


def main() -> None:
    out = {"source": "Pantone Fashion Color Trend Report, New York Fashion Week (pantone.com)",
           "built": date.today().isoformat(), "seasons": []}
    for sid, label, window, url in SEASONS:
        page = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
        colours = parse(page)
        print(f"{sid}: {len(colours)} colours ({sum(c['group'] == 'top10' for c in colours)} top 10)")
        out["seasons"].append({"id": sid, "label": label, "window": window, "url": url, "colours": colours})
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()

"""Colour maths for the season palettes.

Pantone names ("Muted Clay", "Neptune Green") are not what people type into a search box, so each
Pantone colour is mapped to the nearest everyday colour word ("terracotta", "sage green") by
CIELAB distance (Delta E 1976). Search interest is then measured for "<word> outfit".
"""
from __future__ import annotations

import colorsys
import math
from typing import Dict, List, Tuple

# Everyday fashion colour words and a representative sRGB value for each.
FAMILIES: Dict[str, str] = {
    "burgundy": "#800020", "cherry red": "#B0122F", "red": "#D22630", "coral": "#FF7F50",
    "terracotta": "#C8644A", "rust": "#B7410E", "burnt orange": "#CC5500", "orange": "#F28C28",
    "mustard yellow": "#D4A017", "butter yellow": "#F3E5A0", "yellow": "#F4D03F",
    "olive green": "#6B6B2F", "khaki": "#B4A574", "sage green": "#A8B38A", "mint green": "#A8DCC1",
    "emerald green": "#1F8A5A", "forest green": "#2F4F3A", "lime green": "#9BC53D",
    "teal": "#167D7F", "turquoise": "#3AB5B0", "baby blue": "#A7C7E7", "sky blue": "#6CA0DC",
    "cobalt blue": "#0047AB", "peach": "#F0A586", "light grey": "#BEBEBE",
    "navy blue": "#1D2B4A", "lilac": "#C8A2C8", "lavender": "#B9A7D1", "plum": "#6A3B5A",
    "fuchsia": "#C2185B", "hot pink": "#F0508A", "baby pink": "#F4C2C2", "dusty pink": "#C99A9E",
    "mauve": "#A57E8C", "chocolate brown": "#5A3A2E", "brown": "#7B4A2D", "camel": "#B88A5A",
    "beige": "#D9C7A8", "cream": "#F2EBDD", "grey": "#8E8C88", "charcoal": "#3B3D40",
    "black": "#151515", "white": "#F7F7F5",
}


def hex_to_rgb(h: str) -> Tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def hex_to_lab(h: str) -> Tuple[float, float, float]:
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in hex_to_rgb(h))
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(a: str, b: str) -> float:
    return math.dist(hex_to_lab(a), hex_to_lab(b))


def nearest_family(h: str) -> Tuple[str, float]:
    name = min(FAMILIES, key=lambda n: delta_e(h, FAMILIES[n]))
    return name, round(delta_e(h, FAMILIES[name]), 1)


def describe(h: str) -> Dict[str, float]:
    """Hue (degrees), saturation and lightness (0-1), and whether the colour reads warm."""
    r, g, b = hex_to_rgb(h)
    hue, light, sat = colorsys.rgb_to_hls(r, g, b)
    hue_deg = hue * 360
    warm = sat > 0.12 and (hue_deg < 75 or hue_deg >= 330)
    return {"hue": round(hue_deg), "sat": round(sat, 3), "light": round(light, 3), "warm": warm}


def palette_profile(colours: List[dict]) -> Dict[str, float]:
    """Summary of a palette: mean lightness and saturation, and the share of warm, cool and neutral colours."""
    d = [describe(c["hex"]) for c in colours]
    n = len(d) or 1
    neutral = sum(x["sat"] <= 0.12 for x in d)
    warm = sum(x["warm"] for x in d)
    return {
        "lightness": round(sum(x["light"] for x in d) / n, 3),
        "saturation": round(sum(x["sat"] for x in d) / n, 3),
        "warm": round(warm / n, 3),
        "cool": round((n - warm - neutral) / n, 3),
        "neutral": round(neutral / n, 3),
    }

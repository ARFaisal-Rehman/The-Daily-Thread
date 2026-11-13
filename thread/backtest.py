"""Backtest of the trend labels: would last year's labels have told us anything about what came next?

For every term and every past week t with enough history, the label is computed from the data
known at t only (classify(values[:t])). The outcome is the year-on-year change 12 weeks later
(classify(values[:t + 12]).yoy). Using year-on-year for the outcome removes seasonality, which a
plain "next 12 weeks vs last 12 weeks" comparison would not.

Reported against base rates, because a label is only useful if it beats knowing nothing:
  rising_precision   share of Rising labels still up 25%+ year on year 12 weeks later
  base_rate_rising   the same share across all weeks, whatever their label
  rising_lift        precision / base rate (1.0 = no better than chance)
  falling_precision  share of Fading/Out labels still down 10%+ 12 weeks later, with its base rate
  flip_rate          share of weeks where a term's label changed from the previous week

Caveats: weekly observations of one term overlap heavily, so they are not independent; and the
term list was chosen in 2026 with hindsight, which inflates how often terms look like they rise.
"""
from __future__ import annotations

from statistics import median
from typing import Dict, List, Optional, Sequence

from .trends import FADING, LABELS, METHODOLOGY_VERSION, RISING, WINDOW, YEAR, classify

MIN_HISTORY = WINDOW + YEAR      # weeks needed before a year-on-year label exists


def _share(xs: List[bool]) -> Optional[float]:
    return round(sum(xs) / len(xs), 3) if xs else None


def backtest(series: Dict[str, Sequence[float]], horizon: int = 12) -> Dict:
    obs = []                              # (label, future_yoy)
    flips = steps = 0
    used, skipped = 0, []
    for term, values in series.items():
        n = len(values)
        if n < MIN_HISTORY + horizon:
            skipped.append(term)
            continue
        used += 1
        signals = {t: classify(values[:t]) for t in range(MIN_HISTORY, n + 1)}
        prev = None
        for t in range(MIN_HISTORY, n + 1):
            lab = signals[t].label
            if prev is not None:
                steps += 1
                flips += lab != prev
            prev = lab
            if t + horizon <= n and signals[t].yoy is not None and signals[t + horizon].yoy is not None:
                obs.append((lab, signals[t + horizon].yoy))

    futures = [f for _, f in obs]
    labels = {}
    for lab in [lb for lb in LABELS if any(o[0] == lb for o in obs)]:     # site order: Rising ... Out
        fs = [f for lb, f in obs if lb == lab]
        labels[lab] = {"n": len(fs), "still_up_share": _share([f > 0 for f in fs]),
                       "median_future_yoy": round(median(fs), 3)}

    rising = [f >= RISING for lb, f in obs if lb == "Rising"]
    falling = [f <= FADING for lb, f in obs if lb in ("Fading", "Out")]
    res = {
        "methodology_version": METHODOLOGY_VERSION, "horizon_weeks": horizon, "terms": used,
        "skipped": skipped, "observations": len(obs), "labels": labels,
        "base_rate_up": _share([f > 0 for f in futures]),
        "rising_precision": _share(rising), "base_rate_rising": _share([f >= RISING for f in futures]),
        "falling_precision": _share(falling), "base_rate_falling": _share([f <= FADING for f in futures]),
        "flip_rate": round(flips / steps, 3) if steps else 0.0,
    }
    for kind in ("rising", "falling"):
        p, b = res[f"{kind}_precision"], res[f"base_rate_{kind}"]
        res[f"{kind}_lift"] = round(p / b, 2) if p is not None and b else None
    return res

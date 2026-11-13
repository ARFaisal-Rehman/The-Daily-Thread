"""Backtest of the trend labels: would past labels have told us anything about what came next?

For every term and every past week t with enough history, the label is computed from the data
known at t only (classify(values[:t])). The outcome is the year-on-year change 12 weeks later
(classify(values[:t + 12]).yoy). Using year-on-year for the outcome removes seasonality, which a
plain "next 12 weeks vs last 12 weeks" comparison would not.

Reported against base rates, because a label is only useful if it beats knowing nothing:
  rising_precision   share of Rising labels still up 25%+ year on year 12 weeks later
  base_rate_rising   the same share across all weeks, whatever their label
  falling_precision  share of Fading/Out labels still down 10%+ 12 weeks later, with its base rate
  emerging           share of Emerging labels that reached Rising strength (+25%) 12 weeks later,
                     against the same share for every week not already Rising
  confidence         for Rising and for Fading/Out: hit rates of "High" (held 4+ weeks and a strong
                     move, not low volume) vs "Lower"
  flip_rate          share of weeks where a term's label changed from the previous week
  holdout            the same figures for weeks on or after `split` only (pass dates to get it):
                     the Emerging and confidence rules were chosen on earlier data, so this is
                     the out-of-sample check

Caveats: weekly observations of one term overlap heavily, so they are not independent; and the
term list was chosen in 2026 with hindsight, which inflates how often terms look like they rise.
"""
from __future__ import annotations

from statistics import median
from typing import Dict, List, Optional, Sequence

from .trends import (FADING, HELD_WEEKS, LABELS, METHODOLOGY_VERSION, RISING, STRONG_FALL, STRONG_RISE, WINDOW,
                     YEAR, classify)

MIN_HISTORY = WINDOW + YEAR      # weeks needed before a year-on-year label exists


def _share(xs: List[bool]) -> Optional[float]:
    return round(sum(xs) / len(xs), 3) if xs else None


def _lift(p: Optional[float], b: Optional[float]) -> Optional[float]:
    return round(p / b, 2) if p is not None and b else None


def _summarise(obs: List[Dict]) -> Dict:
    futures = [o["fut"] for o in obs]
    labels = {}
    for lab in [lb for lb in LABELS if any(o["label"] == lb for o in obs)]:     # site order
        fs = [o["fut"] for o in obs if o["label"] == lab]
        labels[lab] = {"n": len(fs), "still_up_share": _share([f > 0 for f in fs]),
                       "median_future_yoy": round(median(fs), 3)}

    res = {"observations": len(obs), "labels": labels, "base_rate_up": _share([f > 0 for f in futures]),
           "rising_precision": _share([o["fut"] >= RISING for o in obs if o["label"] == "Rising"]),
           "base_rate_rising": _share([f >= RISING for f in futures]),
           "falling_precision": _share([o["fut"] <= FADING for o in obs if o["label"] in ("Fading", "Out")]),
           "base_rate_falling": _share([f <= FADING for f in futures])}
    res["rising_lift"] = _lift(res["rising_precision"], res["base_rate_rising"])
    res["falling_lift"] = _lift(res["falling_precision"], res["base_rate_falling"])

    emerging = [o["fut"] >= RISING for o in obs if o["label"] == "Emerging"]
    not_rising = [o["fut"] >= RISING for o in obs if o["label"] != "Rising"]
    res["emerging"] = {"n": len(emerging), "hit_share": _share(emerging), "base_rate": _share(not_rising),
                       "lift": _lift(_share(emerging), _share(not_rising))}

    res["confidence"] = {}
    for group, members, strong, hit in [
            ("Rising", {"Rising"}, lambda o: o["yoy"] >= STRONG_RISE, lambda o: o["fut"] >= RISING),
            ("Falling", {"Fading", "Out"}, lambda o: o["yoy"] <= STRONG_FALL, lambda o: o["fut"] <= FADING)]:
        tiers: Dict[str, List[bool]] = {}
        for o in obs:
            if o["label"] in members:
                tier = "High" if o["held"] >= HELD_WEEKS and strong(o) and not o["low"] else "Lower"
                tiers.setdefault(tier, []).append(hit(o))
        res["confidence"][group] = {t: {"n": len(v), "hit_share": _share(v)} for t, v in tiers.items()}
    return res


def backtest(series: Dict[str, Sequence[float]], horizon: int = 12,
             dates: Optional[Dict[str, Sequence[str]]] = None, split: str = "2025-01-01") -> Dict:
    obs: List[Dict] = []
    flips = steps = 0
    used, skipped = 0, []
    for term, values in series.items():
        n = len(values)
        if n < MIN_HISTORY + horizon:
            skipped.append(term)
            continue
        used += 1
        signals = {t: classify(values[:t]) for t in range(MIN_HISTORY, n + 1)}
        prev, run = None, 0
        for t in range(MIN_HISTORY, n + 1):
            s = signals[t]
            run = run + 1 if s.label == prev else 1
            if prev is not None:
                steps += 1
                flips += s.label != prev
            prev = s.label
            if t + horizon <= n and s.yoy is not None and signals[t + horizon].yoy is not None:
                obs.append({"label": s.label, "yoy": s.yoy, "held": run, "low": s.low_volume,
                            "fut": signals[t + horizon].yoy,
                            "date": dates[term][t - 1] if dates and term in dates else None})

    res = {"methodology_version": METHODOLOGY_VERSION, "horizon_weeks": horizon, "terms": used,
           "skipped": skipped, **_summarise(obs), "flip_rate": round(flips / steps, 3) if steps else 0.0}
    if dates:
        later = [o for o in obs if o["date"] and o["date"] >= split]
        res["holdout"] = {"from": split, **_summarise(later)}
    return res

"""Turn a weekly search-interest series into a trend label.

Signals (all computed on complete weeks only):
  recent   mean of the last 12 weeks
  prior    mean of the same 12 weeks one year earlier (52 weeks back), so seasonality cancels out
  yoy      (recent - prior) / prior
  momentum slope of a straight line through the last 12 weeks, as % of the recent mean per week
  vs_peak  recent / highest 12-week mean in the series (how close to its all-time high in the window)

Labels, checked in this order:
  Rising    yoy >= +25%
  Out       yoy <= -25% and vs_peak < 40%
  Fading    yoy <= -10%
  Emerging  yoy +10% to +25% and momentum above +2% a week (added in 1.1, see below)
  Peaking   vs_peak >= 80% (near its high and no longer growing fast)
  Stable    anything else
A term whose recent and prior means are both under 5 (on Google's 0-100 scale) is marked low volume.

Version 1.1 (13 Nov 2026), chosen by backtest (thread/backtest.py) on terms' own history:
  Emerging  picked on data before 2025, checked on 2025-26: 42% reached Rising strength within
            12 weeks vs a 25% base rate. Weaker than in-sample, as expected, but it held.
  Confidence (assess): "High" when a Rising/Fading/Out label has held 4+ weeks AND the move is
            strong (+50% / -25% or more); otherwise "Lower". High was the best tier in both periods;
            a finer scale did not hold out of sample, so it is two levels only. Low volume -> Lower.
  Rejected  hysteresis (sticky thresholds): fewer label changes, but lower accuracy.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import List, Optional, Sequence

import numpy as np

METHODOLOGY_VERSION = "1.1"   # bump whenever a rule or threshold below changes
WINDOW = 12
YEAR = 52
RISING, FADING, OUT_YOY, OUT_PEAK, PEAK = 0.25, -0.10, -0.25, 0.40, 0.80
EMERGING_YOY, EMERGING_MOMENTUM = 0.10, 0.02
STRONG_RISE, STRONG_FALL, HELD_WEEKS = 0.50, -0.25, 4
LABELS = ["Rising", "Emerging", "Peaking", "Stable", "Fading", "Out"]
CONFIDENCE_LABELS = {"Rising", "Fading", "Out"}       # the labels the backtest supports a confidence for


@dataclass
class TrendSignal:
    label: str
    yoy: Optional[float]
    momentum: float
    vs_peak: float
    recent: float
    prior: Optional[float]
    low_volume: bool

    def as_dict(self) -> dict:
        return asdict(self)


def _mean(x: Sequence[float]) -> float:
    return float(np.mean(x)) if len(x) else 0.0


def classify(values: Sequence[float], window: int = WINDOW) -> TrendSignal:
    v = np.asarray(values, dtype=float)
    if len(v) < window * 2:
        raise ValueError(f"need at least {window * 2} weeks, got {len(v)}")
    recent = _mean(v[-window:])
    prior = _mean(v[-window - YEAR:-YEAR]) if len(v) >= window + YEAR else None
    yoy = (recent - prior) / prior if prior else None

    slope = float(np.polyfit(np.arange(window), v[-window:], 1)[0])
    momentum = slope / recent if recent else 0.0

    rolling = np.convolve(v, np.ones(window) / window, mode="valid")
    vs_peak = recent / rolling.max() if rolling.max() > 0 else 0.0

    if yoy is not None and yoy >= RISING:
        label = "Rising"
    elif yoy is not None and yoy <= OUT_YOY and vs_peak < OUT_PEAK:
        label = "Out"
    elif yoy is not None and yoy <= FADING:
        label = "Fading"
    elif yoy is not None and EMERGING_YOY <= yoy < RISING and momentum > EMERGING_MOMENTUM:
        label = "Emerging"
    elif vs_peak >= PEAK:
        label = "Peaking"
    else:
        label = "Stable"
    low = recent < 5 and (prior is None or prior < 5)
    return TrendSignal(label, None if yoy is None else round(yoy, 3), round(momentum, 4),
                       round(vs_peak, 3), round(recent, 2), None if prior is None else round(prior, 2), low)


@dataclass
class Assessment(TrendSignal):
    weeks_held: int = 1               # consecutive weeks (up to 12) this label has held, this week included
    confidence: Optional[str] = None  # "High" / "Lower" for Rising, Fading, Out; None for other labels


def assess(values: Sequence[float], max_back: int = 12) -> Assessment:
    """classify() plus how long the label has held and a confidence level (see module docstring)."""
    sig = classify(values)
    held = 1
    while held < max_back and len(values) - held >= WINDOW * 2 and classify(values[:-held]).label == sig.label:
        held += 1
    confidence = None
    if sig.label in CONFIDENCE_LABELS:
        strong = sig.yoy is not None and (sig.yoy >= STRONG_RISE if sig.label == "Rising" else sig.yoy <= STRONG_FALL)
        confidence = "High" if strong and held >= HELD_WEEKS and not sig.low_volume else "Lower"
    return Assessment(**sig.as_dict(), weeks_held=held, confidence=confidence)


def window_change(dates: List[str], values: Sequence[float], start: str, end: str) -> Optional[dict]:
    """Mean interest between two ISO dates and the same dates one year earlier."""
    def mean_between(a: str, b: str) -> Optional[float]:
        sel = [x for d, x in zip(dates, values) if a <= d <= b]
        return _mean(sel) if sel else None

    now = mean_between(start, end)
    then = mean_between(_minus_year(start), _minus_year(end))
    if now is None or then is None:
        return None
    return {"now": round(now, 2), "year_before": round(then, 2),
            "change": round((now - then) / then, 3) if then else None}


def _minus_year(iso: str) -> str:
    y, rest = iso.split("-", 1)
    return f"{int(y) - 1}-{rest}"


def wiki_yoy(months: List[str], views: Sequence[float], n: int = 3) -> Optional[float]:
    """Pageviews of the last n complete months against the same months a year earlier."""
    if len(views) < 12 + n:
        return None
    now, then = _mean(views[-n:]), _mean(views[-n - 12:-12])
    return round((now - then) / then, 3) if then else None

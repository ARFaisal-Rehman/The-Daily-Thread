"""Data-source adapters. Each one talks to a single provider and returns a FetchResult.

Every adapter has the same contract, so the refresh code never sees a provider's raw format and
a failure is always a value, never a crash:

  status   "ok"           series is filled
           "empty"        the provider answered but had nothing (not the same as zero)
           "rate_limited" the provider refused because of too many requests
           "invalid"      the provider answered with data that failed validation
           "error"        network or other failure
  series   normalised data, or None
  params   the query settings, stored next to the data so every number says where it came from
  detail   a short reason when status is not "ok"
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class FetchResult:
    key: str
    status: str
    series: Optional[Dict]
    params: Dict = field(default_factory=dict)
    detail: str = ""


def check_series(dates, values, lo: float = 0, hi: Optional[float] = None) -> str:
    """Return a problem description, or "" if the series looks sane."""
    if not dates or len(dates) != len(values):
        return "dates and values missing or of different length"
    if any(b <= a for a, b in zip(dates, dates[1:])):
        return "dates are not strictly increasing"
    if any(v is None or v < lo or (hi is not None and v > hi) for v in values):
        return f"values outside {lo:g}-{hi:g}" if hi is not None else f"values below {lo:g}"
    return ""

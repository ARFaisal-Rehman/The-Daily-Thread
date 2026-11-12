"""Fetch live signals: Google Trends (via pytrends) and Wikipedia pageviews (Wikimedia REST API).

pytrends is unofficial and archived; Google may rate-limit it. Every call is wrapped with a
pause and retries, and callers save results to a dated snapshot so the app never depends on
a live request.
"""
from __future__ import annotations

import time
from datetime import date
from typing import Dict, List, Optional

import requests

UA = {"User-Agent": "TheDailyThread-TrendRadar/1.0 (portfolio project; github.com/ARFaisal-Rehman/The-Daily-Thread)"}
WIKI = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{a}/monthly/{s}/{e}"


def google_series(term: str, timeframe: str = "today 5-y", geo: str = "", tries: int = 4,
                  pause: float = 4.0) -> Optional[Dict[str, List]]:
    """Weekly Google search interest (0-100, relative to the term's own peak) for one term.
    The last week is dropped if Google marks it as partial."""
    from pytrends.request import TrendReq

    for attempt in range(tries):
        try:
            client = TrendReq(hl="en-US", tz=0, timeout=(10, 30))
            client.build_payload([term], timeframe=timeframe, geo=geo)
            df = client.interest_over_time()
            if df.empty:
                return None
            if "isPartial" in df and bool(df["isPartial"].iloc[-1]):
                df = df.iloc[:-1]
            return {"dates": [d.strftime("%Y-%m-%d") for d in df.index], "values": [int(x) for x in df[term]]}
        except Exception as exc:  # 429s and timeouts: back off and retry
            wait = pause * (2 ** attempt)
            print(f"  google '{term}' failed ({type(exc).__name__}); retrying in {wait:.0f}s")
            time.sleep(wait)
    return None


def wiki_monthly(article: str, start: str = "20210101", end: Optional[str] = None) -> Optional[Dict[str, List]]:
    """Monthly user pageviews for an English Wikipedia article (complete months only)."""
    end = end or date.today().replace(day=1).strftime("%Y%m%d")
    r = requests.get(WIKI.format(a=article, s=start, e=end), headers=UA, timeout=30)
    if r.status_code != 200:
        return None
    items = r.json().get("items", [])
    this_month = date.today().strftime("%Y%m")
    items = [i for i in items if not i["timestamp"].startswith(this_month)]
    return {"months": [i["timestamp"][:4] + "-" + i["timestamp"][4:6] for i in items],
            "views": [i["views"] for i in items]}

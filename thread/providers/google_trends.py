"""Google Trends adapter (via pytrends, an unofficial and archived library: treat it as fragile).

Values are Google's relative index: 100 = this query's busiest week in the chosen window and
region. They are not search counts, and two separately fetched queries are not on one scale.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from . import FetchResult, check_series

SOURCE = "google_trends"


def _default_client():
    from pytrends.request import TrendReq
    return TrendReq(hl="en-US", tz=0, timeout=(10, 30))


def fetch(query: str, geo: str = "", timeframe: str = "today 5-y", client_factory: Optional[Callable] = None,
          tries: int = 4, pause: float = 4.0, sleep: Callable[[float], None] = time.sleep) -> FetchResult:
    params = {"geo": geo or "worldwide", "timeframe": timeframe, "query": query}
    factory = client_factory or _default_client
    status, detail = "error", ""
    for attempt in range(tries):
        try:
            client = factory()
            client.build_payload([query], timeframe=timeframe, geo=geo)
            df = client.interest_over_time()
        except Exception as exc:  # pytrends raises many types; classify, back off, retry
            name = type(exc).__name__
            status = "rate_limited" if "TooManyRequests" in name or "429" in str(exc) else "error"
            detail = name
            if attempt < tries - 1:
                sleep(pause * (2 ** attempt))
            continue
        if df.empty:
            return FetchResult(query, "empty", None, params, "Google returned no data")
        if query not in df.columns:
            return FetchResult(query, "invalid", None, params, f"no column for '{query}' in the response")
        if "isPartial" in df and bool(df["isPartial"].iloc[-1]):
            df = df.iloc[:-1]                     # the current week is unfinished
        series = {"dates": [d.strftime("%Y-%m-%d") for d in df.index], "values": [int(x) for x in df[query]]}
        problem = check_series(series["dates"], series["values"], 0, 100)
        if problem:
            return FetchResult(query, "invalid", None, params, problem)
        return FetchResult(query, "ok", series, params)
    return FetchResult(query, status, None, params, detail)

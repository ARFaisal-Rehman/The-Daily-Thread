"""Wikipedia pageviews adapter (official Wikimedia REST API, no key needed).

Monthly views of one English Wikipedia article by people (bots excluded). A secondary signal:
encyclopaedia readers are not shoppers, and many fashion items have no article.
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import requests

from . import FetchResult, check_series

SOURCE = "wikipedia"
UA = {"User-Agent": "TheDailyThread-TrendRadar/1.0 (portfolio project; github.com/ARFaisal-Rehman/The-Daily-Thread)"}
URL = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{a}/monthly/{s}/{e}"


def fetch(article: str, start: str = "20210101", today: Optional[str] = None,
          get: Callable = requests.get) -> FetchResult:
    day = date.fromisoformat(today) if today else date.today()
    params = {"article": article, "project": "en.wikipedia", "agent": "user"}
    try:
        r = get(URL.format(a=article, s=start, e=day.replace(day=1).strftime("%Y%m%d")), headers=UA, timeout=30)
    except requests.RequestException as exc:
        return FetchResult(article, "error", None, params, f"{type(exc).__name__}: {exc}")
    if r.status_code == 404:
        return FetchResult(article, "empty", None, params, "no such article or no views")
    if r.status_code == 429:
        return FetchResult(article, "rate_limited", None, params, "HTTP 429")
    if r.status_code != 200:
        return FetchResult(article, "error", None, params, f"HTTP {r.status_code}")
    this_month = day.strftime("%Y%m")
    items = [i for i in r.json().get("items", []) if not i["timestamp"].startswith(this_month)]
    items.sort(key=lambda i: i["timestamp"])
    series = {"months": [i["timestamp"][:4] + "-" + i["timestamp"][4:6] for i in items],
              "views": [int(i["views"]) for i in items]}
    if not items:
        return FetchResult(article, "empty", None, params, "no complete months")
    problem = check_series(series["months"], series["views"], 0)
    if problem:
        return FetchResult(article, "invalid", None, params, problem)
    return FetchResult(article, "ok", series, params)

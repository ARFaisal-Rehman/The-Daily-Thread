"""RSS adapter for fashion news feeds: headline, link, date and feed name only.

Article text, images and descriptions are never stored, so the site can link out to publishers
without republishing their work. Check each publisher's terms before deploying publicly.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import Callable, Dict

import requests

from . import FetchResult

SOURCE = "rss"
UA = {"User-Agent": "TheDailyThread/1.0 (portfolio project; headlines and links only)"}
FEEDS: Dict[str, str] = {
    "WWD": "https://wwd.com/feed/",
    "Business of Fashion": "https://www.businessoffashion.com/arc/outboundfeeds/rss/?outputType=xml",
    "Vogue": "https://www.vogue.com/feed/rss",
}


def _day(text: str | None) -> str | None:
    try:
        return parsedate_to_datetime(text).date().isoformat() if text else None
    except (TypeError, ValueError):
        return None


def fetch(name: str, url: str, get: Callable = requests.get) -> FetchResult:
    params = {"feed": name, "url": url}
    try:
        r = get(url, headers=UA, timeout=30)
    except requests.RequestException as exc:
        return FetchResult(name, "error", None, params, f"{type(exc).__name__}: {exc}")
    if r.status_code == 429:
        return FetchResult(name, "rate_limited", None, params, "HTTP 429")
    if r.status_code != 200:
        return FetchResult(name, "error", None, params, f"HTTP {r.status_code}")
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as exc:
        return FetchResult(name, "invalid", None, params, f"not XML: {exc}")
    if root.tag != "rss":
        return FetchResult(name, "invalid", None, params, f"not an RSS feed (root <{root.tag}>)")
    items = []
    for it in root.iter("item"):
        title, link, day = (it.findtext("title") or "").strip(), (it.findtext("link") or "").strip(), _day(it.findtext("pubDate"))
        if title and link and day:
            items.append({"title": title, "link": link, "published": day, "feed": name})
    if not items:
        return FetchResult(name, "empty", None, params, "no dated items")
    return FetchResult(name, "ok", {"items": items}, params)

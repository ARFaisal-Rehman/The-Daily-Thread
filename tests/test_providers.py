"""Provider adapters, tested with fixtures only (no network).

The Wikipedia fixture is a real API response recorded on 13 Nov 2026. The Google fixtures are
synthetic DataFrames shaped like pytrends output, because pytrends has no stable raw response
to record.
"""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from thread.providers import google_trends, wikipedia  # noqa: E402

FIX = ROOT / "tests" / "fixtures"


class FakeTrends:
    """Stands in for pytrends.TrendReq: returns a prepared DataFrame or raises."""

    def __init__(self, result):
        self.result = result

    def build_payload(self, kw_list, timeframe, geo):
        self.kw = kw_list

    def interest_over_time(self):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def frame(values, partial_last=False, term="ballet flats"):
    idx = pd.date_range("2024-01-07", periods=len(values), freq="W")
    return pd.DataFrame({term: values, "isPartial": [False] * (len(values) - 1) + [partial_last]}, index=idx)


def no_sleep(_):
    pass


def test_google_ok_drops_the_unfinished_week():
    r = google_trends.fetch("ballet flats", client_factory=lambda: FakeTrends(frame(list(range(30)), True)),
                            sleep=no_sleep)
    assert r.status == "ok"
    assert len(r.series["values"]) == 29 and r.series["dates"][0] == "2024-01-07"
    assert r.params == {"geo": "worldwide", "timeframe": "today 5-y", "query": "ballet flats"}


def test_google_empty_is_not_an_error():
    r = google_trends.fetch("nothing", client_factory=lambda: FakeTrends(pd.DataFrame()), sleep=no_sleep)
    assert r.status == "empty" and r.series is None


def test_google_rate_limit_is_recorded_after_retries():
    from pytrends.exceptions import TooManyRequestsError
    calls = []

    def factory():
        calls.append(1)
        return FakeTrends(TooManyRequestsError.__new__(TooManyRequestsError))

    r = google_trends.fetch("trench coat", client_factory=factory, tries=3, sleep=no_sleep)
    assert r.status == "rate_limited" and len(calls) == 3 and r.series is None


def test_google_rejects_values_outside_0_to_100():
    r = google_trends.fetch("odd", client_factory=lambda: FakeTrends(frame([10] * 29 + [140], term="odd")),
                            sleep=no_sleep)
    assert r.status == "invalid" and "0-100" in r.detail


def test_google_unexpected_shape_is_invalid_not_a_crash():
    r = google_trends.fetch("odd", client_factory=lambda: FakeTrends(frame([10] * 30)), sleep=no_sleep)
    assert r.status == "invalid" and "column" in r.detail


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code, self._payload = status, payload

    def json(self):
        return self._payload


def test_wikipedia_parses_a_recorded_response():
    payload = json.loads((FIX / "wikipedia_ballet_flat_2024_2025.json").read_text(encoding="utf-8"))
    r = wikipedia.fetch("Ballet_flat", today="2026-01-15", get=lambda *a, **k: FakeResponse(200, payload))
    assert r.status == "ok"
    assert r.series["months"][0] == "2024-01" and len(r.series["months"]) == 24
    assert all(isinstance(v, int) for v in r.series["views"])


def test_wikipedia_drops_the_current_month():
    payload = {"items": [{"timestamp": "2026011500", "views": 5}, {"timestamp": "2025121500", "views": 9}]}
    r = wikipedia.fetch("X", today="2026-01-20", get=lambda *a, **k: FakeResponse(200, payload))
    assert r.series["months"] == ["2025-12"]


def test_wikipedia_missing_article_and_network_errors_never_raise():
    assert wikipedia.fetch("No_such", get=lambda *a, **k: FakeResponse(404)).status == "empty"
    assert wikipedia.fetch("Busy", get=lambda *a, **k: FakeResponse(429)).status == "rate_limited"

    def boom(*a, **k):
        raise requests.ConnectionError("offline")

    r = wikipedia.fetch("Ballet_flat", get=boom)
    assert r.status == "error" and "offline" in r.detail

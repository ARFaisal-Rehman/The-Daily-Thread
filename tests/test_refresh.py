"""The refresh run end to end, with fake providers (no network)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from thread.providers import FetchResult  # noqa: E402
from thread.refresh import run  # noqa: E402
from thread.trends import METHODOLOGY_VERSION  # noqa: E402

TERMS = [{"term": "barrel jeans", "category": "Denim"},
         {"term": "trench coat", "category": "Pieces", "wiki": "Trench_coat"}]


def weekly(n=80):
    return {"dates": [f"w{i:03d}" for i in range(n)], "values": [50] * n}


def fake_google(query, **_):
    if query == "trench coat":
        return FetchResult(query, "rate_limited", None, {"query": query}, "TooManyRequestsError")
    return FetchResult(query, "ok", weekly(), {"query": query, "geo": "worldwide", "timeframe": "today 5-y"})


def fake_wiki(article, **_):
    return FetchResult(article, "error", None, {"article": article}, "ConnectionError: offline")


def test_run_publishes_with_a_manifest_and_carries_failures_forward(tmp_path):
    old = {"fetched": "2026-11-06", "geo": "worldwide",
           "google": {"trench coat": {**weekly(), "collected_at": "2026-11-06"}}, "colours": {}, "wiki": {}}
    (tmp_path / "2026-11-06.json").write_text(json.dumps(old), encoding="utf-8")

    report = run(tmp_path, TERMS, ["rust"], google=fake_google, wiki=fake_wiki, today="2026-11-13", pause=0)

    out = json.loads((tmp_path / "2026-11-13.json").read_text(encoding="utf-8"))
    assert out["google"]["barrel jeans"]["collected_at"] == "2026-11-13"
    assert out["google"]["barrel jeans"]["source"] == "google_trends"
    assert out["google"]["trench coat"]["carried_from"] == "2026-11-06"      # failure did not erase it
    m = out["run"]
    assert m["methodology_version"] == METHODOLOGY_VERSION
    assert m["attempted"] == 4 and m["ok"] == 2                              # 2 terms + 1 colour + 1 wiki
    assert m["failed"]["google:trench coat"] == "rate_limited: TooManyRequestsError"
    assert m["failed"]["wiki:Trench_coat"].startswith("error: ConnectionError")
    assert report["carried"] == 1


def test_run_resumes_from_todays_draft(tmp_path):
    calls = []

    def counting(query, **_):
        calls.append(query)
        return fake_google(query)

    run(tmp_path, TERMS[:1], [], google=counting, wiki=fake_wiki, today="2026-11-13", pause=0, publish_at_end=False)
    run(tmp_path, TERMS[:1], [], google=counting, wiki=fake_wiki, today="2026-11-13", pause=0)
    assert calls == ["barrel jeans"]                                           # second run skipped it


def test_brands_go_to_their_own_bucket_keyed_by_topic(tmp_path):
    brands = [{"topic": "/m/033j5y", "wiki": "Prada"}]
    seen = []

    def google(query, **_):
        seen.append(query)
        return fake_google(query)

    run(tmp_path, [], [], brands=brands, google=google, wiki=fake_wiki, today="2026-11-13", pause=0)
    out = json.loads((tmp_path / "2026-11-13.json").read_text(encoding="utf-8"))
    assert seen == ["/m/033j5y"]
    assert "/m/033j5y" in out["brands"] and out["google"] == {}
    assert "wiki:Prada" in out["run"]["failed"]                               # brand articles use the wiki bucket


def test_second_run_same_day_only_fills_gaps(tmp_path):
    run(tmp_path, TERMS[:1], [], google=fake_google, wiki=fake_wiki, today="2026-11-13", pause=0)   # publishes
    calls = []

    def counting(query, **_):
        calls.append(query)
        return fake_google(query)

    run(tmp_path, TERMS, [], google=counting, wiki=fake_wiki, today="2026-11-13", pause=0)
    assert calls == ["trench coat"]                       # barrel jeans was already collected today
    out = json.loads((tmp_path / "2026-11-13.json").read_text(encoding="utf-8"))
    assert out["google"]["barrel jeans"]["collected_at"] == "2026-11-13"

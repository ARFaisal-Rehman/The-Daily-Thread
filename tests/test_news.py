import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from thread.news import mentions, merge_items  # noqa: E402
from thread.providers import FetchResult, rss  # noqa: E402
from thread.refresh import run  # noqa: E402

SAMPLE = (ROOT / "tests" / "fixtures" / "feed_sample.xml").read_bytes()


class Resp:
    def __init__(self, content, status=200):
        self.content, self.status_code = content, status


def test_rss_keeps_only_headline_link_and_date():
    res = rss.fetch("Sample", "https://example.com/feed", get=lambda *a, **k: Resp(SAMPLE))
    assert res.status == "ok"
    items = res.series["items"]
    assert items[0] == {"title": "Prada Back on Top as Celine Climbs", "link": "https://example.com/a",
                        "published": "2026-11-13", "feed": "Sample"}
    assert all(set(i) == {"title", "link", "published", "feed"} for i in items)   # no article text stored
    assert items[2]["published"] == "2026-11-11"
    assert len(items) == 3                                                        # undated item dropped


def test_rss_failures_are_classified():
    assert rss.fetch("S", "u", get=lambda *a, **k: Resp(b"<html>not a feed")).status == "invalid"
    assert rss.fetch("S", "u", get=lambda *a, **k: Resp(b"", 429)).status == "rate_limited"
    empty = b'<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
    assert rss.fetch("S", "u", get=lambda *a, **k: Resp(empty)).status == "empty"


def test_merge_dedupes_by_link_and_drops_old_items():
    old = [{"title": "Old", "link": "x", "published": "2026-07-01", "feed": "S"},
           {"title": "Kept", "link": "y", "published": "2026-10-01", "feed": "S"}]
    new = [{"title": "Kept (edited)", "link": "y", "published": "2026-10-01", "feed": "S"},
           {"title": "New", "link": "z", "published": "2026-11-13", "feed": "S"}]
    out = merge_items(old, new, today="2026-11-13", keep_days=90)
    assert [i["link"] for i in out] == ["z", "y"]                                 # newest first, old one gone
    assert out[1]["title"] == "Kept (edited)"


def test_mentions_match_names_without_accents_and_skip_exclusions():
    items = rss.fetch("Sample", "u", get=lambda *a, **k: Resp(SAMPLE)).series["items"]
    brands = [{"slug": "prada", "name": "Prada"}, {"slug": "celine", "name": "Celine", "news_exclude": ["Celine Dion"]},
              {"slug": "chloe", "name": "Chloé"}, {"slug": "hermes", "name": "Hermès"}, {"slug": "dior", "name": "Dior"}]
    m = mentions(items, brands, today="2026-11-13", days=30)
    assert [i["link"] for i in m["celine"]] == ["https://example.com/a"]           # not the Celine Dion story
    assert len(m["chloe"]) == 1 and len(m["hermes"]) == 1
    assert m["dior"] == []                                                         # missing is an empty list


def test_refresh_stores_feeds_in_the_news_bucket_and_keeps_history(tmp_path):
    prev = {"fetched": "2026-11-06", "google": {}, "colours": {}, "wiki": {}, "brands": {},
            "news": {"Sample": {"items": [{"title": "Earlier", "link": "e", "published": "2026-11-05", "feed": "Sample"}]}}}
    (tmp_path / "2026-11-06.json").write_text(json.dumps(prev), encoding="utf-8")

    def feed(name, url):
        return FetchResult(name, "ok", {"items": [{"title": "Today", "link": "t", "published": "2026-11-13",
                                                  "feed": name}]}, {"url": url}, "")

    run(tmp_path, [], [], feeds={"Sample": "https://example.com/feed"}, news=feed, today="2026-11-13", pause=0)
    out = json.loads((tmp_path / "2026-11-13.json").read_text(encoding="utf-8"))
    assert [i["link"] for i in out["news"]["Sample"]["items"]] == ["t", "e"]


from thread.news import dedupe, desk  # noqa: E402

ITEMS = [
    {"title": "Prada Back on Top", "link": "a", "published": "2026-11-12", "feed": "WWD"},
    {"title": "Prada back on top!", "link": "a2", "published": "2026-11-12", "feed": "Business of Fashion"},
    {"title": "Kering Names New Gucci Chief", "link": "b", "published": "2026-11-11", "feed": "Vogue"},
    {"title": "Why Ballet Flats Are Everywhere", "link": "c", "published": "2026-11-10", "feed": "Vogue"},
    {"title": "Celine Dion Announces Tour", "link": "d", "published": "2026-11-09", "feed": "Vogue"},
]
TAGS = [{"slug": "prada", "name": "Prada", "kind": "brand", "names": ["Prada"]},
        {"slug": "gucci", "name": "Gucci", "kind": "brand", "names": ["Gucci"]},
        {"slug": "celine", "name": "Celine", "kind": "brand", "names": ["Celine"], "exclude": ["Celine Dion"]},
        {"slug": "kering", "name": "Kering", "kind": "group", "names": ["Kering"]},
        {"slug": "ballet-flats", "name": "Ballet flats", "kind": "term", "names": ["Ballet flats", "ballet flat", "ballerina flats"]}]


def test_dedupe_merges_the_same_headline_across_feeds():
    out = dedupe(ITEMS)
    assert [i["link"] for i in out] == ["a", "b", "c", "d"]
    assert out[0]["also_in"] == ["Business of Fashion"]


def test_desk_tags_groups_days_and_counts():
    d = desk(ITEMS, TAGS, today="2026-11-13")
    first = d["days"][0]
    assert first[0] == "2026-11-12" and [t["slug"] for t in first[1][0]["tags"]] == ["prada"]
    kering = next(i for day, items in d["days"] for i in items if i["link"] == "b")
    assert {t["slug"] for t in kering["tags"]} == {"gucci", "kering"}
    flats = next(i for day, items in d["days"] for i in items if i["link"] == "c")
    assert [t["kind"] for t in flats["tags"]] == ["term"]
    dion = next(i for day, items in d["days"] for i in items if i["link"] == "d")
    assert dion["tags"] == []
    assert d["count"] == 4 and ("prada", "Prada", 1) in d["top"] and len(d["top"]) == 4


def test_desk_filters_by_tag_and_feed():
    assert [i["link"] for _, items in desk(ITEMS, TAGS, today="2026-11-13", tag="kering")["days"] for i in items] == ["b"]
    assert {i["feed"] for _, items in desk(ITEMS, TAGS, today="2026-11-13", feed="Vogue")["days"] for i in items} == {"Vogue"}

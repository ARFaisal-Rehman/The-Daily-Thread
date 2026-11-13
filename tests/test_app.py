import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app, mindful_score  # noqa: E402
from thread.colours import nearest_family  # noqa: E402


def weekly(values, end=date(2026, 11, 1)):
    start = end - timedelta(weeks=len(values) - 1)
    return {"dates": [(start + timedelta(weeks=i)).isoformat() for i in range(len(values))], "values": values}


@pytest.fixture()
def client(tmp_path):
    snaps = tmp_path / "snapshots"
    snaps.mkdir()
    google = {
        "barrel jeans": weekly([10] * 118 + [40] * 12),
        "skinny jeans": weekly([60] * 20 + [80] * 12 + [40] * 86 + [12] * 12),
    }
    palettes = json.loads((ROOT / "data" / "palettes.json").read_text(encoding="utf-8"))
    words = {nearest_family(c["hex"])[0] for s in palettes["seasons"] for c in s["colours"]}
    colours = {w: weekly([20] * 130) for w in words}
    snap = {"fetched": "2026-11-13T00:00+00:00", "geo": "worldwide", "google": google, "colours": colours,
            "wiki": {"Skinny_jeans": {"months": [f"m{i}" for i in range(15)], "views": [100] * 12 + [60] * 3}}}
    snap["google"]["trench coat"] = {**weekly([30] * 130), "collected_at": "2026-11-06", "carried_from": "2026-11-06"}
    (snaps / "2026-11-13.json").write_text(json.dumps(snap), encoding="utf-8")
    app = make_app(tmp_path, snaps)
    app.config["TESTING"] = True
    return app.test_client()


def make_app(tmp_path, snaps):
    return create_app(db_path=str(tmp_path / "t.db"), snapshots=snaps, instance_path=str(tmp_path / "instance"))


def test_wardrobe_survives_a_restart(tmp_path, client):
    client.post("/wardrobe", data={"name": "Probe coat", "kind": "Outerwear", "colour": "#755139"})
    cookie = client.get_cookie("session").value
    restarted = make_app(tmp_path, tmp_path / "snapshots").test_client()   # new process, same instance folder
    restarted.set_cookie("session", cookie)
    assert "Probe coat" in restarted.get("/wardrobe").get_data(as_text=True)


def test_dateline_shows_when_the_data_ends_not_the_file_date(client):
    html = client.get("/").get_data(as_text=True)
    assert "Search data to 1 Nov 2026" in html
    assert "refreshed 13 Nov 2026" in html


def test_front_page_states_coverage(client):
    html = client.get("/").get_data(as_text=True)
    assert "3 of 36 terms have data" in html                 # fixture has 3 of the 36 tracked terms
    assert "1 carried from an older refresh" in html
    assert "33 unavailable" in html


def test_method_page_reports_the_last_refresh(tmp_path):
    snaps = tmp_path / "s"
    snaps.mkdir()
    snap = {"fetched": "2026-11-13T09:00+00:00", "geo": "worldwide", "colours": {}, "wiki": {},
            "google": {"barrel jeans": weekly([10] * 118 + [40] * 12)},
            "run": {"methodology_version": "1.0", "started": "2026-11-13T08:00+00:00",
                    "finished": "2026-11-13T09:00+00:00", "attempted": 5, "ok": 3,
                    "failed": {"google:trench coat": "rate_limited: TooManyRequestsError",
                               "wiki:Trench_coat": "error: ConnectionError: offline"}}}
    (snaps / "2026-11-13.json").write_text(json.dumps(snap), encoding="utf-8")
    html = make_app(tmp_path, snaps).test_client().get("/method").get_data(as_text=True)
    assert "Methodology version 1.0" in html
    assert "3 of 5 series fetched" in html
    assert "trench coat" in html and "rate_limited" in html


def test_method_page_shows_the_backtest(tmp_path, client):
    bt = {"methodology_version": "1.0", "horizon_weeks": 12, "terms": 33, "observations": 6036, "skipped": [],
          "labels": {"Rising": {"n": 2614, "still_up_share": 0.93, "median_future_yoy": 0.58}},
          "base_rate_up": 0.6, "rising_precision": 0.77, "base_rate_rising": 0.44, "rising_lift": 1.76,
          "falling_precision": 0.67, "base_rate_falling": 0.18, "falling_lift": 3.61, "flip_rate": 0.054,
          "snapshot": "2026-11-13", "generated": "2026-11-13"}
    path = tmp_path / "backtest.json"
    path.write_text(json.dumps(bt), encoding="utf-8")
    client.application.config["BACKTEST"] = path
    html = client.get("/method").get_data(as_text=True)
    assert "6,036 label-weeks" in html
    assert "77%" in html and "44%" in html and "1.76" in html


def test_method_page_without_a_backtest_says_so(client, tmp_path):
    client.application.config["BACKTEST"] = tmp_path / "none.json"
    assert "No backtest has been run" in client.get("/method").get_data(as_text=True)


def test_dictionary_page_lists_terms_by_category(client):
    html = client.get("/dictionary").get_data(as_text=True)
    assert "Clothing" in html and "Jeans" in html and "Aesthetics" in html
    assert "curve outward through the thigh" in html                       # barrel jeans definition
    assert 'href="/trend/barrel-jeans"' in html                              # has radar data in the fixture
    assert "Barn jacket" in html and 'href="/trend/barn-jacket"' not in html # no data: listed, not linked


def test_dictionary_search_finds_aliases(client):
    html = client.get("/dictionary?q=stealth+wealth").get_data(as_text=True)
    assert "Quiet luxury" in html and "1 reviewed term and 0 proposed" in html


def test_trend_page_shows_the_dictionary_entry(client):
    html = client.get("/trend/barrel-jeans").get_data(as_text=True)
    assert "curve outward through the thigh" in html
    assert "Also called" in html and "horseshoe jeans" in html
    assert "Clothing / Bottoms / Jeans" in html
    assert "Baggy jeans" in html                                            # related term


def test_carried_forward_terms_say_how_old_they_are(client):
    html = client.get("/").get_data(as_text=True)
    assert "data from 6 Nov 2026" in html


def test_front_page_sorts_terms_into_in_and_out(client):
    html = client.get("/").get_data(as_text=True)
    assert "Barrel jeans: searches +300% on a year ago" in html
    assert "Wikipedia agrees" in html


def test_trend_page_and_404(client):
    assert client.get("/trend/skinny-jeans").status_code == 200
    assert client.get("/trend/not-a-trend").status_code == 404


def test_colours_page_shows_this_and_last_season(client):
    html = client.get("/colours").get_data(as_text=True)
    assert "Autumn/Winter 2026/27" in html and "Spring/Summer 2026" in html


def test_wardrobe_persists_and_validates(client):
    assert client.post("/wardrobe", data={"name": "", "kind": "Top", "colour": "#000000"}).status_code == 400
    r = client.post("/wardrobe", data={"name": "Suede jacket", "kind": "Outerwear", "colour": "#755139",
                                       "term": "barrel-jeans"}, follow_redirects=True)
    assert "Suede jacket" in r.get_data(as_text=True)
    assert "in season" in r.get_data(as_text=True)          # #755139 is Pantone Toffee, AW26 core


def test_mindful_score_uses_the_radar():
    rising = {"label": "Rising", "term": "barrel jeans"}
    form = {"wears": "1", "pairs": "no", "gap": "no", "hype": "yes"}
    assert mindful_score(form, rising, 0)["verdict"] == "Probably skip"
    good = {"wears": "8", "pairs": "yes", "gap": "yes", "hype": "no"}
    assert mindful_score(good, {"label": "Stable", "term": "trench coat"}, 0)["verdict"] == "Mindful buy"


def test_dictionary_page_lists_proposed_terms_separately_with_credit(client):
    html = client.get("/dictionary").get_data(as_text=True)
    assert "awaiting review" in html
    assert "Polo shirt" in html and 'href="/trend/polo-shirt"' not in html
    assert "Fashionpedia" in html and "CC BY 4.0" in html
    active_part = html.split("awaiting review")[0]
    assert "Polo shirt" not in active_part                                   # not mixed in with reviewed terms


def test_dictionary_search_includes_proposed_terms(client):
    html = client.get("/dictionary?q=batwing").get_data(as_text=True)
    assert "Dolman sleeve" in html and "proposed" in html


def test_brand_watch_page(client):
    html = client.get("/brands").get_data(as_text=True)
    assert "Brand Watch" in html
    assert "Lyst Index Q3 2026" in html and "https://www.lyst.com/the-lyst-index/Q3-26/" in html
    assert html.index("Prada") < html.index("Chanel")                          # Lyst order
    assert "no search data yet" in html                                       # fixture has no brand series
    assert "not ranked" in html                                               # Louis Vuitton, Hermes
    assert "not collected yet" in html                                        # no news archive in the fixture


def test_brand_watch_keeps_money_separate_and_scoped(client):
    html = client.get("/brands").get_data(as_text=True)
    money = html.split('id="company-figures"')[1]
    assert "Prada Group" in money and "group" in money and "segment" in money
    assert "Organic growth excludes Versace" in money
    assert "+15%" in money and "constant currency" in money                   # growth named the company's way
    assert "pradagroup.com" in money                                          # every figure links its source


def test_nav_links_brand_watch(client):
    assert 'href="/brands"' in client.get("/").get_data(as_text=True)


def test_stale_marker_does_not_blame_a_failure(client):
    html = client.get("/").get_data(as_text=True)
    assert "data from 6 Nov 2026 (not updated in the last refresh)" in html

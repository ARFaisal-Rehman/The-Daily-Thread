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


def test_carried_forward_terms_say_how_old_they_are(client):
    html = client.get("/").get_data(as_text=True)
    assert "data from 6 Nov 2026 (last refresh failed)" in html


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

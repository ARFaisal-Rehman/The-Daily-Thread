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
    (snaps / "2026-11-13.json").write_text(json.dumps(snap), encoding="utf-8")
    app = create_app(db_path=str(tmp_path / "t.db"), snapshots=snaps)
    app.config["TESTING"] = True
    return app.test_client()


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

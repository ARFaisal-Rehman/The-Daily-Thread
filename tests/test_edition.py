import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from thread.brands import load as load_brands  # noqa: E402
from thread.colours import nearest_family  # noqa: E402


def weekly(values, end=date(2026, 11, 1)):
    start = end - timedelta(weeks=len(values) - 1)
    return {"dates": [(start + timedelta(weeks=i)).isoformat() for i in range(len(values))], "values": values}


def snapshot(google, brands=None, news=None):
    palettes = json.loads((ROOT / "data" / "palettes.json").read_text(encoding="utf-8"))
    words = {nearest_family(c["hex"])[0] for s in palettes["seasons"] for c in s["colours"]}
    return {"fetched": "x", "geo": "worldwide", "google": google, "colours": {w: weekly([20] * 130) for w in words},
            "wiki": {}, "brands": brands or {}, "news": news or {}}


@pytest.fixture()
def client(tmp_path):
    snaps = tmp_path / "snapshots"
    snaps.mkdir()
    b = load_brands().by_slug
    older = snapshot({"skinny jeans": weekly([10] * 118 + [40] * 12)})
    newer = snapshot(
        {"barrel jeans": weekly([10] * 118 + [40] * 12), "skinny jeans": weekly([60] * 118 + [20] * 12)},
        brands={b["prada"].search: weekly([20] * 118 + [50] * 12),
                b["gucci"].search: weekly([60] * 118 + [30] * 12),
                b["chloe"].search: weekly([10] * 130 + [40] * 130)},           # broken series: never a mover
        news={"WWD": {"items": [
            {"title": "Kering Names New Gucci Chief", "link": "https://wwd.com/k", "published": "2026-11-12", "feed": "WWD"},
            {"title": "A Story About Nothing", "link": "https://wwd.com/n", "published": "2026-11-12", "feed": "WWD"}]}})
    (snaps / "2026-11-06.json").write_text(json.dumps(older), encoding="utf-8")
    (snaps / "2026-11-13.json").write_text(json.dumps(newer), encoding="utf-8")
    app = create_app(db_path=str(tmp_path / "t.db"), snapshots=snaps, instance_path=str(tmp_path / "i"))
    app.config["TESTING"] = True
    return app.test_client()


def test_latest_edition_leads_with_the_biggest_riser_and_faller(client):
    html = client.get("/edition").get_data(as_text=True)
    assert "13 Nov 2026" in html
    lead = html.split('class="edition-lead"')[1]
    assert "Barrel jeans" in lead.split("</article>")[0]
    assert "Skinny jeans" in html


def test_edition_brand_movers_skip_broken_series(client):
    html = client.get("/edition").get_data(as_text=True)
    brands = html.split('id="edition-brands"')[1].split("</section>")[0]
    assert "Prada" in brands and "Gucci" in brands
    assert "Chlo" not in brands


def test_edition_shows_only_tagged_headlines(client):
    html = client.get("/edition").get_data(as_text=True)
    news = html.split('id="edition-news"')[1].split("</section>")[0]
    assert "Kering Names New Gucci Chief" in news and "A Story About Nothing" not in news


def test_past_edition_uses_its_own_snapshot(client):
    html = client.get("/edition/2026-11-06").get_data(as_text=True)
    assert "6 Nov 2026" in html
    lead = html.split('class="edition-lead"')[1].split("</article>")[0]
    assert "Skinny jeans" in lead and "Barrel jeans" not in lead


def test_past_edition_hides_facts_published_after_it(client):
    old = client.get("/edition/2026-11-06").get_data(as_text=True)
    new = client.get("/edition/2026-11-13").get_data(as_text=True)
    assert "Lyst Index" not in old                      # Lyst Q3 2026 was entered on 13 Nov
    assert "Lyst Index" in new


def test_archive_lists_editions_newest_first(client):
    html = client.get("/editions").get_data(as_text=True)
    assert html.index('href="/edition/2026-11-13"') < html.index('href="/edition/2026-11-06"')


@pytest.mark.parametrize("day", ["2026-10-01", "not-a-date", "..%2Fsecret"])
def test_unknown_or_malformed_editions_are_404(client, day):
    assert client.get(f"/edition/{day}").status_code == 404


def test_nav_links_todays_edition(client):
    assert 'href="/edition"' in client.get("/").get_data(as_text=True)

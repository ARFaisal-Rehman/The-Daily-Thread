import copy
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from thread.brands import BrandWatch, load  # noqa: E402

REG, FACTS = ROOT / "data" / "brands.json", ROOT / "data" / "brand_facts.json"


def weekly(values, end=date(2026, 11, 1)):
    start = end - timedelta(weeks=len(values) - 1)
    return {"dates": [(start + timedelta(weeks=i)).isoformat() for i in range(len(values))], "values": values}


def raw():
    return json.loads(REG.read_text(encoding="utf-8")), json.loads(FACTS.read_text(encoding="utf-8"))


def write(tmp_path, reg, facts):
    a, b = tmp_path / "brands.json", tmp_path / "facts.json"
    a.write_text(json.dumps(reg), encoding="utf-8")
    b.write_text(json.dumps(facts), encoding="utf-8")
    return a, b


def test_registry_and_facts_load():
    data = load()
    assert len(data.brands) == 22
    assert data.by_slug["celine"].search == "/m/0463vt1"          # the brand, not Celine Dion
    assert data.groups[data.by_slug["gucci"].group]["name"] == "Kering"
    assert data.lyst["edition"] == "Q3 2026" and data.lyst["ranks"][0]["brand"] == data.by_slug["prada"].id
    assert all(f["source"].startswith("https://") for f in data.financials)


@pytest.mark.parametrize("mutate, message", [
    (lambda r, f: r["brands"][0].update(group="nobody"), "unknown group"),
    (lambda r, f: r["brands"][1].update(search=r["brands"][0]["search"]), "duplicate search"),
    (lambda r, f: r["brands"].append(copy.deepcopy(r["brands"][0])), "duplicate id"),
    (lambda r, f: f["lyst"][0]["ranks"][0].update(brand="br-999"), "unknown brand"),
    (lambda r, f: f["financials"][0].update(scope="vibes"), "scope"),
    (lambda r, f: f["financials"][2].pop("brand"), "brand-scope figures need a brand"),
    (lambda r, f: f["financials"][0].update(source=""), "source"),
    (lambda r, f: f["financials"][0].update(growth={}), "growth"),
    (lambda r, f: f["financials"][0].update(growth={"vibes": 0.1}), "growth"),
])
def test_validation_rejects_broken_entries(tmp_path, mutate, message):
    reg, facts = raw()
    mutate(reg, facts)
    with pytest.raises(ValueError, match=message):
        load(*write(tmp_path, reg, facts))


def two_lyst_editions(tmp_path):
    reg, facts = raw()
    q3 = facts["lyst"][0]
    q1 = {**copy.deepcopy(q3), "edition": "Q1 2027", "retrieved": "2027-02-10",
          "ranks": [{**q3["ranks"][1], "rank": 1}, {**q3["ranks"][0], "rank": 2}]}
    facts["lyst"] = [q1, q3]                                    # file order must not matter
    return load(*write(tmp_path, reg, facts))


def test_latest_lyst_is_the_newest_retrieved_not_the_last_label(tmp_path):
    data = two_lyst_editions(tmp_path)
    assert data.lyst["edition"] == "Q1 2027"                    # "Q1 2027" sorts before "Q3 2026" as text


def test_lyst_for_a_day_is_the_edition_known_on_that_day(tmp_path):
    data = two_lyst_editions(tmp_path)
    assert data.lyst_for("2026-11-13")["edition"] == "Q3 2026"
    assert data.lyst_for("2027-03-01")["edition"] == "Q1 2027"
    assert data.lyst_for("2026-11-12") == {}                    # nothing entered yet


def test_watch_as_of_a_day_uses_that_days_lyst(tmp_path):
    data = two_lyst_editions(tmp_path)
    prada = data.by_slug["prada"].slug
    assert BrandWatch({}, data).row(prada)["lyst_rank"] == 2
    assert BrandWatch({}, data, as_of="2026-11-13").row(prada)["lyst_rank"] == 1


@pytest.fixture()
def watch():
    data = load()
    snap = {"brands": {data.by_slug["prada"].search: weekly([20] * 118 + [50] * 12),
                       data.by_slug["gucci"].search: {**weekly([60] * 118 + [30] * 12), "carried_from": "2026-11-06",
                                                     "collected_at": "2026-11-06"}},
            "wiki": {"Prada": {"months": [f"m{i}" for i in range(15)], "views": [100] * 12 + [150] * 3}}}
    return BrandWatch(snap, data)


def test_rows_combine_search_wikipedia_and_lyst(watch):
    prada = watch.row("prada")
    assert prada["lyst_rank"] == 1 and prada["lyst_move"] == 5
    assert prada["label"] == "Rising" and prada["yoy"] > 0.25
    assert prada["wiki_yoy"] == pytest.approx(0.5)
    assert prada["group_name"] == "Prada Group"
    gucci = watch.row("gucci")
    assert gucci["label"] in ("Fading", "Out") and gucci["carried_from"] == "2026-11-06"


def test_missing_data_is_missing_not_zero(watch):
    chanel = watch.row("chanel")
    assert chanel["label"] is None and chanel["yoy"] is None and chanel["wiki_yoy"] is None
    lv = watch.row("louis-vuitton")
    assert lv["lyst_rank"] is None                              # Lyst does not rank it: not rank 0


def test_rows_follow_the_lyst_ranking_then_unranked(watch):
    names = [r["name"] for r in watch.rows()]
    assert names[:3] == ["Prada", "Chanel", "Miu Miu"]
    assert names[-2:] == ["Hermès", "Louis Vuitton"]


def test_financials_keep_their_scope(watch):
    prada_figures = watch.financials_for("prada")
    scopes = {f["scope"] for f in prada_figures}
    assert scopes == {"group", "brand"}                          # the brand's own figure and its owner's
    assert watch.financials_for("chanel") == []                  # private: no figures, and none invented
    celine = watch.financials_for("celine")
    assert [f["scope"] for f in celine] == ["segment"]           # only LVMH's division figure exists


def test_rows_count_recent_headlines_and_keep_celine_dion_out():
    data = load()
    items = [{"title": "Prada Back on Top", "link": "a", "published": "2026-11-12", "feed": "WWD"},
             {"title": "Celine Dion Announces Tour", "link": "b", "published": "2026-11-12", "feed": "Vogue"},
             {"title": "Prada and Miu Miu Results", "link": "c", "published": "2026-08-01", "feed": "WWD"}]
    watch = BrandWatch({"news": {"WWD": {"items": items}}}, data, today="2026-11-13")
    prada = watch.row("prada")
    assert prada["news_count"] == 1 and prada["headlines"][0]["link"] == "a"      # August is outside 30 days
    assert watch.row("celine")["news_count"] == 0
    assert watch.row("chanel")["news_count"] == 0 and watch.row("chanel")["headlines"] == []


def test_no_news_archive_means_unknown_not_zero():
    watch = BrandWatch({}, load(), today="2026-11-13")
    assert watch.row("prada")["news_count"] is None


from thread.brands import level_break  # noqa: E402


def test_level_break_flags_a_sudden_permanent_jump():
    assert level_break([10] * 130 + [40] * 130)


def test_level_break_ignores_seasons_that_repeat_every_year():
    year = [10] * 13 + [40] * 13 + [70] * 13 + [20] * 13            # winter-coat brand
    assert level_break(year * 5) is None


def test_level_break_ignores_steady_growth():
    assert level_break([10 + i * 0.3 for i in range(260)]) is None


def test_level_break_flags_a_series_with_no_data():
    assert "no search data" in level_break([0] * 250 + [7] * 10)


def test_a_broken_series_gets_no_label():
    data = load()
    snap = {"brands": {data.by_slug["prada"].search: weekly([10] * 130 + [40] * 130)}}
    row = BrandWatch(snap, data, today="2026-11-13").row("prada")
    assert row["label"] is None and row["yoy"] is None and row["unreliable"]


def test_wikipedia_median_gives_context_for_each_brand():
    data = load()
    up = {"months": [f"m{i}" for i in range(15)], "views": [100] * 12 + [150] * 3}
    down = {"months": [f"m{i}" for i in range(15)], "views": [100] * 12 + [50] * 3}
    snap = {"wiki": {"Prada": up, "Chanel": down, "Gucci": down}}
    assert BrandWatch(snap, data, today="2026-11-13").wiki_median == pytest.approx(-0.5)
    assert BrandWatch({}, data, today="2026-11-13").wiki_median is None


def test_a_reviewed_hold_withholds_the_label_and_says_why():
    data = load()
    hermes = data.by_slug["hermes"]
    assert hermes.search_hold
    row = BrandWatch({"brands": {hermes.search: weekly([10 + i * 0.1 for i in range(260)])}}, data,
                     today="2026-11-13").row("hermes")
    assert row["label"] is None and row["unreliable"] == hermes.search_hold

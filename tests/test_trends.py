import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from thread.colours import delta_e, nearest_family, palette_profile  # noqa: E402
from thread.trends import METHODOLOGY_VERSION, assess, classify, wiki_yoy, window_change  # noqa: E402


def emerging_series(weeks=130):
    """Flat at 40, last year's same weeks at 40, then the last 12 weeks climbing from 40 to ~54."""
    v = [40.0] * weeks
    v[-12:] = [40 + 1.2 * i for i in range(12)]        # mean ~46.6 (+16% YoY), slope 1.2/wk (~2.6%)
    v[30:42] = [60.0] * 12                              # an earlier high, so it is not "Peaking"
    return v


def test_emerging_is_a_rise_not_yet_big_enough_for_rising():
    sig = classify(emerging_series())
    assert sig.label == "Emerging"
    assert 0.10 <= sig.yoy < 0.25 and sig.momentum > 0.02


def test_methodology_version_changed_with_the_rules():
    assert METHODOLOGY_VERSION == "1.1"


def test_confidence_is_high_only_for_a_strong_label_held_four_weeks():
    v = [20.0] * 100 + [60.0] * 30                      # +200% for 30 weeks: Rising, strong, long-held
    a = assess(v)
    assert a.label == "Rising" and a.weeks_held >= 4 and a.confidence == "High"

    fresh = [20.0] * 118 + [60.0] * 12                  # just turned Rising: not held long enough... yet
    assert assess(fresh[:-9]).confidence == "Lower"


def test_confidence_is_not_given_for_labels_the_backtest_does_not_cover():
    assert assess(emerging_series()).confidence is None   # Emerging, Stable, Peaking: no confidence claim


def test_low_volume_caps_confidence():
    v = [1.0] * 100 + [4.0] * 30
    assert assess(v).confidence == "Lower"


def series(last_year: float, this_year: float, weeks: int = 130, peak: float | None = None):
    """Flat at last_year, then this_year for the final 12 weeks; optional earlier peak."""
    v = [last_year] * weeks
    v[-12:] = [this_year] * 12
    if peak is not None:
        v[20:32] = [peak] * 12
    return v


@pytest.mark.parametrize("before,after,peak,label", [
    (20, 40, None, "Rising"),          # +100% on a year ago
    (40, 10, 90, "Out"),               # -75% and far below its high
    (40, 34, None, "Fading"),          # -15%
    (50, 52, None, "Peaking"),         # flat but at its own high
    (40, 42, 90, "Stable"),            # +5%, well under its high
])
def test_labels_follow_the_written_rules(before, after, peak, label):
    assert classify(series(before, after, peak=peak)).label == label


def test_seasonality_does_not_count_as_a_trend():
    # Same seasonal wave every year: the year-on-year change should be zero.
    v = [50 + 40 * math.sin(2 * math.pi * w / 52) for w in range(52 * 3)]
    sig = classify(v)
    assert abs(sig.yoy) < 0.02
    assert sig.label in {"Stable", "Peaking"}


def test_low_volume_is_flagged():
    assert classify(series(2, 4)).low_volume


def test_short_series_is_rejected():
    with pytest.raises(ValueError):
        classify([1] * 10)


def test_window_change_compares_same_dates_a_year_apart():
    dates = ["2025-09-07", "2025-10-05", "2026-09-06", "2026-10-04"]
    out = window_change(dates, [10, 10, 15, 15], "2026-09-01", "2026-10-31")
    assert out == {"now": 15.0, "year_before": 10.0, "change": 0.5}


def test_wiki_yoy():
    views = [100] * 12 + [150] * 3
    assert wiki_yoy([str(i) for i in range(15)], views) == 0.5


def test_colour_words_are_sensible():
    assert nearest_family("#F3ECE0")[0] == "cream"          # Pantone Egret
    assert nearest_family("#00539C")[0] == "cobalt blue"    # Pantone Princess Blue
    assert delta_e("#123456", "#123456") == 0


def test_palette_profile_shares_sum_to_one():
    p = palette_profile([{"hex": "#D22630"}, {"hex": "#167D7F"}, {"hex": "#8E8C88"}])
    assert p["warm"] + p["cool"] + p["neutral"] == pytest.approx(1, abs=0.005)  # each share is rounded
    assert p["neutral"] == pytest.approx(1 / 3, abs=0.01)


def test_committed_palettes_have_four_seasons():
    data = json.loads((ROOT / "data" / "palettes.json").read_text(encoding="utf-8"))
    assert [s["id"] for s in data["seasons"]] == ["aw25", "ss26", "aw26", "ss27"]
    for s in data["seasons"]:
        assert sum(c["group"] == "top10" for c in s["colours"]) == 10
        assert all(c["hex"].startswith("#") and len(c["hex"]) == 7 for c in s["colours"])

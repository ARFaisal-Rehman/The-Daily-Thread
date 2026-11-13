import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from thread.backtest import backtest  # noqa: E402


def steady_growth(n=160):
    return [10 + i * 0.5 for i in range(n)]          # keeps rising: every Rising label should hold


def flat(n=160):
    return [50.0] * n                                 # never moves: Stable/Peaking, never Rising


def test_backtest_counts_only_weeks_with_a_known_future():
    res = backtest({"a": steady_growth()}, horizon=12)
    # labels need 64 weeks of history (12 + 52), the outcome needs 12 more weeks of future
    assert res["observations"] == 160 - 64 - 12 + 1
    assert res["terms"] == 1 and res["horizon_weeks"] == 12


def test_a_trend_that_keeps_rising_scores_perfect_precision():
    res = backtest({"a": steady_growth()}, horizon=12)
    rising = res["labels"]["Rising"]
    assert rising["n"] > 0
    assert rising["still_up_share"] == 1.0
    assert res["rising_precision"] == 1.0


def test_flat_series_never_rises_and_never_flips():
    res = backtest({"b": flat()}, horizon=12)
    assert "Rising" not in res["labels"]
    assert res["flip_rate"] == 0.0


def test_base_rates_are_reported_for_comparison():
    res = backtest({"a": steady_growth(), "b": flat()}, horizon=12)
    assert 0 < res["base_rate_up"] <= 1
    assert res["rising_lift"] == round(res["rising_precision"] / res["base_rate_rising"], 2)


def test_short_series_are_skipped_not_crashed():
    res = backtest({"short": [1.0] * 40, "a": steady_growth()}, horizon=12)
    assert res["terms"] == 1 and res["skipped"] == ["short"]

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from thread.snapshots import draft_path, latest_published, load_draft, publish, save_draft  # noqa: E402


def series(v, collected="2026-11-06"):
    return {"dates": [f"2026-10-{d:02d}" for d in range(1, len(v) + 1)], "values": v, "collected_at": collected}


def snapshot(google, colours=None, wiki=None, fetched="2026-11-06T09:00+00:00"):
    return {"fetched": fetched, "geo": "worldwide", "google": google, "colours": colours or {}, "wiki": wiki or {}}


def test_drafts_are_never_read_as_published(tmp_path):
    (tmp_path / "2026-11-06.json").write_text(json.dumps(snapshot({"a": series([1])})), encoding="utf-8")
    save_draft(tmp_path, "2026-11-13", snapshot({"b": series([2])}))
    assert latest_published(tmp_path).name == "2026-11-06.json"
    assert load_draft(tmp_path, "2026-11-13")["google"] == {"b": series([2])}
    assert draft_path(tmp_path, "2026-11-13").parent.name == "drafts"


def test_publish_carries_forward_what_the_refresh_missed(tmp_path):
    old = snapshot({"barrel jeans": series([1, 2]), "trench coat": series([5, 6])},
                   colours={"rust": series([3])}, wiki={"Trench_coat": {"months": ["2026-10"], "views": [9]}})
    (tmp_path / "2026-11-06.json").write_text(json.dumps(old), encoding="utf-8")
    new = snapshot({"barrel jeans": series([7, 8], collected="2026-11-13")}, fetched="2026-11-13T09:00+00:00")

    report = publish(tmp_path, "2026-11-13", new)

    out = json.loads((tmp_path / "2026-11-13.json").read_text(encoding="utf-8"))
    assert out["google"]["barrel jeans"]["values"] == [7, 8]               # fresh data wins
    assert "carried_from" not in out["google"]["barrel jeans"]
    assert out["google"]["trench coat"]["values"] == [5, 6]                # missing term kept...
    assert out["google"]["trench coat"]["carried_from"] == "2026-11-06"    # ...and marked as old
    assert out["colours"]["rust"]["carried_from"] == "2026-11-06"
    assert out["wiki"]["Trench_coat"]["carried_from"] == "2026-11-06"
    assert report["fresh"] == 1 and report["carried"] == 3


def test_publish_marks_old_series_without_a_collection_date(tmp_path):
    old = snapshot({"a": {"dates": ["2026-10-01"], "values": [1]}}, fetched="2026-11-06T09:00+00:00")
    (tmp_path / "2026-11-06.json").write_text(json.dumps(old), encoding="utf-8")
    publish(tmp_path, "2026-11-13", snapshot({}, fetched="2026-11-13T09:00+00:00"))
    out = json.loads((tmp_path / "2026-11-13.json").read_text(encoding="utf-8"))
    assert out["google"]["a"]["collected_at"] == "2026-11-06"


def test_rerun_on_the_same_day_keeps_earlier_results(tmp_path):
    publish(tmp_path, "2026-11-13", snapshot({"a": series([1], collected="2026-11-13")}))
    publish(tmp_path, "2026-11-13", snapshot({"b": series([2], collected="2026-11-13")}))
    out = json.loads((tmp_path / "2026-11-13.json").read_text(encoding="utf-8"))
    assert set(out["google"]) == {"a", "b"}
    assert "carried_from" not in out["google"]["a"]                        # same day: still fresh


def test_publish_removes_the_draft(tmp_path):
    save_draft(tmp_path, "2026-11-13", snapshot({"a": series([1])}))
    publish(tmp_path, "2026-11-13", load_draft(tmp_path, "2026-11-13"))
    assert not draft_path(tmp_path, "2026-11-13").exists()


def test_brands_bucket_is_carried_forward(tmp_path):
    from thread.snapshots import BUCKETS
    assert "brands" in BUCKETS
    old = {"fetched": "2026-11-06", "google": {}, "colours": {}, "wiki": {}, "brands": {"/m/x": {"values": [1]}}}
    (tmp_path / "2026-11-06.json").write_text(json.dumps(old), encoding="utf-8")
    publish(tmp_path, "2026-11-13", {"google": {}, "colours": {}, "wiki": {}, "brands": {}})
    out = json.loads((tmp_path / "2026-11-13.json").read_text(encoding="utf-8"))
    assert out["brands"]["/m/x"]["carried_from"] == "2026-11-06"

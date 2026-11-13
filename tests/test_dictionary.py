import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from thread.dictionary import load  # noqa: E402

DICT = ROOT / "data" / "dictionary.json"
OLD_SLUGS = {  # the 36 trend-page URLs from before the dictionary; they must keep working
    "barrel-jeans", "baggy-jeans", "wide-leg-jeans", "flare-jeans", "skinny-jeans", "mom-jeans", "ballet-flats",
    "mary-jane-shoes", "penny-loafers", "adidas-samba", "chunky-sneakers", "cowboy-boots", "knee-high-boots",
    "quiet-luxury", "old-money-aesthetic", "coquette-aesthetic", "mob-wife-aesthetic", "clean-girl-aesthetic",
    "y2k-fashion", "cottagecore", "gorpcore", "boho-chic", "office-siren", "leopard-print", "polka-dot-dress",
    "suede-jacket", "barn-jacket", "bomber-jacket", "trench-coat", "cargo-pants", "capri-pants", "maxi-skirt",
    "bubble-skirt", "sheer-dress", "crochet-top", "faux-fur-coat"}


@pytest.fixture(scope="module")
def d():
    return load(DICT)


def raw():
    return json.loads(DICT.read_text(encoding="utf-8"))


def test_all_36_terms_migrated_with_their_urls(d):
    active = [t for t in d.terms if t.status == "active"]
    assert len(active) == 36
    assert {t.slug for t in active} == OLD_SLUGS


def test_every_term_is_complete(d):
    for t in d.terms:
        assert re.fullmatch(r"dt-\d{3}", t.id)
        assert t.definition and t.definition.endswith(".")
        assert t.category in d.categories
        assert all(r in d.by_id for r in t.related)


def test_category_tree_paths(d):
    jeans = d.by_slug["barrel-jeans"]
    assert d.path(jeans.category) == ["Clothing", "Bottoms", "Jeans"]
    assert d.section(jeans.category) == "Clothing"


def test_aliases_find_the_canonical_term(d):
    assert d.find("Barrel-Leg Jeans").slug == "barrel-jeans"
    assert d.find("  stealth wealth ").slug == "quiet-luxury"
    assert d.find("red dress") is None
    hits = d.search("jacket")
    assert hits and all("jacket" in (t.name + " " + " ".join(t.aliases)).lower() for t in hits)


def test_tracked_terms_keep_the_snapshot_keys(d):
    tracked = d.tracked()
    assert len(tracked) == 36
    barrel = next(t for t in tracked if t["slug"] == "barrel-jeans")
    assert barrel["term"] == "barrel jeans"                 # the Google query, i.e. the snapshot key
    assert barrel["category"] == "Clothing" and barrel["id"].startswith("dt-")


@pytest.mark.parametrize("mutate, message", [
    (lambda r: r["terms"].append(copy.deepcopy(r["terms"][0])), "duplicate id"),
    (lambda r: r["terms"][0].update(category="clothing/nowhere"), "unknown category"),
    (lambda r: r["terms"][0].update(status="trendy"), "status"),
    (lambda r: r["terms"][0].update(related=["dt-999"]), "unknown related"),
    (lambda r: r["terms"][1].update(aliases=r["terms"][0]["aliases"][:1]), "alias"),
])
def test_validation_rejects_broken_entries(tmp_path, mutate, message):
    r = raw()
    mutate(r)
    bad = tmp_path / "dictionary.json"
    bad.write_text(json.dumps(r), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load(bad)

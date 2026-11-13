import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from thread.dictionary import load  # noqa: E402
from thread.fashionpedia import build, convert  # noqa: E402


def attr(i, name, sup="nickname", tax=None):
    return {"id": i, "name": name, "supercategory": sup, "taxonomy_id": tax or f"att{i:06d}_00"}


@pytest.mark.parametrize("name, sup, query, category", [
    ("polo (shirt)", "nickname", "polo shirt", "clothing/tops"),
    ("pea (jacket)", "nickname", "pea jacket", "clothing/outerwear"),
    ("dress (coat )", "nickname", "dress coat", "clothing/outerwear"),
    ("bermuda (shorts)", "nickname", "bermuda shorts", "clothing/bottoms/shorts"),
    ("jeans", "nickname", "jeans", "clothing/bottoms/jeans"),
    ("kaftan", "nickname", "kaftan", "clothing/dresses"),
    ("peter pan (collar)", "nickname", "peter pan collar", "details/necklines"),
    ("set-in sleeve", "nickname", "set-in sleeve", "details/sleeves"),
    ("a-line", "silhouette", "a-line", "silhouettes"),
    ("midi", "length", "midi", "silhouettes"),
    ("boat (neck)", "neckline type", "boat neck", "details/necklines"),
    ("double breasted", "opening type", "double breasted", "details/closures"),
    ("sequin(a)", "textile finishing, manufacturing techniques", "sequin", "details/finishes"),
    ("houndstooth (pattern)", "textile pattern", "houndstooth pattern", "patterns"),
    ("zebra", "animal", "zebra", "patterns/prints"),
    ("suede", "leather", "suede", "materials"),
    ("basque (wasitline)", "waistline", "basque waistline", "silhouettes"),   # typo in the source
    ("cheongsams", "nickname", "cheongsam", "clothing/dresses"),
])
def test_convert_names_and_categories(name, sup, query, category):
    t = convert(attr(5, name, sup))
    assert t["query"] == query
    assert t["category"] == category
    assert t["name"] == query[0].upper() + query[1:]
    assert t["slug"] == query.replace(" ", "-")
    assert t["status"] == "proposed" and t["id"] == "fp-005"


def test_combined_names_become_aliases():
    t = convert(attr(213, "dolman (sleeve), batwing (sleeve)", tax="combo000005"))
    assert t["query"] == "dolman sleeve" and t["aliases"] == ["batwing sleeve"]


@pytest.mark.parametrize("name, sup", [
    ("no opening", "opening type"), ("no non-textile material", "non-textile material type"),
    ("symmetrical", "silhouette"), ("plain (pattern)", "textile pattern"), ("letters, numbers", "textile pattern")])
def test_placeholder_values_are_not_terms(name, sup):
    assert convert(attr(1, name, sup)) is None


def test_unmapped_garment_fails_loudly():
    with pytest.raises(ValueError, match="no category"):
        convert(attr(1, "onesie"))


def test_source_is_credited():
    src = convert(attr(3, "henley (shirt)", tax="att000005_00"))["sources"][0]
    assert src["type"] == "fashionpedia" and src["licence"] == "CC BY 4.0"
    assert src["attribute_id"] == 3 and src["taxonomy_id"] == "att000005_00" and src["name"] == "henley (shirt)"


def test_build_skips_terms_already_in_the_dictionary():
    d = load()
    attrs = [attr(42, "cargo (pants)"), attr(1, "polo (shirt)"), attr(2, "no opening", "opening type")]
    terms, matched, skipped = build(attrs, d)
    assert [t["query"] for t in terms] == ["polo shirt"]
    assert matched == [("cargo (pants)", "dt-030")]
    assert skipped == ["no opening"]

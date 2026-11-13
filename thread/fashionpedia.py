"""Turn the Fashionpedia ontology into *proposed* Fashion Dictionary terms.

Fashionpedia (Jia et al., ECCV 2020) publishes 294 fine-grained fashion attributes: garment
nicknames, silhouettes, lengths, necklines, patterns, materials. Its annotations are CC BY 4.0, so
we can reuse the names with credit. They arrive as proposed terms: not on the radar, no definition,
until someone reviews them and moves them into data/dictionary.json.

Names look like 'polo (shirt)': the bracket says which garment the attribute belongs to, and
dropping the brackets gives the phrase people search ('polo shirt').
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

URL = "https://s3.amazonaws.com/ifashionist-dataset/annotations/instances_attributes_val2020.json"
SOURCE = {"type": "fashionpedia", "licence": "CC BY 4.0", "url": "https://fashionpedia.github.io/home/"}

# Values that describe the absence or default of something, or are too generic to be a trend.
EXCLUDE = {"symmetrical", "plain (pattern)", "regular (fit)", "normal waist", "regular (collar)", "lining",
           "letters, numbers", "printed", "short (length)"}
CORRECTIONS = {"basque (wasitline)": "basque (waistline)", "cheongsams": "cheongsam"}

BY_SUPERCATEGORY = {
    "silhouette": "silhouettes", "waistline": "silhouettes", "length": "silhouettes",
    "neckline type": "details/necklines", "opening type": "details/closures",
    "textile finishing, manufacturing techniques": "details/finishes",
    "textile pattern": "patterns", "animal": "patterns/prints",
    "leather": "materials", "non-textile material type": "materials",
}
# For garment nicknames: the word in brackets, or the last word, names the garment.
BY_GARMENT_WORD = {
    "shirt": "clothing/tops", "t-shirt": "clothing/tops", "top": "clothing/tops",
    "jacket": "clothing/outerwear", "coat": "clothing/outerwear",
    "pants": "clothing/bottoms/trousers", "shorts": "clothing/bottoms/shorts",
    "skirt": "clothing/bottoms/skirts", "dress": "clothing/dresses",
    "collar": "details/necklines", "lapel": "details/necklines", "sleeve": "details/sleeves",
    "pocket": "details/pockets",
}
# Nicknames with no garment word in them.
BY_NICKNAME = {
    **dict.fromkeys(["undershirt", "camisole", "hoodie"], "clothing/tops"),
    **dict.fromkeys(["blazer", "anorak", "windbreaker", "bolero", "parka", "raincoat", "kimono", "robe"],
                    "clothing/outerwear"),
    "jeans": "clothing/bottoms/jeans",
    **dict.fromkeys(["sweatpants", "leggings", "culottes", "jodhpur"], "clothing/bottoms/trousers"),
    **dict.fromkeys(["trunks", "boardshorts", "skort", "bloomers"], "clothing/bottoms/shorts"),
    "kilt": "clothing/bottoms/skirts",
    **dict.fromkeys(["cheongsam", "sundress", "kaftan", "nightgown", "gown"], "clothing/dresses"),
}


def _phrase(name: str) -> Tuple[str, str]:
    """'polo (shirt)' -> ('polo shirt', 'shirt'); 'sequin(a)' -> ('sequin', '')."""
    name = re.sub(r"\(a\)$", "", name)
    m = re.search(r"\(([^)]*)\)", name)
    word = m.group(1).strip() if m else ""
    return re.sub(r"\s+", " ", re.sub(r"[()]", " ", name)).strip(), word


def _category(phrase: str, word: str, supercategory: str) -> str:
    if supercategory != "nickname":
        return BY_SUPERCATEGORY[supercategory]
    for key in (word, phrase.split()[-1]):
        if key in BY_GARMENT_WORD:
            return BY_GARMENT_WORD[key]
    if phrase in BY_NICKNAME:
        return BY_NICKNAME[phrase]
    raise ValueError(f"Fashionpedia attribute '{phrase}' has no category mapping; add it to BY_NICKNAME")


def convert(attribute: Dict) -> Optional[Dict]:
    """One Fashionpedia attribute -> a proposed dictionary entry, or None for placeholder values."""
    raw = attribute["name"]
    if raw.startswith("no ") or raw in EXCLUDE:
        return None
    names = [_phrase(n.strip()) for n in CORRECTIONS.get(raw, raw).split(",")]
    query, word = names[0]
    return {"id": f"fp-{attribute['id']:03d}", "name": query[0].upper() + query[1:],
            "slug": re.sub(r"[^a-z0-9]+", "-", query).strip("-"), "query": query,
            "category": _category(query, word, attribute["supercategory"]), "definition": "",
            "aliases": [n for n, _ in names[1:]], "status": "proposed",
            "sources": [{**SOURCE, "attribute_id": attribute["id"], "taxonomy_id": attribute["taxonomy_id"],
                         "name": raw}]}


def build(attributes: List[Dict], dictionary) -> Tuple[List[Dict], List[Tuple[str, str]], List[str]]:
    """Proposed terms, plus (name, existing id) for those already in the dictionary and the skipped names."""
    terms, matched, skipped, seen = [], [], [], set()
    for a in attributes:
        t = convert(a)
        if t is None:
            skipped.append(a["name"])
            continue
        existing = dictionary.find(t["query"]) or next(filter(None, map(dictionary.find, t["aliases"])), None)
        if existing is not None and existing.status != "proposed":
            matched.append((a["name"], existing.id))
        elif t["query"] not in seen:
            seen.add(t["query"])
            terms.append(t)
    return terms, matched, skipped

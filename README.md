<div align="center">

```
██████╗  █████╗ ██╗██╗  ██╗   ██╗  ████████╗██╗  ██╗██████╗ ███████╗ █████╗ ██████╗
██╔══██╗██╔══██╗██║██║  ╚██╗ ██╔╝  ╚══██╔══╝██║  ██║██╔══██╗██╔════╝██╔══██╗██╔══██╗
██║  ██║███████║██║██║   ╚████╔╝█████╗██║   ███████║██████╔╝█████╗  ███████║██║  ██║
██║  ██║██╔══██║██║██║    ╚██╔╝ ╚════╝██║   ██╔══██║██╔══██╗██╔══╝  ██╔══██║██║  ██║
██████╔╝██║  ██║██║███████╗██║        ██║   ██║  ██║██║  ██║███████╗██║  ██║██████╔╝
╚═════╝ ╚═╝  ╚═╝╚═╝╚══════╝╚═╝        ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═════╝
```

### A Fashion Trend Radar: What Is In, What Is Out, and the Colours of the Season, from Live Search Data

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Google Trends](https://img.shields.io/badge/Google_Trends-pytrends-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://trends.google.com)
[![Wikipedia](https://img.shields.io/badge/Wikimedia-pageviews_API-000000?style=for-the-badge&logo=wikipedia&logoColor=white)](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/)
[![SQLite](https://img.shields.io/badge/SQLite-wardrobe-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)](tests/)

<img src="docs/front.jpg" alt="The Daily Thread front page: terms sorted into In, Holding and Out with sparklines" width="100%">

</div>

---

## Table of Contents

- [Overview](#overview)
- [What changed in the November 2026 revision](#what-changed-in-the-november-2026-revision)
- [How It Works](#how-it-works)
- [Results](#results)
- [Getting Started](#getting-started)
- [Data and Licences](#data-and-licences)
- [Challenges and Solutions](#challenges-and-solutions)
- [Roadmap](#roadmap)
- [Author](#author)

---

## Overview

The Daily Thread reads public search data and tells you, in newspaper form (Today's Edition at `/edition` puts the lead stories of every section on one page):

1. **What is in and what is out.** 36 fashion terms from the project's own Fashion Dictionary (each with a definition, other names and a place in a category tree), labelled Rising, Emerging, Peaking, Stable, Fading or Out from five years of weekly Google Trends data, with a confidence level, Wikipedia page views as a second opinion, and every rule backtested.
2. **The colours of the season.** Pantone's New York Fashion Week palette for the current season, whether people are actually searching for those colours compared with a year ago, what changed from last season's palette, and a preview of next season.
3. **Who people are looking at.** Brand Watch follows 22 brands (the Lyst Index Q3 2026 top 20 plus Louis Vuitton and Hermès) by Google search interest, Wikipedia page views and Lyst rank, with company revenue figures kept in a separate, scoped panel.
4. **What the trade is writing about.** A News Desk of WWD, Business of Fashion and Vogue headlines, merged across feeds and tagged with the brands, owner groups and dictionary terms they name.
5. **Whether to buy it.** A wardrobe you can fill in and a five-question purchase check that scores a planned buy, using the radar (buying a Rising style means buying near the top of the hype).

Every label comes from a written rule, shown on the site's How It Works page.

## What changed in the November 2026 revision

| Before | After |
|---|---|
| Repo could not run: HTML files at the root, no `templates/` or `static/` | Standard Flask layout, one command to run |
| "Trends" from synthetic Kaggle sets and mock CSVs (about 14 MB committed) | Live Google Trends and Wikipedia data, saved as dated snapshots; synthetic data removed |
| Wardrobe and purchase history kept in the session cookie (about 4 KB cap, items silently dropped) | SQLite, keyed to an anonymous per-browser id |
| No notion of "in" or "out" | Five labels from year-on-year change and distance from the five-year high |
| No colour analysis | Pantone palettes for four seasons, mapped to everyday colour words by CIELAB distance, with search interest year on year |
| Reddit feed needing API keys, unused TensorFlow dependency, emoji README | Removed |
| No tests | pytest suite for the label rules, colour maths and every page |

## How It Works

```
data/dictionary.json┐                                   ┌──► Trend Radar  (In / Holding / Out)
                  ├─► scripts/refresh_trends.py ──────┤
Pantone reports ──┤     Google Trends, 5 y weekly     │    thread/trends.py
 (build_palettes) │     Wikipedia, monthly views      ├──► Term page    (chart + signals)
                  │            │                      │
data/palettes.json┘            ▼                      │    thread/colours.py
                     data/snapshots/YYYY-MM-DD.json ──┼──► Colours of the Season
                                                      │
                     data/thread.db (SQLite) ─────────┴──► Wardrobe, Should I Buy It?
```

**Trend label.** For each term's weekly series (Google's 0 to 100 scale, the unfinished week dropped):

| Signal | Definition |
|---|---|
| Year on year | mean of the last 12 weeks vs the same 12 weeks a year earlier (cancels seasonality) |
| Share of high | last 12 weeks vs the busiest 12-week stretch in five years |
| Momentum | slope of the last 12 weeks, as % of their mean per week (shown, not used in the label) |

| Label | Rule (checked in this order) |
|---|---|
| Rising | year on year +25% or more |
| Out | year on year -25% or less and under 40% of the five-year high |
| Fading | year on year -10% or less |
| Emerging | year on year +10% to +25% and momentum above +2% a week (added in methodology 1.1) |
| Peaking | 80% or more of the five-year high |
| Stable | anything else |

**Confidence** (Rising, Fading, Out only): *High* when the label has held 4+ weeks and the move is strong (+50% or -25% or more), otherwise *Lower*; low volume is always Lower. Emerging, Peaking and Stable get no confidence level because the backtest gives no evidence for one. A quality indicator, not a probability.

Terms averaging under 5 on Google's scale are flagged low volume. If the term has a Wikipedia article, the last three months of views against the same months a year earlier is shown beside the label, with whether it points the same way.

**Colours.** Nobody searches for "Arabian Spice", so each Pantone colour is matched to the nearest of about 40 everyday colour words ("rust", "sage green") by Delta E in CIELAB. Searches for "&lt;word&gt; outfit" during the season are compared with the same dates a year earlier. Palettes are summarised by mean HSL lightness and saturation and by warm, cool and neutral shares.

**Snapshots.** Google rate-limits scripted requests, so the app never calls it live. `scripts/refresh_trends.py` writes a draft (resumable: a re-run fetches only what is missing) and publishes it only when the run ends, merged with the last good snapshot. Anything a run failed to fetch is carried forward and marked with the date it came from, so a blocked refresh never makes the site worse. Each series records its source, query settings and collection date, and each snapshot carries a run log (methodology version, what was attempted, every failure and why), shown on the How It Works page.

**Data sources as adapters.** `thread/providers/` has one small module per source (Google Trends, Wikipedia). Each returns the same result: `ok`, `empty`, `rate_limited`, `invalid` or `error`, plus the query settings and a reason. A network error or an odd response becomes a recorded value, never a crash, and every adapter is tested with saved responses, no internet needed.

## Results

From the committed snapshot of 13 November 2026 (worldwide). Reproduce with `python scripts/summarise.py`.

**Coverage.** 33 of 36 terms (Google blocked *barn jacket*, *bomber jacket* and *trench coat* after repeated retries), 17 of 36 colour words, 15 Wikipedia articles. Missing data shows as "n/a" on the site; the next refresh fills it.

**Labels:** 11 Rising, 2 Peaking, 15 Stable, 2 Fading, 3 Out.

| Biggest risers | Year on year | | Biggest fallers | Year on year |
|---|---|---|---|---|
| ballet flats | +105% | | old money aesthetic | -45% (Out) |
| capri pants | +93% | | office siren | -28% (Out) |
| barrel jeans | +83% | | mob wife aesthetic | -26% (Out, low volume) |
| sheer dress | +72% | | adidas samba | -14% (Fading) |
| maxi skirt | +62% | | clean girl aesthetic | -11% (Fading) |

**Do the labels mean anything? Backtest.** For every term and past week with enough history, the label was recomputed from only the data known that week and checked against the year-on-year change 12 weeks later (`python scripts/backtest_labels.py`, 33 terms, 6,036 label-weeks):

| Label | Weeks | Still up year on year 12 weeks later | Median year-on-year change then |
|---|---|---|---|
| Rising | 2,614 | 93% | +58% |
| Emerging | 239 | 95% | +23% |
| Peaking | 1,125 | 80% | +13% |
| Stable | 902 | 62% | +6% |
| Fading | 994 | 16% | -14% |
| Out | 162 | 18% | -37% |

77% of Rising labels were still up 25% or more 12 weeks later, against 44% for all weeks (1.76 times the base rate); 67% of Fading/Out labels were still down 10% or more, against 18% (3.6 times). Labels change from one week to the next 6.5% of the time (5.4% before Emerging was added).

**Methodology 1.1: Emerging and confidence, tested out of sample.** Both were chosen using weeks before 2025 and then checked on 2025-26, which they had not seen. Emerging reached Rising strength within 12 weeks 42% of the time there, against a 25% base rate (44% vs 18% over all weeks). High-confidence Rising labels held 83% vs 70% for lower confidence; for Fading/Out, 83% vs 45%. A three-level confidence scale and "sticky" labels (hysteresis) were tried and rejected: the middle level did not hold up on unseen data, and sticky labels changed less often but were less accurate.

 So the labels capture momentum that usually lasts a few more months. They do not predict which new item breaks out next, weekly observations of one term overlap, and the hand-picked 2026 term list flatters them. An earlier quick check that compared the next 12 weeks with the previous 12 suggested the labels were a coin flip; that comparison mixed seasons (autumn vs winter), which the year-on-year version removes.

**The second signal disagrees more often than it agrees.** Wikipedia views point the same way as Google searches for only 5 of the 13 terms with both signals (for example *adidas samba*: Google -14%, Wikipedia -42%; *skinny jeans*: Google +38%, Wikipedia -26%). Encyclopaedia readers and shoppers are different audiences, so the site shows the Wikipedia figure beside each label instead of mixing it into the label.

**Colours of the season (Autumn/Winter 2026/27).** Searches for "&lt;word&gt; outfit" from 1 September to 1 November 2026 against the same weeks of 2025:

| Pantone colour | Reads as | Change | | Pantone colour | Reads as | Change |
|---|---|---|---|---|---|---|
| Acacia | butter yellow | +204% | | Toffee | brown | +25% |
| Red Mahogany | chocolate brown | +89% | | Egret | cream | +18% |
| Burnt Olive | forest green | +30% | | Candied Ginger | khaki | -4% |
| Arabian Spice | brown | +25% | | Festival Fuchsia | fuchsia | -39% |

Against last season (Spring/Summer 2026), the palette swapped beige, burgundy, plum, sage, teal and terracotta for browns, khaki, olive, mint, grey and fuchsia. Against the same season a year earlier (Autumn/Winter 2025/26) it is a little less saturated (0.39 vs 0.45) and less warm (67% vs 73%). Next season (Spring/Summer 2027) is the lightest and most saturated of the four (0.57 lightness, 0.56 saturation).

| Season | Lightness | Saturation | Warm | Cool | Neutral |
|---|---|---|---|---|---|
| Autumn/Winter 2025/26 | 0.50 | 0.45 | 73% | 20% | 7% |
| Spring/Summer 2026 | 0.51 | 0.41 | 62% | 31% | 6% |
| Autumn/Winter 2026/27 | 0.50 | 0.39 | 67% | 27% | 7% |
| Spring/Summer 2027 | 0.57 | 0.56 | 67% | 27% | 7% |

<img src="docs/colours.jpg" alt="Colours of the Season page with Pantone swatches and search changes" width="100%">

## Getting Started

```bash
pip install -r requirements.txt
python app.py                        # http://localhost:5004, reads the committed snapshot
python -m pytest                     # 65 tests, no network needed
```

Settings are environment variables; see `.env.example`. Without `SECRET_KEY` the app creates one once in `instance/secret_key` (git-ignored), so wardrobes survive restarts.

Refresh the data (takes 10 to 20 minutes because of rate limits; re-run if some terms come back empty, and set `TRENDS_PAUSE=15` or more if Google keeps refusing):

```bash
python scripts/refresh_trends.py     # draft while running, publishes data/snapshots/<today>.json at the end
python scripts/backtest_labels.py    # re-runs the label backtest, writes data/backtest.json
python scripts/summarise.py          # prints the tables in this README
python scripts/build_palettes.py     # re-reads the Pantone reports into data/palettes.json
```

Terms live in `data/dictionary.json` (the Fashion Dictionary): add an entry with an id, name, slug, Google query, category, definition and aliases, and the tests validate it. The Dictionary page lists every term with search by any of its names.

Candidate terms live in `data/dictionary_proposed.json`, generated by `python scripts/import_fashionpedia.py` from the Fashionpedia ontology: 277 garment names, silhouettes, lengths, necklines, sleeves, fastenings, finishes, patterns and materials. They are searchable and listed on the Dictionary page as proposed, but are not tracked and have no definition. To promote one, move it into `dictionary.json`, write a definition and set its status to active. Four Fashionpedia names were already tracked (bomber jacket, cargo pants, capri pants, trench coat), and 13 placeholders such as "no opening" are skipped. Top-level categories carry their [Google Product Taxonomy](https://www.google.com/basepages/producttype/taxonomy-with-ids.en-US.txt) id as a cross-reference.

### Brand Watch

Brands live in `data/brands.json`. Ambiguous names use a Google Trends *topic* id, because the word "Celine" mostly finds Celine Dion and "Coach" finds buses and sports coaches; topics were picked from Google's own suggestions. Unambiguous names (Dior, Burberry, Bottega Veneta, Stone Island, Dries Van Noten) use plain search words, because their topics turned out to be broken: Google had remapped them, and the series showed sudden permanent jumps (Burberry's quarterly level went from 9 to 37 to 78, then fell to 6) that no real change in interest explains.

`level_break()` now checks every brand series for this: a 13-week level that changes 2.5 times or more against the previous 13 weeks, without the same jump a year before or after (Moncler's winter peaks pass, Burberry's remapping does not). A broken series gets no label, and the page says why. A human can also hold a series after review (`search_hold`): Hermès is held because its only usable topic, a small "jewellery company" entity, grew steadily from 8 to 31 while its Wikipedia views fell, which looks like Google moving searches onto it rather than real interest. Hand-entered facts live in `data/brand_facts.json`, and `thread/brands.py` validates both.

The page keeps two rules:

- **Broken is not data.** A series that fails the break check shows as unreliable, not as Rising or Out.
- **Missing is missing.** A brand with no search series shows "no search data yet", not Stable; Louis Vuitton and Hermès show "not ranked" by Lyst, not rank 0; private houses (Chanel, The Row, Khaite, OTB) have no figures, and none are estimated.
- **Money keeps its scope.** Every figure is labelled group, segment or brand, with the growth basis the company used (reported, organic, comparable, constant currency). The reason is in the data: Prada Group grew 15% at constant currency in the first nine months of 2026, but 11 points of that came from buying Versace (4% organic), and the Prada label's own retail sales grew 2%.

Headlines come from the WWD, Business of Fashion and Vogue RSS feeds: only the headline, link, date and feed name are stored, the archive grows with each refresh (90 days kept, duplicates merged by link), and a brand counts as mentioned when its name appears in a headline, ignoring accents, minus phrases such as "Celine Dion". Wikipedia views are down for almost every brand year on year, so the page shows the median brand beside them.

### Editions

Each published snapshot is an edition. `/edition` is the latest, `/edition/<day>` any earlier one and `/editions` the archive. `thread/edition.py` writes the front page from that day's data only: the biggest riser and faller among terms with enough volume (none is invented when nothing rises or falls), up to three more Rising or Emerging terms, the brands with the largest search moves in each direction (brands with a broken or held series never qualify), and the newest headlines that name something tracked. Hand-entered facts are not stored per day, so an edition shows the Lyst ranking only if it was entered on or before the edition's date.

### News Desk

`/news` shows the headline archive by day. `thread/news.py` merges a headline that several feeds ran (by its words, ignoring punctuation and case) and tags it with every brand, owner group and reviewed dictionary term it names, using the same whole-word, accent-insensitive matching as Brand Watch; proposed dictionary terms are left out because words like "dot" and "check" would tag nonsense. Tags and feeds work as filters, and a side panel counts the most-mentioned tags over 30 days. On the first archive, 139 headlines, none named a tracked trend term: trade headlines are about companies, not "barrel jeans", which is itself a finding.

Refresh brands and news alone with `python scripts/refresh_trends.py --brands`; everything else is carried forward. A second refresh on the same day only fetches what is still missing.

## Data and Licences

| Data | Use | Terms |
|---|---|---|
| Google Trends, via [pytrends](https://github.com/GeneralMills/pytrends) 4.9.2 | Weekly search interest | Public Google data; pytrends is unofficial and archived (April 2025), so refreshes can break |
| [Wikimedia pageviews API](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/) | Monthly article views | CC0 data, official API |
| [Fashionpedia](https://fashionpedia.github.io/home/) ontology (Jia et al., ECCV 2020) | Names of proposed dictionary terms | Annotations under CC BY 4.0, credited on the Dictionary page; images are not used |
| [Google Product Taxonomy](https://www.google.com/basepages/producttype/taxonomy-with-ids.en-US.txt) (2021-09-21) | Category ids as a cross-reference | Only the numeric ids are stored |
| [Lyst Index](https://www.lyst.com/the-lyst-index/) Q3 2026 | Brand ranking | Hand-entered facts (rank, brand, Lyst's reported move) with a link; no text copied |
| Company releases: [LVMH](https://www.lvmh.com/en/publications/continued-growth-in-the-third-quarter-of-2026), [Kering](https://www.kering.com/en/news/revenue-for-the-3rd-quarter-of-2026/), [Prada Group](https://www.pradagroup.com/content/dam/pradagroup/documents/investors/9M-2026/Prada-Group-9M26-Press-release.pdf), [Hermès](https://finance.hermes.com/en/publications/third-quarter-2026-revenue/) | Revenue and growth, first nine months of 2026 | Public results; each figure stored with its scope, period, growth basis and source |
| [Pantone Fashion Color Trend Reports](https://www.pantone.com/fashion-color-trend-report), NYFW AW25/26, SS26, AW26/27, SS27 | Season palettes | Only colour names, codes and chip hex values are stored, with links to each report |

## Challenges and Solutions

| Challenge | Solution |
|---|---|
| Google Trends blocks scripted requests after a few dozen queries | Back-off and retry per query, resumable dated snapshots, and an app that only reads snapshots |
| Seasonal items (boots in October) look like trends | Compare the last 12 weeks with the same 12 weeks a year earlier, not with the previous 12 weeks |
| Google's numbers are relative, not absolute | Each term is fetched on its own, so year-on-year ratios are within one series |
| Pantone colour names aren't searched | Nearest everyday colour word by CIELAB distance; the distance is kept so poor matches are visible |
| Short spikes shared by unrelated terms (mid-February 2026) | Labels use 12-week means, so one odd week can't decide a label; noted on the site |
| pytrends' retry option breaks on urllib3 2 | Own retry loop with exponential back-off |
| A half-finished refresh replaced good data on the site (the app read the newest file, even with 2 of 33 terms) | Draft then publish; misses carried forward and dated |
| A new random secret key on every start orphaned every reader's wardrobe | Key from `SECRET_KEY` or generated once into `instance/` |
| "Is a label worth anything?" was untested | Backtest against base rates, year on year so seasons don't distort it |
| New label ideas can look good just by chance | Chosen on pre-2025 weeks, reported on 2025-26 weeks they had not seen; ideas that failed (hysteresis, a three-level confidence) were dropped |
| A list of 36 strings had no meaning, aliases or structure | A versioned Fashion Dictionary with stable ids, a category tree and validation; old URLs kept |
| Brand names are ambiguous in search (Celine, Coach, Diesel, Chloé) | Google Trends topic ids instead of search words |
| Some topics broke: Google remapped them and history jumped (Dior, Burberry, Chloé) | A break check that withholds the label, and plain search words where the name is unambiguous |
| GDELT refused every request from this connection (HTTP 429, even after a pause) | News from publisher RSS feeds instead, as an archive that grows each refresh; GDELT kept on the roadmap |
| Group revenue is easy to misread as brand performance | Every figure carries its scope and growth basis; brand figures shown only where the company publishes them |
| Growing the vocabulary without inventing words | 277 proposed terms from the Fashionpedia ontology, kept apart from reviewed terms until an editor promotes them |
| Checking a proposed term's search volume with pytrends | Not possible yet: each series is scaled 0 to 100 on its own, so volume needs a comparison against an anchor term, which costs more rate-limited requests. Waiting for the official Google Trends API, whose consistent scaling makes this a single lookup |

## Roadmap

- Pakistan as a second region (Google Trends `geo=PK`) beside worldwide.
- A scheduled weekly refresh (GitHub Actions) that commits the new snapshot.
- Reddit mentions as a third signal for users who add their own API key.
- The social side of the original idea: a feed where people post outfits and react, on top of the existing SQLite store. The original virtual pet is retired.
- Review the 277 proposed terms: check search volume (with the official Google Trends API once access is granted), write definitions and promote the ones worth tracking. Bags, accessories and jewellery still need a source.
- Brand Watch, next part: GDELT news volume once its rate limit allows (one request per 5 seconds, cached daily), brand pages, and share prices if Alpha Vantage covers Paris-listed stocks.
- News Desk, next part: GDELT discovery once its rate limit allows, more feeds after reading each publisher's terms, and and a weekly scheduled refresh so a new edition appears without anyone running a script.

## Author

**Abdul Rehman Faisal** · BS Data Science, GIKI (2027)
[GitHub](https://github.com/ARFaisal-Rehman) · [LinkedIn](https://linkedin.com/in/abdul-rehman-faisal-2a680b297)

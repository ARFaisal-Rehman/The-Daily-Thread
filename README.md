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

The Daily Thread reads public search data and tells you, in newspaper form:

1. **What is in and what is out.** 36 fashion terms from the project's own Fashion Dictionary (each with a definition, other names and a place in a category tree), labelled Rising, Emerging, Peaking, Stable, Fading or Out from five years of weekly Google Trends data, with a confidence level, Wikipedia page views as a second opinion, and every rule backtested.
2. **The colours of the season.** Pantone's New York Fashion Week palette for the current season, whether people are actually searching for those colours compared with a year ago, what changed from last season's palette, and a preview of next season.
3. **Whether to buy it.** A wardrobe you can fill in and a five-question purchase check that scores a planned buy, using the radar (buying a Rising style means buying near the top of the hype).

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

## Data and Licences

| Data | Use | Terms |
|---|---|---|
| Google Trends, via [pytrends](https://github.com/GeneralMills/pytrends) 4.9.2 | Weekly search interest | Public Google data; pytrends is unofficial and archived (April 2025), so refreshes can break |
| [Wikimedia pageviews API](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/) | Monthly article views | CC0 data, official API |
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

## Roadmap

- Pakistan as a second region (Google Trends `geo=PK`) beside worldwide.
- A scheduled weekly refresh (GitHub Actions) that commits the new snapshot.
- Reddit mentions as a third signal for users who add their own API key.
- The social side of the original idea: a feed where people post outfits and react, on top of the existing SQLite store. The original virtual pet is retired.
- Grow the Fashion Dictionary beyond 36 terms (materials, bags, accessories) and have its definitions reviewed by an editor.
- Brand Watch: brand search interest, Wikipedia and news attention, with group-level company financials kept separate.
- A news desk from GDELT and permitted RSS feeds, deduplicated and tagged by brand.

## Author

**Abdul Rehman Faisal** · BS Data Science, GIKI (2027)
[GitHub](https://github.com/ARFaisal-Rehman) · [LinkedIn](https://linkedin.com/in/abdul-rehman-faisal-2a680b297)

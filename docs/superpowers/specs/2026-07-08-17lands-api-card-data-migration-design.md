# 17Lands `/api/card_data` Migration — Design

**Date:** 2026-07-08
**Branch:** 418

## Problem

The ETL pipeline and desktop client fetch card ratings from
`https://www.17lands.com/card_ratings/data`. 17Lands rebuilt their card data
page and moved the JSON API to `/api/card_data`. The old route still returns
HTTP 200 but is a degraded shim:

- Ignores `colors` — responses with and without `colors=WU` are byte-identical,
  so every archetype in the ETL output was a copy of "All Decks" (caught by
  `server/validate.py`).
- Ignores `time_period` — always serves a small stale snapshot (~2.5K games for
  MSH's most-played card vs ~63K from the real endpoint).
- Nulls out win-rate fields such as `opening_hand_win_rate` (caused the
  TradSealed "0% win rate despite non-zero samples" validation error).

## API changes to absorb

1. Endpoint: `/card_ratings/data` → `/api/card_data` (still on www.17lands.com;
   api.17lands.com remains a different, unsuitable host).
2. Query param rename: `format` → `event_type`.
3. Response shape: bare JSON array → `{"copyright": ..., "notes": ...,
   "data": [...]}`. Card objects inside `data` are unchanged.

`/color_ratings/data` (client + ETL) is unaffected — the new frontend still
calls it with `event_type`, and live requests return correct data.

## Changes

| Location | Change |
|---|---|
| `src/seventeenlands.py:_fetch_archetype_with_cache` | New URL + `event_type` param + unwrap `data` |
| `src/seventeenlands.py:download_card_ratings` | Same |
| `src/seventeenlands.py:build_card_ratings_url` | Same (test-only helper) |
| `server/extract.py:extract_17lands_data` | Same; refresh the stale endpoint comment |

Supporting changes:

- **Cache buster:** raw-cache filenames in `Temp/RawCache` gain a `_v2` marker
  so degraded responses cached in the last 12 hours are not reused. The cache
  keeps storing the unwrapped card array.
- **Defensive unwrap:** accept both a dict payload (`payload["data"]`) and a
  bare list, so older cached arrays and any future un-wrapping keep parsing.
- **Tests:** update mocked URLs and payload shapes in
  `tests/test_seventeenlands.py` and `tests/server/test_extract.py`.

## Rejected alternative

Fallback to the old endpoint on failure: rejected because the old endpoint
fails by returning *misleading* data, not errors — a fallback would silently
reintroduce the corruption the validator just caught. Fail loudly instead.

## Verification

1. Updated unit tests pass (test-first).
2. Live spot-check: MSH PremierDraft `colors=WU` differs from All Decks and
   game counts are full-population.
3. Full ETL run regenerates MSH datasets with validation passing.

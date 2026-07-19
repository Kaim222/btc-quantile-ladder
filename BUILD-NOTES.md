# Build notes — 2026-07-18

## Remediation completed

- Group A root causes: FRED now emits `observation_date` rather than the assumed `DATE`, and row-index arithmetic mixed daily and weekly cadences. The collector now skips `.` values, uses daily-row changes for daily series and calendar-day lookbacks for weekly liquidity series. Missing BTC/FRED correlations and global-M2 construction also prevented otherwise healthy inputs from scoring.
- Stablecoin scoring had incorrectly depended on locally accumulated cache history; every run now reads DefiLlama's all-history chart. Deribit futures summaries expose a result list and `estimated_delivery_price`; the basis parser now selects the nearest quarterly expiry at least 21 days away. Bitcoin-data receives one 30-second retry on 429 and unusable payloads are source failures. Unrecognized Farside markup is explicitly `parse-unrecognized` rather than healthy.
- Added the specified ISM and China/Japan M2 manual observations. Global M2 uses US and euro-area three-month changes in YoY growth plus the manual China/Japan deltas.
- Group C publishes a compact `ledger_recent.json` projection with 250 rows. The page fetches only `latest.json`, `scores.json`, `ledger_recent.json`, and `news.json`; calibration is precomputed in scores. Evidence marked as third-party is surfaced as “published, not ours.”

## Scoring v2 definitions

`scores.json` declares `scoring: "v2-decided-window"`. Composite calls are UP at score >= +10, DOWN at <= -10, and otherwise NEUTRAL; event abstention forces NEUTRAL. Signal calls require absolute score >= 1. Realized windows are UP/DOWN only beyond the unchanged 0.75%/2%/5% deadbands, otherwise NO_DECISION. Directional hit rate includes only windows having both a directional call and directional realization. Call rate, decided rate, decided count, and abstention count expose coverage. Always-up and seven-day-momentum baselines use the identical scored windows. Brier uses realized directional windows only. Edge status compares Wilson bounds with `max(0.5, baseline_alwaysup)`.

## Full-ledger backtest summary

| Horizon | Decided n | Hit rate | Wilson 95% | Call rate | Decided rate | Always-up | Momentum |
|---|---:|---:|---:|---:|---:|---:|---:|
| 24h | 727 | 52.5% | 48.9–56.2% | 39.1% | 69.3% | 53.2% | 46.7% |
| 7d | 1,590 | 48.6% | 46.2–51.1% | 80.7% | 72.4% | 55.0% | 49.0% |
| 30d | 1,446 | 55.1% | 52.5–57.7% | 74.7% | 73.0% | 58.2% | 54.6% |

These are the observed v2 results without tuning. The full ledger was recomputed from stored returns; no outcome history was refetched.

## Acceptance observations

- Fresh collection scored 30 signals; the four unavailable signals were `sth_sopr`, `etf_flow_5d`, `sth_rp_regime`, and `mvrv_z`. Their unavailable upstreams were recorded down (bitcoin-data 429 after retry and Farside `parse-unrecognized`). Three composites were written. A repeat inside four hours did not add a live row.
- `score.py` completed as a clean no-op for live outcome resolution and rebuilt all v2 scores.
- The backfill ledger contains 2,727 backtest rows plus one live row. The follow-up idempotency run appended zero rows.
- Headless Chrome unlocked and rendered all page sections with zero console errors. The only browser messages were the expected Babel-in-browser warning and Chrome's password-form recommendation. All four page data requests returned HTTP 200.
- Payload sizes: `latest.json` 11,761 bytes; `scores.json` 1,626,325; `ledger_recent.json` 304,934; `news.json` 9,905; combined 1,952,925 bytes (1.86 MiB).
- `signals.html` contains no request for `data/ledger.json`. Rolling histories retain at most 365 points and weekly-decimate observations older than 90 days.
- `index.html` remains a 10-addition/4-removal surgical diff versus HEAD. No commit or push was made.

## Endpoint notes and review flags

Coinbase, CoinGecko, Alternative.me, OKX, Deribit, FRED, ECB, DefiLlama, Blockchain.com, Wikimedia, and reachable RSS feeds returned successfully during verification. Bitcoin-data was intermittent/rate-limited: available payloads used named fields, while final failed retries were recorded unhealthy. Farside returned a page but no recognized stable table shape, so ETF flow conservatively abstains and reports parser failure.

The source ledger remains intentionally complete and large; only the compact projection is browser-facing. Historical targets remain Coinbase daily closes. The pre-existing client-side FormSubmit `token` field in the ladder was not changed under the surgical index constraint.

## Files touched

`signals.html`, `index.html`, `README.md`, `BUILD-NOTES.md`, `collector/collect.py`, `collector/score.py`, `collector/backfill.py`, `collector/lib.py`, `config/weights.json`, `config/manual.json`, `config/calendar.json`, `config/signals-meta.json`, `data/latest.json`, `data/ledger.json`, `data/ledger_recent.json`, `data/scores.json`, `data/news.json`, `data/pricecache.json`, `data/stablecache.json`, and `.github/workflows/collect.yml`.

## Post-review fixes (2026-07-18, skeptic pass)

Skeptic verdict on the fix build was FIX with one blocking + two substantial findings; all addressed:

1. **Backtest look-ahead purge (blocking).** `backfill.py` had applied today's `config/manual.json` values (dat_stress, polymarket_ye, gli_phase, cwac_analyst, ism_regime — ~20% of d30 weight) to every historical day. All 2,727 backtest rows were purged and regenerated with the five operator signals excluded (weight renormalized away), making backtest rows strictly point-in-time. README claim updated to match. New pooled table:

   | horizon | n | hit rate | Wilson 95% | call rate | always-up | momentum | status |
   |---|---|---|---|---|---|---|---|
   | 24h | 727 | 52.5% | 48.9-56.2% | 39.1% | 53.2% | 46.7% | NO_EDGE |
   | 7d | 1,592 | 48.6% | 46.2-51.1% | 80.8% | 55.0% | 49.0% | BELOW_BASELINE |
   | 30d | 1,551 | 56.0% | 53.5-58.5% | 79.2% | 58.5% | 54.6% | BELOW_BASELINE |

   The static backtested composite does not beat always-up; the dashboard displays that verdict. Live tracking + Wilson-gated weight evolution is the path to earning (or refusing) edge claims.

2. **Tiny-n drill-down guard (substantial).** Signal-table measured-record text now requires n≥30, matching the gauge Stat component ("warming up (n=X)" below that) — a 100%-at-n=11 stat can no longer render as if meaningful.
3. **Threshold disclosure (substantial).** Gauge tilt now has LEAN UP/LEAN DOWN states between ±10 and ±20 (aligned to the scored-call boundary) and the methodology footer documents the label bands explicitly.
4. Edge-status classifier corrected earlier the same evening: the fall-through case (Wilson upper bound below baseline) now reports BELOW_BASELINE instead of PROMISING.
5. Added `.gitignore` (`__pycache__/`, `*.pyc`). Repaired double-encoded UTF-8 in signals.html (two-pass latin-1/cp1252 round-trip).

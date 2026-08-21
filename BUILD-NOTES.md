# BTC Quantile Ladder — Build Notes

## v2 (Aug 2026) — 4-tier PMCC ladder

**Live:** https://kaim222.github.io/btc-quantile-ladder/ (passcode 4241)
**Monitor:** github.com/Kaim222/btc-monitor (private) — GitHub Actions, every 15 min

### Ladder

| Band | Position | Long anchor | Short anchor |
|---|---|---|---|
| 0–15q | MSTX PMCC | 0.1q @ ~6 mo | 15q @ ~3 mo |
| 15–50q | MSTR PMCC | 15q @ ~9 mo | 50q @ ~6 mo |
| 50–85q | IBIT PMCC | 50q @ ~12 mo | 85q @ ~9 mo |
| 85–100q | STRC on 1.5× margin | — | — |

One position per band — no intra-band sizing. Strikes are quantile-anchored:
long = band floor projected on the power-law curve at the long expiry, short =
band ceiling at the short expiry. The short strike doubles as the rotation
trigger. Strikes shown BTC-level; MSTR/MSTX translation lives in the mapping
workbook (mNAV + leveraged-ETF decay drag baked in there).

Rotation uses **±1.0q hysteresis**: the monitor fires only when quantile crosses
a band boundary by more than 1 point (state in `state.json`, held band
persists inside the buffer). The app shows both rotation trigger prices in the
tier card and a buffer badge when within 1q of a boundary.

STRC band: shares only, 1.5× margin framework — ~15.6% net carry on equity at
12% yield / 4.75% margin rate, margin call at −33% (STRC ≈ $67 from par,
50% maintenance). Par break usually coincides with the preferred-ATM stall.

### Model
Kaim Power Law: A=5.82, B=−17.029, genesis 2009-01-03.
Band offsets per BAND_DEFS (99.9/95/85 decay linearly, frozen at today for
forward projections; 50/15/0.1 constant). `quantileToPrice` inverts
`priceToQuantile` by interpolating offsets in quantile space — round-trip
exact within the 0.01–99.99 clamps.

### Removed in v2
SIGNALS page, EO TRACKER page, collector/, config/, data/ (stale since Jul).
IBIT Shares and EPD tiers. All sizing/split/scaling machinery. Delta-ladder
SHORT_LEG config. Income converter + margin.json (v2.3). Unused QuantileGauge.

v2.3 also replaced the tier chip row and band dial with a quantile rail:
full-width 0-100 bar, four band segments, needle at current quantile.

### Revert
`index_v6tier_backup.html` (this repo) and `monitor_v6tier_backup.py`
(btc-monitor repo) — copy back over index.html / monitor.py.

### Price feeds
CoinGecko primary, Coinbase spot fallback (app + monitor).

### Pushover format (v2)
```
Title: 🪜 MSTX PMCC → MSTR PMCC

Bitcoin $86,300  ·  Quantile 16.1%

Position
MSTR PMCC

Structure
Long 15q · May 2027 · ~$108K BTC
Short 50q · Feb 2027 · ~$162K BTC
```

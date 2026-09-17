# BTC Quantile Ladder — Build Notes

## v2 (Aug 2026) — 4-tier PMCC ladder

**Live:** https://kaim222.github.io/btc-quantile-ladder/ (passcode 4241)
**Monitor:** github.com/Kaim222/btc-monitor (private) — GitHub Actions, every 5 min (cron `*/5`, 13:00-21:59 UTC weekdays; the script keeps itself to 9:35-16:00 New York)

### Where the thresholds live

`data/mstr-config.json` in this repo is the single source of truth for the alert lines and the slope: `lag_threshold` -0.015 (-3% MSTX), `cheap_threshold` -0.03 (-6% MSTX), `rich_threshold` 0.04 (+8% MSTX), `btc_slope_per_2500` 0.0125, `regime_gate` false. The monitor fetches that file raw from GitHub on every run and falls back to its own `mstr_config.json` only if the fetch fails, so the two files must agree. Holdings and the assumed diluted share count come live from api.strategy.com and are never edited by hand; `btc_held` and `shares_m` stay `"auto"` unless you deliberately override.

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

## v3 (Sep 2026) · Playbook tab

A tab row sits under the header: LADDER | PLAYBOOK. State lives in `localStorage`
under `bql_tab`. LADDER renders exactly what v2 rendered. The passcode gate,
the model selector and the light-mode toggle are shared by both tabs.

### PLAYBOOK tab · the daily card

The tab is one card, written in the ladder tab's own visual language. Five stat
tiles run across the top: the regime and its ticker off the ladder's tier for the
live quantile, the quantile with its band word, IV rank (a hand-entered 52-week
rank first, then the ledger-window rank labelled with its window length, then
"unknown"), the trigger as one word coloured by state, and the days to the next
known event, each with a short phrase under the value. The regime tile is tinted
with the tier colour the way the ladder's quantile card is. Under the tiles sits
one action sentence in a tier-card callout with a left accent in the trigger
colour, chosen in a fixed order: above the 85th band it says STRC per the ladder,
an unknown IV rank stops the day, OFF and HOLD say what not to open, and ENTRY
with fewer than three verticals open and no red expiry inside the last ten
trading days prices a paper call, halved when a known event falls inside two
weeks. It always ends "Sleeve is paper." while nothing is adopted. Then the
allocation bar: one rounded target bar at the 45 / 30 / 25 split in the tier
palette, with a thinner deployed bar drawn beneath it at whatever three hand
fields say is deployed, reading "not filled" until they are. Then the positions
as a structure-panel list, one row each with a status dot, the position written
as text, and the failing rule in three words when the dot is red. The LEAPS leg
is green when its net debit is under the strike width and its ticker matches the
regime, and up to three verticals are green when the debit is under the strike
gap, no two share an expiry, and the expiries sit ten trading days apart. Every
input hides behind a pencil, so the card shows no input boxes until one is
clicked. A price counts only when it came from the live feed, a hand entry, or
the refresh's close, so the ladder's 85,000 render seed is never shown as a
market price and every number off a BTC level reads "unknown" without one. One
footer line closes the card. "Paper ledger" carries the count of paper calls and
opens the journal as a text table, with the sleeve fields, the copy-as-JSON
button, and an input row that appears only after "+ row". "Why" opens the two
weekly inputs with a hand override each, the IV rank hand field, and the refresh
timestamp. Both panels stay closed until clicked, and every hand field persists
in `localStorage` under a `bql_pb_` key. The rule card, the backtest notes, the
long note strings, the two stack verdicts, the ENTRY WEEK line, the events list
and the gate list left `index.html`: the rules live in `doctrine.md`, which is
not on this site.

**The trigger inputs, 2026-09-13.** The 9/13 vertical-trigger backtest found
nothing adoptable in 397 candidates and named one pair as the closest thing, so
`tools/playbook_rules.json` (v3, nine components) carries it as `paper_trigger`
and keeps the superseded 9/12 composition as `paper_trigger_previous`.
`btc_weekly_macd_8_21_5_hist_rising` runs MACD(8,21,5) over completed
Monday-to-Sunday UTC weekly bars built from the Yahoo daily closes, drops the
in-progress week, seeds the EMAs on their first value, and passes when the last
complete bar's histogram is above zero and above the prior bar's.
`btc_weekly_macd_8_21_5_fresh_cross` asks the same bars whether the histogram
turned positive inside the last three, which is the entry-timing cell and the one
cell that cleared the adoption bar; it sits outside `paper_trigger` under
`entry_timing`. `ladder_quantile` is the page's own `priceToQuantile` ported into
the refresh script, scored at the Yahoo daily close, passing at 85 or below and
carrying its band label; the script's self-test pins the port to the 9.303rd
quantile the site read at BTC 77,200 on 2026-09-12. Those two weekly inputs are
what the card's trigger word reads. Nothing is adopted, so the funded stack
cannot go live and the sleeve stays on paper.

### Refresh script

`python tools/playbook_refresh.py` (run from the repo root) pulls MSTR, MSTX and
BTC-USD from Yahoo through yfinance, pulls the 30-day implied-vol series from
AlphaQuery, and writes `data/playbook.json`:

- BTC close, 200-day SMA and above flag
- BTC 200-week SMA over completed calendar weeks and above flag
- MSTR close, weekly MACD(12,26,9) versus signal, completed weeks only

A calendar week ends Sunday 23:59:59 UTC and counts as complete only when that
Sunday falls strictly before the current UTC date's 00:00, so a run on a Sunday
excludes the week it is still inside. Both the 200-week SMA and the weekly MACD
use that cutoff. A self-test in the script asserts it against a Sunday fixture
(2026-09-13 resolves to the week ending 2026-09-06) and runs on every refresh.
- MSTR hidden bullish divergence: a higher swing low with a lower RSI(14) at the
  two lows, swing low = lowest low with 5 bars each side, pairs inside a 20-bar
  window, confirmed inside the last 10 bars. RSI is Wilder's, initialized on a
  simple average of the first 14 changes and then smoothed recursively: the first
  14 bars are NaN, a zero average loss reads 100, and a pair with a NaN reading
  at either low is skipped rather than compared. The earlier version filled every
  NaN with 50, so a monotonically rising series read a neutral 50 and the warm-up
  did too
- MSTR Bollinger width percentile (20-day, 2 sigma, width / mid, percentile over
  the trailing 252 days, tight below 20)
- MSTR 20-day realized vol and its percentile over the trailing 252 days
- MSTR and MSTX Yahoo daily closes, which seed the mapping box's "now" fields
- MSTR ATM 30-day implied vol from the Yahoo option chain (one row, informational)
- an `iv` block: 30-day implied vol for MSTR, MSTX and IBIT from AlphaQuery's
  keyless `option-statistic-chart` endpoint (browser User-Agent plus the matching
  Referer, JSON `[{x, value}]`, value a fraction), each ticker's ledger window
  (n days, first and last date, min, max), an IV rank over that window, and the
  MSTX/MSTR IV ratio. A failed pull writes null plus the error string.
- the next three events from `tools/events.json` with days-to, each carrying its
  source URL and verified flag
- the backtest status, adopted flags and `paper_trigger` from
  `tools/playbook_rules.json`

**IV rank honesty.** AlphaQuery's free tier returns about 63 trading days, so the
rank is a 3-month rank and is labelled "rank over N days, not 52 weeks" wherever
it appears. The window is the trailing 252 AlphaQuery entries at most
(`IV_RANK_WINDOW`), so a multi-year ledger ranks the last year of readings rather
than every reading on file, and it is called a 52-week window only at a full 252
entries. No rank is computed under 30 entries. That is why the ledger
exists: each run merges the rolling window in and the history grows past what one
call returns. `data/iv-ledger.json` is keyed ticker, then date, then source, and
it is append-only: an entry already on file for that ticker, date and source is
never overwritten. Keying by source is what lets a Yahoo option-chain reading and
an AlphaQuery observation share a date, which the earlier date-only key did not:
whichever landed first blocked the other, usually Yahoo blocking the series the
rank is computed from. The pre-v3 flat MSTR list and the date-only shape that
followed it are both migrated on first run. The rank window uses the AlphaQuery entries only; the
Yahoo option-chain entries stay in the ledger but are excluded from the min/max,
because Yahoo's ATM chain vol and AlphaQuery's 30-day mean are different
constructions and a range that mixes them ranks nothing. The page prefers, in
order, a hand-entered 52-week rank from the broker, then the ledger-window rank
with its window label, then "unknown", and prints one muted outside
reference beside it (projectoption 2026-09-11: 30-day IV 67.3%, 52-week 49.2% to
120.6%, rank 25, percentile 29, a single source, un-cross-checked).

**A stale reading is labelled stale.** An implied-vol fetch that fails does not
silently reuse the old number. The ticker's window is still computed from the
ledger, which is what the ledger is for, but the block carries `error`,
`as_of_fetch: null` and `stale: true`, and `iv.stale` goes true for the run, which
is what the ledger window reports. The MSTX/MSTR IV ratio is computed only when
the two readings carry the same observation date, and is null with the two dates
named when they differ. A BTC or MSTR download failure writes `btc_price` and
`mstr_price` as null plus the error string rather than omitting the key, so the
page can tell "the source failed" from "nobody asked".

**A field is never a fabricated number.** Every source is wrapped, and a source
that fails writes `value: null` plus an error string, which the card renders as
"unknown" on a state line and "fill by hand" on a hand field. A missing
`data/playbook.json` renders "refresh not run" in the why panel and the card
still works on its own hand inputs.

### Files

| File | What |
|---|---|
| `index.html` | tab row, `PlaybookTab`, the daily card |
| `tools/playbook_refresh.py` | the refresh script |
| `tools/events.json` | hand calendar, every row carries a `verified` flag, a source URL and a note |
| `tools/playbook_rules.json` | v3: eight trigger components with their backtest status and adopted flag, plus `paper_trigger` and `paper_trigger_previous` |
| `data/playbook.json` | generated, the page's live inputs plus the `iv` block |
| `data/iv-ledger.json` | generated, append-only implied-vol history, keyed ticker, then date, then source |

Yahoo data is delayed and unofficial, and the option-chain implied vol is
Yahoo's own field. The page states no quote: live numbers come from the chain
and the P/L tool.

### Calendar, 2026-09-12

Every row verified against the primary source except MSTR earnings: FOMC 9/16,
10/28 and 12/9 and CPI 10/14, 11/10 and 12/10 come from federalreserve.gov and
bls.gov. MSTR earnings 11/4 is a third-party calendar (tipranks) and stays
`verified: false` with the note "third-party calendar; confirm on the IR page",
because the company IR page was unreachable. The card names only the next event and its days
out. The flags stay in the JSON.

### Backtest status, 2026-09-12

Nothing is adopted. Hit rates are signal-on versus signal-off over MSTR trading
days 2020-01-02 to 2026-08-26 on a forward 10-trading-day return:

| Component | Status | Reading |
|---|---|---|
| BTC above 200-day | UNPROVEN | 50.5% on vs 54.4% off |
| BTC above 200-week | UNPROVEN | 51.0% vs 58.8% off, on 86% of days |
| MSTR weekly MACD above signal | UNPROVEN | 50.8% vs 53.3% off |
| MSTR hidden bullish divergence | UNTESTABLE | 11 events in 6.7 years |
| MSTR Bollinger width bottom quintile | NEGATIVE | 40.6% vs 52.6% off; added to the trend stack it cut the hit rate to 31% |
| MSTR realized-vol rank 70 or above | PROMISING | 54.8% vs 47.7% off, n_eff 45 |

This study's `paper_trigger` was the trend trio plus realized-vol rank at 70 or
above, all passing. It was the two PROMISING readings from the study and nothing
more: no component is ADOPTED, so the funded stack cannot go live and the sleeve
stays on paper until the 8-week record beats implied odds. The 2026-09-13
research replaced it as `paper_trigger` and it now sits in the same file as
`paper_trigger_previous`, kept for the record and no longer scored on the page.

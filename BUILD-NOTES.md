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

## v3 (Sep 2026) · Playbook tab

A tab row sits under the header: LADDER | PLAYBOOK. State lives in `localStorage`
under `bql_tab`. LADDER renders exactly what v2 rendered. The passcode gate,
the model selector and the light-mode toggle are shared by both tabs.

### PLAYBOOK tab

Static rules first, live inputs second.

1. **Rule card.** An allocation line, then R1 to R5, rendered from the
   `PLAYBOOK_RULES` constant at the top of the script. R1 hold, R2 entry after a
   rotation, R3 vertical-sleeve FIRE, R4 NO TRADE, R5 refill. The text is fixed
   and versioned (v3, 2026-09-12); it changes only between sessions, never
   mid-trade. The allocation line above R1 is the frame the sizing rules sit in:
   LEAPS leg 40 to 50% of the account, cash floor 30% and never deployed,
   vertical sleeve the rest and paper until the eight-week record beats implied
   odds. v3 settles the sizing and the sleeve limits. The LEAPS leg is 40 to 50%
   of the account in R1 and R2, sized so a 50% drop in the underlying does not
   touch the 30% cash floor. An R3 vertical is the smaller of 5% of the account
   and half-Kelly on the sleeve. The open-vertical cap drops from 5 to 3 in R3,
   R4 and the sleeve table. R5 refills the sleeve from its own realized profits
   or its own undeployed reserve on the first trading day of the month, never
   from the cash floor, and a sleeve that has spent its reserve is dead until a
   session re-funds it. v3 keeps the 9/12
   study's conclusions: R3 structure splits on *dated versus undated* rather
   than on IV rank alone (a dated thesis of six weeks or less takes a vertical at
   any IV rank; the diagonal is the preferred shape only under IV rank 30 with a
   tail past the date; an undated thesis needs IV rank under 50), R3 exit is 75%
   of max profit with sell-half-at-100% ruled out, R3 reinvests 25% with 50%
   ruled out, R4's undated-thesis block moves from IV rank 30 to 50, and R2
   carries the IV-rank scale line (low under 30 is a 30-day IV under about 71%,
   high over 50 is over about 85%, on the 2026-09-11 52-week range).
2. **Ladder inputs.** Quantile, regime ticker, distance to each rotation
   boundary in quantile points and BTC dollars, buffer flag. Same
   rotateUp / rotateDown and 1.0q hysteresis the tier card uses, recomputed in
   the tab off the price the tab is allowed to use rather than taken from the
   ladder tab, so a quantile is never printed beside a level from a different
   price. **The tab never renders the render seed as a price.** The ladder's price
   input starts on a hard-coded 85,000 so the page has something to draw before
   any fetch returns. A price counts here only when it came from the live feed,
   from `btc_price` in `data/playbook.json`, or from a hand entry, and with none
   of those the card reads "no live price yet" and every number off a BTC level
   stays blank: quantile, ticker, buffer, the rotation rows, the short strike and
   the whole mapping output. A "BTC price by hand" field in the mapping box
   unblocks the tab, and the card prints which of the four the number came
   from.
3. **LEAPS leg rule for today.** Ticker by regime, the 0.60-delta long rule, and
   the short strike as the regime-exit BTC price at the short's expiry
   (`quantileToPrice(tier.qMax + HYST, todayTs + 16 months)`). The mapping box
   below it defaults to the operator's projection sheet of 2026-09-12, holdings
   845,050, diluted shares 450,121,000, chop 1.85, and every default is
   labelled "from your sheet, 2026-09-12". mNAV is not hand-seeded: it follows
   the sheet's own rule, `0.9 + (BTC − 75,000) / 100,000` clamped to 0.65 and
   1.525, evaluated at the exit BTC price, with a hand override field beside it.
   MSTR now and MSTX now default to the Yahoo closes in `data/playbook.json`
   (130.97 and 14.01 as of 2026-09-11, labelled Yahoo delayed), each with a hand
   override. The MSTX mapping is the sheet's **power** form,
   `MSTX_exit = MSTX_now × (MSTR_exit / MSTR_now) ^ chop`, not a linear multiple
   of the MSTR move, and it carries the standing caveat that 1.85 is a ceiling
   for a two-week rally (plan 1.8, stress 1.6, selloffs about 2.1) and that
   daily-reset drag over 16 months makes the mapping optimistic. Every derived
   number is labelled "from your sheet inputs". Empty fields read "fill by hand"
   and never a placeholder number. The mapping's localStorage key is
   `bql_pb_mapping_v2`: v1 shipped invented defaults, and the key had to move for
   the sheet's figures to land in a browser that already stored the old shape.
4. **Trigger inputs.** Eleven rows from `data/playbook.json`, each with value,
   pass or fail, source, as-of date, a status chip, and a hand override that
   marks the row "by hand". Status is the 9/12 backtest verdict from
   `tools/playbook_rules.json`, gold for PROMISING, red for NEGATIVE, muted for
   UNPROVEN and UNTESTABLE; the Bollinger row stays visible with its NEGATIVE
   chip rather than being dropped, and each component's one-line reading prints
   under the table. Realized-vol rank now carries a pass/fail at the 70
   threshold instead of being context only. The last three rows (MSTR 30-day IV,
   MSTX 30-day IV, MSTX/MSTR IV ratio) read the `iv` block, are informational,
   and show a dash in the pass and override columns. An implied-vol pull that
   failed on the last refresh still shows its newest ledger reading, dated by its
   own observation date, and carries a STALE chip plus a one-line reason instead
   of passing an old number off as today's. BTC above its 200-day is
   also computed in the page from the 365-day CoinGecko history, and both
   readings show when both exist. Then **two** verdicts: FUNDED STACK, from the
   adopted components only, which reads "no adopted trigger; sleeve cannot be
   funded" while nothing is adopted, and PAPER STACK LIVE / NOT LIVE from the
   rules file's `paper_trigger` (the trend trio plus realized-vol rank at 70 or
   above), naming the failing components. When the paper stack is live the page
   says to log a paper call in the sleeve state and score it at 10 trading days
   against the implied probability.
5. **Sleeve state.** Hand-kept: balance, open verticals (up to three, implied
   probability = debit / width), last expiry, paper gate, refill date. Produces
   CAN FIRE / CANNOT FIRE with every gate from R3 and R4 listed. The R3 trigger
   gate is the FUNDED stack, so the sleeve cannot fire real size while nothing is
   adopted. **The paper gate counts weeks, not rows.** It passes only when the
   journal's paper rows span 56 calendar days or more from the first dated row to
   the last, at least eight rows carry a scored outcome, and the hit rate over
   those scored rows beats their average implied probability. Eight rows logged
   the same afternoon are one afternoon, so the span is a hard requirement and it
   can only be read off dated journal rows. The three hand fields stay as a
   running tally and leave the gate unknown, because a hand-entered count carries
   no dates. The "10 or more trading days since the last entry" gate skips
   weekends and a US market holiday list for 2026 and 2027 (New Year's Day, MLK
   Day, Presidents Day, Good Friday, Memorial Day, Juneteenth, Independence Day
   observed, Labor Day, Thanksgiving, Christmas observed), so a shut market never
   counts toward the wait, and the refill date is the first trading day of next
   month off the same list.
6. **Journal.** Hand rows for closed trades with a copy-as-JSON button. Each row
   carries a paper-or-funded field. When any row is marked paper the paper-gate
   counters (calls, hits, implied average) are computed from those rows. A
   result reading hit, win, green or yes counts as a hit, the implied average is
   the mean of debit ÷ width. The three hand fields say they are ignored.
   With no paper rows the hand fields still drive the gate.

Every hand-filled field persists in `localStorage` under a `bql_pb_` key.

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
with its window label, then "fill by hand", and prints one muted outside
reference beside it (projectoption 2026-09-11: 30-day IV 67.3%, 52-week 49.2% to
120.6%, rank 25, percentile 29, a single source, un-cross-checked).

**A stale reading is labelled stale.** An implied-vol fetch that fails does not
silently reuse the old number. The ticker's window is still computed from the
ledger, which is what the ledger is for, but the block carries `error`,
`as_of_fetch: null` and `stale: true`, and `iv.stale` goes true for the run, which
is what the tab's STALE chip reads. The MSTX/MSTR IV ratio is computed only when
the two readings carry the same observation date, and is null with the two dates
named when they differ. A BTC or MSTR download failure writes `btc_price` and
`mstr_price` as null plus the error string rather than omitting the key, so the
page can tell "the source failed" from "nobody asked".

**A field is never a fabricated number.** Every source is wrapped, and a source
that fails writes `value: null` plus an error string, which the page renders as
"source failed" or "fill by hand". A missing `data/playbook.json` renders
"refresh not run" and the page still works on its own inputs.

### Files

| File | What |
|---|---|
| `index.html` | tab row, `PLAYBOOK_RULES`, `PlaybookTab` |
| `tools/playbook_refresh.py` | the refresh script |
| `tools/events.json` | hand calendar, every row carries a `verified` flag, a source URL and a note |
| `tools/playbook_rules.json` | v2: six trigger components with their backtest status and adopted flag, plus `paper_trigger` |
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
because the company IR page was unreachable. The tab prints VERIFIED or UNVERIFIED per
row straight off the flag.

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

`paper_trigger` is the trend trio plus realized-vol rank at 70 or above, all
passing. It is the two PROMISING readings from the study and nothing more: no
component is ADOPTED, so the funded stack cannot go live and the sleeve stays on
paper until the 8-week record beats implied odds.

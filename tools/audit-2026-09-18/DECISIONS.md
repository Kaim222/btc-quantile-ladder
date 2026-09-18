# Site cleanup decisions, 2026-09-18

Alex: the site is noisy and hard to digest, too much was added, make it minimalistic again without removing everything.
Git history settles what "again" means. The Ladder tab reached its shape on 2026-08-21 after twenty commits of his own
tuning. The Playbook tab (9/12 to 9/15) and the MSTX tab (9/16 to 9/17) are the recent additions.

Principle: the 8/21 Ladder tab is the baseline and stays as it is. Everything added since 9/12 has to earn its place.
The four audit reports beside this file (ladder.json, playbook.json, mstx.json, alerts.json) carry line numbers and
reasons for every section. Where a report and this file disagree, this file wins.

## Shell and Ladder tab

KEEP UNTOUCHED (the 8/21 baseline): PIN gate, header, standard/weighted selector and half-life slider, light-mode
toggle, tab bar, price input row and steppers, price presets, the three stat cards, tier card, structure card, margin
card, forward projections table, price lookup, power-law chart.

CUT: the "Band history" card (added 9/17).

TRIM: "The rules" card (added 9/17) to four rows: gate, entry, size, exit. Band, time and strikes are already the tier
card and the structure card.

FIX, small and safe:
- The header LIVE chip must read MANUAL whenever a typed price is driving the numbers (defect 1 in ladder.json).
- Remove the duplicate `opacity` prop on the band path (index.html about line 795).
- Remove dead code the audit confirmed unused: bandRows, bandsAbove, bandsBelow, nearestAboveQ, nearestBelowQ,
  isThirdFriday, displayName (inline its one call), the LINE constant, the mnavEV field, the lvl.count_rule branch.
- The hardcoded footer build stamp goes; keep the rest of the footer line.
- The mobile stylesheet's stat-grid selector must match the real `repeat(3,1fr)` grid so the three stat cards stack
  on a phone.
- README.md describes a site that no longer exists. Rewrite it in under 30 lines: the three tabs, the data files and
  what writes each, the tools, the monitor repo.

## Playbook tab: four panels

1. HERO. The word, the phase, the next-action steps, the next_action_detail line, and the refresh age, red past two
   days. CUT the chip row under it.
2. PHASE 1, WHAT IS ON. For each spread: key, legs, contracts, debit, cost. Then the ledger's `positions` text and the
   exits. Read only ledger fields that exist. Remove the debit_natural / hurdle / odds_short reads, the "hurdle unknown"
   text and the sk() helper.
3. LEAPS UNITS, one panel, in this order: a one-line objective (plan.objective, first sentence); today's unit price from
   data/leaps-cost.json; the by-close table from the ledger's units_by_price with the UNIT PRICE and LEAPS columns
   recomputed from leaps-cost.json `unit_at` (nearest MSTX row; LEAPS = dollars / (unit x 100)) and the slider kept;
   the LeapsCost chart; its reference cards cut to four (TODAY, 1 MONTH AGO, 2 MONTHS AGO, LOW); the routes table,
   compact, last. One footer note for the whole panel.
4. WEEKLY MACD. The histogram, compact, captioned with the bar date it reads. The caption may say "rising since"
   only when the last bar is above the one before it; otherwise "falling since".

CUT: the Phase 2 strike-map panel, the LADDER QUANTILE and IV RANK stat cards, the hero chip row and the scroll-to
behaviour on chips.

FIX: the tab's ticker name and accent colour come from the monthly-close tier, the same read the Ladder tab uses, not
the live quantile. The three fetches must not swallow errors silently: a failed file shows one plain line saying which
file failed.

## MSTX tab: six sections

1. MSTX NOW. The lag verdict headline and sentence, then three tiles: MSTX price, lag against the last hour, monitor
   heartbeat. The heartbeat tile shows the monitor's last run; amber when it is more than 20 minutes old during market
   hours, red when more than 60. A dead monitor must not look like a sleeping one.
2. LEVEL. The CHEAP / FAIR / RICH word, then three tiles: gap in MSTX terms, projected MSTX, BTC against its 50-day.
   mNAV, target mNAV and BTC per share leave the page.
3. ALERT LOG. The ledger cut to five columns (when, kind, lag MSTX, MSTX after 60 min, MSTR minus BTC after 60 min),
   with a narrow-screen variant like every other table, the scored tally under it, and ONE rules line that matches
   data/mstr-config.json: Lag at -3.0% MSTX against its own last hour at MSTR's bar low while BTC holds, only with BTC
   above its 50-day; Cheap at -6% MSTX, same gate; Rich at +8% MSTX in either regime. The current text says Rich is
   muted unless BTC is below its 50-day. That is wrong since 9/17 and must go.
4. GAP CHART. The gap sub-chart only, in MSTX terms, dashed lines at the Cheap and Rich thresholds from the config,
   tap for a day. The MSTR price-against-projection chart is cut.
5. WHAT IF. Four boxes (BTC, MSTR, MSTX, STRC), three result cards (projected MSTX, gap, verdict), reset to live, and
   the edit-config link. No slope toggle, no holdings boxes.
6. DETAILS, collapsed by default. The lag evidence table and the two regime lines. Nothing else.

CUT: the THIS WEEK card (8-K line and five-day chips), the closed-market and as-of footnotes, the monitor strip above
the log, the WHEN IT FIRES list and tvLine paragraph (replaced by the one rules line), the cheap-episodes table, the
what-happened-next table, the target-rule footer.

FIX: the MSTX price, projected MSTX and gap come from the monitor's mstr_state.json first (fields mstx, proj_mstx,
gap_mstx, last_run), and from data/mstr-model.json only as a fallback. A stale model file must never blank the price
tile.

## Rules for the edit

- One file, index.html, plus README.md. No new dependencies, no build step, the same inline-style idiom.
- Do not touch data/*.json except as listed. Do not touch tools/leaps_cost.py beyond adding `unit_at`.
- Removed components, helpers, constants and state go completely. No commented-out blocks.
- The light-mode and mobile stylesheets match inline styles by substring. After the edit, no selector may point at a
  style that no longer exists, and nothing surviving may lose its light-mode or mobile rule.
- Target: index.html at least 25% shorter than its current 2,887 lines.

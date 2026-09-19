# Math and truth audit — 2026-09-19

Local code/data only; no network, application/data edits, commits, or pushes. References use repository-relative paths; `../mstr-mnav-model` is the sibling repository. Rendered values were checked against `tools/audit-2026-09-19/rendered-text.json`. Findings rank financial consequences first. Yesterday's cleanup decisions and the disclosed old routes formula are not reopened.

## Findings

### 1. Settlement position values do not reproduce the stated pricing basis

**Evidence:** `index.html:1120–1125,1210–1218` copies position dollars directly from `data/paper-ledger.json:30–109`. The ledger's `units_note` at line 110 specifies shorts at intrinsic, seven days on the $16 long and fourteen on the $18 long; its `routes_note` at line 176 calls 100% volatility the site's basis. Using those legs, 275 and 175 contracts, zero cash, and the supplied Python Black–Scholes convention (4%, calendar days/365; `tools/leaps_cost.py:21–27`), the table does not reproduce:

| MSTX on Oct 2 | Page position | Recomputed position |
|---|---:|---:|
| $13 | $3,734 | $2,697 |
| $15 | $18,893 | $17,786 |
| $16 | $35,461 | $34,330 |
| $16.50 | $32,568 | $31,432 |
| $18 | $33,278 | $32,151 |
| $22 | $7,450 | $6,397 |

All thirteen rows differ, by roughly $1,037–$1,137. This is not dollar rounding. The supplied data does not identify a different rate, cash balance, or timing adjustment that reconciles the numbers; do not infer one. **Smallest fix:** regenerate these dollars from explicit rate, volatility, valuation time, and cash inputs; expose the 100% volatility assumption beside the table. The currently displayed table omits even the ledger's `units_note` (`index.html:1260–1261`).

### 2. Position basis is $1,000 inconsistent, and the break-evens do not match the stated basis

**Evidence:** `data/paper-ledger.json:7,13–29`, rendered by `index.html:1195–1200`. Listed costs are $5,775 + $11,200 = **$16,975**, but position prose says **$17,975 in**. The journal's $17,975 was an earlier account amount including $1,200 cash (`data/paper-ledger.json:343`); later cash trades/losses are separate (`:350–379`). It is not the sum of the two current spread debits.

At the table's 100% volatility, 4% rate, zero cash, and stated remaining days, Oct 2 break-evens against $17,975 are **$15.01 / $19.43**, versus the page's **$14.93 / $19.59**. Against the actual listed spread basis of $16,975, they are **$14.94 / $19.57**. At 118% volatility and $16,975 basis they move to **$14.43 / $20.47**: these are conditional model break-evens, not fixed properties of calendars. **Smallest fix:** distinguish current spread basis from account recovery target, and regenerate/label break-evens using that basis and a named volatility.

### 3. The monitor fallback gives three incompatible measures of the same projected gap

**Evidence:** `index.html:1412–1414` falls back to twice the MSTR gap and translates projected MSTX off the current close. The gap chart instead uses prior-session closes (`:1478–1481`). Local rows at `data/mstr-model.json:3146–3166` provide Sep 17 MSTR/MSTX $132.25/$14.14 and Sep 18 $153.92/$18.73, projected MSTR $146.04.

For that same Sep 18 observation:

- LEVEL fallback: projected MSTX **$16.81**, gap **+10.8%**.
- Required daily-fund calculation: `14.14 × (1 + 2 × (146.04 / 132.25 − 1))` = **$17.09**; `18.73 / 17.088818 − 1` = **+9.6%**.
- Even the fallback's own $16.812219 price implies **+11.4%**, not its displayed +10.8%.

**Smallest fix:** derive fallback price and gap together from the quote session's preceding closes, sharing the chart/WHAT IF calculation. If that session basis is unavailable, do not substitute an unlabelled doubled-MSTR approximation.

### 4. Same-day scenarios can display a negative MSTX price

**Evidence:** `index.html:1449–1451,1568–1569` applies the linear daily leverage expression without rejecting values below zero. With the supplied Sep 17 closes, BTC $50,000, STRC at/above $97.50, and 845,050 BTC/450.112M shares, projected MSTR is **$61.02** and displayed projected MSTX is **−$1.09**. At BTC $40,000 it becomes **−$5.31**. Those Bitcoin inputs are accepted at `:1593` (and $50k is the chart's left endpoint at `:1584`). WHAT IF can then substitute a MSTR-based gap because its calculated MSTX price failed `> 0`.

**Smallest fix:** show “outside daily approximation” when the daily expression is nonpositive; do not present a negative fund price or silently change gap definitions. This is a validity guard, not a change to the supplied leverage formula.

### 5. UNIT COST LOOKUP prices a short option after it has expired

**Evidence:** `index.html:1018–1019,1031` permits dates through the long's December 2028 expiry, while the short expires January 21, 2028 (`data/leaps-cost.json:19–22`). `lcCall` returns current intrinsic for every expired leg (`index.html:925`), effectively repricing the already-settled short at a later stock price.

Example: July 21, 2028 and MSTX $80 gives long **$49.44**, expired short “value” **$20**, and “one unit” **$29.44**. The live long alone is $49.44; any January short settlement depends on January's stock price, which the lookup never requests. There is no July purchase price for the original two-leg unit. **Smallest fix:** limit this unit-purchase lookup to dates before the short expiry. A later-date position-value model would need settlement history and is a different calculation.

### 6. The settlement unit count uses September prices for October purchases

**Evidence:** `tools/leaps_cost.py:73–75` creates `unit_at` on the latest close, September 18. `index.html:1122–1125` uses it for “BY MSTX CLOSE ON SETTLEMENT,” despite the objective specifying that day's unit price (`data/paper-ledger.json:157`). Repricing the identical fitted vols on October 2 gives:

| MSTX | Page unit | Oct 2 unit | Page LEAPS | Oct 2 count using the same page dollars |
|---|---:|---:|---:|---:|
| $15 | $3.17 | $3.2153 | 60 | 58.76 |
| $16 | $3.39 | $3.4419 | 105 | 103.03 |
| $16.50 | $3.50 | $3.5539 | 93 | 91.64 |
| $18 | $3.82 | $3.8842 | 87 | 85.68 |

This isolates the date error; fixing finding 1 changes counts again. **Smallest fix:** use the existing BS unit function with the settlement date and stored fitted vols. No new pricing model is needed.

### 7. Affordable contract counts are rounded up

**Evidence:** `index.html:1125,1136,1218` computes fractional units and displays `toFixed(0)` as how many LEAPS the account can buy. At MSTX $16 the page shows **105** from $35,461 and a $3.39 unit. Those 105 cost **$35,595**, $134 more than the stated proceeds; affordable whole units are **104** at the page's own rounded price. At $15 it shows **60**, costing $19,020 against $18,893; affordable is **59**. **Smallest fix:** floor purchasable unit counts, using the unrounded model unit cost. This is independent of the date and position-value corrections.

### 8. Historical “best estimate” evidence is conditional on future inputs, not a forecast made five days earlier

**Evidence:** `index.html:1542,1629,1677` describes an estimate made five trading days earlier. Both `../mstr-mnav-model/mnav_gap_fade.py:32–34` and `../mstr-mnav-model/build_mnav_history.py:26,32` use the **destination day's** Bitcoin and STRC prices. Only the gap is lagged. The research explicitly acknowledges this at `../mstr-mnav-model/2026-09-19-mnav-shape.md:84–85`; the page drops that qualification.

The quoted valuation errors reproduce: rule **0.083/0.082/0.083/0.072**, fading gap **0.039/0.055/0.066/0.067** at 5/10/20/40 trading days. They are premium-point errors given future inputs, not demonstrated errors of the LEVEL card's unchanged-Bitcoin MSTX forecasts. **Smallest fix:** say “conditional valuation using that day's BTC/STRC and the gap from five sessions earlier”; add the future-input qualification to the walk-forward claim.

### 9. The best-estimate gap chart does not score the forward MSTX formula

**Evidence:** `index.html:1484–1487` carries a five-session-old valuation gap but converts the result to MSTX using the **previous day's** closes. `aheadMstx` and future lookup rows use the earlier starting MSTX price, squared MSTR ratio and volatility decay (`:1455–1459,1568–1569`). Thus the chart cannot be read as the realized error of those forecasts.

Using Sep 11→Sep 18 rows (`data/mstr-model.json:3102–3166`), seven calendar days, the chart's conditional MSTR estimate is **$143.4336**. Its prior-close conversion gives MSTX **$16.5315**, gap **+13.30%**. The supplied multi-day conversion from Sep 11 gives **$16.6231**, gap **+12.67%**, even holding that conditional MSTR estimate identical. **Smallest fix:** label the series “daily MSTX equivalent of five-session valuation residual.” If intended as forecast performance, anchor MSTX to the forecast origin and apply the multi-day formula, while retaining finding 8's qualification.

### 10. A chosen decay assumption is stated as an observed law

**Evidence:** `index.html:1460–1461` says “About half of a gap fades/closes in a month.” The source test compares prediction errors for selected half-lives; it does not measure that half of actual gaps closed in that interval (`../mstr-mnav-model/mnav_gap_fade.py:24–36`). `data/mstr-config.json:22` explicitly says 28 days is a choice, not a fit.

Recomputed 20-session errors for **28/42/56 calendar-day** half-lives are **0.066/0.063/0.063**. At 28 calendar days those assumptions retain **50.0%/63.0%/70.7%** of a gap. Similar error scores do not establish 50% realized closure. **Smallest fix:** “The best-estimate model assumes half the gap fades every 28 calendar days.”

### 11. The “three of five Rich readings / 25% and 52%” statistic has no reproducible definition on the page

**Evidence:** `index.html:1460` repeats the research sentence at `../mstr-mnav-model/2026-09-19-mnav-shape.md:31`, without threshold, episode grouping, return instrument, or horizon. The current rule is +8% MSTX (`data/mstr-config.json:7`; `index.html:1409`). A transparent census of contiguous days above **+4% MSTR** in the supplied CSV gives **eight starts**, seven before the unscored Sep 18 start; above +5% gives **six starts**, five before Sep 18. Thus “five” cannot be identified with the current rule's raw episodes without additional selection rules.

For the February 5 +4% episode, 20-session MSTR return is **+24.8%**; for April 15 it is **+24.0%**, not 52%. This does not prove 52% false at every horizon; it proves the omitted horizon matters. **Smallest fix:** retain the qualitative “Rich is not a sell on its own,” and supply dated episode rows and a named horizon before quoting that tally/return pair as current-rule evidence.

### 12. “Average miss … as a share of the price” uses the estimate as denominator

**Evidence:** `index.html:1674–1677` describes distance from MSTR's close as a share of price. The builder actually computes `abs(actual / estimate − 1)` (`../mstr-mnav-model/build_mnav_history.py:30–33,39–42`). On the same 282 scored observations, displayed All errors **10.4% / 4.6%** reproduce with estimate denominators (**10.4089% / 4.6331%**). As a share of actual MSTR price they are **9.6172% / 4.5554%**, displaying **9.6% / 4.6%**. The All DAYS cell says **287**, which includes five dates with no best estimate.

**Smallest fix:** label the denominator “as a share of the estimate” and distinguish 287 era observations from 282 scored pairs. Alternatively calculate both errors against actual price and change 10.4% to 9.6%.

### 13. The 30/90-day mNAV labels mean trading observations, unlike the 28-day decay clock

**Evidence:** `index.html:1638,1654–1655` uses the last 30/90 rows; the history line uses `.rolling(90)` (`../mstr-mnav-model/build_mnav_history.py:27`). The page calls these “30-DAY” and “90-DAY,” alongside calendar-day decay.

Through September 18, CSV recomputation gives **0.84965 / 0.83013**, matching displayed **0.85 / 0.83**, for 30/90 trading observations. For the last 30/90 calendar days, the observed-close averages are **0.88768 / 0.78049**, displaying **0.89 / 0.78**. **Smallest fix:** label these “30-session” and “90-session” averages, including the chart caption. Label the 28-day decay explicitly in calendar days.

### 14. Identical high-Bitcoin scenarios use different mNAV caps, and “capped high” can exceed its cap

**Evidence:** Ladder's MSTR conversion caps target at 2.0 (`index.html:369`, disclosed at `:447`), while MSTX lookup projected `tLo` is uncapped (`:1561`). `tHi` takes `max(tLo, min(cap, curve))` (`:1563`), so “High is the capped convex fit” (`:1629`) is false once `tLo > cap`.

At BTC **$200,000**, STRC base **0.90**, and the local 845,050/450.112M holdings basis, Ladder gives target **2.00**, MSTR **$750.97**; the MSTX lookup projected and high both give target **2.15**, MSTR **$807.29**. The difference is **$56.32**, or 7.5% of the Ladder value. The footnote explains the Ladder cap; it does not make the other “capped” label true. **Smallest fix:** explicitly distinguish the capped Ladder scenario from uncapped projected, and describe high as “at least projected; convex contribution capped at 2.0.” No Ladder layout change is needed.

### 15. Rounded exported vols prevent exact Python/browser reproduction

**Evidence:** Python computes cost and `unit_at` with full-precision fitted vols, then exports the lookup vols rounded to four decimals (`tools/leaps_cost.py:58–61,75,82–83`). At the identical September 18 date and MSTX $18.73, `data/leaps-cost.json:27–30` gives **$79,442** for 200 units; Python using the exported vols 1.1602/1.3185 gives **$79,426.27**, i.e. **$79,426**. The largest difference against the rounded `unit_at` entries is **$0.00572 per share**. This is small (about $16 on the current 200-unit total), but it is a real same-input reproducibility failure rather than a browser BS error.

**Smallest fix:** export the pricing vols at full precision, or generate every exported price from the same rounded model parameters the browser receives.

## Checks that passed and limits

- Browser BS algebra matches Python, with the expected small normal-CDF approximation error (`index.html:923–927`; `tools/leaps_cost.py:23–27`). At September 19, MSTX $18.73 and 200 units, recomputed lookup cost is **$79,526.37**. The displayed sensitivities reproduce: MSTX +$1 **+$4,156.24**; seven calendar days **+$703.71**; both baseline vols ×1.10 **−$1,652.49**. These are finite scenario changes, not per-share analytic greeks. Their signs are correct. The TODAY card's September 18 date versus the default lookup's September 19 date explains most of their apparent difference; it is not itself a pricing bug.
- Projected target, STRC steps, multiplicative `tHeld`, 28-calendar-day weight, `aheadMstx`, and future `mstxAt` match the supplied definitions. `tMine` correctly implements `max(0, myM × BTC NAV/share − obligations/share)` for positive obligations. The convex coefficients recompute to **0.01234268 / 0.00144466**, consistent with the stored 0.0123/0.0014. This verifies fit arithmetic, not predictive superiority or a confidence bound.
- Alert thresholds correctly convert config fractions to **−3% Lag, −6% Cheap, +8% Rich** in MSTX terms. The alert log explicitly distinguishes MSTX returns from MSTR-minus-BTC returns; no scale defect is demonstrated there. Minute-bar evidence cannot be independently regenerated from the daily CSV. DETAILS' “four episodes” refers to its model's older −4% MSTR cheap sample (`data/mstr-model.json`, `regime.note`), not a newly recomputed −6% MSTX sample.
- All **105** history weekly premiums match the CSV-derived scaled premiums to rounding (maximum difference **0.000472**). The period medians reproduce **2.69, 2.08, 1.43, 0.96, 0.76**. Overall current premium and 30/90/250-observation averages reproduce the history JSON. The fading-gap script ran locally and reproduced every quoted horizon error; evaluation counts are **33/32/30/26**.
- **Skipped the 200-day flag**, as requested: the builder fetches its Bitcoin series with yfinance (`../mstr-mnav-model/build_mnav_history.py:16–18`). No network was used, and the bull/bear assignments, regime-specific medians/errors, and 70% bear share were therefore not independently certified. Nor were the shape research's network-dependent trend/momentum regressions rerun. The all-observation calculations above do not require that flag.
- Ladder quantile interpolation and its inverse agree at the calibration bands; current tier boundaries and the 90-calendar-day short quantile match `data/ladder-rules.json:6–9`. The displayed long is a chain-selected 0.75-delta instruction, not the unused numeric band-floor long price (`index.html:2170`). No Ladder redesign is proposed. Margin algebra gives **15.625%** net carry, **33.333%** drawdown to call and **$66.67** call price under its stated par/leverage assumptions (`index.html:301–304`). Historical “bottom episode” descriptions cannot be independently certified from the supplied MSTR CSV.
- Playbook's latest histogram **1,947.020697 < 2,379.228808**, OFF state, falling-since September 6 caption and seven weeks since July 26 agree with `data/playbook.json` and `index.html:1087–1093,1140–1148`. The current exit steps are copied faithfully. The older route counts are explicitly footnoted; no duplicate finding is raised for that known issue, and no exact revised expected counts are invented without their scenario probabilities and pricing inputs.

Verdict: FIX — the core formulas mostly hold, but inconsistent position values, fallback gaps, purchase dates, and overstated evidence can change trades or undermine trust.

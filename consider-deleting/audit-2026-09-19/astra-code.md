# Code audit — 2026-09-19

Read all 2,360 lines of `index.html` in successive chunks, the prior cleanup decisions, the rendered-text capture, and the relevant local JSON. No network, application/data edits, commits, or dependency installation. Arithmetic reproductions ran in memory against the local files. This is a source/data audit, not a new browser rendering test. Findings are ordered by potential trading loss or loss of trust, then polish. Line numbers refer to this checkout.

## 1. Model fallback uses two incompatible approximations for projected MSTX and its gap

**Evidence:** `index.html:1412–1414` uses twice the model's MSTR gap and projects MSTX from the current model row's MSTR/MSTX, rather than the preceding session's closes. The gap chart correctly uses the preceding row at `index.html:1478–1481`. With the actual 9/17 and 9/18 rows (`data/mstr-model.json:3146–3165`), the prior-close calculation is `14.14 × (1 + 2 × (146.04 / 132.25 − 1)) = 17.088818`, with gap **+9.6038%**. The fallback tiles instead show **$16.81 and +10.8%**. Even those two fallback tiles disagree internally: $18.73 / $16.812219 − 1 is **+11.4071%**. This path runs when monitor fields are unavailable.

**Smallest fix:** Calculate the fallback projected price from the two latest valid consecutive sessions, then derive its gap from that exact price. Return unavailable when that pair is missing; reuse the calculation in the chart.

## 2. A stale or missing session anchor silently changes the daily-fund formula

**Evidence:** `index.html:1446–1450` takes the session from `last_bar`, otherwise today's New York date, and accepts *any* earlier valid model row. It never verifies that this is the immediately preceding completed session. If `last_bar` is unavailable on Saturday 9/19 while the price fallback is Friday's close, it chooses Friday itself as the reference, instead of Thursday. A fresh Monday monitor with a model last updated Thursday also passes. If there is no reference row, WHAT IF uses the current-price linear approximation (`1450`), while same-day lookup falls through to the squared-ratio formula (`1568–1569`). Thus two panels can disagree precisely when a fetch fails.

**Smallest fix:** Associate the price snapshot with its quote session; require that snapshot's preceding session closes. If unavailable, withhold the same-day MSTX result consistently rather than silently selecting a different formula.

## 3. Live polling leaves the calculation files frozen indefinitely

**Evidence:** Model, config and mNAV history fetch only once in the mounted MSTX component (`index.html:1374–1376`); its recurring poll fetches only monitor state, ledger and holdings (`1377–1390`). MSTX stays mounted even when hidden (`2246`), so changing tabs cannot recover a failed config fetch or advance its model. Playbook's three files also fetch only on mount (`1060–1070`). The Ladder's MSTR conversion inputs fetch once (`336–365`). Meanwhile prices and clocks advance. An open dashboard can therefore combine today's prices with yesterday's prior-close table, old thresholds, old unit costs and old conversion inputs. Successful but old files have no freshness rejection; the visible Playbook refresh age reads only `pb.generated_at` (`1095–1099`, `1173–1174`), not the ledger or LEAPS file.

**Smallest fix:** Retry failed loads and refresh these existing file reads on the relevant session/day change and visibility return. Validate each file's own timestamp before calling its values current. Refresh Ladder conversion inputs on the existing polling schedule.

## 4. A fresh heartbeat can accompany stale prices and an unqualified LEVEL

**Evidence:** `index.html:1396–1397` always prefers individual monitor fields over model fields, without checking their timestamps. `1416` combines `last_run` and `last_regime_check` with `Math.max`; the comment explicitly says the latter can be an off-hours-only check. Outside regular hours `1424` calls any timestamped state OFF HOURS, regardless of quote age. The monitor dot is green whenever heartbeat color is neutral (`1467`), and LEVEL continues showing CHEAP/FAIR/RICH and forecasts (`1508–1513`) even when the headline is STALE. Partial state can also mix a monitor price with an unrelated model projection and gap.

**Smallest fix:** Track quote age separately from process/regime heartbeat. Select a coherent price/projection/gap snapshot and mark its age in the existing tiles; suppress actionable LEVEL/forecast readings when that snapshot is unusable. Keep monitor-first precedence for valid snapshots.

## 5. A LEAPS file failure increases the apparent buying capacity

**Evidence:** `index.html:1123–1125` falls back to the ledger's old unit prices and counts when the calibrated curve is absent. At MSTX $16.50, the current file supplies unit **$3.50** (`data/leaps-cost.json:153–154`), producing about **93** units from $32,568. The ledger supplies **$2.88 / 113 units** (`data/paper-ledger.json:62–65`). A failed `leaps-cost.json` therefore changes the same table from 93 to 113. The error line names the failed file (`1166`), but the explanation that ledger prices are now in use is hidden in the footer (`1260–1261`). An object missing `unit_at` does not even generate that fetch error.

**Smallest fix:** Keep position dollars visible but make calibrated unit price/count unavailable when the curve is missing, or explicitly mark the affected table as using the old ledger estimates beside its heading. Do not silently present the older count as equivalent.

## 6. Missing MSTR input becomes an invented zero gap and a valid-looking best estimate

**Evidence:** The lookup only requires `bps > 0` and `strcI > 0` at `index.html:1557`, plus Bitcoin at `1570–1571`. `1573` assigns `gapNow = 0` whenever MSTR is missing/nonpositive. Clearing the MSTR WHAT IF box consequently leaves a numerical BEST ESTIMATE MSTR and mNAV, with a claimed 0% current gap (`1602–1603`). With a prior row, same-day BEST ESTIMATE MSTX remains numerical too (`1568`). The current gap is unknown, not zero.

**Smallest fix:** Use null for an unavailable current gap and withhold best-estimate outputs until Bitcoin, MSTR and the projected baseline are valid. Projected-only values can remain available.

## 7. Out-of-domain scenarios display negative MSTX prices, and gap charts can divide by zero

**Evidence:** The unbounded daily formula at `index.html:1449`, `1478–1487` and `1568` becomes zero when estimated MSTR is half the reference MSTR and negative below that. Using the supplied model rows and its inferred BTC/share, Bitcoin $50,000 gives projected MSTR about $61.01 and same-day MSTX **−$1.09**. The Bitcoin input has no minimum model-domain restriction (`1593`), and a low custom mNAV can also drive MSTR to zero (`1581`). WHAT IF still derives a gap from a different MSTR approximation if its projected MSTX is nonpositive (`1451`), potentially attaching a verdict to an impossible price. The historical calculations divide by the computed projected MSTX without checking it: a zero denominator produces Infinity, contaminating the shared SVG extent and coordinates (`1489–1492`).

**Smallest fix:** Centralize the daily calculation with a finite, strictly positive result check. Mark scenarios outside the formula's usable domain unavailable; skip invalid chart points and never substitute another gap formula for a nonpositive projected price.

## 8. Numeric parsing accepts nonfinite values and malformed numbers

**Evidence:** `nm` at `index.html:884–885` checks only `isNaN`, not finiteness or a complete numeric match. In-memory execution confirms `nm('9'.repeat(400))` is Infinity and `nm('1.2.3')` is 1.2. WHAT IF and lookup accept arbitrary-length text (`1549`, `1593`, `1599`). Infinity passes many `> 0` guards; Infinity/Infinity produces NaN, which `verdict` classifies FAIR because neither comparison succeeds (`1410`). Formatting helpers `1320–1322` handle null but not NaN/Infinity. Partial malformed JSON numbers/strings can reach the same paths.

**Smallest fix:** Parse the complete normalized value and require `Number.isFinite`. Preserve incomplete edits in input state but pass null to calculations until valid. Make verdict/formatters reject nonfinite values too.

## 9. Partial LEAPS data can crash rendering rather than show unavailable values

**Evidence:** `index.html:964` accepts a chart row based solely on numeric `cost`; hovering it unconditionally calls `h.mstx.toFixed` and `h.unit.toFixed` (`1005`). Reference cards validate only that the record is an object (`974`) before calling `r.mstx.toFixed` (`1012`). For example `{cost:100}` passes the row filter but the hover expression throws `TypeError: Cannot read properties of undefined (reading 'toFixed')`. Five such rows satisfy the chart length guard. Fetch acceptance checks only that the top-level JSON is an object (`1064`), and there is no error boundary around these components (`2244`, `2272`).

**Smallest fix:** Validate the finite fields needed by each row/reference card, or null-guard those format calls. Validate model fields before offering its lookup, rather than accepting merely object-shaped long/short legs (`961`).

## 10. Unit-cost lookup continues pricing a two-leg unit after its short has expired

**Evidence:** The short expires **2028-01-21**, long **2028-12-15** (`data/leaps-cost.json:14–22`). The date input permits dates through the long expiry (`index.html:1031`). `lcCall` returns intrinsic value for any expired option (`925`), and `unitAt` subtracts it using the *future lookup stock price* (`1017–1019`). That treats an already-settled short as if its payoff were determined by the later lookup price. By the long expiry and stock above $60, the displayed unit mechanically becomes $27, irrespective of the stock price at the actual short settlement.

**Smallest fix:** Cap this two-leg unit lookup at the short expiry. Modeling later dates requires separately specified short-settlement proceeds/liability, which this interface does not collect.

## 11. Overlapping requests can overwrite newer snapshots with older ones

**Evidence:** MSTX schedules its next poll without waiting for the current fetches (`index.html:1377–1390`), and every successful response replaces state regardless of response timestamp (`1372`, `1379–1388`). BTC does the same (`1777`) and can launch an additional request on visibility return (`1778`). The `on` flags prevent most updates after unmount, but do not order responses within a mount. A delayed earlier poll can overwrite a newer completed poll, including fresh holdings or monitor state.

**Smallest fix:** Allow one in-flight request per resource or use a monotonically increasing request ID and ignore superseded responses. Check returned snapshot timestamps as well for monitor state.

## 12. Date defaults stop following today, and Playbook advances dates in UTC

**Evidence:** MSTX is permanently mounted (`index.html:2246`), but `lkDay` initializes only once (`1362`) while `today` advances (`1564`). An untouched lookup left open overnight retains yesterday's date, now below its own minimum (`1596`), while `Math.max(0, ...)` silently evaluates it as today. LEAPS has the same initialization-only date (`962`), and Ladder lookup caches `daysFromNow` without a clock dependency (`511–519`). Playbook chooses its phase using `todayTs.toISOString().slice(0,10)` (`1074`, `1102–1103`), so in New York it can advance to tomorrow's phase in the evening, while both MSTX date defaults use New York dates.

**Smallest fix:** Use one New York trading-date helper. Roll untouched defaults when that date changes; validate explicitly chosen past dates instead of silently treating them as today. Include the day in the Ladder lookup memo's dependencies.

## 13. “Market open” is only a weekday/time test

**Evidence:** `index.html:1343–1348` returns true every Monday–Friday from 09:30 to 16:00 New York time. It has no holiday or early-close input. This controls STALE/BUY/OFF HOURS (`1415–1424`), quote-session choice (`343`, `1335–1341`) and polling (`1390`, `1774`). A closed weekday session or an early-close afternoon is therefore treated as live trading, with old bars becoming an apparent monitor failure.

**Smallest fix:** Feed an exchange-session open/close value into this helper, preferably from existing monitor state if supplied, with an explicit unknown fallback. A local session calendar also suffices; retain the current timezone conversion.

## 14. mNAV average labels overstate their time windows, especially with short series

**Evidence:** `index.html:1638` takes the last *n trading rows*, not n calendar days, then allows any window with only `min(n,20)` valid observations. The current 30-row average runs **8/7–9/18**, and the 90-row average **5/12–9/18** (`data/mstr-model.json:9` series onward; endpoint `3157`). They are labeled “30-DAY” and “90-DAY” (`1654–1655`). More seriously, a 20-row file can populate all three labels, including “1-YEAR AVERAGE,” with the same 20-row mean.

**Smallest fix:** Say “30/90 trading days” for these existing calculations and require complete windows, or show the actual observation count when incomplete. Require the intended one-year coverage before displaying that label.

## 15. Chart extents do not include all rendered series

**Evidence:** Bitcoin lookup chooses its y ceiling solely from the high formula at $160,000 (`index.html:1585`), but also draws the carried-gap and custom-mNAV curves (`1613–1615`) and the selected best-estimate dot (`1618`) with no clipping. Entering a sufficiently high custom mNAV, or raising the WHAT IF MSTR enough to create a large carried gap, puts these curves outside the plot/SVG; the number cards still display them. LEAPS likewise scales only from `cost` (`967`) while drawing `avg10` and print costs (`997–998`); five zero-cost rows yield a zero top and NaN coordinates (`968`). mNAV history guards its short-series denominator with `weekly.length > 10` (`1633`), and the gap chart explicitly handles fewer than two rows (`1490`); those particular short-series divisions are safe.

**Smallest fix:** Derive finite extents from every displayed curve/point, ensure a positive y span, and add a plot clip path. Keep a fixed x window only if out-of-window selections are visibly identified.

## 16. BTC fetch failure is called manual, while its stale button still says live

**Evidence:** After both price sources fail, `index.html:1754` sets `liveFetch` unavailable but preserves the previous `livePrice` and `priceStr`. Header `1931` conflates this with deliberate manual entry as “PRICE MANUAL.” The button at `2029–2033` remains green and labeled “Live,” and clicking it copies that stale price. Initial failures instead leave the hardcoded $85,000 default (`1708`). The existing timestamp is fetch receipt time (`1736`), with no age check.

**Smallest fix:** Separate unavailable/stale from manual in the existing status chip, and disable or relabel the live button when its cached quote is stale. Label the initial default as an unpriced/manual starting value. No layout change is needed.

## 17. The rules file can fail completely without any visible indication

**Evidence:** `index.html:898–903` swallows all fetch/JSON errors and returns null until rules exist. A failed file removes the gate/entry/size/exit card altogether. Unlike Playbook (`1166`) and MSTX (`1499`), this component does not expose its failure. It also accepts any rules array and accesses `r.k` without validating entries (`910`), so an array containing null throws.

**Smallest fix:** Add a plain failed/unavailable line in the existing card location and filter/validate rule objects before rendering. Keep exactly the four agreed rules.

## 18. Light mode loses the new white lookup curve and white chart markers

**Evidence:** Light mode turns chart backgrounds almost white at `index.html:1883`, but recolors only paths whose stroke is exactly `#f1f5f9` (`1885`). The new lookup best-estimate path uses `#e2e8f0` (`1613`), and the LEAPS print dots (`998`) and lookup current-price dot (`1617`) use white `fill` values with no corresponding override. LEAPS hover lines (`999`) and lookup current-Bitcoin lines (`1616`) also remain pale. The gap chart's white path (`1537`) and mNAV history's white path (`1666`) *do* match the existing override; LEVEL text colors match the existing text mappings. This is a specific missing mapping, not a general failure of all new cards.

**Smallest fix:** Add SVG overrides for these precise white path/line/fill colors, preserving a contrasting current-price marker and best-estimate curve on the light chart background.

## 19. Light-mode separator and native-input rules miss their actual properties

**Evidence:** `index.html:1892` matches the alpha color used by `SEP` (`866`) but changes only `border-top-color`. Many matching elements actually set `borderBottom`: alert rows `1517`, `1522`; lookup rows `1625`; history tables `1649`; DETAILS rows `1685`. Their faint white bottom borders remain faint on light backgrounds. Separately, date controls force `colorScheme:"dark"` at `538`, `1025`/`1031`, and `1597`, while the light injector changes the input backgrounds/text (`1839`) without changing the native scheme. Calendar affordances retain the dark scheme on light inputs.

**Smallest fix:** Match and override the actual bottom border as well as the existing top-border use. Add a light color-scheme override for all three date-control sites.

## 20. Several controls have no accessible name, state, or visible focus

**Evidence:** Unnamed inputs are the Ladder date (`index.html:537`), settlement range (`1233`), model half-life range (`1970`), BTC price (`2019`) and PIN (`2281`); their neighboring text is not an associated label. Focus outlines are removed globally for ranges (`45`) and by the date style (`524`), WHAT IF/shared inputs (`873`, used at `1550`, `1594`, `1597`, `1600`), BTC (`2022`) and PIN (`2286`) without replacement. Unit selectors (`328`), gap-reference selectors (`1529`), model selectors (`1947`), theme (`1986`) and navigation (`2000`) expose no selected/pressed state. DETAILS lacks `aria-expanded` (`1680`), although More correctly supplies it (`948`). Interactive chart history is pointer/touch-only: LEAPS `986–987`, weekly MACD `1290–1291`, gap `1531–1532`.

**Smallest fix:** Add labels/aria-labels, pressed/current/expanded state, and a visible focus rule. Give chart selection a keyboard-operable index/date control or equivalent focus/arrow-key handling. Preserve the present layout and existing More implementation.

## 21. Mobile tap controls remain much smaller than a reliable touch target

**Evidence:** More is 11px text with only 3px vertical padding and no horizontal padding (`index.html:874–876`, `948–950`); DETAILS has 11px text and zero padding (`1680`). The new gap toggles inherit 11px text with 4px vertical padding (`1529`), and UnitPick uses 10px text with 3px vertical padding (`329–330`). No mobile selector adds minimum target dimensions (`2318–2348`). These are particularly unforgiving on a phone under stress.

**Smallest fix:** Add a larger minimum hit area, ideally 44px high, for these touch controls on mobile while keeping the visible typography compact. Static inspection found responsive wrapping for LEVEL tiles (`1465`), gap toggle rows (`1527–1529`), the five-column lookup (`1622–1625`) and mNAV history (`1645–1649`); it did not establish a current-data 390px page overflow. Do not invent a layout redesign on that basis.

## 22. Money formatting diverges for the same kinds of prices

**Evidence / all affected sites:** The grouping-safe cents helper is `msUsd` (`index.html:1322`), used by today's LEAPS price (`1209`), MSTX/LEVEL tiles (`1504`, `1511–1513`) and WHAT IF (`1552`). Equivalent prices bypass it: LEAPS hover MSTX/unit (`1005`), LEAPS reference MSTX (`1012`), unit-lookup MSTX (`1042`) and unit price (`1044`); position debit (`1117`, `1196`); settlement MSTX and unit price (`1133–1136`, `1216–1218`); lookup STRC (`1602`), every projected/best/custom MSTX card (`1582`, `1604–1605`) and all projected/best MSTX table cells (`1624`); debt/preferred dollars per share (`1630`). These raw `.toFixed(2)` paths omit thousands separators, unlike the main tiles. `usdS` drops cents for integral settlement prices (`1133`, `1134`, `1216`), while the slider readout drops both currency and trailing zeros (`1240`): the captured page shows `$16.50` alongside `16.5`. Abbreviations also differ: uppercase K in `fmt`/Ladder axis (`313`, `847`) versus lowercase k on LEAPS axis (`972`, `991`) and lookup axis/mobile Bitcoin cells (`1611`, `1624`); the lookup axis also omits `$`. Grouped integer helpers themselves mix browser-default locale (`316`) with explicit en-US (`324`, `972`, `1135`, `1217`, `1582`). Deliberate whole-dollar MSTR versus cents MSTX precision is not the defect.

**Smallest fix:** Route dollar amounts through shared explicit-en-US whole-dollar/cents helpers and use one compact-currency helper for monetary axes. Keep input editing strings unformatted. Make the settlement readout use the same price precision as its table.

## 23. Signed-number formatting mixes hyphens, minus signs and zero conventions

**Evidence / all sites in these families:** Raw minus signs come from `.toFixed`/numeric string conversion in Ladder band differences (`index.html:581`), held-quantile return (`606`), deviation calculation/display (`1899`, `2059`) and LEAPS reference percentage change (`1013`). These also add `+` to zero in some paths or can display `-0.0`. The shared Unicode-minus percent helper `msPct` (`1320–1321`) suppresses signs on rounded zero; its rendered sites are the lag explanation (`1427–1428`), tally (`1433`), rule sentence (`1435–1437`), alert cells (`1472–1475`), lag tile (`1505`), LEVEL (`1511`), chart selection/axis (`1530`, `1536`), WHAT IF (`1552`), lookup current gap (`1603`) and DETAILS (`1684`). Other Unicode paths are `sgn` (`888`, used `1155`, `1287`), LEAPS dollar sensitivity (`1026`, `1047`), vol label (`1036`), unit-price change (`1045`), past-date offset (`561`) and margin drawdown (`2208`); `sgn` itself prints `+0` where `msPct` prints `0%`.

**Smallest fix:** Use one signed-number core with Unicode minus and an explicit rounded-zero policy, then wrap it for percent/dollar/integer output at the listed sites. Leave unsigned magnitudes unsigned.

## 24. Dates switch format even within the same card

**Evidence / all date-display families:** `md` (`index.html:886`) gives M/D at LEAPS chart ends (`1001–1002`), references (`1012`), unit lookup (`1042`), Playbook refresh (`1098`), MACD tooltip (`1155`), MACD labels (`1282–1285`) and caption (`1294–1295`), lookup decay/table dates (`1604`, `1621`), and mNAV rolling-average captions (`1654–1655`). `mdy` (`887`) gives M/D/YY for gap selection/endpoints (`1530`, `1540`), mNAV STRC-start prose (`1652`), history endpoints (`1667`), build caption (`1671`) and date-range caption (`1672`). The LEAPS hover instead displays raw YYYY-MM-DD (`1005`), as do model fallback price provenance (`1504`) and rules agreement (`909`); LEAPS update text prints the raw `YYYY-MM-DD HH:mm` field (`1261`, `data/leaps-cost.json:2`). `fmtMonth` gives month-name/year (`240`, used `2118`, `2180`); header uses month-name/day/year (`1939`). Alert/monitor timestamps use M/D plus local-device time (`1350–1352`, `1472`, `1506`), while the BTC time is local-device time alone (`1935`). Neither specifies the New York timezone used by the session logic. Native date inputs (`537`, `1031`, `1596`) add browser-locale presentation. Embedded narrative dates are content, not helper call sites, and are outside this formatting finding.

**Smallest fix:** Share explicit New York date/time helpers; use a consistent short-date policy, including year for historical/multiyear views. In particular make LEAPS hover match its surrounding chart dates, and label ET timestamps. Keep native date inputs, with their accessible labels.

## 25. Confirmed leftovers add maintenance noise

**Evidence:** `canvasRef` is allocated and never used (`index.html:617`); `mEv` is computed and never used (`1578`), making the `mnavEv` field stored at `1388` dead too. The light-mode primary-background rule appears twice identically (`1814`, `1820`). Comments still promise an alert bell (`1984`) and tier circles (`2332`) that the corresponding markup no longer contains. Every hook in the reviewed components precedes its conditional return; there is no demonstrated conditional-hook defect. Mobile selectors for four Ladder stats (`2320`), six-column lookup (`2322`), and existing slider/rail layouts still correspond to actual markup. The new five-column lookup intentionally has its own `narrow` branch, so absence of a five-column substring selector is not itself a bug.

**Smallest fix:** Remove the unused ref/value/dead field and duplicate rule; correct those two comments. Do not remove working selectors merely because a particular tab/state does not currently render their targets.

Verdict: The dashboard needs coherent dated price snapshots and failure-safe calculations before its live-looking outputs can be trusted under fetch failures or an overnight session.

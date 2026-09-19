# Adversarial product review, 2026-09-19

Lens: one trader, on a phone, under money stress, moving fast. Read-only review. Evidence is
`tools/audit-2026-09-19/rendered-text.json` (exact rendered text, default and expanded), `index.html`
line by line, and `data/*.json`. Yesterday's cleanup decisions (`tools/audit-2026-09-18/DECISIONS.md`)
are treated as settled and not relitigated. The Ladder tab's shape is treated as settled too: the two
Ladder findings below are a wrong number and a missing word, not a redesign.

Verdict is at the end.

---

## HIGH

### 1. The PRICE LOOKUP band percentages are computed backwards and carry no label

**Principle.** A bare signed percentage next to a price is read as "what I make if it gets there."
If the number is actually something else, the reader does not discover that; he acts on it. Two
percentages on the same card must never be computed in opposite directions.

**Where.** Ladder tab, PRICE LOOKUP, band cards. `index.html:571` and `:578-583`.

**The exact text.** At today's $81,007, the six band cards render:

```
0.1%   $66,056   +22.6%      15%   $89,333   -9.3%      50%  $144,481  -43.9%
85%   $181,036   -55.3%      95%  $238,253  -66.0%   99.9%  $259,675  -68.8%
```

`$89,333` is **above** today's price, and the card puts `-9.3%` under it **in red**. Reaching it is a
**+10.3%** move. `$144,481` shows `-43.9%` in red; reaching it is **+78%**. The code is
`aboveBelow = (ref / shown - 1) * 100` — "today is 9.3% below that band" — rendered with no words.
Eight lines below, on the same card, `TODAY'S 11.3q HELD TO THIS DATE` renders `+2.4% from today's
price` using the **opposite** formula (`index.html:597`, `shown / ref - 1`) and a label.

**Why it matters.** He uses this card to pick the short strike. Every band above today's price is
painted red with a negative number, which is the visual grammar of a loss.

**Smallest change.** Flip to `shown / ref - 1` so it matches the row below, and add three words.
Replacement: `+10.3% from today` under `$89,333`, `+78.4% from today` under `$144,481`. Keep the
green/red colouring, which then means what it looks like it means.

---

### 2. The routes table calls LEAPS unit counts "ODDS"

**Principle.** A two-digit number in the forties and fifties under a column headed ODDS is a
probability. Nothing else. If it is not one, the header has to change.

**Where.** Playbook tab, LEAPS UNITS AT THE END, BY ROUTE. `index.html:1249`; data
`data/paper-ledger.json` → `plan.routes[].units_thesis` / `units_market`.

**The exact text.**

```
ROUTE                                                            YOUR ODDS   MARKET ODDS
Double calendar to Fri 10/2 → Jan/Dec (strike map) → LEAPS 12/19        49            52
Double calendar to Fri 10/2 → LEAPS straight on 10/5                    51            52
Close today and buy LEAPS now, after five cents of slippage             57            57
```

49, 51, 57 are **LEAPS unit counts** at the end of each route. The card title says so. The column
headers contradict the card title, and the headers are what a fast reader takes.

**Why it matters.** "Close today: 57% odds vs 49%" is a route decision. "Close today: 57 units vs 49"
is the same decision for a different reason, and he needs to know which he is making.

**Smallest change.** Headers to `YOUR VIEW` and `MARKET`, and add one word to the card title so the
unit travels: `LEAPS UNITS AT THE END, BY ROUTE (COUNT, NOT ODDS)` — or simply put `UNITS` in both
headers: `UNITS, YOUR VIEW` / `UNITS, MARKET`.

---

### 3. Cheap and Rich fire below the bias the site itself measures, and the test window is 70% bear

**Principle.** A threshold on a biased estimator is a threshold on the bias, not on the thing. If a
page publishes both the threshold and the bias, it has to reconcile them on the page.

**Where.** MSTX tab. Thresholds: `data/mstr-config.json` (`rich_threshold 0.04`, `cheap_threshold
-0.03`, doubled to MSTX terms at `index.html:1409`). Bias: `data/mnav-history.json` → `era`, rendered
at `index.html:1652-1653`. Gate consumer: Ladder THE RULES, ENTRY row.

**The exact text.** mNAV HISTORY renders:

> Projected has only been tested since STRC began on 7/30/25: 287 days, 70% of them bear-market days.
> MSTR ran above projected in both, by 10.4% on bull days and 4.0% on bear days.

And the ALERT LOG rules line renders:

> ... Cheap at −6% MSTX ...; Rich at +8% MSTX. Rich fires in either regime.

Those are the same units once doubled. Bull-day bias is **10.4% MSTR = 20.8% MSTX**, against a Rich
line at **+8% MSTX**. Bear-day bias is **4.0% MSTR = 8.0% MSTX** — the Rich line exactly. So on the
average bear day the tab already sits at RICH, and in a bull market it would sit far past it, more or
less permanently.

Then the Ladder ENTRY rule says: **"Never open a primary while Rich is on."**

**Why it matters.** This is his stated worry ("the math is only tested on bear-market data") and the
site has the numbers to confirm it four cards apart without ever putting them together. Today's
`FAIR` at `+7.7%` does not mean fairly priced. It means *one tick under the average bear-market
premium*. Taken literally, the entry rule locks him out of the next bull market.

**Smallest change.** Two things, both wording, no maths:

1. One line under the rules line in ALERT LOG: `Measured against projected, which has run +8.0% MSTX
   above price on the average bear day and +20.8% on the average bull day (287 days since 7/30/25,
   70% bear). Rich at +8% is roughly the bear-market average, not an extreme.`
2. On the LEVEL card, replace the tile sub `against projected` with `against projected · bear-market
   average is +8.0%`.

Re-cutting the thresholds is a separate decision and is not a wording fix. Flag it, do not do it here.

---

### 4. "Gap" is four numbers and at least two different quantities on one tab

**Principle.** One word, one number. If a stressed reader sees the same word carrying different values
inches apart, he stops trusting all of them — or worse, picks whichever supports what he already wants.

**Where.** MSTX tab. `index.html:1412` (LEVEL), `:1451` (WHAT IF), `:1478-1481` (GAP CHART),
`:1573` (BITCOIN PRICE LOOKUP).

**The exact text, all on one screen scroll.**

| Card | Renders | What it actually is |
|---|---|---|
| LEVEL | `GAP MSTX +7.7% / against projected` | live level gap, price over projected |
| WHAT IF | `GAP MSTX +7.8% / against projected` | the same thing off the typed boxes |
| GAP CHART · MSTX | `9/18/26 · gap vs projected +9.6%` | a **one-day** gap, a different quantity |
| BITCOIN PRICE LOOKUP | `carries 100% of today's +4.4% MSTR gap` | level gap, MSTR terms, third base |

The chart is the serious one. `gapsProj` computes
`mstx_today / (mstx_yesterday × (1 + 2 × (proj_today / mstr_yesterday − 1))) − 1` — a single day's
deviation. Checked against the data: 9/17 MSTX 14.14 / MSTR 132.25, 9/18 MSTX 18.73 / proj 146.04
gives **+9.6%**, which is what renders. But `data/mstr-model.json` carries the *level* gap for 9/18 as
`gap: 5.4` (**+10.8% MSTX**), and the chart's own fallback branch (`:1481`) uses exactly that when the
previous row is missing. **So one line mixes two definitions depending on data availability** — and it
is drawn against the `−6%` / `+8%` dashed lines, which are level thresholds the alerts fire on.

**Why it matters.** The chart looks like the history of the LEVEL number and of the alert line. It is
not. He cannot use it to ask "how often does this fire" or "how extreme is today."

**Smallest change.** Make the chart plot the level gap (`r.gap × 2`) for every row, which is the
quantity the dashed lines belong to and the quantity LEVEL shows. If the one-day series is worth
keeping, it is a second toggle with its own name (`day move` vs the existing `vs projected` /
`vs best estimate`), not the same word. And in BITCOIN PRICE LOOKUP, say `MSTR gap` in the tile sub so
the unit is visible: `carries 100% of today's +4.4% gap in MSTR terms (+8.8% MSTX)`.

---

### 5. The routes are ranked on counts the site says are ~15% too high, and it says so last

**Principle.** A known error belongs beside the number, not at the end of a hidden paragraph. If the
error is bigger than the spread between the options, the table cannot be used to choose.

**Where.** Playbook tab, routes footnote. `index.html:1260-1261`; data `plan.routes_note`.

**The exact text**, the last sentence of a 740-character paragraph that is collapsed by default:

> These counts were built on the earlier unit formula, which reads about 15% below the real option
> prints at these prices, so each count is high by about that much. The by-close table above uses the
> print-based unit price.

The three route counts are **49, 51, 57**. A 15% haircut takes them to roughly **42, 43, 48**. The
spread between the first two routes is 2 units; the stated error is 7.

**Why it matters.** He is choosing between three routes with real money and real settlement dates on a
table whose own footnote says it is inflated, in text he has to tap twice to reach.

**Smallest change.** Either recompute the three counts off `data/leaps-cost.json` `unit_at`, the same
source the by-close table already uses, or put the haircut on the surface. If the second: add one
visible line directly under the table, outside the `More`:
`Counts run about 15% high: they use the older unit formula, not the print-based one in the table
above.`

---

### 6. "OFF" in 28px above the position panel, with nothing saying what is off

**Principle.** The largest word on the first screen is the one word the reader takes away. It must be
self-describing.

**Where.** Playbook tab, hero. `index.html:1090-1091` (the value) and `:1175-1176` (the render).

**The exact text.**

```
MSTX · TODAY                                  REFRESHED 9/18 · 1 DAY OLD
OFF · PHASE 1
Hold both calendars. No reshapes: eight alternatives were tested on 9/18 ...
```

`OFF` is `trig`, the weekly-MACD entry gate (`ENTRY` / `HOLD` / `OFF`). It is rendered unlabelled,
in tier colour, immediately above a panel headed `PHASE 1 · WHAT IS ON`.

**Why it matters.** "OFF · PHASE 1" on a phone, half-read, is "phase 1 is off." He has $17,975 in two
calendars. The correct reading is "new entries are gated off; phase 1 is running."

**Smallest change.** One word in front of it. Replace `{trig + " · PHASE " + ph.id}` with a small
label above the word: `ENTRY GATE` over `OFF`, and move `PHASE 1` down next to the position panel
where it belongs. Minimal version, one string: `ENTRY OFF · IN PHASE 1`.

---

### 7. A hardcoded, undated, unsourced statistic shows up at the sell decision

**Principle.** A number that argues for or against a trade must be dated and sourced, or it will
outlive its evidence silently. A number baked into the page source never updates and never announces
that it has not.

**Where.** MSTX tab, LEVEL card, the RICH branch. `index.html:1460`, a string literal in the JSX.

**The exact text.**

> Behind projected... / *when RICH:* Ahead of projected. Three of five past Rich readings faded and the
> last two ran 25% and 52%, so it is not a sell on its own. About half of a gap fades in a month.

"Three of five" and "25% and 52%" are typed into the component. Nothing recomputes them. Nothing dates
them. Every other statistic on this tab comes from a JSON file with an `as_of`.

**Why it matters.** This text appears exactly when he is looking at a RICH reading and deciding
whether to sell. It is the most consequential sentence on the tab and the least maintained one.

**Smallest change.** Either drive it from `data/mstr-model.json` `episodes` like the rest of the tab,
or, minimum today, stamp it: `Three of five past Rich readings faded; the last two ran 25% and 52%
(hand-counted 9/17, not auto-updated).`

---

### 8. Every timestamp is browser-local, unlabelled, and year-less, while the market clock is New York

**Principle.** A trading clock without a zone is not a clock. Staleness judgments made off it are
guesses.

**Where.** `index.html:1350-1352` (`msWhen`) against `:1343-1348` (`msOpen`).

**The exact text.** The header renders `5:29 PM` and `Sep 19, 2026`. The MSTX tab renders `MONITOR /
9/19, 5:22 PM / last run · 6 min ago`. The alert log renders `9/18, 3:15 PM`, `9/17, 11:13 AM`.

`msWhen` is `toLocaleString` with no `timeZone`, so it prints the **browser's** zone with **no label
and no year**. `msOpen` is explicitly `America/New_York`. So `OFF HOURS` is decided in ET and every
timestamp beside it is printed in whatever zone the device is in.

**Why it matters.** The heartbeat is the one thing standing between him and trading off a dead
monitor. "6 min ago" is correct in any zone, but the moment he cross-checks the stamp against the
market clock — which is the natural thing to do when something looks wrong — the two disagree and he
cannot tell which is lying. The alert log has the same problem plus no year, so 9/17 rows will read
identically next September.

**Smallest change.** Pin `msWhen` to `timeZone: "America/New_York"` and append ` ET` once per card,
not per row. On the ALERT LOG header, `WHEN` becomes `WHEN (ET)`.

---

## MEDIUM

### 9. The hero and the Exits paragraph are the same text, twice

**Where.** Playbook tab. `index.html:1177-1183` (hero) against `:1200-1202` (Phase 1 Exits).

**The exact text.** The hero renders the three `next_action_steps` plus `next_action_detail`. The
Exits line renders `next_action + " " + next_action_detail`. `next_action_detail` therefore appears
**verbatim twice** on one tab:

> Proposed for Mon 9/21, not yet decided: sell both calendars 20 to 30 minutes after the open and buy
> LEAPS units in thirds. One third Monday, one third when the gap is at or under zero or on 10/2, one
> third on a Cheap alert or on 10/16. No Phase 2.

And `next_action` restates the three steps he just read in the hero, in compressed form.

**Why it matters.** He said there is too much text. This is ~450 characters of exact repetition on the
tab's first two cards, which is also why the tripwire reads as two contradictory bands (`above $20 or
under $15` in the hero, `outside $15 to $19` in the checkpoint) — both true, both restated, neither
adjacent to the other.

**Smallest change.** Delete the Exits block (`index.html:1201-1202`). The hero already carries every
word of it. If Phase 1 needs a closing line, use the one fact the hero lacks: `Decision date Fri 10/2.`

---

### 10. "TODAY" in LEAPS UNITS is yesterday's close, and two cards give two "today" costs

**Where.** Playbook tab. `index.html:1209`, `:973-974`, `:1020-1021`, `:1040-1045`. Data
`data/leaps-cost.json` → `ref.today.d = "2026-09-18"`, `model.asof = "2026-09-18"`,
`model.mstx_last = 18.73`.

**The exact text.**

```
Today’s unit price: $3.97
TODAY  $79,442   9/18 · MSTX $18.73
200 UNITS COST  $79,526   9/19 · MSTX $18.73
ONE UNIT  $3.98   same as today
```

Three problems in four lines. `TODAY` is the **9/18** close. The lookup stamps **9/19** onto the
**9/18** price. The two 200-unit costs differ by $84 and both call themselves today. And `$3.98` is
labelled `same as today` on a card that said `$3.97` sixty pixels earlier. Meanwhile the MSTX tab
shows MSTX at **$18.49** live, so the whole panel is priced 1.3% off.

**Smallest change.** Label the panel once instead of six times: change the headline to
`Unit price at the 9/18 close: $3.97` and set the lookup's default date to `lc.model.asof` rather than
today, so the date and the price agree. Round the lookup's one-unit display to match (`$3.97`).

---

### 11. Two Bitcoin prices on two tabs, and the MSTX one reads like the 50-day

**Where.** Ladder stat card against MSTX LEVEL card, `index.html:1513`.

**The exact text.** Ladder: `PRICE $81,007`. MSTX: `BTC VS 50-DAY / above / $81,111`.

The tile's value is the regime word and its sub is the BTC price from the monitor — but the tile is
headed `BTC VS 50-DAY`, so `$81,111` reads as *the 50-day*, which is the one number a reader would
want there. And it disagrees with the Ladder's $81,007 by $104 with no stamp on either.

**Smallest change.** Put the 50-day in the sub, which is what the label promises, and name the other:
`BTC VS 50-DAY / above / BTC $81,111 · 50-day $7x,xxx`. If the 50-day is not in the monitor state,
at minimum label the number: `BTC $81,111 (monitor)`.

---

### 12. The SIZE rule is a schedule; he has to work out which line is today

**Where.** Ladder tab, THE RULES. `index.html:910-913`; data `data/ladder-rules.json`.

**The exact text.**

> SIZE — The primary takes 80% of the sleeve on 9/17, 70% on 9/26, 60% at the LEAPS and after. The rest
> is the two 10% gap sleeves and a cash floor that grows with each phase.

Today is 9/19. The answer is 80%, and he has to derive it. `ladder-rules.json` already carries a
`sizing` array with `{when, primary_pct}` and the exact dates (`2026-09-17: 80`, `2026-09-26: 70`,
`2026-12-19: 60`), so the live number is one lookup away.

**Why it matters.** This is the number that decides position size. It should be a number, not a
schedule to parse on a phone.

**Smallest change.** Render the live figure and demote the schedule:
`SIZE — 80% of the sleeve today. Drops to 70% on 9/26 and 60% on 12/19. The rest is two 10% gap
sleeves and a cash floor.`

---

### 13. The ENTRY rule turns on a number that only exists on another tab

**Where.** Ladder THE RULES, ENTRY row, against MSTX LEVEL.

**The exact text.**

> ENTRY — Gap at or under zero. Cheap is the add. Never open a primary while Rich is on.

The Ladder tab never renders the gap or the verdict. Today they are `+7.7%` and `FAIR`, so entry is
off — and nothing on the tab that states the rule says so.

**Smallest change.** Append the live read to the ENTRY row, sourced the same way the MSTX tab sources
it: `ENTRY — Gap at or under zero. Cheap is the add. Never open a primary while Rich is on. Now: FAIR,
gap +7.7%.`

---

### 14. mNAV is two different numbers on one card, both called mNAV

**Where.** MSTX tab, BITCOIN PRICE LOOKUP and mNAV HISTORY. `index.html:1598`, `:1602`, `:1654`.

**The exact text.**

```
YOUR mNAV, DEBT AND PREFERRED INCLUDED (NOW 1.17)
BEST ESTIMATE mNAV   1.00   projected 0.96 · high 0.96
mNAV NOW             1.00   projected 0.96
```

`1.17` is the debt-and-preferred-inclusive identity; `1.00` is gross. The difference is explained in a
footnote 300 words long, behind a `more`.

**Why it matters.** He types a number into that box. If he types the 1.00 he sees on the card beside
it, he gets an answer computed on the other definition.

**Smallest change.** Name them differently on the surface. `mNAV NOW 1.00` becomes `mNAV NOW (GROSS)
1.00`; the box label becomes `YOUR mNAV (NET OF DEBT AND PREFERRED) · NOW 1.17`, and the placeholder
becomes `1.17` instead of `optional` so the default is the right scale.

---

### 15. Jargon is never defined where he first meets it, and one term outlived its panel

**Where.** Throughout. Worst offenders and first appearance:

| Term | First met | Defined? |
|---|---|---|
| `sleeve`, `the two 10% gap sleeves` | Ladder, SIZE rule | never |
| `strike map` | Playbook routes row 1 | never — the Phase 2 strike-map panel was **cut** on 9/18 |
| `q` / `11.3q` | Ladder, QUANTILE stat card | never |
| `projected` vs `best estimate` | MSTX LEVEL tiles | only in BITCOIN PRICE LOOKUP, three cards later |
| `gap` | MSTX LEVEL | never, and see finding 4 |
| `units` (LEAPS) | Playbook LEAPS UNITS | yes, correctly, in the objective line — the one good example |

**Why it matters.** The LEAPS objective line shows the right pattern: define it once, at first sight,
in one sentence. Nothing else on the site does.

**Smallest change.** Four one-liners, each in the sub-label of the card where the word first appears.
`sleeve` → add `(the sleeve is the MSTX book, not the whole account)` to the SIZE row. `q` → add
`quantile: where BTC sits in the power-law band, 0 to 100` to the QUANTILE stat sub. `projected` →
move the existing `Projected is your mNAV formula` line from BITCOIN PRICE LOOKUP up to LEVEL, which
is where the word first lands. `strike map` → replace with the plain description in the route string,
since the panel that explained it is gone: `Jan/Dec at the mapped strikes`.

---

### 16. Internal working notes are on the page

**Where.** Playbook routes footnote. `data/paper-ledger.json` → `plan.routes_note`, rendered at
`index.html:1260-1261`.

**The exact text.**

> ... **Leif model**, 2026-09-18 13:10 ET, MSTX $18.00, no cash carried. Phase 1 marked at 100% vol at
> the 10/2 close, **the site's basis**; ... **Your view =** the 10/2 and 12/18 odds shifted one dollar
> up, and it **LOWERS** the count here because ...

`Leif model` is the name of the system that wrote it, not a fact about the trade. `Your view =` is
addressed at a note-taker, not a reader. `LOWERS` in capitals is emphasis from a working draft.

**Why it matters.** He asked for an 11/10 product. A product does not refer to its own authoring
system in the middle of a footnote, and the shift in address ("your view") breaks the voice the rest
of the site holds.

**Smallest change.** Rewrite the note's first and third sentences:
`Priced 9/18 1:10 PM ET at MSTX $18.00, no cash carried. Phase 1 is marked at 100% vol at the 10/2
close; at 118% the first two routes read 65 / 69 and 68 / 69, and closing today reads 57 to 75
depending on the vol the calendars are sold at. Shifting the 10/2 and 12/18 strikes one dollar up
lowers the count, because Phase 1 pays for MSTX sitting between $16 and $18.`

---

### 17. The one-week estimate is higher than the one-month estimate, with no explanation

**Where.** MSTX tab, LEVEL card. `index.html:1512`, `aheadMstx` at `:1455-1459`.

**The exact text.**

```
BEST ESTIMATE, 1 WEEK   $18.05
1 month $16.97 · model, if Bitcoin holds
```

Bitcoin is held flat in both, so the fall from $18.05 to $16.97 is pure 2x volatility decay at 75%
MSTR vol. Nothing says so.

**Why it matters.** It reads as an error, and the card is the site's own better-tested estimate. One
number that looks broken discredits the three beside it.

**Smallest change.** Change the sub to: `1 month $16.97 · flat Bitcoin, after 2x decay`.

---

### 18. LEVEL at FAIR says nothing about what to do or what would change it

**Where.** MSTX tab, LEVEL. `index.html:1460-1461` — `levelRead` is set for RICH and CHEAP and is the
**empty string** for FAIR.

**The exact text.** Today the card renders `LEVEL / FAIR` and four tiles, and no sentence at all.
RICH and CHEAP each get a paragraph.

**Why it matters.** FAIR is the state he will see most days. It is the only state the card has no
words for, so the most common visit to the most consequential card returns nothing actionable. A
trader expects two things here: what to do now, and what would change the read.

**Smallest change.** Give FAIR one sentence with the trigger levels in it:
`Between Cheap and Rich. No add here: entry wants the gap at or under zero. Cheap is $16.13, Rich is
$18.53 at today's projected.` (Both derived from `projected × (1 + threshold)`, already on the card.)

---

### 19. A GitHub edit link to the live thresholds sits inside the trading surface

**Where.** MSTX tab, WHAT IF card. `index.html:1555`.

**The exact text.** `RESET TO LIVE    edit config` — the second is an anchor to
`github.com/.../edit/main/data/mstr-config.json`.

**Why it matters.** It is one tap from `reset to live`, on a phone, and it opens an editor on the file
that sets Cheap, Rich and the lag line. Maintenance affordances do not belong beside trading controls.

**Smallest change.** Move it to the collapsed DETAILS section at the bottom of the tab, where the other
maintenance content already lives.

---

### 20. Format drift: dates, currency and punctuation

**Where.** Across the Playbook and MSTX tabs.

**The exact text.** Six date formats on one tab: `9/18` · `9/18/26` · `2026-09-19 13:05` ·
`Sep 19, 2026` · `Fri Oct 2` · `Dec 15 2028`. Plus:

- `MSTX ON SETTLEMENT  16.5` — bare number, no `$`, beside a table column reading `$16.50`
  (`index.html:1240`).
- `Today’s unit price` — curly apostrophe; everywhere else is straight (`index.html:1209`).
- Alert log rows of kind `rich` and `watch` render `pending` in both scoring columns **permanently** —
  scoring only ever applies to `kind === "lag"` (`index.html:1431`, `:1472-1475`). The top row of the
  log has read `pending / pending` since 9/18 and always will.

**Why it matters.** He named this one himself. Each is trivial; together they are the texture that
makes a page feel unfinished.

**Smallest change.** One date helper, `m/d` inside the current year and `m/d/yy` outside it, used
everywhere; `$` on the slider readout; straight apostrophe; and render `—` instead of `pending` for
rows whose kind is never scored.

---

## Top 5 changes I would ship today

1. **Fix the PRICE LOOKUP percentages** (finding 1). Flip the formula to match the row directly
   beneath it and add `from today`. A red `-9.3%` under a price 10% above the market is the one thing
   on the site that can be read backwards in a single glance.
2. **Rename the routes columns** (finding 2). `YOUR ODDS` / `MARKET ODDS` → `UNITS, YOUR VIEW` /
   `UNITS, MARKET`. Two words, removes a probability-versus-count confusion on a live route decision.
3. **Put the bias next to the threshold** (finding 3). One line under the ALERT LOG rules line saying
   Rich at +8% is about the bear-market average. It answers his own standing worry using numbers the
   site already publishes, and it stops `FAIR` from reading as "fairly priced."
4. **Delete the Exits block and label the hero word** (findings 9 and 6). `ENTRY OFF · IN PHASE 1` at
   the top, and the duplicate 450-character paragraph gone. Biggest text cut available for the least
   risk, on the tab he says is too wordy.
5. **Surface the routes haircut** (finding 5). One visible line under the routes table saying the
   counts run ~15% high. Until the counts are recomputed, the table should not be readable without it.

Findings 4 (gap definitions) and 8 (timezone) are the next two, and both are larger than a wording
change — 4 needs the chart series rebuilt on the level gap, 8 needs `msWhen` pinned to ET. Schedule
them, do not rush them.

---

## Verdict

**FIX.**

The site is close and the structure is right. The Ladder tab earns the affection he has for it, the
LEAPS objective line is a model of how to define a term once and move on, and the monitor heartbeat is
exactly the right instinct. But three findings put a wrong number under a stressed reader's thumb —
the inverted lookup percentages, the counts labelled as odds, and a Rich threshold sitting at the
measured bear-market average while a rule says never to enter while Rich is on. Those are not polish.
Fix 1, 2, 3 and 5 before the next session in front of it; 6 and 9 the same day because they are free.
Then it ships.

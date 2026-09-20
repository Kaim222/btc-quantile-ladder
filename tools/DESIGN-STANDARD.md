# Design standard for the ladder site (agreed 2026-09-19)

Alex reads this on a desktop and a phone. Anything that breaks these rules reads as sloppy to him. Check every change against them with real screenshots at 1280px and 390px before pushing.

1. Type scale on the MSTX and Playbook tabs. 10px uppercase labels and chart axis text. 12px secondary text, table cells, tile sub lines, legends and footnotes. 14px body sentences and primary table rows. 22px tile numbers. The card's one headline word is the only larger text. Use the shared TYPE constants, never a typed number. One row or one table uses one size and one weight, except the single emphasized number.
2. Every range slider shows a track about 4px tall, a filled part in the accent colour and a 16px thumb.
3. Charts are at least 200px tall on a desktop and 180px on a phone. Each has a visible legend row of colour swatches with short names under its header. Legends never sit behind the More toggle.
4. Projected is the mNAV formula price. Best estimate is projected plus today's gap, which fades over weeks. Both are defined in a visible line where the words first appear. Never call the formula price "the rule". Show projected and best estimate for both MSTR and MSTX whenever either appears.
5. Copy has no colons, semicolons, em dashes or en dashes inside sentences and no parenthetical asides. Sentences run 20 words or fewer. A card shows at most two sentences and the rest goes behind More or is cut. Ranges say "to". Labels and meta lines may use the middle dot. Text that scripts generate follows the same rules, so fix the script, not the output.
6. Numbers carry commas, dollar signs and a true minus sign. A rounded zero has no sign. Input boxes show commas too. Big numbers on chart axes, the price rail and the forward table stay compact, for example $100K.
7. Tables have aligned columns and a header row. No orphan tile alone on a desktop row. No text wraps in the middle of a word. No sideways scroll at 390px.
8. The Ladder tab is liked as it is. Fix clear inconsistencies there and nothing else.
9. No helper text under a label, tile or heading unless it carries a fact the reader needs and cannot get from the heading. This is the house writing skill's rule for UI copy. A tile is a label and a number. A sub line earns its place only with a needed fact, such as a time stamp or a comparison value.
10. Every sentence has one thought, under 20 words and at most one comma. Each visible sentence sits on its own line on a desktop. At 1280px no text wraps to a second line in the default state. At 390px no label, tile value, tile sub line, table header or table cell wraps, and body sentences take at most two lines.
11. Every input box that holds dollars shows a "$" inside the box. Chart axes that show dollars carry the "$" too.
12. A price typed into the Ladder tab is a what-if. The instrument and structure cards show the rung for that price and say the live band is unchanged.

Acceptance test. `tools/measure_ui.js` runs in a Playwright page against a local server and lists every wrapped text node, every sentence over 20 words or with two or more commas, and every dollar input without a "$", on all three tabs at 1280px and 390px. A change is done when the desktop lists are empty and the phone lists hold body sentences only.

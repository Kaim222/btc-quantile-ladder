# -*- coding: utf-8 -*-
# Re-applies the EVIDENCE block on top of whatever the model generator last wrote.
# Idempotent: safe to re-run after every rebuild of data/mstr-model.json.
import json, collections, sys
p = r"C:/Users/AlexKaim/orchestrators/my-projects/personal/trading/btc-quantile-ladder/data/mstr-model.json"
raw = open(p, "rb").read()
nl = "\r\n" if b"\r\n" in raw else "\n"
d = json.loads(raw.decode("utf-8"), object_pairs_hook=collections.OrderedDict)

bt = d.get("backtest") or {}
c4 = bt.get("cheap_4pct") or {}
reg = d.get("regime") or {}
rows = reg.get("rows") or []
def find(sub):
    for r in rows:
        if sub in str(r.get("state", "")).lower(): return r
    return {}
above, below = find("above"), find("below")

d["evidence"] = collections.OrderedDict([
  ("lag", collections.OrderedDict([
    ("note", "5-minute bars, 60 days since 2026-07-20. MSTR drops this far vs the trailing hour while BTC holds. Returns are MSTR minus BTC."),
    ("rows", [
      {"mstr": -0.5, "mstx": -1.0, "n": 109, "m30": -0.04, "m60": -0.14},
      {"mstr": -1.0, "mstx": -2.0, "n": 21,  "m30": 0.05,  "m60": 0.15},
      {"mstr": -1.5, "mstx": -3.0, "n": 6,   "m30": 0.83,  "m60": 0.82},
      {"mstr": -2.0, "mstx": -4.0, "n": 3,   "m30": 0.91,  "m60": 1.06}]),
  ])),
  ("level", collections.OrderedDict([
    ("note", "Daily closes, 285 days since STRC listed. Cheap by 4% MSTR, 8% MSTX."),
    ("sheet_slope", collections.OrderedDict([
      ("slope", 0.025), ("days", c4.get("days")), ("episodes", c4.get("episodes")),
      ("above_50d_mstr_5d", above.get("mstr_5d")), ("below_50d_mstr_5d", below.get("mstr_5d"))])),
    ("measured_slope", {"slope": 0.0125, "episodes": 2, "read": "both states positive"}),
    ("rich", collections.OrderedDict([
      ("bars", "hourly"), ("cut_mstr", 3.0), ("cut_mstx", 6.0), ("episodes", 12),
      ("mstr_vs_btc_5d", -1.9),
      ("read", "Rich by 3%+ MSTR (6% MSTX), hourly bars: 12 episodes, \u22121.9% vs BTC over 5 days.")])),
  ])),
  ("verdict", "One threshold has data behind it: -1.5% MSTR lag (-3% MSTX), six events in two months that came back 0.8% in half an hour. The rest are levels that depend on BTC's trend, or knobs. The monitor's log is the live test."),
  ("verdict_lines", [
    "The \u22123% MSTX lag is the one line with data.",
    "Six events in two months, back +1.7% in half an hour.",
    "The rest are levels that ride BTC's trend, or knobs.",
    "The monitor's log is the live test."]),
])

d["episodes_meta"] = {"cut_mstr": 4, "slope": d.get("model", {}).get("slope", 0.025)}
if "verdict" in bt: bt.pop("verdict")

# short labels so the table reads on a phone, and a read that fits in two lines
SHORT = {"above": "BTC above 50-day", "below": "BTC below 50-day",
         "since": "Since Jul 2026", "all": "All"}
for r in rows:
    st = str(r.get("state", "")).lower()
    for k, v in SHORT.items():
        if k in st: r["short"] = v; break
    r.setdefault("short", str(r.get("state", "")))
reg["note"] = "Cheap by 4%+ vs projection (8% MSTX), split by BTC's state. 285 days."
reg["read_lines"] = [
  "Above the 50-day, cheap closed with MSTR rising. Below it, BTC fell instead.",
  "Four episodes: a rule to trade by, not a proof."]

open(p, "wb").write(json.dumps(d, indent=1, ensure_ascii=False).replace("\n", nl).encode("utf-8"))
sys.stdout.write("evidence re-applied; sheet_slope above=%s below=%s days=%s eps=%s\n"
                 % (above.get("mstr_5d"), below.get("mstr_5d"), c4.get("days"), c4.get("episodes")))

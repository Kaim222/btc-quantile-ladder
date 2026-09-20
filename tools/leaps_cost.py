"""leaps_cost.py: estimate what 50 LEAPS units cost on every trading day, and write data/leaps-cost.json for the site.

One unit = long MSTR Jun 16 2028 $345 call, short MSTR Jan 21 2028 $500 call (the unit since 2026-09-20; before that it was
long MSTX Dec 15 2028 $33, short MSTX Jan 21 2028 $60). Run:  python tools/leaps_cost.py

Method. The short leg has real trades on Yahoo back to Sep 2025 and the long leg back to Apr 2026. On each short-leg trade
day its implied vol is backed out of that day's close against MSTR's close, smoothed over five prints, and carried between
prints. The long leg's vol is backed out of its own trades the same way. Before its first trade it is the short leg's vol
times the one multiple that best reproduces the unit price on the days both legs traded. Each day's unit is then Black-Scholes on both legs at that day's MSTR close. This is a MODEL estimate at about the mid. It is not what a fill costs: the long leg's market is several dollars wide. Days when both legs really traded
are kept as "prints" so the model can be checked against them.
"""
import json, math, os, datetime as dt
import numpy as np, pandas as pd, yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "leaps-cost.json")
UNDER = "MSTR"
LONG = {"sym": "MSTR280616C00345000", "k": 345.0, "exp": dt.date(2028, 6, 16)}
SHORT = {"sym": "MSTR280121C00500000", "k": 500.0, "exp": dt.date(2028, 1, 21)}
R, N_UNITS = 0.04, 50
LABEL = "long Jun 16 2028 $345 call, short Jan 21 2028 $500 call"

def ncdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))
def call(S, K, T, s):
    if T <= 0: return max(S - K, 0.0)
    d1 = (math.log(S / K) + (R + 0.5 * s * s) * T) / (s * math.sqrt(T))
    return S * ncdf(d1) - K * math.exp(-R * T) * ncdf(d1 - s * math.sqrt(T))
def implied(price, S, K, T):
    lo, hi = 0.20, 3.00
    if not (call(S, K, T, lo) < price < call(S, K, T, hi)): return None
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if call(S, K, T, mid) < price: lo = mid
        else: hi = mid
    return 0.5 * (lo + hi)
def daily(sym):
    h = yf.Ticker(sym).history(period="max")
    h.index = pd.to_datetime(h.index).tz_localize(None).normalize()
    return h

px = daily(UNDER)["Close"].dropna()
mx = daily("MSTX")["Close"].dropna()          # Phase 1 settles on MSTX, so the site maps an MSTX close to an MSTR level
last_common = px.index.intersection(mx.index)[-1]          # both anchors come from the same completed session
px = px[px.index <= last_common]; mstx_last = float(mx[last_common])
try: DRAG = float(json.load(open(os.path.join(HERE, "..", "data", "evidence.json"), encoding="utf-8"))["mstx_drag"]["k_1y"])
except Exception: DRAG = 0.98
sh, lg = daily(SHORT["sym"]), daily(LONG["sym"])
sh, lg = sh[sh["Volume"] > 0]["Close"], lg[lg["Volume"] > 0]["Close"]
start = sh.index[0]
px = px[px.index >= start]
T = lambda d, leg: (leg["exp"] - d.date()).days / 365.0

iv_s = pd.Series({d: implied(p, px[d], SHORT["k"], T(d, SHORT)) for d, p in sh.items() if d in px.index}).dropna()
iv_s = iv_s.clip(0.35, 1.6).rolling(5, min_periods=1).median()
iv_short = iv_s.reindex(px.index).ffill().bfill()
# the long leg's vol as a multiple of the short leg's: the multiple that best reproduces the days both legs really traded
pr = [(d, float(lg[d] - sh[d])) for d in lg.index.intersection(sh.index) if d in px.index]
def sse(q): return sum((call(px[d], LONG["k"], T(d, LONG), iv_short[d] * q) - call(px[d], SHORT["k"], T(d, SHORT), iv_short[d]) - u) ** 2 for d, u in pr)
ratio = min((0.70 + 0.005 * i for i in range(81)), key=sse) if pr else 0.86
iv_long = iv_short * ratio
# the long leg trades most days too, so from its first print it carries its own vol; the multiple only fills the days before
iv_l = pd.Series({d: implied(p, px[d], LONG["k"], T(d, LONG)) for d, p in lg.items() if d in px.index}).dropna().clip(0.35, 1.6).rolling(5, min_periods=1).median()
if len(iv_l): iv_long = iv_l.reindex(px.index).ffill().combine_first(iv_long)
listed = lg.index[0] if len(lg) else px.index[-1]          # first real trade of the long leg

rows = []
for d, S in px.items():
    u = call(S, LONG["k"], T(d, LONG), iv_long[d]) - call(S, SHORT["k"], T(d, SHORT), iv_short[d])
    rows.append({"d": d.strftime("%Y-%m-%d"), "px": round(float(S), 2), "unit": round(u, 2), "cost": round(u * 100 * N_UNITS),
                 "iv": round(float(iv_short[d]), 2)})
ser = pd.Series([r["cost"] for r in rows], index=px.index)
avg = ser.rolling(10, min_periods=3).mean()
for r, a in zip(rows, avg): r["avg10"] = None if pd.isna(a) else round(float(a))
prints = [{"d": d.strftime("%Y-%m-%d"), "unit": round(float(lg[d] - sh[d]), 2), "cost": round(float(lg[d] - sh[d]) * 100 * N_UNITS)}
          for d in lg.index.intersection(sh.index)]
err = [abs(next(r["unit"] for r in rows if r["d"] == p["d"]) - p["unit"]) for p in prints if any(r["d"] == p["d"] for r in rows)]

def back(n):
    i = max(0, len(rows) - 1 - n); return rows[i]
last = rows[-1]
lo = min(rows, key=lambda r: r["cost"]); hi = max(rows, key=lambda r: r["cost"])
ref = {"today": last, "week_ago": back(5), "month_ago": back(21), "two_months_ago": back(42), "three_months_ago": back(63), "low": lo, "high": hi}
# what one unit costs today at other MSTX prices, on today's vols: the site's by-close table reads this
d0 = px.index[-1]
unit_at = [{"px": k, "unit": round(call(k, LONG["k"], T(d0, LONG), iv_long[d0]) - call(k, SHORT["k"], T(d0, SHORT), iv_short[d0]), 2)} for k in range(100, 701, 10)]
out = {"updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "units": N_UNITS,
       "unit": LABEL, "underlying": UNDER,
       "long_first_trade": listed.strftime("%Y-%m-%d"), "short_first_trade": start.strftime("%Y-%m-%d"),
       "vol_ratio_long_to_short": round(ratio, 3), "model_vs_prints_mean_abs_error": round(float(np.mean(err)), 2) if err else None,
       "note": "Model estimate near the mid. Black Scholes runs on each day's MSTR close. Each leg's vol comes from its own real trades. Before the long leg first traded the line is hypothetical. A fill costs more than the mid. On 9/18 the long leg's market was $6.50 wide.",
       "model": {"r": R, "underlying": UNDER, "px_last": round(float(px.iloc[-1]), 2), "mstr_last": round(float(px.iloc[-1]), 2), "mstx_last": round(mstx_last, 2), "drag_k": round(DRAG, 3),
                 "asof": px.index[-1].strftime("%Y-%m-%d"),
                 "long": {"k": LONG["k"], "exp": str(LONG["exp"]), "iv": round(float(iv_long.iloc[-1]), 8)},
                 "short": {"k": SHORT["k"], "exp": str(SHORT["exp"]), "iv": round(float(iv_short.iloc[-1]), 8)}},
       "ref": ref, "unit_at": unit_at, "prints": prints, "series": rows}
tmp = OUT + ".tmp"          # write whole, then swap, so a crash never leaves half a file for the workflow to commit
with open(tmp, "w") as fh: json.dump(out, fh, indent=1, allow_nan=False)
os.replace(tmp, OUT)
print("wrote %d days, %s to %s. vol ratio %.3f. prints %d, mean abs error vs prints $%.2f a unit" % (len(rows), rows[0]["d"], last["d"], ratio, len(prints), np.mean(err) if err else float("nan")))
for k, r in ref.items(): print("  %-17s %s  %s %7.2f  unit $%6.2f  %d units $%s" % (k, r["d"], UNDER, r["px"], r["unit"], N_UNITS, format(r["cost"], ",")))
for p in prints:
    m = next(r for r in rows if r["d"] == p["d"]); print("  print %s  real $%.2f  model $%.2f" % (p["d"], p["unit"], m["unit"]))

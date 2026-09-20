"""leaps_cost.py: estimate what 200 LEAPS units cost on every trading day, and write data/leaps-cost.json for the site.

One unit = long MSTX Dec 15 2028 $33 call, short MSTX Jan 21 2028 $60 call. Run:  python tools/leaps_cost.py

Method. The short leg has real trades on Yahoo back to May 2026. On each trade day its implied vol is backed out of
that day's close against MSTX's close, smoothed over five prints, and carried between prints. The long leg listed in
August 2026 and has only a handful of trades, so its vol is the short leg's vol times the one multiple that best
reproduces the unit price on the days both legs really traded. Each day's unit is then Black-Scholes on both legs at
that day's MSTX close. This is a MODEL estimate at about the mid. It is not what a fill costs: the long leg's market is several dollars wide. Days when both legs really traded
are kept as "prints" so the model can be checked against them.
"""
import json, math, os, datetime as dt
import numpy as np, pandas as pd, yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "leaps-cost.json")
LONG = {"sym": "MSTX281215C00033000", "k": 33.0, "exp": dt.date(2028, 12, 15)}
SHORT = {"sym": "MSTX280121C00060000", "k": 60.0, "exp": dt.date(2028, 1, 21)}
R, N_UNITS = 0.04, 200

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

px = daily("MSTX")["Close"].dropna()
sh, lg = daily(SHORT["sym"]), daily(LONG["sym"])
sh, lg = sh[sh["Volume"] > 0]["Close"], lg[lg["Volume"] > 0]["Close"]
start = sh.index[0]
px = px[px.index >= start]
T = lambda d, leg: (leg["exp"] - d.date()).days / 365.0

iv_s = pd.Series({d: implied(p, px[d], SHORT["k"], T(d, SHORT)) for d, p in sh.items() if d in px.index}).dropna()
iv_s = iv_s.clip(0.6, 2.0).rolling(5, min_periods=1).median()
iv_short = iv_s.reindex(px.index).ffill().bfill()
# the long leg's vol as a multiple of the short leg's: the multiple that best reproduces the days both legs really traded
pr = [(d, float(lg[d] - sh[d])) for d in lg.index.intersection(sh.index) if d in px.index]
def sse(q): return sum((call(px[d], LONG["k"], T(d, LONG), iv_short[d] * q) - call(px[d], SHORT["k"], T(d, SHORT), iv_short[d]) - u) ** 2 for d, u in pr)
ratio = min((0.70 + 0.005 * i for i in range(81)), key=sse) if pr else 0.86
iv_long = iv_short * ratio
listed = lg.index[0] if len(lg) else px.index[-1]          # first real trade of the long leg

rows = []
for d, S in px.items():
    u = call(S, LONG["k"], T(d, LONG), iv_long[d]) - call(S, SHORT["k"], T(d, SHORT), iv_short[d])
    rows.append({"d": d.strftime("%Y-%m-%d"), "mstx": round(float(S), 2), "unit": round(u, 2), "cost": round(u * 100 * N_UNITS),
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
unit_at = [{"mstx": k / 2, "unit": round(call(k / 2, LONG["k"], T(d0, LONG), iv_long[d0]) - call(k / 2, SHORT["k"], T(d0, SHORT), iv_short[d0]), 2)} for k in range(16, 61)]
out = {"updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "units": N_UNITS,
       "unit": "long Dec 15 2028 $33 call, short Jan 21 2028 $60 call",
       "long_first_trade": listed.strftime("%Y-%m-%d"), "short_first_trade": start.strftime("%Y-%m-%d"),
       "vol_ratio_long_to_short": round(ratio, 3), "model_vs_prints_mean_abs_error": round(float(np.mean(err)), 2) if err else None,
       "note": "Model estimate near the mid. Black Scholes runs on each day's MSTX close. Vol comes from the short leg's real trades. The long leg's vol is scaled from it. Before the long leg first traded the line is hypothetical. A fill costs more than the mid because the long leg's market is several dollars wide.",
       "model": {"r": R, "mstx_last": round(float(px.iloc[-1]), 2), "asof": px.index[-1].strftime("%Y-%m-%d"),
                 "long": {"k": LONG["k"], "exp": str(LONG["exp"]), "iv": round(float(iv_long.iloc[-1]), 8)},
                 "short": {"k": SHORT["k"], "exp": str(SHORT["exp"]), "iv": round(float(iv_short.iloc[-1]), 8)}},
       "ref": ref, "unit_at": unit_at, "prints": prints, "series": rows}
json.dump(out, open(OUT, "w"), indent=1, allow_nan=False)
print("wrote %d days, %s to %s. vol ratio %.3f. prints %d, mean abs error vs prints $%.2f a unit" % (len(rows), rows[0]["d"], last["d"], ratio, len(prints), np.mean(err) if err else float("nan")))
for k, r in ref.items(): print("  %-17s %s  MSTX %6.2f  unit $%5.2f  200 units $%s" % (k, r["d"], r["mstx"], r["unit"], format(r["cost"], ",")))
for p in prints:
    m = next(r for r in rows if r["d"] == p["d"]); print("  print %s  real $%.2f  model $%.2f" % (p["d"], p["unit"], m["unit"]))

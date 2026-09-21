"""model_refresh.py: keeps the MSTX tab's model files current without anyone running a script by hand.

One daily source, data/mstr-daily.csv (date, MSTR, MSTX, BTC, STRC, Bitcoin per share). BTC is the close of the 4 PM New York
hour bar, the convention the whole file was built on; the 9/18 row first held an unfinished bar and was corrected. Each run:
  1. appends every completed session the file is missing (closes from Yahoo, Bitcoin per share live from strategy.com,
     falling back to the last row's value), stopping at the first day it cannot complete so the file never has a hole;
  2. rebuilds data/mstr-model.json: projected MSTR, the gap and mNAV for every STRC-era day at the slope in
     data/mstr-config.json, plus the Cheap episodes. The factors, backtest and regime blocks are research output and are
     carried through unchanged;
  3. rebuilds data/mnav-history.json: two years of mNAV split by bull and bear market (Bitcoin against its 200-day
     average), calendar-day averages, the typical MSTX gap by market, and how far projected and the best estimate missed.
Bitcoin per share is stored per day and never rescaled afterwards, so history does not move when the share count does.
"""
import datetime as dt, json, os, sys, urllib.request
import numpy as np, pandas as pd, yfinance as yf
from zoneinfo import ZoneInfo
from mnav_fit import target, atomic_text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda f: os.path.join(ROOT, "data", f)
NY = ZoneInfo("America/New_York")
HALF_LIFE = 28.0
# NYSE full-day closures. A weekday outside this list is an expected session: if Yahoo has no row for it the append stops there.
HOLIDAYS = {"2026-11-26", "2026-12-25", "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24"}


def live_bps():
    try:
        req = urllib.request.Request("https://api.strategy.com/btc/bitcoinKpis", headers={"User-Agent": "Mozilla/5.0"})
        k = json.loads(urllib.request.urlopen(req, timeout=15).read())["results"]
        v = float(k["satsPerShare"]) / 1e8
        return v if 0.0005 < v < 0.01 else None
    except Exception as e:
        print("strategy.com unavailable (%s); carrying the last Bitcoin per share forward" % e); return None


def append_days(d):
    last = pd.to_datetime(d["d"].iloc[-1]).date()
    now = dt.datetime.now(NY)
    through = now.date() if now.time() >= dt.time(17, 5) else now.date() - dt.timedelta(days=1)   # the 4 PM hour bar closes at 5
    if through <= last: return d, 0
    def daily(tk):
        h = yf.Ticker(tk).history(start=str(last), end=str(through + dt.timedelta(days=1)))
        h.index = pd.to_datetime(h.index).tz_localize(None).normalize(); return h["Close"]
    mstr, mstx, strc = daily("MSTR"), daily("MSTX"), daily("STRC")
    btc = yf.Ticker("BTC-USD").history(period="1mo", interval="1h")["Close"]; btc.index = btc.index.tz_convert(NY)
    bps_now, rows = live_bps(), []
    expected = [pd.Timestamp(x) for x in pd.bdate_range(last + dt.timedelta(days=1), through) if str(x.date()) not in HOLIDAYS]
    for day in expected:      # every expected session in order, so a day Yahoo is missing can never become a hole
        at4 = btc[(btc.index.date == day.date()) & (btc.index.hour == 16)]
        vals = [mstr.get(day), mstx.get(day), strc.get(day), at4.iloc[0] if len(at4) else None]
        if any(v is None or not np.isfinite(v) or v <= 0 for v in vals):
            print("%s is incomplete (MSTR, MSTX, STRC, BTC at 4 PM: %s); stopping here" % (day.date(), vals)); break
        rows.append({"d": str(day.date()), "mstr": round(float(vals[0]), 4), "mstx": round(float(vals[1]), 4), "btc": round(float(vals[3]), 2),
                     "strc": round(float(vals[2]), 4), "bps": bps_now or float(d["bps"].iloc[-1])})
        print("appended %s  MSTR %.2f  MSTX %.2f  STRC %.2f  BTC at 4 PM %.0f" % (day.date(), vals[0], vals[1], vals[2], vals[3]))
    if rows: d = pd.concat([d, pd.DataFrame(rows)], ignore_index=True)
    return d, len(rows)


def build_model(d, fit, cheap):
    e = d[d["strc"].notna()].reset_index(drop=True).copy()
    e["target"] = target(e["btc"], e["strc"], fit)
    e["proj"] = e["bps"] * e["btc"] * e["target"]; e["gap"] = e["mstr"] / e["proj"] - 1; e["mnav"] = e["mstr"] / (e["btc"] * e["bps"])
    sig = (e["gap"] * 100 <= cheap).values; eps, i = [], 0
    while i < len(e):
        if sig[i]:
            j = i
            while j + 1 < len(e) and any(sig[j + 1:j + 6]): j += 1
            eps.append((i, j)); i = j + 1
        else: i += 1
    rows = []
    for a, b in eps:
        s, z = e.iloc[a], e.iloc[b]; worst = int(e.iloc[a:b + 1]["gap"].idxmin()); w = e.loc[worst]
        out = {"start": s["d"], "end": z["d"], "days": int(b - a + 1), "worst_gap": round(100 * w["gap"], 1), "worst_date": w["d"],
               "mstr_at_worst": round(w["mstr"], 2), "proj_at_worst": round(w["proj"], 2), "btc_at_worst": int(round(w["btc"]))}
        for h in (5, 10):
            f = e.iloc[worst + h] if worst + h < len(e) else None
            out["mstr_%dd" % h] = None if f is None else round(100 * (f["mstr"] / w["mstr"] - 1), 1); out["btc_%dd" % h] = None if f is None else round(100 * (f["btc"] / w["btc"] - 1), 1)
            out["proj_%dd" % h] = None if f is None else round(100 * (f["proj"] / w["proj"] - 1), 1); out["gap_%dd" % h] = None if f is None else round(100 * f["gap"], 1)
        rows.append(out)
    old = json.load(open(D("mstr-model.json"), encoding="utf-8"))
    site = {"as_of": e["d"].iloc[-1], "model": dict(slope=fit["b"], fit=fit, target_description="Fitted Bitcoin line with STRC shortfall below par and mNAV capped at 2",
                                                    btc_per_share_note="Bitcoin per share %.7f on the last row, live from strategy.com when the row was added" % float(e["bps"].iloc[-1])),
            "series": [{"d": r.d, "mstr": round(r.mstr, 2), "mstx": (None if pd.isna(r.mstx) else round(r.mstx, 2)), "btc": int(round(r.btc)), "strc": round(r.strc, 2),
                        "bps": float(r.bps), "mnav": round(r.mnav, 4), "target": round(r.target, 4), "proj": round(r.proj, 2), "gap": round(100 * r.gap, 2)} for r in e.itertuples()],
            "episodes": rows, "factors": old.get("factors"), "backtest": old.get("backtest"), "regime": old.get("regime")}
    return e, site


def build_history(d, e, rich):
    h = d.copy(); h.index = pd.to_datetime(h["d"]); h["prem"] = h["mstr"] / (h["btc"] * h["bps"])
    b = yf.Ticker("BTC-USD").history(start=str((h.index[0] - pd.Timedelta(days=330)).date()))["Close"]; b.index = b.index.tz_localize(None).normalize()
    if len(b) < 250: raise RuntimeError("Bitcoin history too short for the 200-day average")
    h["vs200"] = (b / b.rolling(200).mean() - 1).reindex(h.index, method="ffill"); h = h.dropna(subset=["prem", "vs200"]); h["bull"] = h["vs200"] > 0
    h["avg90"] = h["prem"].rolling("90D", min_periods=30).mean()
    x = e.copy(); x.index = pd.to_datetime(x["d"]); x = x.join(h[["prem", "bull"]], how="inner")
    x["miss"] = (x["target"] / x["prem"] - 1).abs()
    days = pd.Series(x.index, index=x.index).diff(5).dt.days
    x["best"] = np.minimum(2.0, x["target"] * (1 + x["gap"].shift(5) * 0.5 ** (days / HALF_LIFE))); x["miss_best"] = (x["best"] / x["prem"] - 1).abs()
    x["gap_x"] = (x["mstx"] / (x["mstx"].shift(1) * (1 + 2 * (x["proj"] / x["mstr"].shift(1) - 1))) - 1) * 100
    def block(f, name):
        return {"name": name, "days": int(len(f)), "median": round(float(f.prem.median()), 2), "low": round(float(f.prem.quantile(0.25)), 2),
                "high": round(float(f.prem.quantile(0.75)), 2), "min": round(float(f.prem.min()), 2), "max": round(float(f.prem.max()), 2)}
    def era(f, name):
        g = f.dropna(subset=["miss_best"])
        return {"name": name, "days": int(len(f)), "scored": int(len(g)), "median_premium": round(float(f.prem.median()), 2), "bias_projected": round(float(f.gap.mean()) * 100, 1),
                "err_projected": round(float(g.miss.mean()) * 100, 1), "err_best": round(float(g.miss_best.mean()) * 100, 1)}
    cal = lambda n: round(float(h.prem[h.index > h.index[-1] - pd.Timedelta(days=n)].mean()), 3)
    gx = x.dropna(subset=["gap_x"]).iloc[1:]
    res = {"as_of": str(h.index[-1].date()), "from": str(h.index[0].date()), "strc_from": str(x.index[0].date()),
           "all": [block(h[h.bull], "bull"), block(h[~h.bull], "bear")], "era": [era(x[x.bull], "bull"), era(x[~x.bull], "bear"), era(x, "all")],
           "now": {"premium": round(float(h.prem.iloc[-1]), 3), "avg30": cal(30), "avg90": cal(90), "avg365": cal(365), "avg_all": round(float(h.prem.mean()), 3), "target": round(float(x.target.iloc[-1]), 3)},
           "gap_mstx": {"all": round(float(gx.gap_x.median()), 1), "bull": round(float(gx[gx.bull].gap_x.median()), 1), "bear": round(float(gx[~gx.bull].gap_x.median()), 1),
                        "last60": round(float(gx.gap_x.tail(60).median()), 1), "rich_share": int(round(100 * float((gx.gap_x >= rich * 200).mean()))),
                        "rich_share_last60": int(round(100 * float((gx.gap_x.tail(60) >= rich * 200).mean())))}, "gap_mstr": {"rich_share": int(round(100 * float((x.gap >= rich).mean()))),
                        "rich_share_last60": int(round(100 * float((x.gap.tail(60) >= rich).mean())))}, "periods": []}
    for a, z, lab in (("2024-09", "2024-12", "late 2024"), ("2025-01", "2025-06", "early 2025"), ("2025-07", "2025-12", "late 2025"), ("2026-01", "2026-06", "early 2026"),
                      ("2026-07", "2026-12", "since July 2026"), ("2027-01", "2027-06", "early 2027"), ("2027-07", "2027-12", "late 2027")):
        q = h.loc[a:z]
        if len(q): res["periods"].append({"name": lab, "median": round(float(q.prem.median()), 2), "bull_pct": int(round(100 * q.bull.mean()))})
    w = h.join(x[["target"]]).resample("W-FRI").last().dropna(subset=["prem"])
    res["weekly"] = [{"d": str(i.date()), "p": round(float(r.prem), 3), "a": None if pd.isna(r.avg90) else round(float(r.avg90), 3),
                      "t": None if pd.isna(r.target) else round(float(r.target), 3), "btc": int(round(r.btc)), "bull": bool(r.bull)} for i, r in w.iterrows()]
    res["note"] = ("mNAV = MSTR close / (Bitcoin at 4 PM New York x Bitcoin per share). This uses the site's share convention. Levels before mid 2025 are approximate. "
                   "Bull = Bitcoin above its 200 day average. Best estimate = projected carrying the gap from five sessions earlier, faded with a 28 day half life. "
                   "Both use that day's actual Bitcoin and STRC prices. Averages are calendar-day windows. Built by tools/model_refresh.py.")
    return res


def build_evidence(e, d_all, btc_daily):
    """What the record says, for the Playbook. Model marks only: Black-Scholes at 120% vol, no bid and ask, one market era."""
    import math
    def ncdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))
    def call(S, K, T, v, r=0.04):
        if T <= 0: return max(S - K, 0.0)
        d1 = (math.log(S / K) + (r + 0.5 * v * v) * T) / (v * math.sqrt(T)); return S * ncdf(d1) - K * math.exp(-r * T) * ncdf(d1 - v * math.sqrt(T))
    x = e.dropna(subset=["mstx", "mstr", "proj", "btc"]).reset_index(drop=True)
    H, VOLM, VOL = 10, 0.75, 1.20
    rows = []
    for i in range(1, len(x) - H):
        a, b = x.iloc[i], x.iloc[i + H]
        days = (pd.Timestamp(b["d"]) - pd.Timestamp(a["d"])).days
        g = a["mstr"] / a["proj"] - 1; decay = math.exp(-VOLM * VOLM * days / 365)
        rows.append({"g": g, "s0": a["mstx"], "s1": b["mstx"], "btc": b["btc"] / a["btc"] - 1, "today": a["mstx"],
                     "projected": a["mstx"] * (a["proj"] / a["mstr"]) ** 2 * decay,
                     "best": a["mstx"] * (min(2 * a["btc"] * a["bps"], a["proj"] * (1 + g * 0.5 ** (days / HALF_LIFE))) / a["mstr"]) ** 2 * decay})
    A = pd.DataFrame(rows)
    if len(A) < 100: raise RuntimeError("too few days for the evidence file")
    miss = lambda col: round(100 * float(np.median(np.abs(np.log(A["s1"] / A[col])))), 1)
    rel = np.log(A["s1"] / A["s0"]) - 2 * np.log(1 + A["btc"])          # MSTX's move beyond twice Bitcoin's
    def band(m): return {"days": int(m.sum()), "median_vs_btc": round(100 * float(np.median(rel[m])), 1)}
    def cal(col):
        pl = []
        for k in range(0, len(A), 5):
            K = max(0.5, round(A[col].iloc[k] * 2) / 2); s0, s1 = A["s0"].iloc[k], A["s1"].iloc[k]
            deb = call(s0, K, 21 / 365, VOL) - call(s0, K, 14 / 365, VOL)
            if deb < 0.03: continue
            pl.append((call(s1, K, 7 / 365, VOL) - max(s1 - K, 0.0)) / deb - 1)
        pl = np.array(pl); return {"trades": int(len(pl)), "won_pct": int(round(100 * float((pl > 0).mean()))), "median_pct": int(round(100 * float(np.median(pl)))), "average_pct": int(round(100 * float(pl.mean())))}
    gp = (x["mstr"] / x["proj"] - 1).values; RECENT = 120
    def left(h, lo, hi):
        r = [gp[i + h] / gp[i] for i in range(max(lo, 0), min(hi, len(gp) - h)) if abs(gp[i]) > 0.05]
        return None if len(r) < 10 else int(round(100 * float(np.median(r))))
    cut = len(gp) - RECENT
    fade = {"recent_days": RECENT, "recent_after20": left(20, cut, len(gp)), "recent_after40": left(40, cut, len(gp)),
            "earlier_after20": left(20, 0, cut), "earlier_after40": left(40, 0, cut)}
    def drag(f):
        f = f.dropna(subset=["mstr", "mstx"]); yrs = (pd.Timestamp(f["d"].iloc[-1]) - pd.Timestamp(f["d"].iloc[0])).days / 365
        return (math.log(f["mstx"].iloc[-1] / f["mstx"].iloc[0]) - 2 * math.log(f["mstr"].iloc[-1] / f["mstr"].iloc[0])) / yrs
    k1, k2 = -drag(d_all.tail(253)), -drag(d_all)
    if not (0.2 < k1 < 3): raise RuntimeError("measured MSTX drag out of range: %s" % k1)
    # the drag follows volatility, not direction: every 60 session window, split by what MSTR did
    f = d_all.dropna(subset=["mstr", "mstx"]).reset_index(drop=True); W = 60; roll = []
    for i in range(0, len(f) - W):
        a, b = f.iloc[i], f.iloc[i + W]; yrs = (pd.Timestamp(b["d"]) - pd.Timestamp(a["d"])).days / 365
        lm = math.log(b["mstr"] / a["mstr"]); roll.append((lm, -(math.log(b["mstx"] / a["mstx"]) - 2 * lm) / yrs))
    roll = np.array(roll); loss = lambda k: int(round(100 * (1 - math.exp(-float(k)))))
    up, dn = roll[roll[:, 0] >= math.log(1.2), 1], roll[roll[:, 0] <= math.log(0.8), 1]
    fx = f.copy(); fx.index = pd.to_datetime(fx["d"]); dd = np.log(fx["mstx"]).diff() - 2 * np.log(fx["mstr"]).diff()
    above = (btc_daily > btc_daily.rolling(50).mean()).shift(1).reindex(fx.index, method="ffill").fillna(False).astype(bool)
    yr = fx.index > fx.index[-1] - pd.Timedelta(days=365)
    kreg = lambda msk: round(-float(dd[msk & yr].dropna().mean() * 252), 3) if int((msk & yr).sum()) >= 40 else None
    mdrag = {"k_1y": round(k1, 3), "k_all": round(k2, 3), "loss_1y_pct": int(round(100 * (1 - math.exp(-k1)))), "k_above50": kreg(above), "k_below50": kreg(~above),
             "k_calm": round(float(np.percentile(roll[:, 1], 25)), 3), "windows": int(len(roll)),
             "up20_loss_pct": loss(np.median(up)) if len(up) >= 20 else None, "down20_loss_pct": loss(np.median(dn)) if len(dn) >= 20 else None,
             "mstr_vol_1y": round(float(np.log(d_all["mstr"]).diff().tail(252).std() * np.sqrt(252)), 3)}
    return {"as_of": str(x["d"].iloc[-1]), "from": str(x["d"].iloc[0]), "horizon_sessions": H, "start_days": int(len(A)), "gap_fade": fade, "mstx_drag": mdrag,
            "guides": {"today": miss("today"), "projected": miss("projected"), "best": miss("best")},
            "gap_signal": {"over": band(A["g"] > 0.05), "within": band((A["g"] <= 0.05) & (A["g"] >= -0.05)), "under": band(A["g"] < -0.05)},
            "calendars": {"vol_pct": int(VOL * 100), "today": cal("today"), "projected": cal("projected"), "best": cal("best")},
            "note": ("Every start day since STRC began. Guides are scored on MSTX ten sessions later. The gap bands use MSTR 5% from projected, about 10% on MSTX. "
                     "Calendars are two week model trades opened every five sessions at 120% vol with no bid and ask. One market era only.")}


def main():
    cfg = json.load(open(D("mstr-config.json"), encoding="utf-8"))
    fit, cheap = cfg["fit"], float(cfg["cheap_threshold"]) * 100
    d = pd.read_csv(D("mstr-daily.csv"))
    n0 = len(d)
    try:
        d, added = append_days(d)
    except Exception as ex:
        print("append failed (%s); rebuilding from the rows on file" % ex); added = 0
    if len(d) < n0 or d["d"].duplicated().any() or not d["d"].is_monotonic_increasing:
        print("daily file failed its checks; nothing written"); return 1
    try:                       # build everything in memory first; one failure publishes nothing
        e, site = build_model(d, fit, cheap)
        res = build_history(d, e, float(cfg["rich_threshold"]))
        bd = yf.Ticker("BTC-USD").history(start=str((pd.Timestamp(d["d"].iloc[0]) - pd.Timedelta(days=120)).date()))["Close"]; bd.index = bd.index.tz_localize(None).normalize()
        if len(bd) < 200: raise RuntimeError("Bitcoin history too short for the 50 day split")
        evid = build_evidence(e, d, bd)
        if not (len(site["series"]) >= 200 and len(res["weekly"]) >= 50 and 0.2 < res["now"]["premium"] < 6): raise RuntimeError("outputs failed their checks")
    except Exception as ex:
        print("build failed (%s); nothing written" % ex); return 1
    if added: atomic_text(D("mstr-daily.csv"), d.to_csv(index=False, lineterminator="\n"))
    atomic_text(D("mstr-model.json"), json.dumps(site, indent=0, allow_nan=False))
    atomic_text(D("mnav-history.json"), json.dumps(res, indent=1, allow_nan=False))
    atomic_text(D("evidence.json"), json.dumps(evid, indent=1, allow_nan=False))
    print("rows added %d; daily file ends %s; model %d rows; history through %s, mNAV %.3f" % (added, d["d"].iloc[-1], len(e), res["as_of"], res["now"]["premium"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

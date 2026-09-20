"""ladder_cutpoints_study.py: where do the numbers put the ladder's three lines?

The ladder holds one of four things by Bitcoin's power-law quantile: an MSTX call diagonal under 15, an MSTR one from 15 to
50, an IBIT one from 50 to 85, and STRC on margin above 85. This asks which three lines would have grown the account fastest.

Method. Every day since 2014 (2010 as a check) gets the site's quantile. For each day and each instrument the script buys a
12 month call at 0.75 delta, as the rules say, and marks it 90 days later (or at expiry) with Black Scholes at the implied
vols on Yahoo's chains of Fri 2026-09-18. The underlying moves as in ladder_bands_study.py: IBIT = r, MSTR = beta x r,
MSTX = 2 x beta x r - k x T, with r the Bitcoin log return. STRC earns its carry (1.5 x 12% less 0.5 x 4.75% margin) at a
flat price, with the whole account in it and no price risk counted. The score is the mean log growth of an account that puts a share f of itself into the position and keeps the
rest at 4%. f = 0.6 is his LEAPS sizing. Log growth punishes a wipe-out far more than it rewards a double, which is what
lets the calmer instrument ever win. Then every ordered set of lines on a 5 point grid is scored, and the best set is
refitted with each cycle left out and tested on the cycle it never saw. Vols are held flat, windows overlap and there are
three or four cycles. Read the shape.
"""
import math, os, sys, itertools
import numpy as np, pandas as pd, yfinance as yf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ladder_bands_study import quantile

RF = 0.04
IV = {"ibit": (0.52, 0.45), "mstr": (0.82, 0.78), "mstx": (1.25, 1.40)}     # 12 month and 90 day
STRC = 1.5 * 0.12 - 0.5 * 0.0475
ERF = np.vectorize(math.erf)
D75, D30 = 0.6744898, -0.5244005
CUR, EQ = (15, 50, 85), (25, 50, 75)          # CUR is the baseline the study ran against. The ladder moved to 10 / 60 / 75 on 2026-09-20
INST = ["mstx", "mstr", "ibit", "strc"]
ERAS = [("2010 to Jan 2015", "2010-01-01", "2015-01-14"), ("Jan 2015 to Dec 2018", "2015-01-14", "2018-12-15"),
        ("Dec 2018 to Nov 2022", "2018-12-15", "2022-11-21"), ("Nov 2022 on", "2022-11-21", "2100-01-01")]


def N(x): return 0.5 * (1 + ERF(np.asarray(x, float) / math.sqrt(2)))


def bs(S, K, T, v):
    S = np.asarray(S, float)
    if T <= 0: return np.maximum(S - K, 0)
    d1 = (np.log(S / K) + (RF + v * v / 2) * T) / (v * math.sqrt(T))
    return S * N(d1) - K * math.exp(-RF * T) * N(d1 - v * math.sqrt(T))


def strike(d1, v, T): return math.exp(-d1 * v * math.sqrt(T) + (RF + v * v / 2) * T)


def position_return(ratio, inst, H, pmcc):
    """Return on the money put in. ratio = underlying at the mark over underlying at entry. Entry price is 1."""
    assert not pmcc or H == 90, "the short leg is a 90 day call, so the diagonal is only marked at 90 days"
    vl, vs = IV[inst]; T = H / 365; KL = strike(D75, vl, 1.0); prem = float(bs(1.0, KL, 1.0, vl)); val = bs(ratio, KL, 1.0 - T, vl)
    if pmcc:
        KS = strike(D30, vs, 90 / 365); prem -= float(bs(1.0, KS, 90 / 365, vs)); val = val - np.maximum(ratio - KS, 0)
    return val / prem - 1


def load(extended):
    px = yf.Ticker("BTC-USD").history(period="max")["Close"].dropna(); px.index = px.index.tz_localize(None).normalize()
    if extended:
        cm = pd.read_csv(extended, parse_dates=["time"]).set_index("time")["PriceUSD"]; cm.index = cm.index.tz_localize(None).normalize()
        px = pd.concat([cm[cm.index < px.index[0]], px])
    px = px[~px.index.duplicated()].asfreq("D").ffill()
    d = pd.DataFrame({"p": px}); d["q"] = [quantile(p, t) for t, p in zip(d.index, d["p"])]
    d["gate"] = d["p"] > d["p"].rolling(50).mean()
    return d


def growth(d, H, beta, k, f, pmcc):
    """Per day log growth of the account for each instrument. Days whose window runs past the data are dropped."""
    T = H / 365; r = np.log(d["p"].shift(-H) / d["p"]); ok = r.notna(); g = pd.DataFrame(index=d.index[ok]); rr = r[ok].values
    for inst, e, kk in (("mstx", 2 * beta, k), ("mstr", beta, 0.0), ("ibit", 1.0, 0.0)):
        R = position_return(np.exp(e * rr - kk * T), inst, H, pmcc)
        g[inst] = np.log(1 + f * R + (1 - f) * RF * T)
    g["strc"] = math.log(1 + STRC * T)
    return g[INST]


def score(g, q, lines):
    a, b, c = lines; pick = np.where(q < a, 0, np.where(q < b, 1, np.where(q < c, 2, 3)))
    return float(g.values[np.arange(len(g)), pick].mean())


def best_lines(g, q):
    bucket = np.minimum((q // 5).astype(int), 19); sums = np.zeros((20, 4)); best = (-1e18, None)
    for j in range(4): sums[:, j] = np.bincount(bucket, weights=g.values[:, j], minlength=20)
    cs = np.vstack([np.zeros(4), sums.cumsum(0)])
    for a, b, c in itertools.combinations_with_replacement(range(0, 105, 5), 3):
        ia, ib, ic = a // 5, b // 5, c // 5
        tot = cs[ia, 0] + (cs[ib, 1] - cs[ia, 1]) + (cs[ic, 2] - cs[ib, 2]) + (cs[20, 3] - cs[ic, 3])
        if tot > best[0]: best = (tot, (a, b, c))
    return best[1]


def yearly(x, H): return 100 * (math.exp(x * 365 / H) - 1)


SWITCH_2X = "2024-11-01"      # MSTX ran at 1.75x from its Aug 2024 launch and moved to 2x at the end of Oct 2024
CANDS = [(15, 50, 85), (25, 50, 75), (10, 50, 85), (10, 60, 85), (10, 60, 75), (10, 60, 65), (10, 50, 65), (15, 50, 65), (10, 65, 65)]


def real_series(drag_mult=1.0):
    """Real closes on US trading days since MSTR began buying Bitcoin (Aug 2020). MSTX is the real fund from Nov 2024, when it
    became a 2x fund, and before that a 2x daily fund built from MSTR's own daily moves. The build's daily cost is fitted on
    the 2x period only. IBIT is the real fund from Jan 2024 and Bitcoin itself before."""
    h = lambda t, **k: (lambda c: c.set_axis(c.index.tz_localize(None).normalize()))(yf.Ticker(t).history(**k)["Close"].dropna())
    m = h("MSTR", start="2020-08-11"); x = h("MSTX", period="max"); ib = h("IBIT", period="max"); btc = h("BTC-USD", start="2020-08-01")
    two = np.log1p((2 * m.pct_change()).clip(lower=-0.95)); real = np.log(x).diff().dropna(); real = real[real.index >= SWITCH_2X]
    both = real.index.intersection(two.dropna().index); gap = float((real.loc[both] - two.loc[both]).mean())
    lr = (two + gap * drag_mult).dropna(); lr.loc[both] = real.loc[both]
    mstx = pd.concat([pd.Series([1.0], index=[m.index[0]]), np.exp(lr.cumsum())])
    bl = np.log(btc.reindex(m.index).ffill()).diff().dropna(); il = np.log(ib).diff().dropna(); k = il.index.intersection(bl.index); bl.loc[k] = il.loc[k]
    ibit = pd.concat([pd.Series([1.0], index=[m.index[0]]), np.exp(bl.cumsum())])
    return pd.DataFrame({"mstr": m, "mstx": mstx, "ibit": ibit}).dropna(), gap * 252


def real_frame(base, H, f, drag_mult=1.0):
    """Entry at the close of a US trading day on the quantile from Bitcoin's close the day before, so the signal was known.
    The mark is the last US close on or before H calendar days later."""
    px, drag = real_series(drag_mult); T = H / 365
    end = px.reindex(px.index + pd.Timedelta(days=H), method="ffill"); end.index = px.index
    ok = (px.index + pd.Timedelta(days=H)) <= px.index[-1]; ratio = (end / px)[ok]
    g = pd.DataFrame({i: np.log(1 + f * position_return(ratio[i].values, i, H, False) + (1 - f) * RF * T) for i in ("mstx", "mstr", "ibit")}, index=ratio.index)
    g["strc"] = math.log(1 + STRC * T); q = base["q"].shift(1).reindex(g.index).values
    keep = ~np.isnan(q); return g[INST][keep], q[keep], drag


def zone_table(g, q, zones, H, title):
    if title: print(title)
    for lo, hi in zones:
        msk = (q >= lo) & (q < hi)
        if msk.sum() < 40: print("   %3d to %3d %5d days, too few" % (lo, hi, msk.sum())); continue
        mean = g[msk].mean()
        print("   %3d to %3d %5d days | MSTX %+6.0f%%  MSTR %+6.0f%%  IBIT %+6.0f%%  STRC %+4.0f%% | best %s" % (
            lo, hi, msk.sum(), yearly(mean["mstx"], H), yearly(mean["mstr"], H), yearly(mean["ibit"], H), yearly(mean["strc"], H), mean.idxmax().upper()))


def real_check(base):
    B = pd.Timestamp("2022-11-21"); zones = [(0, 10), (10, 15), (15, 25), (25, 35), (35, 50), (50, 65), (65, 85), (85, 101)]
    print("")
    print("5. The same test on real prices since Aug 2020 (two tops, two bottoms). Scores are annualised mean log growth of the")
    print("   account over fixed holds. They are scenario scores, not the growth of a ladder that switches at the lines.")
    frames = {}
    for H in (90, 180, 365):
        for f in (0.6, 0.3): frames[(H, f)] = real_frame(base, H, f)
    print("   MSTX build: daily cost fitted on the 2x period, %.2f log a year on top of 2x volatility decay" % -frames[(90, 0.6)][2])
    for H in (90, 365):
        g, q, _ = frames[(H, 0.6)]
        zone_table(g, q, zones, H, "   Score by start zone, 60%% of the account in a 12 month 0.75 delta call, %d day hold" % H)
        Rr = {i: np.expm1(g[i]) for i in ("mstx", "mstr", "ibit")}
        print("   position lost half or more, by zone: " + " | ".join("%d-%d MSTX %.0f%% MSTR %.0f%% IBIT %.0f%%" % (
            lo, hi, *[100 * float((((np.exp(g[i][(q >= lo) & (q < hi)]) - 1 - 0.4 * RF * H / 365) / 0.6) <= -0.5).mean()) for i in ("mstx", "mstr", "ibit")]) for lo, hi in zones if ((q >= lo) & (q < hi)).sum() >= 40))
        print("   fitted best lines, %d day hold: %d / %d / %d" % ((H,) + best_lines(g, q)))
    print("   fitted best lines, 180 day hold: %d / %d / %d" % best_lines(*frames[(180, 0.6)][:2]))
    print("")
    print("   Candidate lines scored. Columns: 90d, 180d, 365d at 60%; 90d, 365d at 30%; then each half of the sample at 90d and 365d")
    print("   (halves purged: a start whose hold crosses 21 Nov 2022 is in neither half)")
    for L in CANDS:
        out = [yearly(score(frames[k][0], frames[k][1], L), k[0]) for k in ((90, .6), (180, .6), (365, .6), (90, .3), (365, .3))]
        for H in (90, 365):
            g, q, _ = frames[(H, 0.6)]; first = np.asarray(g.index + pd.Timedelta(days=H) < B); second = np.asarray(g.index >= B)
            out += [yearly(score(g[first], q[first], L), H), yearly(score(g[second], q[second], L), H)]
        print("   %-9s %s" % ("%d/%d/%d" % L, " ".join("%+6.0f%%" % v for v in out)))
    print("")
    print("   Lines fitted on one half and scored on the other (90 day hold). This is the honest test of fitting lines at all.")
    g, q, _ = frames[(90, 0.6)]; first = np.asarray(g.index + pd.Timedelta(days=90) < B); second = np.asarray(g.index >= B)
    for name, tr, te in (("fit to Nov 2022, score after", first, second), ("fit after Nov 2022, score before", second, first)):
        bl = best_lines(g[tr], q[tr])
        print("   %-32s fitted %2d / %2d / %2d scored %+5.0f%% | 15/50/85 %+5.0f%% | 25/50/75 %+5.0f%% | 10/60/65 %+5.0f%%" % (
            name, bl[0], bl[1], bl[2], yearly(score(g[te], q[te], bl), 90), yearly(score(g[te], q[te], CUR), 90), yearly(score(g[te], q[te], EQ), 90), yearly(score(g[te], q[te], (10, 60, 65)), 90)))
    print("")
    print("   MSTX build cost halved and raised by half (it only touches the years before Nov 2024)")
    for mult in (0.5, 1.5):
        for H in (90, 365):
            g, q, _ = real_frame(base, H, 0.6, mult)
            print("   cost x%.1f, %3d day hold: fitted best %2d / %2d / %2d | 15/50/85 %+5.0f%% | 25/50/75 %+5.0f%% | 10/60/65 %+5.0f%%" % (
                (mult, H) + best_lines(g, q) + (yearly(score(g, q, CUR), H), yearly(score(g, q, EQ), H), yearly(score(g, q, (10, 60, 65)), H))))


def era_lines(d):
    print("")
    print("6. Best lines inside each cycle on its own (mapped prices, base setting). Shows how the answer has drifted.")
    g = growth(d, 90, 1.8, 1.0, 0.6, False); q = d.loc[g.index, "q"].values; t = g.index
    for name, s, e in ERAS:
        held = np.asarray((t >= s) & (t < e))
        if held.sum() < 200: continue
        bl = best_lines(g[held], q[held])
        print("   %-22s best %2d / %2d / %3d | %+6.0f%% a year | 15/50/85 %+6.0f%% | highest quantile reached %3.0f" % (
            name, bl[0], bl[1], bl[2], yearly(score(g[held], q[held], bl), 90), yearly(score(g[held], q[held], CUR), 90), q[held].max()))
        zone_table(g[held], q[held], [(0, 15), (15, 35), (35, 50), (50, 65), (65, 85), (85, 101)], 90, "")


def main():
    ext = sys.argv[1] if len(sys.argv) > 1 else None
    base = load(None); print("Bitcoin %s to %s, quantile today %.1f" % (base.index[0].date(), base.index[-1].date(), base["q"].iloc[-1]))

    # 1. the shape: growth by where Bitcoin stood, base case
    H, beta, k, f = 90, 1.8, 1.0, 0.6
    g = growth(base, H, beta, k, f, False); q = base.loc[g.index, "q"].values
    rr_all = np.log(base["p"].shift(-H) / base["p"]).loc[g.index].values
    print("")
    print("1. Account growth a year, 60%% of the account in a 12 month 0.75 delta call marked %d days later" % H)
    print("   start zone   days | MSTX   MSTR   IBIT   STRC | best | chance the position lost half or more: MSTX MSTR IBIT")
    for lo in range(0, 100, 10):
        m = (q >= lo) & (q < lo + 10 + (0.01 if lo == 90 else 0))
        if m.sum() < 60: print("   %2d to %3d  %5d | too few" % (lo, lo + 10, m.sum())); continue
        mean = g[m].mean(); half = {}
        for inst, e, kk in (("mstx", 2 * beta, k), ("mstr", beta, 0.0), ("ibit", 1.0, 0.0)):
            half[inst] = 100 * float((position_return(np.exp(e * rr_all[m] - kk * H / 365), inst, H, False) <= -0.5).mean())
        print("   %2d to %3d  %5d | %+5.0f%% %+5.0f%% %+5.0f%% %+5.0f%% | %-4s | %3.0f%% %3.0f%% %3.0f%%" % (
            lo, lo + 10, m.sum(), yearly(mean["mstx"], H), yearly(mean["mstr"], H), yearly(mean["ibit"], H), yearly(mean["strc"], H),
            mean.idxmax().upper(), half["mstx"], half["mstr"], half["ibit"]))

    # 2. the best ordered lines under each reasonable setting
    print("")
    print("2. Best three lines under each setting. Account growth a year under them, under 15/50/85 and under 25/50/75")
    rows = []
    settings = [("base: long call, 90 days, beta 1.8, decay 1.0, 60% in", base, 90, 1.8, 1.0, 0.6, False, None),
                ("with the short 90 day call sold against it", base, 90, 1.8, 1.0, 0.6, True, None),
                ("held the full 12 months", base, 365, 1.8, 1.0, 0.6, False, None),
                ("held 180 days", base, 180, 1.8, 1.0, 0.6, False, None),
                ("30% of the account in", base, 90, 1.8, 1.0, 0.3, False, None),
                ("softer MSTR, beta 1.5", base, 90, 1.5, 1.0, 0.6, False, None),
                ("calm-market decay 0.79", base, 90, 1.8, 0.79, 0.6, False, None),
                ("two-year decay 1.32", base, 90, 1.8, 1.32, 0.6, False, None),
                ("only days Bitcoin closed above its 50 day", base, 90, 1.8, 1.0, 0.6, False, "gate")]
    full = load(ext) if ext else None
    if ext: settings.append(("history from 2010", full, 90, 1.8, 1.0, 0.6, False, None))
    for name, d, HH, b_, k_, f_, pmcc, filt in settings:
        gg = growth(d, HH, b_, k_, f_, pmcc)
        if filt: gg = gg[d.loc[gg.index, filt].values]
        qq = d.loc[gg.index, "q"].values; bl = best_lines(gg, qq); rows.append(bl)
        print("   %-54s best %2d / %2d / %3d | %+5.0f%% | 15/50/85 %+5.0f%% | 25/50/75 %+5.0f%%" % (
            name, bl[0], bl[1], bl[2], yearly(score(gg, qq, bl), HH), yearly(score(gg, qq, CUR), HH), yearly(score(gg, qq, EQ), HH)))
    print("   median of the best lines across settings: %d / %d / %d" % tuple(np.median(np.array(rows), 0)))

    # 3. out of sample: fit the lines without one cycle, then score them on that cycle against today's lines
    d = full if ext else base
    print("")
    print("3. Lines fitted without a cycle, then scored on that cycle (base setting). History %s" % ("from 2010" if ext else "from 2014"))
    g = growth(d, 90, 1.8, 1.0, 0.6, False); q = d.loc[g.index, "q"].values; t = g.index
    for name, s, e in ERAS:
        held = np.asarray((t >= s) & (t < e))
        if held.sum() < 200: continue
        bl = best_lines(g[~held], q[~held])
        print("   held out %-22s fitted %2d / %2d / %3d | on that cycle: fitted %+5.0f%% | 15/50/85 %+5.0f%% | 25/50/75 %+5.0f%% | 10/50/65 %+5.0f%%" % (
            name, bl[0], bl[1], bl[2], yearly(score(g[held], q[held], bl), 90), yearly(score(g[held], q[held], CUR), 90),
            yearly(score(g[held], q[held], EQ), 90), yearly(score(g[held], q[held], (10, 50, 65)), 90)))

    # 4. one line at a time, the other two held at today's values
    print("")
    print("4. Move one line, hold the other two at 15/50/85 (base setting, same history as 3). Account growth a year.")
    for idx, label in ((0, "MSTX to MSTR line"), (1, "MSTR to IBIT line"), (2, "sell line")):
        out = []
        for v in range(0, 105, 5):
            L = list(CUR); L[idx] = v
            if L[0] <= L[1] <= L[2]: out.append("%d: %+.0f%%" % (v, yearly(score(g, q, tuple(L)), 90)))
        print("   %-18s %s" % (label, "  ".join(out)))
    real_check(base)
    era_lines(d)
    return 0


if __name__ == "__main__":
    sys.exit(main())

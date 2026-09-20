"""ladder_bands_study.py: where should the ladder's rungs start and stop?

The ladder picks its instrument from Bitcoin's power-law quantile: MSTX under 15, MSTR 15 to 50, IBIT 50 to 85, sell
above 85. This asks the record what happened after Bitcoin sat in each part of the band, and which underlying that favoured.

Method. Bitcoin daily closes (Yahoo, from Sep 2014) get the site's own quantile (same A, B and band offsets). For every
day, the forward Bitcoin log return r over 90, 180 and 365 days is mapped to each underlying:
  IBIT  = r
  MSTR  = beta x r              beta 1.8 is what the site's mNAV formula implies near today's prices; 1.5 is a softer check
  MSTX  = 2 x beta x r - k x T  a 2x daily fund on MSTR, k = 1.0 log a year, the decay measured on MSTX itself
These are moves of the underlying, not of an option structure, and one era of MSTR behaviour stands in for all history.
Windows overlap and there are only a handful of cycles, so read the shape, not the decimals.
"""
import math, sys
import numpy as np, pandas as pd, yfinance as yf

A, B, GEN = 5.82, -17.029, pd.Timestamp("2009-01-03")
BANDS = [(99.9, -0.0000756204, 0.7434), (95, -0.0000583518, 0.5943), (85, -0.0000516698, 0.4318), (50, 0, -0.0004), (15, 0, -0.2092), (0.1, 0, -0.3403)]
TODAY_DAYS = (pd.Timestamp.utcnow().tz_localize(None) - GEN).days


def quantile(price, day):
    days = (day - GEN).days
    res = math.log10(price / 10 ** (A * math.log10(days) + B))
    off = [(q, m * min(days, TODAY_DAYS) + c if m < 0 else c) for q, m, c in BANDS]
    for (qh, oh), (ql, ol) in zip(off, off[1:]):
        if ol <= res <= oh: return ql + (res - ol) / (oh - ol) * (qh - ql)
    if res > off[0][1]: return min(99.99, off[0][0] + (off[0][0] - off[1][0]) / (off[0][1] - off[1][1]) * (res - off[0][1]))
    return max(0.01, off[-1][0] + (off[-2][0] - off[-1][0]) / (off[-2][1] - off[-1][1]) * (res - off[-1][1]))


def main():
    px = yf.Ticker("BTC-USD").history(period="max")["Close"].dropna(); px.index = px.index.tz_localize(None).normalize()
    d = pd.DataFrame({"p": px}); d["q"] = [quantile(p, t) for t, p in zip(d.index, d["p"])]
    print("Bitcoin %s to %s, %d days. Quantile today %.1f" % (d.index[0].date(), d.index[-1].date(), len(d), d["q"].iloc[-1]))
    edges = [0, 5, 10, 15, 20, 25, 35, 50, 65, 85, 100.01]; labels = ["%g to %g" % (a, b if b < 100 else 100) for a, b in zip(edges, edges[1:])]
    d["bucket"] = pd.cut(d["q"], edges, labels=labels, right=False)
    print("\nShare of all days spent in each part of the band:")
    share = d["bucket"].value_counts(normalize=True).reindex(labels)
    print("  " + "  ".join("%s: %.0f%%" % (l, 100 * share[l]) for l in labels))
    print("  current rungs: under 15 %.0f%% | 15 to 50 %.0f%% | 50 to 85 %.0f%% | over 85 %.0f%%" % tuple(100 * ((d.q >= a) & (d.q < b)).mean() for a, b in ((0, 15), (15, 50), (50, 85), (85, 101))))
    K = 1.0
    for beta in (1.8, 1.5):
        for H in (90, 365):
            T = H / 365; r = np.log(d["p"].shift(-H) / d["p"]); f = d.assign(r=r).dropna(subset=["r"])
            print("\nbeta %.1f, %d days ahead. Per start zone: days | Bitcoin median, worst quarter, up 15%%+ | MEAN LOG RETURN ibit / mstr / mstx -> best | MEDIAN RETURN ibit / mstr / mstx | lost over half: mstr / mstx" % (beta, H))
            for l in labels:
                g = f[f["bucket"] == l]["r"]
                if len(g) < 60: print("  %-9s %4d days, too few" % (l, len(g))); continue
                logs = {"ibit": g, "mstr": beta * g, "mstx": 2 * beta * g - K * T}
                ml = {k: float(v.mean()) for k, v in logs.items()}; best = max(ml, key=ml.get)
                med = {k: 100 * (math.exp(float(v.median())) - 1) for k, v in logs.items()}
                half = {k: 100 * float((v < math.log(0.5)).mean()) for k, v in logs.items()}
                print("  %-9s %4d | %+5.0f%% %+5.0f%% %3.0f%% | %+5.2f / %+5.2f / %+5.2f -> %-4s | %+5.0f%% / %+6.0f%% / %+6.0f%% | %3.0f%% / %3.0f%%" % (
                    l, len(g), 100 * (math.exp(g.median()) - 1), 100 * (math.exp(g.quantile(0.25)) - 1), 100 * float((g > math.log(1.15)).mean()),
                    ml["ibit"], ml["mstr"], ml["mstx"], best.upper(), med["ibit"], med["mstr"], med["mstx"], half["mstr"], half["mstx"]))
    # how long did a visit under each line last, and how fast did Bitcoin leave it
    print("\nVisits under a line: count, median length in days, median Bitcoin move over the next 90 days from the first day")
    for line in (10, 15, 20, 25):
        below = (d["q"] < line).values; starts = [i for i in range(1, len(d)) if below[i] and not below[i - 1]]
        starts = [s for k, s in enumerate(starts) if k == 0 or (d.index[s] - d.index[starts[k - 1]]).days > 60]
        lens = []
        for s in starts:
            e = s
            while e < len(d) and below[e]: e += 1
            lens.append(e - s)
        fwd = [100 * (d["p"].iloc[min(s + 90, len(d) - 1)] / d["p"].iloc[s] - 1) for s in starts]
        print("  under %2d: %2d visits | median %3.0f days | next 90 days median %+4.0f%%" % (line, len(starts), np.median(lens), np.median(fwd)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""ladder_band_history.py: how long Bitcoin's monthly close sat in each ladder band.

Feeds the history block in data/ladder-rules.json. Monthly closes since 2013 get the site's quantile (same port as
ladder_bands_study.py) and are grouped into visits: a run of consecutive month ends inside one band. Pass the lines as
arguments to compare, for example: python tools/ladder_band_history.py 10 60 75
Bitcoin before Sep 2014 comes from the CoinMetrics community file, after that from Yahoo.
"""
import io, os, sys, urllib.request
import numpy as np, pandas as pd, yfinance as yf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ladder_bands_study import quantile

CM = "https://raw.githubusercontent.com/coinmetrics/data/master/csv/btc.csv"


def monthly():
    px = yf.Ticker("BTC-USD").history(period="max")["Close"].dropna(); px.index = px.index.tz_localize(None).normalize()
    cm = pd.read_csv(io.BytesIO(urllib.request.urlopen(CM, timeout=60).read()), usecols=["time", "PriceUSD"], parse_dates=["time"]).dropna()
    cm = cm.set_index("time")["PriceUSD"]; cm.index = cm.index.tz_localize(None).normalize()
    px = pd.concat([cm[cm.index < px.index[0]], px]); px = px[~px.index.duplicated()].asfreq("D").ffill()
    m = px[px.index >= "2013-01-01"].resample("ME").last()
    if m.index[-1] > px.index[-1]: m = m.iloc[:-1]            # the running month has not closed
    return pd.DataFrame({"p": m, "q": [quantile(p, t) for t, p in zip(m.index, m)]})


def visits(d, lines):
    a, b, c = lines; names = ["MSTX, under %g" % a, "MSTR, %g to %g" % (a, b), "IBIT, %g to %g" % (b, c), "%g and up" % c]
    band = np.where(d.q < a, 0, np.where(d.q < b, 1, np.where(d.q < c, 2, 3))); runs = []; s = 0
    for i in range(1, len(band) + 1):
        if i == len(band) or band[i] != band[s]: runs.append((band[s], d.index[s], d.index[i - 1], i - s, i == len(band))); s = i
    out = []
    for k, name in enumerate(names):
        r = [x for x in runs if x[0] == k]; done = [x[3] for x in r if not x[4]] or [x[3] for x in r]; live = [x for x in r if x[4]]
        out.append({"band": name, "visits": len(r), "median_months": int(np.median(done)) if done else 0, "longest_months": int(max(x[3] for x in r)) if r else 0,
                    "last": r[-1][2].strftime("%Y-%m") if r else None, "current_since": live[0][1].strftime("%Y-%m") if live else None,
                    "share_of_months_pct": int(round(100 * float((band == k).mean())))})
    return out, runs


def main():
    lines = tuple(float(x) for x in sys.argv[1:4]) if len(sys.argv) >= 4 else (10.0, 60.0, 75.0)
    d = monthly(); print("monthly closes %s to %s, %d months. Last close quantile %.1f" % (d.index[0].date(), d.index[-1].date(), len(d), d.q.iloc[-1]))
    out, runs = visits(d, lines)
    for o in out: print(o)
    top = [x for x in runs if x[0] == 3]
    print("runs in the top band:", "; ".join("%s to %s (%d)" % (x[1].strftime("%Y-%m"), x[2].strftime("%Y-%m"), x[3]) for x in top))
    low = [x for x in runs if x[0] == 0]
    print("runs in the bottom band:", "; ".join("%s to %s (%d)" % (x[1].strftime("%Y-%m"), x[2].strftime("%Y-%m"), x[3]) for x in low))
    cyc = d[(d.index >= "2023-01-01")]; print("since 2023 the monthly close peaked at quantile %.0f in %s; months at or above the top line: %d" % (cyc.q.max(), cyc.q.idxmax().strftime("%Y-%m"), int((cyc.q >= lines[2]).sum())))
    return 0


if __name__ == "__main__":
    sys.exit(main())

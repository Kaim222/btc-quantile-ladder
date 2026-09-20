"""model_refit_explore.py: which clock start and sample start give the least biased centre line? Exploration behind model v2.

The centre line is a least squares slope with the intercept lowered to the median of the gaps. For each clock start and each
sample start it is fitted on data to every year end from 2014 to 2024 and scored on the two years that followed. Bias is the
median gap of price over the line: plus means price ran above the line. In-sample R2 moves by under 0.006 across clock starts,
so it cannot decide. Read the table with care: eleven overlapping vintages from one price path carry no significance. It is a
tie-break on bias. Section 2 lists the chosen line and the Jan 2010 alternative vintage by vintage, and section 3 shows where
the cycle lows and highs sit against each line.
"""
import io, math, os, sys, urllib.request, warnings
import numpy as np, pandas as pd, yfinance as yf
warnings.filterwarnings("ignore")

GEN = pd.Timestamp("2009-01-03")
CM = "https://raw.githubusercontent.com/coinmetrics/data/master/csv/btc.csv"
CUTS = ["%d-12-31" % y for y in range(2014, 2025)]


def load():
    px = yf.Ticker("BTC-USD").history(period="max")["Close"].dropna(); px.index = px.index.tz_localize(None).normalize()
    src = sys.argv[1] if len(sys.argv) > 1 else io.BytesIO(urllib.request.urlopen(CM, timeout=60).read())
    cm = pd.read_csv(src, usecols=["time", "PriceUSD"], parse_dates=["time"]).dropna().set_index("time")["PriceUSD"]; cm.index = cm.index.tz_localize(None).normalize()
    px = pd.concat([cm[cm.index < px.index[0]], px]); px = px[~px.index.duplicated()].asfreq("D").ffill()
    d = pd.DataFrame({"p": px}); d["y"] = np.log10(d["p"]); d["g"] = (d.index - GEN).days.astype(float)
    return d


def fit(x, y):
    """Least squares slope, intercept lowered to the median gap: the centre line the site uses."""
    X = np.column_stack([x, np.ones(len(x))]); b, *_ = np.linalg.lstsq(X, y, rcond=None); a, c = float(b[0]), float(b[1])
    return a, c + float(np.median(y - (a * x + c)))


def usd(v): return "$" + format(int(round(v, -2)), ",")


def vintages(d, clock, start):
    sh = (pd.Timestamp(clock) - GEN).days; out = []
    for c in CUTS:
        s = d[(d.index >= start) & (d.index <= c)]; a, b = fit(np.log10(s.g - sh).values, s.y.values)
        f = d[(d.index > pd.Timestamp(c)) & (d.index <= pd.Timestamp(c) + pd.Timedelta(days=730))]
        out.append(float((f.y - (a * np.log10(f.g - sh) + b)).median()))
    return out


def main():
    d = load(); today = d.index[-1]
    print("1. CLOCK START AND SAMPLE START, scored on the two years after each year-end fit 2014 to 2024. Log10 units: 0.10 is about 26%.")
    print("   clock       sample from | mean bias | last 5 bias | mean miss | slope | R2     | centre today | end 2027 | end 2030 | days under the centre since 2022")
    for clock in ("2008-07-03", "2009-01-03", "2009-07-03", "2010-01-03"):
        for start in ("2010-07-18", "2011-07-01", "2013-01-01"):
            sh = (pd.Timestamp(clock) - GEN).days
            if (pd.Timestamp(start) - GEN).days - sh < 150: continue
            es = vintages(d, clock, start); s = d[d.index >= start]; x = np.log10(s.g - sh).values; a, b = fit(x, s.y.values); r = s.y.values - (a * x + b)
            r2 = 1 - float(((r - r.mean()) ** 2).sum() / ((s.y.values - s.y.values.mean()) ** 2).sum())
            f = lambda day: 10 ** (a * math.log10((pd.Timestamp(day) - GEN).days - sh) + b)
            print("   %s  %s | %+.3f    | %+.3f      | %.3f     | %.2f  | %.4f | %12s | %8s | %8s | %3.0f%%" % (clock, start, np.mean(es), np.mean(es[-5:]), np.mean(np.abs(es)), a, r2,
                  usd(f(today)), usd(f("2027-12-31")), usd(f("2030-12-31")), 100 * float((r < 0)[s.index >= "2022"].mean())))

    print("\n2. VINTAGE BY VINTAGE, all days from Jul 2010. Median gap of price over the line in the two years after each cut.")
    gen, alt = vintages(d, "2009-01-03", "2010-07-18"), vintages(d, "2010-01-03", "2010-07-18")
    print("   cut         genesis clock | Jan 2010 clock")
    for c, g, a in zip(CUTS, gen, alt): print("   %s   %+.3f      | %+.3f" % (c, g, a))
    print("   The swings are the cycle. The clock moves every vintage the same way, by about a tenth of a log10.")

    print("\n3. WHERE THE LOWS AND HIGHS SIT against each line fitted on all days from Jul 2010. Log10 gaps.")
    lows = [("2015-01-01", "2015-10-31"), ("2018-11-01", "2019-03-31"), ("2020-03-01", "2020-03-31"), ("2022-06-01", "2023-01-31"), ("2026-01-01", str(today.date()))]
    highs = [("2013-07-01", "2014-12-31"), ("2016-01-01", "2018-12-31"), ("2020-01-01", "2022-06-30"), ("2024-01-01", "2026-06-30")]
    for clock in ("2009-01-03", "2010-01-03"):
        sh = (pd.Timestamp(clock) - GEN).days; s = d[d.index >= "2010-07-18"]; a, b = fit(np.log10(s.g - sh).values, s.y.values)
        res = s.y - (a * np.log10(s.g - sh) + b)
        lo = [float(res[(res.index >= x) & (res.index <= y)].min()) for x, y in lows]; hi = [float(res.loc[d[(d.index >= x) & (d.index <= y)].p.idxmax()]) for x, y in highs]
        print("   clock %s slope %.2f | lows 2015 %+.3f 2019 %+.3f 2020 %+.3f 2022 %+.3f 2026 %+.3f | highs 2013 %+.2f 2017 %+.2f 2021 %+.2f 2025 %+.2f" % (clock, a, *lo, *hi))
    return 0


if __name__ == "__main__":
    sys.exit(main())

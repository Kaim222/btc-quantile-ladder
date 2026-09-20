"""model_audit.py: does the math behind the power-law quantile model hold up?

The site's model is log10(price) = 5.82 x log10(days since 2009-01-03) - 17.029 for the median, fixed log offsets for the
15th and 0.1st percentile lines, and upper lines whose log offset falls linearly with time (frozen at today's value for
any future date). This script tests that against the record. Bitcoin daily closes: CoinMetrics community file from Jul 2010,
Yahoo from Sep 2014. Nothing here is a forecast. It asks what the data supports and how much of it is hindsight.
"""
import io, math, os, sys, urllib.request, warnings
import numpy as np, pandas as pd, yfinance as yf
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, kpss
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ladder_bands_study import quantile as site_quantile

A, B, GEN = 5.82, -17.029, pd.Timestamp("2009-01-03")
LOW = {15: -0.2092, 0.1: -0.3403}
UP = {85: (-0.0000516698, 0.4318), 95: (-0.0000583518, 0.5943), 99.9: (-0.0000756204, 0.7434)}
CM = "https://raw.githubusercontent.com/coinmetrics/data/master/csv/btc.csv"


def load():
    px = yf.Ticker("BTC-USD").history(period="max")["Close"].dropna(); px.index = px.index.tz_localize(None).normalize()
    src = sys.argv[1] if len(sys.argv) > 1 else io.BytesIO(urllib.request.urlopen(CM, timeout=60).read())
    cm = pd.read_csv(src, usecols=["time", "PriceUSD"], parse_dates=["time"]).dropna().set_index("time")["PriceUSD"]; cm.index = cm.index.tz_localize(None).normalize()
    px = pd.concat([cm[cm.index < px.index[0]], px]); px = px[~px.index.duplicated()].asfreq("D").ffill()
    d = pd.DataFrame({"p": px}); d["days"] = (d.index - GEN).days; d["x"] = np.log10(d["days"]); d["y"] = np.log10(d["p"])
    d["res"] = d["y"] - (A * d["x"] + B)
    return d


def ols(x, y):
    X = np.column_stack([x, np.ones(len(x))]); b, *_ = np.linalg.lstsq(X, y, rcond=None); return float(b[0]), float(b[1])


def fv(a, b, day): return 10 ** (a * math.log10((pd.Timestamp(day) - GEN).days) + b)


def usd(v): return "$" + format(int(round(v, -2)), ",")


def main():
    d = load(); today = d.index[-1]
    print("Bitcoin %s to %s, %d days. Last close %s. Site median today %s. Site quantile today %.1f" % (
        d.index[0].date(), today.date(), len(d), usd(d.p.iloc[-1]), usd(fv(A, B, today)), site_quantile(d.p.iloc[-1], today)))

    print("\n1. REFIT THE MEDIAN LINE. The site uses slope 5.82, intercept -17.029.")
    for start in ("2010-07-18", "2011-01-01", "2012-01-01", "2013-01-01", "2014-01-01", "2015-01-01"):
        s = d[d.index >= start]; a, b = ols(s.x, s.y); qr = sm.QuantReg(s.y.values, sm.add_constant(s.x.values)).fit(q=0.5)
        r2 = 1 - ((s.y - (a * s.x + b)) ** 2).sum() / ((s.y - s.y.mean()) ** 2).sum()
        print("   data from %s: least squares slope %.3f intercept %.3f R2 %.3f, median today %s | median regression slope %.3f, median today %s" % (
            start, a, b, r2, usd(fv(a, b, today)), qr.params[1], usd(10 ** (qr.params[0] + qr.params[1] * d.x.iloc[-1]))))

    print("\n2. WHAT EACH YEAR'S FIT WOULD HAVE SAID. Least squares on data through each year end.")
    print("   fit through | slope  | that fit's median for today | its median 2 years later | what Bitcoin did then vs that median")
    for yr in range(2013, 2027):
        cut = pd.Timestamp("%d-12-31" % yr) if yr < 2026 else today
        s = d[d.index <= cut]; a, b = ols(s.x, s.y); t2 = cut + pd.Timedelta(days=730); fut = d.p.get(t2)
        print("   %s  | %.3f | %12s | %12s | %s" % (cut.date(), a, usd(fv(a, b, today)), usd(fv(a, b, t2)),
              ("%+.0f%% (price %s)" % (100 * (fut / fv(a, b, t2) - 1), usd(fut))) if fut else "not yet"))

    print("\n3. ARE THE PERCENTILE LINES CALIBRATED? Share of days at or under each site line. A calibrated 50 line has half the days under it.")
    d["q"] = [site_quantile(p, t) for t, p in zip(d.index, d.p)]
    eras = [("all data", "2010-01-01", "2100-01-01"), ("Jul 2010 to 2013", "2010-01-01", "2014-01-01"), ("2014 to 2017", "2014-01-01", "2018-01-01"),
            ("2018 to 2021", "2018-01-01", "2022-01-01"), ("2022 to today", "2022-01-01", "2100-01-01"), ("last 365 days", str((today - pd.Timedelta(days=365)).date()), "2100-01-01")]
    print("   era               days | under 0.1 | under 15 | under 50 | under 85 | under 95 | median quantile")
    for name, s0, s1 in eras:
        s = d[(d.index >= s0) & (d.index < s1)]
        print("   %-17s %5d | %8.1f%% | %7.0f%% | %7.0f%% | %7.0f%% | %7.0f%% | %5.0f" % (name, len(s), 100 * (s.q <= 0.1).mean(), 100 * (s.q < 15).mean(),
              100 * (s.q < 50).mean(), 100 * (s.q < 85).mean(), 100 * (s.q < 95).mean(), s.q.median()))

    print("\n4. THE QUANTILE WITHOUT HINDSIGHT. Each day refits the line on data to that day and ranks the day's gap against gaps seen so far.")
    xs, ys = d.x.values, d.y.values
    def rank_without_hindsight(t):
        i = d.index.get_loc(t); a_, b_ = ols(xs[:i], ys[:i]); r = ys[:i] - (a_ * xs[:i] + b_); return 100 * float((r <= ys[i] - (a_ * xs[i] + b_)).mean())
    marks = [("2015-01-14", "2015 low"), ("2017-12-16", "2017 top"), ("2018-12-15", "2018 low"), ("2020-03-16", "Mar 2020"), ("2021-04-13", "Apr 2021 top"),
             ("2021-11-08", "Nov 2021 top"), ("2022-11-21", "2022 low"), ("2025-10-06", "Oct 2025 top"), ("2026-06-30", "Jun 2026 low"), (str(today.date()), "today")]
    print("   The line is fitted on data through the day before. One specification, a descriptive rank, not a probability.")
    print("   date         what          | site quantile | rank without hindsight")
    for day, what in marks:
        t = pd.Timestamp(day); print("   %s  %-13s | %13.1f | %10.1f" % (day, what, d.q.loc[t], rank_without_hindsight(t)))

    print("\n5. THE FLOOR. Each cycle low measured as a log10 gap under the site's median line. The site's floor is -0.340, its 15 line -0.209.")
    lows = [("2011-10-01", "2011-12-31"), ("2015-01-01", "2015-10-31"), ("2018-11-01", "2019-03-31"), ("2020-03-01", "2020-03-31"), ("2022-06-01", "2023-01-31"), ("2026-01-01", str(today.date()))]
    for s0, s1 in lows:
        s = d[(d.index >= s0) & (d.index <= s1)]; t = s.res.idxmin()
        print("   low %s  price %10s | gap %+.3f (%.0f%% under the median) | days under the floor line in this window: %d" % (
            t.date(), usd(s.p.loc[t]) if s.p.loc[t] > 1000 else "$%.2f" % s.p.loc[t], s.res.loc[t], 100 * (1 - 10 ** s.res.loc[t]), int((s.res < LOW[0.1]).sum())))
    under = d.res < LOW[0.1]
    print("   days under the floor line in all data: %d of %d = %.2f%%, against the 0.1%% its label implies. By era: %s" % (int(under.sum()), len(d), 100 * under.mean(),
          ", ".join("%s %d" % (lab, int(under[(d.index >= a0) & (d.index < a1)].sum())) for lab, a0, a1 in (("2010-13", "2010", "2014"), ("2014-17", "2014", "2018"), ("2018-21", "2018", "2022"), ("2022 on", "2022", "2100")))))
    jun = d.loc["2026-06-30"]; print("   the site's constants were set on 2026-03-09 and never changed, so June 2026 was a live test: the low close %s sat %.1f%% under the floor line (%s) and was back over it within days." % (
        usd(jun.p), 100 * (1 - 10 ** (jun.res - LOW[0.1])), usd(jun.p / 10 ** (jun.res - LOW[0.1]))))

    print("\n6. THE TOPS. Each cycle high as a log10 gap over the site's median line, and the multiple of the median it reached.")
    tops = [("2011-01-01", "2011-12-31"), ("2013-01-01", "2013-06-30"), ("2013-07-01", "2014-12-31"), ("2016-01-01", "2018-12-31"), ("2020-01-01", "2022-06-30"), ("2024-01-01", "2026-06-30")]
    pk = []
    for s0, s1 in tops:
        s = d[(d.index >= s0) & (d.index <= s1)]; t = s.p.idxmax(); pk.append((d.days.loc[t], s.res.loc[t]))
        print("   high %s  price %10s | gap %+.3f = %.2fx the median | site quantile %.0f" % (t.date(), usd(s.p.loc[t]) if s.p.loc[t] > 1000 else "$%.2f" % s.p.loc[t], s.res.loc[t], 10 ** s.res.loc[t], d.q.loc[t]))
    pk = np.array(pk); m1, c1 = ols(pk[:, 0], pk[:, 1]); m2, c2 = ols(pk[:, 0], np.log(pk[:, 1]))
    nxt = (pd.Timestamp("2029-10-01") - GEN).days
    print("   SCENARIOS ONLY, six points. Straight-line decay through the highs: gap falls %.3f a year and reaches zero on %s" % (-m1 * 365, (GEN + pd.Timedelta(days=-c1 / m1)).date()))
    print("   the same highs on an exponential decay (a different loss, forces the multiple toward one): gap halves every %.1f years. Implied gap in Oct 2029: %+.3f = %.2fx the median (%s)" % (
        math.log(2) / -m2 / 365, math.exp(c2 + m2 * nxt), 10 ** math.exp(c2 + m2 * nxt), usd(fv(A, B, "2029-10-01") * 10 ** math.exp(c2 + m2 * nxt))))
    td = d.days.iloc[-1]
    print("   the site's upper lines today: " + ", ".join("%s line %+.3f = %.2fx the median" % (q, m * td + c, 10 ** (m * td + c)) for q, (m, c) in UP.items()))
    print("   left to run, the site's 85 line would meet its 50 line on %s, which is why the site freezes the decay at today." % ((GEN + pd.Timedelta(days=(-0.0004 - UP[85][1]) / UP[85][0])).date()))

    print("\n7. HOW MUCH INDEPENDENT EVIDENCE IS THERE? Gaps from the line are sticky from one day to the next.")
    r = d.res[d.index >= "2011-01-01"]; rho = float(np.corrcoef(r.values[1:], r.values[:-1])[0, 1]); hl = math.log(0.5) / math.log(rho)
    neff = len(r) * (1 - rho) / (1 + rho)
    print("   day to day correlation of the gap %.4f. A gap takes %.0f days to halve. %d days of data carry very roughly %.0f independent readings (an AR(1) rule of thumb, illustrative)." % (rho, hl, len(r), neff))
    for lab, ser in (("weekly", r.iloc[::7]), ("monthly", r.iloc[::30])):
        rr = float(np.corrcoef(ser.values[1:], ser.values[:-1])[0, 1]); print("   %s gap correlation %.3f" % (lab, rr))
    adf = adfuller(r.iloc[::7].values, regression="c", autolag="AIC"); kp = kpss(r.iloc[::7].values, regression="c", nlags="auto")
    print("   does the gap pull back to the line? ADF on weekly gaps: stat %.2f, p %.3f (under 0.05 says it does). KPSS: stat %.2f, p %.3f (under 0.05 says it drifts)." % (adf[0], adf[1], kp[0], kp[1]))
    print("   caution: these are nominal p values. The line was fitted to the same data, so the real bar is higher by an unknown amount. Neither test proves the gap returns to zero.")
    for s0 in ("2011-01-01", "2014-01-01", "2018-01-01"):
        rs = d.res[d.index >= s0].iloc[::7]; print("   ADF on weekly gaps from %s: stat %.2f p %.3f" % (s0, *adfuller(rs.values, regression="c", autolag="AIC")[:2]))

    print("\n8. DOES THE TIME ORIGIN MATTER? Same fit, same days (Jul 2011 on), with the clock started earlier or later than 3 Jan 2009.")
    for shift in (-730, -365, 0, 365, 547):
        dd = d[d.index >= "2011-07-01"]; x = np.log10(dd.days - shift); a, b = ols(x, dd.y); r2 = 1 - ((dd.y - (a * x + b)) ** 2).sum() / ((dd.y - dd.y.mean()) ** 2).sum()
        f = lambda day: 10 ** (a * math.log10((pd.Timestamp(day) - GEN).days - shift) + b)
        print("   clock starts %s: slope %.2f R2 %.3f | median today %s, end 2027 %s, end 2030 %s" % ((GEN + pd.Timedelta(days=shift)).date(), a, r2, usd(f(today)), usd(f("2027-12-31")), usd(f("2030-12-31"))))

    print("\n9. OUT OF SAMPLE. Fit on data to a cut date, then measure the median miss over the following years (log10 units, + means price ran above the fit).")
    print("   cut date   | power law: next 2y, years 2 to 4 | log-quadratic: next 2y, years 2 to 4 | the two fits' medians for end 2027")
    for cut in ("2015-12-31", "2017-12-31", "2019-12-31", "2021-12-31", "2023-12-31"):
        s = d[(d.index >= "2010-07-18") & (d.index <= cut)]; a, b = ols(s.x, s.y); c2 = np.polyfit(s.x, s.y, 2)
        out = []
        for lo, hi in ((0, 730), (730, 1460)):
            f = d[(d.index > pd.Timestamp(cut) + pd.Timedelta(days=lo)) & (d.index <= pd.Timestamp(cut) + pd.Timedelta(days=hi))]
            out.append((float((f.y - (a * f.x + b)).median()) if len(f) > 100 else float("nan"), float((f.y - np.polyval(c2, f.x)).median()) if len(f) > 100 else float("nan")))
        x27 = math.log10((pd.Timestamp("2027-12-31") - GEN).days)
        print("   %s | %+.2f, %+.2f | %+.2f, %+.2f | %s and %s" % (cut, out[0][0], out[1][0], out[0][1], out[1][1], usd(10 ** (a * x27 + b)), usd(10 ** np.polyval(c2, x27))))

    print("\n10. WHERE THE SITE'S OWN LINES PUT HIS TARGETS. Median line by date, and when the median first reaches each price.")
    for day in ("2026-12-31", "2027-12-31", "2028-12-31", "2029-12-31", "2030-12-31"): print("   median on %s: %s | 15 line %s | floor %s" % (day, usd(fv(A, B, day)), usd(fv(A, B, day) * 10 ** LOW[15]), usd(fv(A, B, day) * 10 ** LOW[0.1])))
    for tgt in (163000, 200000, 250000):
        dd = 10 ** ((math.log10(tgt) - B) / A); print("   the median line reaches %s on %s. The 15 line reaches it on %s." % (usd(tgt), (GEN + pd.Timedelta(days=dd)).date(), (GEN + pd.Timedelta(days=10 ** ((math.log10(tgt) - LOW[15] - B) / A))).date()))
    print("   the same targets on refits that fit about as well:")
    for lab, start, shift in (("least squares, all data", "2010-07-18", 0), ("least squares, data from 2013", "2013-01-01", 0), ("clock started Jan 2010", "2011-07-01", 365)):
        dd = d[d.index >= start]; a_, b_ = ols(np.log10(dd.days - shift), dd.y)
        when = lambda tgt: (GEN + pd.Timedelta(days=shift + 10 ** ((math.log10(tgt) - b_) / a_))).date()
        print("   %-30s median today %s | reaches $163,000 on %s, $200,000 on %s" % (lab, usd(10 ** (a_ * math.log10(d.days.iloc[-1] - shift) + b_)), when(163000), when(200000)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

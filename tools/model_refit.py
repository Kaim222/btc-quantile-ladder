"""model_refit.py: fit model v2 of the power-law quantile ladder and write data/ladder-model.json. Run once a year.

Centre line. Least squares slope of log10(price) on log10(days since the genesis block, 2009-01-03), on every day from Jul
2010, with the intercept lowered so that half of all days sit under the line. That makes the 50 line and the centre line the
same thing (bubbles pull a least squares line above the median). tools/model_refit_explore.py scored clock starts and sample
starts on forecasts from year-end fits 2014 to 2024. Scored on the median gap of price over the line in the two years after
each fit, this combination had a mean gap of -0.002 log10 and a mean absolute gap of 0.237, both the best of the combinations
tested. A clock started in Jan 2010 ran 0.11 to 0.14 log10 under the prices that followed, so it was not used. The vintages
overlap and come from one price path, so this is a tie-break on bias, not a significance test.

Lines. Each line is an offset from the centre in log10 units, shaped c x exp(-age / T) with age in years since the clock
start, so both sides narrow with age and the lines can never cross. The scales c are fitted by pinball loss, so 15, 85 and
95 are nominal targets. The script prints the share of all days actually under each line, and the share era by era. Inside
a single cycle the labels do not hold: 2018 to 2021 spent a third of its days over the 85 line and 2022 on spent almost none.
  Lower side. T is fitted by pinball loss on the 15 and 5 lines together. The 5 line shares the fit and is not drawn.
  Upper side. The data cannot pin T. All days say about 13 years. The four cycle highs fell faster, about 6 years. The model
  uses the geometric mean of the two and records both. This is a judgment, made in the open, and the yearly refit moves it.

Floor and Ceiling. Envelopes of the same shape as their side, pulled out until every daily close from 2014 to the fit date
sits inside. They are not percentiles and not support: sixteen years hold about six independent readings. Their quantile
values 0.1 and 99.9 are interpolation anchors only. A cycle high that repeated 2021's height over the centre would break the
ceiling. The site, the monitor and the Playbook port implement the shapes const and exp only.
"""
import io, json, math, os, sys, urllib.request, warnings
import numpy as np, pandas as pd, yfinance as yf
from scipy.optimize import minimize, minimize_scalar
warnings.filterwarnings("ignore")

CLOCK, START = pd.Timestamp("2009-01-03"), "2010-07-18"
CM = "https://raw.githubusercontent.com/coinmetrics/data/master/csv/btc.csv"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V1 = {"A": 5.82, "B": -17.029}
ERAS = [("2010-13", "2010", "2014"), ("2014-17", "2014", "2018"), ("2018-21", "2018", "2022"), ("2022 on", "2022", "2100")]
HIGHS = [("2013-07-01", "2014-12-31"), ("2016-01-01", "2018-12-31"), ("2020-01-01", "2022-06-30"), ("2024-01-01", "2026-06-30")]


def load():
    px = yf.Ticker("BTC-USD").history(period="max")["Close"].dropna(); px.index = px.index.tz_localize(None).normalize()
    src = sys.argv[1] if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) else io.BytesIO(urllib.request.urlopen(CM, timeout=60).read())
    cm = pd.read_csv(src, usecols=["time", "PriceUSD"], parse_dates=["time"]).dropna().set_index("time")["PriceUSD"]; cm.index = cm.index.tz_localize(None).normalize()
    px = pd.concat([cm[cm.index < px.index[0]], px]); px = px[~px.index.duplicated()].asfreq("D").ffill()
    px = px.iloc[:-1] if px.index[-1] >= pd.Timestamp.utcnow().tz_localize(None).normalize() else px          # drop the running day
    d = pd.DataFrame({"p": px}); d["y"] = np.log10(d["p"]); d["age"] = (d.index - CLOCK).days / 365.25
    return d[d.index >= START].copy()


def centre(d):
    """Least squares slope, intercept lowered to the median of the gaps."""
    x = np.log10(d["age"].values * 365.25); X = np.column_stack([x, np.ones(len(x))]); c, *_ = np.linalg.lstsq(X, d["y"].values, rcond=None)
    a, b = float(c[0]), float(c[1]); lift = float(np.median(d["y"].values - (a * x + b)))
    return a, b + lift, lift


def line(age, c, T): return c * np.exp(-np.asarray(age, float) / T)


def pinball(r, ln, q): e = r - ln; return float(np.mean(np.where(e >= 0, q * e, (q - 1) * e)))


def scales(r, age, qs, sign, T):
    return [sign * minimize_scalar(lambda k: pinball(r, sign * line(age, abs(k), T), q), bounds=(0.01, 30.0), method="bounded").x for q in qs]


def fit_T(r, age, qs, sign):
    """One decay time per side, chosen by pinball loss with the scales refitted at each T."""
    loss = lambda T: sum(pinball(r, line(age, c, T), q) for q, c in zip(qs, scales(r, age, qs, sign, T)))
    return float(minimize_scalar(loss, bounds=(3.0, 60.0), method="bounded", options={"xatol": 0.01}).x)


def envelope(r, age, sign, T):
    """Smallest line of the side's shape that holds every close, rounded outward so the rounded line still holds them."""
    ratio = sign * r / np.exp(-age / T); i = int(np.argmax(ratio)); return sign * math.ceil(float(ratio[i]) * 1e6) / 1e6, i


def usd(v): return "$" + format(int(round(v, -2)), ",")


def main():
    d = load(); today = d.index[-1]; a, b, lift = centre(d); a, b = round(a, 6), round(b, 6)       # everything below uses the constants as they are written
    d["r"] = d["y"] - (a * np.log10(d["age"] * 365.25) + b); r, age = d["r"].values, d["age"].values
    now = lambda off=0.0: 10 ** (a * math.log10(age[-1] * 365.25) + b + off)
    print("Days %s to %s. Least squares sat %.4f log10 above the median of the gaps, so the centre is lowered by that." % (d.index[0].date(), today.date(), -lift))
    print("Centre: log10(price) = %.6f x log10(days since %s) %+.6f. Centre today %s (model v1 %s)." % (a, CLOCK.date(), b, usd(now()), usd(10 ** (V1["A"] * math.log10(age[-1] * 365.25) + V1["B"]))))

    T_low = fit_T(r, age, [0.15, 0.05], -1); T_days = fit_T(r, age, [0.85, 0.95], +1)
    hi = [d[(d.index >= x) & (d.index <= y)].p.idxmax() for x, y in HIGHS]; hv = [float(d.r.loc[t]) for t in hi]
    T_highs = float(-1 / np.polyfit([float(d.age.loc[t]) for t in hi], np.log(hv), 1)[0]); T_up = round(math.sqrt(T_days * T_highs), 6); T_low = round(T_low, 6)
    print("\nUpper decay time: all days say %.1f years, the cycle highs (%s) say %.1f years. Used: %.1f, their geometric mean." % (
        T_days, ", ".join("%s %.2fx" % (t.strftime("%b %Y"), 10 ** v) for t, v in zip(hi, hv)), T_highs, T_up))
    print("Lower decay time: %.1f years, fitted on all days." % T_low)

    c15, = scales(r, age, [0.15], -1, T_low); c85, c95 = scales(r, age, [0.85, 0.95], +1, T_up); c15, c85, c95 = round(c15, 6), round(c85, 6), round(c95, 6)
    since = np.asarray(d.index >= "2014-01-01")
    cf, i_f = envelope(r[since], age[since], -1, T_low); cc, i_c = envelope(r[since], age[since], +1, T_up)
    bands = [{"q": 99.9, "label": "Ceiling", "kind": "exp", "p": [cc, T_up]}, {"q": 95, "label": "95%", "kind": "exp", "p": [c95, T_up]}, {"q": 85, "label": "85%", "kind": "exp", "p": [c85, T_up]},
             {"q": 50, "label": "50%", "kind": "const", "p": [0.0]}, {"q": 15, "label": "15%", "kind": "exp", "p": [c15, T_low]}, {"q": 0.1, "label": "Floor", "kind": "exp", "p": [cf, T_low]}]
    for bd in bands: bd["p"] = [round(float(x), 6) for x in bd["p"]]
    ln_of = lambda bd, ag: np.full(len(np.atleast_1d(ag)), bd["p"][0]) if bd["kind"] == "const" else line(np.atleast_1d(ag), bd["p"][0], bd["p"][1])

    print("\nLINES. Offset today, multiple of the centre today, end 2027 and Oct 2029, share of all days under the line, then the same share era by era.")
    for bd in bands:
        ln = ln_of(bd, age); f = lambda day: 10 ** float(ln_of(bd, (pd.Timestamp(day) - CLOCK).days / 365.25)[0])
        print("   %-8s c %+.4f T %5s | %+.3f | %s = %.2fx, %.2fx, %.2fx | %5.1f%% | %s" % (bd["label"], bd["p"][0], ("%.1f" % bd["p"][1]) if len(bd["p"]) > 1 else "-", float(ln[-1]), usd(now(float(ln[-1]))),
              10 ** float(ln[-1]), f("2027-12-31"), f("2029-10-01"), 100 * float((r < ln).mean()), "  ".join("%s %3.0f%%" % (e[0], 100 * float((r < ln)[(d.index >= e[1]) & (d.index < e[2])].mean())) for e in ERAS)))
    offs = [float(ln_of(bd, 60.0)[0]) for bd in bands]; assert offs == sorted(offs, reverse=True) and all(x != y for x, y in zip(offs, offs[1:])), "lines out of order"
    assert (r[since] >= ln_of(bands[-1], age[since]) - 1e-9).all() and (r[since] <= ln_of(bands[0], age[since]) + 1e-9).all(), "an envelope lost a close after rounding"
    print("   Floor binds on the %s close, Ceiling on the %s close." % (d.index[since][i_f].date(), d.index[since][i_c].date()))

    model = {"version": 2, "fitted": str(today.date()), "clock_start": str(CLOCK.date()), "sample_start": START, "slope": round(a, 6), "intercept": round(b, 6), "bands": bands,
             "note": "Centre line: least squares slope on log10(days since clock_start), intercept lowered to the median of the gaps. Offsets in log10 from the centre: const = p0, exp = p0 * exp(-age_years / p1), age in years of 365.25 days since clock_start. 15, 85 and 95 are nominal pinball targets: the observed share of all days under each line is in evidence.coverage, and the labels do not hold inside a single cycle. Floor and Ceiling are envelopes of every daily close from 2014-01-01 to the fit date (CoinMetrics then Yahoo), not percentiles and not support. Their quantile values 0.1 and 99.9 are interpolation anchors only. Refit once a year.",
             "evidence": {"centre": "genesis clock on all days from Jul 2010 with the median intercept had a mean two-year gap of -0.002 log10 and a mean absolute gap of 0.237 across year-end fits 2014 to 2024, both the best of the combinations tested; a Jan 2010 clock ran 0.11 to 0.14 log10 under the prices that followed (tools/model_refit_explore.py). Overlapping vintages from one path: a tie-break, not a significance test",
                          "upper_decay_years": {"all_days": round(T_days, 1), "cycle_highs": round(T_highs, 1), "used_geometric_mean": round(T_up, 1)}, "lower_decay_years": round(T_low, 1),
                          "coverage": {bd["label"]: round(100 * float((r < ln_of(bd, age)).mean()), 1) for bd in bands if bd["q"] in (15, 50, 85, 95)},
                          "cycle_highs_over_centre": {t.strftime("%Y-%m"): round(10 ** v, 2) for t, v in zip(hi, hv)},
                          "floor_binds_on": str(d.index[since][i_f].date()), "ceiling_binds_on": str(d.index[since][i_c].date())},
             "v1": {"clock_start": "2009-01-03", "slope": 5.82, "intercept": -17.029}}
    out = os.path.join(ROOT, "data", "ladder-model.json"); prev = json.load(open(out, encoding="utf-8")) if os.path.exists(out) else {}
    model["vintages"] = [v for v in prev.get("vintages", []) if v.get("fitted") != model["fitted"]] + [{"fitted": model["fitted"], "slope": model["slope"], "intercept": model["intercept"]}]
    if "--write" in sys.argv:
        json.dump(model, open(out, "w", encoding="utf-8", newline="\n"), indent=1); print("\nwrote", out)
    else: print("\n(dry run, pass --write to save data/ladder-model.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

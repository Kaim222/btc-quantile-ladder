#!/usr/bin/env python3
"""Refresh the PLAYBOOK tab inputs for the BTC Quantile Ladder site.

Run from the repo root (the script resolves paths off its own location, so any
cwd works):

    python tools/playbook_refresh.py

Writes:
    data/playbook.json    the inputs the PLAYBOOK tab reads
    data/iv-ledger.json   append-only implied-vol history, keyed ticker -> date

Hard rule: a field is never a fabricated number. Every computation is wrapped,
and a source that fails writes value null plus an error string. The page shows
"fill by hand" or "source failed" for those, never a placeholder figure.

Prices are Yahoo Finance via yfinance. Delayed, unofficial, and the option-chain
implied vol is Yahoo's own calculation, not a mid-market vol we computed.
The 30-day implied-vol series for MSTR, MSTX and IBIT is AlphaQuery's keyless
option-statistic endpoint. Its free tier returns about 63 trading days, so the
IV rank it supports is a 3-month rank and is labelled as one. The rank window is
the trailing 252 ledger entries at most, and it is called a 52-week window only
when a full 252 entries are in it.

Python 3.11+, yfinance, numpy, pandas.
"""

from __future__ import annotations

import json
import math
import re
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
TOOLS = REPO / "tools"
DATA = REPO / "data"

BTC = "BTC-USD"
MSTR = "MSTR"
MSTX = "MSTX"
START = "2016-01-01"          # 200 weeks needs ~4 years, 2016 is comfortable
TRAIL = 252                   # percentile / IV-rank lookback in observations
IV_TICKERS = ("MSTR", "MSTX", "IBIT")
IV_SERIES_SOURCE = "alphaquery_iv_mean_30d"
IV_RANK_WINDOW = TRAIL        # the rank runs over the trailing 252 entries at most
IV_RANK_WINDOW_3M = 63        # a quarter of trading days, the short-term rank's cap
IV_RANK_MIN = 30              # below this many entries no rank is computed at all
PO_URL = "https://projectoption.com/stocks/mstr/implied-volatility"
AQ_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

TODAY = date.today()
TODAY_UTC = datetime.now(timezone.utc).date()
NOW_ISO = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

ERRORS: list[str] = []


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────
def row(value=None, *, source=None, as_of=None, passes=None, error=None, **extra) -> dict:
    """One input row in the shape the page reads."""
    d = {
        "value": value,
        "pass": passes,
        "source": source,
        "as_of": as_of,
        "error": error,
    }
    d.update(extra)
    return d


def failed(what: str, exc: BaseException) -> dict:
    msg = f"{type(exc).__name__}: {exc}"
    ERRORS.append(f"{what} -> {msg}")
    return row(error=msg, source="failed")


def load_json(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default
    except Exception as exc:  # malformed file is an error, not a silent default
        ERRORS.append(f"read {path.name} -> {type(exc).__name__}: {exc}")
        return default


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, sort_keys=False) + "\n"
    path.write_bytes(text.encode("utf-8"))


def f(x):
    """JSON-safe float."""
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if (math.isnan(v) or math.isinf(v)) else round(v, 6)


def dstr(ts) -> str:
    return pd.Timestamp(ts).date().isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# ladder quantile: a port of the page's own priceToQuantile
#
# Copied from index.html rather than imported, so the script has no dependency
# outside this repo. Fair value is 10 ** (A * log10(days since genesis) + B).
# Bands are offsets in log10(price / fair value); the three decaying bands take
# the smaller of days-elapsed and today's days for their slope term, which is
# what the page's Date.now() does. The quantile is a linear interpolation in
# quantile space between the two band offsets that bracket the residual, with
# the outermost pair's slope extrapolating off either end.
# ─────────────────────────────────────────────────────────────────────────────
LADDER_GENESIS = datetime(2009, 1, 3, tzinfo=timezone.utc)
LADDER_A = 5.82
LADDER_B = -17.029
LADDER_BANDS = [                     # (quantile, slope, intercept), highest first
    (99.9, -0.0000756204, 0.7434),
    (95.0, -0.0000583518, 0.5943),
    (85.0, -0.0000516698, 0.4318),
    (50.0, 0.0, -0.000400),
    (15.0, 0.0, -0.209200),
    (0.1, 0.0, -0.340300),
]


def ladder_days(when) -> float:
    """Float days from the genesis block to `when` (a date or a UTC datetime)."""
    if isinstance(when, datetime):
        d = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    else:
        d = datetime(when.year, when.month, when.day, tzinfo=timezone.utc)
    return (d - LADDER_GENESIS).total_seconds() / 86400.0


def ladder_fair_value(days: float) -> float:
    return 10 ** (LADDER_A * math.log10(days) + LADDER_B) if days > 0 else 0.0


def ladder_band_offsets(days: float, today_days: float) -> list[tuple[float, float]]:
    out = []
    for q, m, c in LADDER_BANDS:
        eff = min(days, today_days) if m < 0 else days
        out.append((q, m * eff + c))
    return out


def price_to_quantile_days(price: float, days: float, today_days: float | None = None) -> float:
    td = ladder_days(TODAY_UTC) if today_days is None else today_days
    fv = ladder_fair_value(days)
    if not fv or price <= 0:
        raise RuntimeError(f"ladder quantile undefined at price {price} and {days} days")
    res = math.log10(price / fv)
    bands = ladder_band_offsets(days, td)
    for i in range(len(bands) - 1):
        hi_q, hi_off = bands[i]
        lo_q, lo_off = bands[i + 1]
        if lo_off <= res <= hi_off:
            t = (res - lo_off) / (hi_off - lo_off)
            return lo_q + t * (hi_q - lo_q)
    if res > bands[0][1]:                                     # above the top band
        slope = (bands[0][0] - bands[1][0]) / (bands[0][1] - bands[1][1])
        return min(99.99, bands[0][0] + slope * (res - bands[0][1]))
    a, z = bands[-2], bands[-1]                               # below the bottom band
    slope = (a[0] - z[0]) / (a[1] - z[1])
    return max(0.01, z[0] + slope * (res - z[1]))


def price_to_quantile(price: float, when, today_days: float | None = None) -> float:
    return price_to_quantile_days(price, ladder_days(when), today_days)


# Model v2 (site default since 2026-09-20, constants from data/ladder-model.json). The functions above are model v1 and stay
# because the 9/13 research leg was measured on v1's 85th band.
LADDER2_CLOCK = datetime(2009, 1, 3, tzinfo=timezone.utc)
LADDER2_A, LADDER2_B = 5.645315, -16.430264
LADDER2_BANDS = [(99.9, 2.468226, 8.871781), (95, 1.589109, 8.871781), (85, 1.048162, 8.871781), (50, 0.0, None), (15, -0.339276, 20.784638), (0.1, -0.659285, 20.784638)]


def price_to_quantile_v2(price: float, when) -> float:
    d = when if isinstance(when, datetime) else datetime(when.year, when.month, when.day, tzinfo=timezone.utc)
    d = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    days = (d - LADDER2_CLOCK).total_seconds() / 86400.0
    if days <= 0 or price <= 0:
        raise RuntimeError(f"ladder quantile undefined at price {price} on {when}")
    res = math.log10(price) - (LADDER2_A * math.log10(days) + LADDER2_B)
    age = days / 365.25
    bands = [(q, c if t is None else c * math.exp(-age / t)) for q, c, t in LADDER2_BANDS]
    for (hq, ho), (lq, lo) in zip(bands, bands[1:]):
        if lo <= res <= ho:
            return lq + (res - lo) / (ho - lo) * (hq - lq)
    if res > bands[0][1]:
        return min(99.99, bands[0][0] + (bands[0][0] - bands[1][0]) / (bands[0][1] - bands[1][1]) * (res - bands[0][1]))
    a, z = bands[-2], bands[-1]
    return max(0.01, z[0] + (a[0] - z[0]) / (a[1] - z[1]) * (res - z[1]))


def ladder_band_label(q: float) -> str:
    """The ladder's four rungs as moved on 2026-09-20 (10, 60, 75). Not the fitted chart bands."""
    if q < 10.0:
        return "below 10"
    if q < 60.0:
        return "10 to 60"
    if q < 75.0:
        return "60 to 75"
    return "above 75"


# ─────────────────────────────────────────────────────────────────────────────
# market data
# ─────────────────────────────────────────────────────────────────────────────
def download(ticker: str) -> pd.DataFrame:
    import yfinance as yf

    df = yf.download(ticker, start=START, auto_adjust=False, progress=False, threads=False)
    if df is None or len(df) == 0:
        raise RuntimeError(f"{ticker}: yfinance returned an empty frame")
    if isinstance(df.columns, pd.MultiIndex):
        df = df.droplevel(-1, axis=1)
    df = df.dropna(subset=["Close"])
    if len(df) < 300:
        raise RuntimeError(f"{ticker}: only {len(df)} rows, too short to score")
    return df


def last_completed_week_end(today: date | None = None) -> date:
    """The Sunday that ends the last complete calendar week as of `today` (UTC).

    Calendar weeks end Sunday 23:59:59 UTC, so a week counts as complete only
    when its Sunday falls strictly before the current UTC date's 00:00. A run on
    a Sunday therefore excludes the week that Sunday is still inside, which the
    old `> TODAY` test let through.
    """
    d = today or TODAY_UTC
    sunday = d + timedelta(days=(6 - d.weekday()) % 7)   # Sunday of d's own week
    while sunday >= d:                                   # strictly before d 00:00
        sunday -= timedelta(days=7)
    return sunday


def weekly_closes(close: pd.Series, today: date | None = None) -> pd.Series:
    """Calendar-week last close, completed weeks only.

    `resample("W")` labels each bucket with the Sunday that closes it, so the
    cutoff is a straight comparison against the last completed week's Sunday.
    """
    end = last_completed_week_end(today)
    wk = close.resample("W").last().dropna()
    if len(wk):
        wk = wk[[d.date() <= end for d in wk.index]]
    return wk


def macd_hist(closes: pd.Series, fast: int = 8, slow: int = 21, signal: int = 5) -> pd.Series:
    """MACD histogram: line minus signal, EMAs seeded on the first value.

    `adjust=False` is the standard first-value seed, the same convention the MSTR
    weekly MACD row already uses and the one the 9/13 backtest ran on.
    """
    line = closes.ewm(span=fast, adjust=False).mean() - closes.ewm(span=slow, adjust=False).mean()
    return line - line.ewm(span=signal, adjust=False).mean()


def macd_hist_rising(closes: pd.Series, fast: int = 8, slow: int = 21, signal: int = 5,
                     warmup: int = 30) -> dict:
    """The 9/13 research's weekly leg: histogram above zero and above the prior bar.

    `closes` must already be completed bars only. Fewer than `warmup` bars is an
    error rather than a reading, because the seeded EMA has not settled.
    """
    hist = macd_hist(closes, fast, slow, signal).dropna()
    if len(hist) < warmup:
        raise RuntimeError(f"only {len(hist)} histogram bars, {warmup} needed for warm-up")
    last, prev = float(hist.iloc[-1]), float(hist.iloc[-2])
    tail = min(16, len(hist))
    return {
        "flag": bool(last > 0.0 and last > prev),
        "hist": last,
        "hist_prev": prev,
        "bar": dstr(hist.index[-1]),
        "prev_bar": dstr(hist.index[-2]),
        "bars": int(len(hist)),
        # the page draws these as a bar chart, oldest bar first
        "last16": [{"bar": dstr(hist.index[i]), "hist": f(hist.iloc[i])}
                   for i in range(len(hist) - tail, len(hist))],
    }


def macd_hist_fresh_cross(closes: pd.Series, fast: int = 8, slow: int = 21, signal: int = 5,
                          warmup: int = 30, window: int = 3) -> dict:
    """The 9/13 research's entry-timing cell: a bullish cross inside the last `window` bars.

    Same bars and same EMA seeding as `macd_hist_rising`, a different question.
    The cross bar is the first bar after the most recent non-positive bar, so the
    flag is exactly "the last complete bar is above zero and at least one of the
    `window - 1` bars before it was at or below zero". A histogram that has never
    been non-positive over the series has no cross bar and no reading; a cross
    older than `window` bars reads false with the cross date still reported.
    """
    hist = macd_hist(closes, fast, slow, signal).dropna()
    if len(hist) < warmup:
        raise RuntimeError(f"only {len(hist)} histogram bars, {warmup} needed for warm-up")
    vals = [float(v) for v in hist]
    n = len(vals)
    last_np = next((i for i in range(n - 1, -1, -1) if vals[i] <= 0.0), None)
    cross = last_np + 1 if (last_np is not None and last_np + 1 < n) else None
    since = (n - 1 - cross) if cross is not None else None
    fresh = since is not None and since <= window - 1
    tail = min(4, n)
    return {
        "flag": bool(fresh),
        "hist": vals[-1],
        "bar": dstr(hist.index[-1]),
        "cross_bar": dstr(hist.index[cross]) if cross is not None else None,
        "bars_since_cross": int(since) if fresh else None,
        "last4": [{"bar": dstr(hist.index[i]), "hist": f(vals[i])} for i in range(n - tail, n)],
        "bars": int(n),
    }


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """Wilder's RSI(n).

    Standard initialization: a simple average of the first n price changes, then
    Wilder's recursive smoothing. The first n bars are NaN (warm-up, no reading),
    and a zero average loss reads 100, not an invented neutral 50. The old
    version replaced a zero average loss with NaN and then filled every NaN with
    50, so a monotonically rising series read 50 instead of 100 and the warm-up
    read 50 as well.
    """
    n = int(n)
    out = pd.Series(np.nan, index=close.index, dtype=float)
    if n < 1 or len(close) <= n:
        return out
    delta = close.astype(float).diff()
    up = delta.clip(lower=0.0).to_numpy(dtype=float)
    dn = (-delta).clip(lower=0.0).to_numpy(dtype=float)
    au = np.full(len(close), np.nan)
    ad = np.full(len(close), np.nan)
    au[n] = float(np.mean(up[1 : n + 1]))                # changes 1..n, bar 0 has none
    ad[n] = float(np.mean(dn[1 : n + 1]))
    for i in range(n + 1, len(close)):
        au[i] = (au[i - 1] * (n - 1) + up[i]) / n
        ad[i] = (ad[i - 1] * (n - 1) + dn[i]) / n
    vals = np.full(len(close), np.nan)
    known = ~np.isnan(ad)
    zero = known & (ad == 0.0)
    calc = known & (ad > 0.0)
    vals[calc] = 100.0 - 100.0 / (1.0 + au[calc] / ad[calc])
    vals[zero] = 100.0                                   # no losses in the window
    out.iloc[:] = vals
    return out


def pct_rank(series: pd.Series, trail: int = TRAIL):
    """Percentile of the last value inside its own trailing window, 0-100."""
    s = series.dropna()
    if len(s) < 30:
        return None, len(s)
    w = s.iloc[-trail:]
    last = float(w.iloc[-1])
    rank = float((w <= last).sum()) / float(len(w)) * 100.0
    return rank, len(w)


def swing_lows(low: pd.Series, span: int = 5) -> list[int]:
    """Index positions where low is the minimum of the +/- span window."""
    vals = low.to_numpy(dtype=float)
    out = []
    for i in range(span, len(vals) - span):
        win = vals[i - span : i + span + 1]
        if vals[i] == win.min() and np.argmin(win) == span:
            out.append(i)
    return out


def hidden_bull_div(df: pd.DataFrame, lookback: int = 20, recent: int = 10, span: int = 5) -> dict:
    """Higher price swing low while RSI(14) at the two swing lows makes a lower low.

    A swing low at position i is confirmed only once `span` bars print after it,
    so the pair "completes" at position j + span for the later low j. The flag is
    true when that completion lands inside the last `recent` trading days.

    Bars inside the RSI warm-up carry no reading, so a pair with a NaN RSI at
    either low is skipped rather than compared.
    """
    low = df["Low"] if "Low" in df else df["Close"]
    r = rsi(df["Close"])
    idx = swing_lows(low, span)
    n = len(df)
    lows = low.to_numpy(dtype=float)
    rvals = r.to_numpy(dtype=float)
    hits = []
    for a in range(len(idx)):
        for b in range(a + 1, len(idx)):
            i, j = idx[a], idx[b]
            if j - i > lookback:
                continue
            if math.isnan(rvals[i]) or math.isnan(rvals[j]):
                continue
            if lows[j] > lows[i] and rvals[j] < rvals[i]:
                completed = j + span
                if completed >= n - recent and completed <= n - 1:
                    hits.append(
                        {
                            "earlier_low_date": dstr(df.index[i]),
                            "earlier_low": f(lows[i]),
                            "earlier_rsi": f(rvals[i]),
                            "later_low_date": dstr(df.index[j]),
                            "later_low": f(lows[j]),
                            "later_rsi": f(rvals[j]),
                            "confirmed_date": dstr(df.index[completed]),
                            "bars_ago": int(n - 1 - completed),
                        }
                    )
    hits.sort(key=lambda h: h["bars_ago"])
    return {"flag": bool(hits), "matches": hits[:3], "n_matches": len(hits)}


# ─────────────────────────────────────────────────────────────────────────────
# IV
# ─────────────────────────────────────────────────────────────────────────────
def atm_iv_30d(spot: float) -> dict:
    import yfinance as yf

    tk = yf.Ticker(MSTR)
    exps = list(tk.options or [])
    if not exps:
        raise RuntimeError("MSTR: yfinance returned no option expiries")
    parsed = []
    for e in exps:
        try:
            parsed.append((e, (date.fromisoformat(e) - TODAY).days))
        except ValueError:
            continue
    forward = [p for p in parsed if p[1] >= 0]
    if not forward:
        raise RuntimeError("MSTR: no option expiry on or after today")
    exp, dte = min(forward, key=lambda p: abs(p[1] - 30))
    chain = tk.option_chain(exp)

    def leg_iv(frame, name):
        if frame is None or len(frame) == 0:
            raise RuntimeError(f"MSTR {exp}: empty {name} chain")
        fr = frame.dropna(subset=["strike"]).copy()
        fr["_d"] = (fr["strike"].astype(float) - float(spot)).abs()
        r = fr.sort_values("_d").iloc[0]
        iv = r.get("impliedVolatility", None)
        iv = None if iv is None or pd.isna(iv) or float(iv) <= 0 else float(iv)
        return iv, float(r["strike"])

    civ, cstrike = leg_iv(chain.calls, "call")
    piv, pstrike = leg_iv(chain.puts, "put")
    legs = [v for v in (civ, piv) if v is not None]
    if not legs:
        raise RuntimeError(f"MSTR {exp}: no positive implied vol on the ATM strikes")
    return {
        "iv": float(np.mean(legs)),
        "expiry": exp,
        "dte": int(dte),
        "call_strike": cstrike,
        "put_strike": pstrike,
        "call_iv": civ,
        "put_iv": piv,
        "spot": float(spot),
        "legs_used": len(legs),
    }


def alphaquery_iv_series(ticker: str) -> list[tuple[str, float]]:
    """30-day mean implied vol series from AlphaQuery's keyless chart endpoint.

    Returns [(YYYY-MM-DD, iv_as_fraction)]. The free tier truncates at about 63
    trading days, which is why the ledger accumulates: each run merges the
    rolling 3-month window in and the history grows past what one call returns.
    """
    url = (
        "https://www.alphaquery.com/data/option-statistic-chart"
        f"?ticker={ticker}&perType=30-Day&identifier=iv-mean"
    )
    ref = f"https://www.alphaquery.com/stock/{ticker}/volatility-option-statistics/30-day/iv-mean"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": AQ_UA, "Referer": ref, "Accept": "application/json, text/plain, */*"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    if not isinstance(raw, list) or not raw:
        raise RuntimeError(f"{ticker}: AlphaQuery returned no series")
    out = []
    for p in raw:
        if not isinstance(p, dict):
            continue
        x, v = p.get("x"), p.get("value")
        if not x or v is None:
            continue
        try:
            d = str(x)[:10]
            date.fromisoformat(d)
            fv = float(v)
        except (ValueError, TypeError):
            continue
        if fv > 0:
            out.append((d, fv))
    if not out:
        raise RuntimeError(f"{ticker}: AlphaQuery series held no usable points")
    out.sort(key=lambda t: t[0])
    return out


PO_LABELS = {
    "Current IV (30-Day)": "iv_30d",
    "IV Rank": "printed",
    "IV Percentile": "percentile",
    "52-Week Low IV": "low_52w",
    "52-Week High IV": "high_52w",
}
PO_CARD = re.compile(
    r'iv-metric-label"[^>]*>\s*([^<]+?)\s*</div>\s*'
    r'<div class="iv-metric-value[^"]*"[^>]*>\s*([^<]+?)\s*</div>',
    re.S,
)
PO_DATE = re.compile(r'stock-iv-data-date"[^>]*>\s*Data as of\s*([^<]+?)\s*</p>', re.S)
PO_MONTHS = ("january", "february", "march", "april", "may", "june",
             "july", "august", "september", "october", "november", "december")


def po_pct(s: str) -> float | None:
    """A projectoption stat value, "67.3%" or "25%", as a bare number."""
    m = re.search(r"-?\d+(?:\.\d+)?", str(s))
    return float(m.group(0)) if m else None


def po_date(s: str) -> str | None:
    """"September 11th, 2026" -> "2026-09-11"."""
    m = re.match(r"\s*([A-Za-z]+)\s+(\d{1,2})[a-z]{0,2},?\s+(\d{4})", str(s))
    if not m or m.group(1).lower() not in PO_MONTHS:
        return None
    return date(int(m.group(3)), PO_MONTHS.index(m.group(1).lower()) + 1,
                int(m.group(2))).isoformat()


def po_iv_stats(html: str) -> dict:
    """projectoption's IV stat cards, read by label rather than by first number.

    The page carries plenty of unrelated figures, so each value is anchored to
    the label of the card that holds it. A missing card is an error, not a
    silently wrong reading. Percentages come back as fractions for the two vol
    levels and as 0-to-100 numbers for the rank and the percentile, which is how
    the rest of this file carries them.
    """
    found: dict = {}
    for label, val in PO_CARD.findall(html):
        key = PO_LABELS.get(" ".join(str(label).split()))
        if key and key not in found:
            found[key] = po_pct(val)
    missing = [k for k in PO_LABELS.values() if found.get(k) is None]
    if missing:
        raise RuntimeError("projectoption stat cards missing " + ", ".join(sorted(missing)))
    for k in ("iv_30d", "low_52w", "high_52w"):
        found[k] = found[k] / 100.0
    m = PO_DATE.search(html)
    found["as_of"] = po_date(m.group(1)) if m else None
    return found


def projectoption_iv(url: str = PO_URL) -> dict:
    """Fetch and parse the projectoption IV page. Static HTML, no key."""
    import requests

    r = requests.get(
        url,
        headers={"User-Agent": AQ_UA, "Accept": "text/html,application/xhtml+xml"},
        timeout=20,
    )
    r.raise_for_status()
    return po_iv_stats(r.text)


def normalize_book(book: dict) -> dict:
    """One ticker's book as date -> source -> entry.

    Migrates the pre-per-source shape, date -> entry, where a single date held one
    vendor's reading. Keying by source as well as by date is what lets a Yahoo
    option-chain reading and an AlphaQuery observation share a date: the old
    `if d not in book` test meant whichever landed first blocked the other, and it
    was usually Yahoo blocking the series the rank is computed from.
    """
    out: dict = {}
    for d, e in (book or {}).items():
        if not isinstance(e, dict):
            continue
        if "iv" in e:                                  # flat: one entry on the date
            out.setdefault(str(d), {})[str(e.get("source") or "unknown")] = e
            continue
        for src, sub in e.items():                     # already per-source
            if isinstance(sub, dict) and sub.get("iv") is not None:
                out.setdefault(str(d), {})[str(src)] = sub
    return out


def merge_ledger(series: dict[str, list[tuple[str, float]]], yahoo_iv: dict | None) -> dict:
    """Merge today's pulls into data/iv-ledger.json, keyed ticker -> date -> source.

    Append-only: an entry already on file for that ticker, date and source is
    never overwritten, so the ledger is the long history the 52-week rank
    eventually needs. Migrates the pre-v3 flat list, which was MSTR
    Yahoo-option-chain readings, and the date -> entry shape that followed it.
    """
    path = DATA / "iv-ledger.json"
    ledger = load_json(path, {})

    if isinstance(ledger, list):           # pre-v3 shape: flat MSTR list
        migrated: dict = {"MSTR": {}}
        for e in ledger:
            if isinstance(e, dict) and e.get("date") and e.get("iv") is not None:
                migrated["MSTR"][str(e["date"])] = {
                    k: v for k, v in e.items() if k != "date"
                }
        ledger = migrated
    if not isinstance(ledger, dict):
        ERRORS.append("iv-ledger.json was neither an object nor an array, starting fresh")
        ledger = {}

    books: dict[str, dict] = {}
    for t, b in ledger.items():
        if not isinstance(b, dict):
            ERRORS.append(f"iv-ledger.json: {t} was not an object, replacing it")
            b = {}
        books[str(t)] = normalize_book(b)

    def put(ticker: str, d: str, source: str, entry: dict) -> None:
        day = books.setdefault(ticker, {}).setdefault(d, {})
        if source not in day:              # no duplicates, never overwrite
            day[source] = entry

    for ticker, pts in series.items():
        for d, v in pts:
            put(ticker, d, IV_SERIES_SOURCE, {"iv": f(v), "source": IV_SERIES_SOURCE})

    if yahoo_iv is not None:
        put(MSTR, TODAY.isoformat(), "yahoo_option_chain", {
            "iv": f(yahoo_iv["iv"]),
            "source": "yahoo_option_chain",
            "expiry": yahoo_iv["expiry"],
            "dte": yahoo_iv["dte"],
            "strike": f(yahoo_iv["call_strike"]),
            "spot": f(yahoo_iv["spot"]),
        })

    ledger = {
        t: {d: dict(sorted(day.items())) for d, day in sorted(b.items())}
        for t, b in sorted(books.items())
    }
    write_json(path, ledger)
    return ledger


def iv_window(ledger: dict, ticker: str) -> dict | None:
    """Min / max / n / first / last / rank over the ticker's AlphaQuery window.

    The rank runs over one vendor's series only. Yahoo option-chain entries stay
    in the ledger but are excluded here: Yahoo's ATM chain vol and AlphaQuery's
    30-day mean are different constructions and a min/max that mixes them is not
    a rank of anything.

    The window is the trailing 252 AlphaQuery entries at most, so a multi-year
    ledger ranks the last year of readings rather than every reading it holds.
    It is called a 52-week window only when the window is a full 252 entries.
    """
    book = ledger.get(ticker) or {}
    series = []
    other = 0
    for d, day in book.items():
        if not isinstance(day, dict):
            continue
        for src, e in day.items():
            if not isinstance(e, dict) or e.get("iv") is None:
                continue
            if src == IV_SERIES_SOURCE:
                series.append((str(d), float(e["iv"])))
            else:
                other += 1
    if not series:
        return None
    series.sort()
    n_ledger = len(series)
    pts = series[-IV_RANK_WINDOW:]
    n = len(pts)
    is_52w = n == IV_RANK_WINDOW
    cur_date, cur = pts[-1]
    lo = min(v for _, v in pts)
    hi = max(v for _, v in pts)
    rank = None
    if n >= IV_RANK_MIN and hi > lo:
        rank = (cur - lo) / (hi - lo) * 100.0
    # the short-term rank: the same reading against a quarter of trading days
    p3 = series[-IV_RANK_WINDOW_3M:]
    n3 = len(p3)
    lo3 = min(v for _, v in p3)
    hi3 = max(v for _, v in p3)
    rank3 = ((cur - lo3) / (hi3 - lo3) * 100.0) if (n3 >= IV_RANK_MIN and hi3 > lo3) else None
    return {
        "iv_30d": f(cur),
        "as_of": cur_date,
        "rank": f(rank),
        "rank_3m": {
            "value": f(rank3),
            "n_days": n3,
            "first": p3[0][0],
            "last": cur_date,
            "min": f(lo3),
            "max": f(hi3),
            "label": f"3-month rank over {n3} days",
            "source": IV_SERIES_SOURCE,
            "max_days": IV_RANK_WINDOW_3M,
            "error": None if rank3 is not None else (
                f"{n3} entries in the window, {IV_RANK_MIN} needed"
                if n3 < IV_RANK_MIN else "the window's high and low did not bracket a range"
            ),
        },
        "rank_label": (
            f"rank over {n} days, 52-week window" if is_52w
            else f"rank over {n} days, not 52 weeks"
        ),
        "is_52w_rank": is_52w,
        "window": {
            "n_days": n,
            "first": pts[0][0],
            "last": cur_date,
            "min": f(lo),
            "max": f(hi),
            "source": IV_SERIES_SOURCE,
            "max_days": IV_RANK_WINDOW,
            "n_ledger_entries": n_ledger,
            "other_source_entries_excluded": other,
        },
        "note": (
            "rank = (current - window min) / (window max - window min). "
            f"The window is the trailing {n} trading days of AlphaQuery 30-day mean IV "
            f"out of {n_ledger} on file. "
            + ("A full 252-day window, so a 52-week rank."
               if is_52w else f"{IV_RANK_WINDOW} days would make it a 52-week rank.")
        ) if rank is not None else (
            f"ledger holds {n_ledger} entries, {IV_RANK_MIN} needed before a rank is computed"
        ),
    }


def rank_52w_row(win: dict | None, po: dict | None, po_err: str | None) -> dict:
    """The 52-week IV rank for MSTR.

    The ledger wins once it holds a full 252-entry AlphaQuery window, because
    that is a rank of the same series every other number here is computed on.
    Until then the reading comes from projectoption, one source, un-cross-checked:
    the rank is computed from their published 52-week high and low and their
    printed rank is kept beside it so the two can disagree in the open.
    """
    blank = {"value": None, "printed": None, "iv_30d": None, "low_52w": None,
             "high_52w": None, "percentile": None, "as_of": None}
    if win and win.get("is_52w_rank") and win.get("rank") is not None:
        w = win.get("window") or {}
        return {**blank, "value": win["rank"], "iv_30d": win.get("iv_30d"),
                "low_52w": w.get("min"), "high_52w": w.get("max"),
                "as_of": win.get("as_of"), "source": "iv ledger, 252 days", "error": None}
    if not po:
        return {**blank, "source": "projectoption.com, single source",
                "error": po_err or "no projectoption reading"}
    lo, hi, iv30 = po.get("low_52w"), po.get("high_52w"), po.get("iv_30d")
    ok = None not in (lo, hi, iv30) and hi > lo
    return {
        "value": f((iv30 - lo) / (hi - lo) * 100.0) if ok else None,
        "printed": f(po.get("printed")),
        "iv_30d": f(iv30),
        "low_52w": f(lo),
        "high_52w": f(hi),
        "percentile": f(po.get("percentile")),
        "as_of": po.get("as_of"),
        "source": "projectoption.com, single source",
        "error": None if ok else "the 52-week high and low did not bracket a range",
    }


def iv_block(ledger: dict, errors: dict[str, str],
             po: dict | None = None, po_err: str | None = None) -> dict:
    """The iv block data/playbook.json carries.

    A ticker whose fetch failed still gets its window computed from the ledger,
    which is what the ledger is for, but it carries `error` plus
    `as_of_fetch: null` and it sets the block's `stale` flag, so the page can show
    the reading and label it stale instead of passing yesterday's number off as
    today's.
    """
    out: dict = {
        "as_of_run": TODAY.isoformat(),
        "source": (
            "AlphaQuery option-statistic chart endpoint, keyless, 30-day mean IV. "
            "Free tier returns about 63 trading days per call; data/iv-ledger.json accumulates."
        ),
        "errors": errors or None,
        "reference": {
            "source": "https://projectoption.com/stocks/mstr/implied-volatility",
            "as_of": "2026-09-11",
            "iv_30d": 0.673,
            "iv_52w_low": 0.492,
            "iv_52w_high": 1.206,
            "iv_rank": 25,
            "iv_percentile": 29,
            "note": "single source, un-cross-checked. Only the current level is corroborated (AlphaQuery 68.3% the same day).",
        },
    }
    stale = False
    for t in IV_TICKERS:
        err = errors.get(t)
        w = iv_window(ledger, t)
        if w is None:
            out[t.lower()] = {
                "iv_30d": None,
                "rank": None,
                "error": err or "no ledger entries for this ticker",
                "as_of_fetch": None,
                "stale": True,
            }
            stale = True
            continue
        w["error"] = err
        w["as_of_fetch"] = None if err else TODAY.isoformat()
        w["stale"] = bool(err)
        if err:
            stale = True
            w["note"] = (
                "today's fetch failed, so this reading is the newest the ledger holds. " + str(w.get("note") or "")
            ).strip()
        out[t.lower()] = w
    # the two ranks the page shows side by side: a 3-month one off the ledger,
    # a 52-week one off projectoption until the ledger can carry it itself
    if isinstance(out.get("mstr"), dict):
        out["mstr"]["rank_52w"] = rank_52w_row(out["mstr"], po, po_err)
        out["mstr"].setdefault("rank_3m", {"value": None, "n_days": 0,
                                           "error": "no ledger window"})
    out["stale"] = stale

    m, x = out.get("mstr") or {}, out.get("mstx") or {}
    mv, xv = m.get("iv_30d"), x.get("iv_30d")
    md, xd = m.get("as_of"), x.get("as_of")
    both = bool(mv and xv)
    same_day = bool(both and md and xd and md == xd)
    out["mstx_mstr_iv_ratio"] = {
        "value": f(xv / mv) if same_day else None,
        "as_of": md if same_day else None,
        "error": (
            None if same_day
            else "needs a 30-day IV for both MSTR and MSTX" if not both
            else f"MSTR reads {md} and MSTX reads {xd}, not the same observation date"
        ),
        "note": (
            "MSTX 30-day IV divided by MSTR 30-day IV, both AlphaQuery. "
            "Computed only when the two readings carry the same observation date, null otherwise."
        ),
    }
    return out


def iv_rank_row(iv: dict) -> dict:
    """The trigger-table IV rank row, a view onto iv.mstr."""
    m = iv.get("mstr") or {}
    if m.get("rank") is None:
        return row(
            error=m.get("error") or m.get("note") or "no IV rank available",
            source=IV_SERIES_SOURCE,
            as_of=m.get("as_of"),
            stale=bool(m.get("stale")),
            as_of_fetch=m.get("as_of_fetch"),
            n_days=(m.get("window") or {}).get("n_days", 0),
            iv=m.get("iv_30d"),
            note="Hand-enter the 52-week IV rank from your broker on the page.",
        )
    w = m.get("window") or {}
    return row(
        m["rank"],
        source=IV_SERIES_SOURCE,
        as_of=m.get("as_of"),
        error=m.get("error"),
        stale=bool(m.get("stale")),
        as_of_fetch=m.get("as_of_fetch"),
        n_days=w.get("n_days"),
        iv=m.get("iv_30d"),
        iv_min=w.get("min"),
        iv_max=w.get("max"),
        window_first=w.get("first"),
        window_last=w.get("last"),
        rank_label=m.get("rank_label"),
        is_52w_rank=m.get("is_52w_rank"),
        note=m.get("note"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# self-test
# ─────────────────────────────────────────────────────────────────────────────
def self_test() -> list[str]:
    """Assertions on the pure functions. Raises on the first failure.

    The week cutoff is the one worth a fixture: a Sunday run date is the case the
    old `> TODAY` test got wrong, and no live data reproduces it on demand.
    """
    checks: list[str] = []

    # Sunday 2026-09-13. The week ending that day is still open, so the last
    # completed week ends Sunday 2026-09-06.
    sunday = date(2026, 9, 13)
    assert sunday.weekday() == 6, "fixture date is not a Sunday"
    end = last_completed_week_end(sunday)
    assert end == date(2026, 9, 6), f"Sunday run: expected 2026-09-06, got {end}"
    # Monday, the day after: the week that just closed is complete.
    assert last_completed_week_end(date(2026, 9, 14)) == date(2026, 9, 13)
    # Midweek: the previous Sunday.
    assert last_completed_week_end(date(2026, 9, 16)) == date(2026, 9, 13)
    checks.append("week cutoff: Sunday run excludes the open week")

    # the same fixture through weekly_closes: daily bars Mon 9/7 to Sun 9/13 must
    # not produce a 9/13 weekly bar when the run date is 9/13.
    idx = pd.date_range("2026-08-24", "2026-09-13", freq="D")
    px = pd.Series(range(1, len(idx) + 1), index=idx, dtype=float)
    wk = weekly_closes(px, sunday)
    assert len(wk), "weekly_closes returned nothing for the fixture"
    assert wk.index[-1].date() == date(2026, 9, 6), \
        f"weekly_closes kept an incomplete week, last bar {wk.index[-1].date()}"
    assert date(2026, 9, 13) not in [d.date() for d in wk.index]
    checks.append("weekly_closes: incomplete Sunday week excluded")

    # Wilder's RSI: a monotonically rising series has no losses, so 100, not 50,
    # and the first 14 bars carry no reading at all.
    rising = pd.Series(np.arange(1.0, 41.0), index=pd.date_range("2026-01-01", periods=40, freq="D"))
    r = rsi(rising)
    assert r.iloc[:14].isna().all(), "RSI printed a reading inside the warm-up"
    assert not math.isnan(r.iloc[14]), "RSI has no reading at bar 14"
    assert abs(float(r.iloc[-1]) - 100.0) < 1e-9, f"rising series read RSI {r.iloc[-1]}, expected 100"
    falling = pd.Series(np.arange(40.0, 0.0, -1.0), index=pd.date_range("2026-01-01", periods=40, freq="D"))
    assert abs(float(rsi(falling).iloc[-1]) - 0.0) < 1e-9, "falling series did not read RSI 0"
    checks.append("Wilder RSI: 14-bar warm-up NaN, rising reads 100, falling reads 0")

    # the 9/13 weekly leg: a rising series must read the histogram positive and
    # rising, a falling one must not. 60 bars clears the 30-bar warm-up.
    wks = pd.date_range("2025-08-03", periods=60, freq="W")
    up = pd.Series(100.0 * np.power(1.02, np.arange(60)), index=wks)
    r_up = macd_hist_rising(up)
    assert r_up["flag"] is True, f"rising weekly series read flag False, hist {r_up['hist']}"
    assert r_up["hist"] > 0 and r_up["hist"] > r_up["hist_prev"], "rising series histogram not positive and rising"
    down = pd.Series(100.0 * np.power(0.98, np.arange(60)), index=wks)
    assert macd_hist_rising(down)["flag"] is False, "falling weekly series read flag True"
    checks.append("weekly MACD(8,21,5): rising series reads positive and rising, falling does not")

    # the entry-timing cell: a 26-week sine on weekly bars crosses the histogram
    # above zero on the bar dated 2025-05-11. Cut two bars later the cross is
    # inside the window, cut six bars later it is not.
    cyc = pd.date_range("2024-06-02", periods=90, freq="W")
    sine = pd.Series(100.0 + 12.0 * np.sin(2 * np.pi * np.arange(90) / 26.0), index=cyc)
    near = macd_hist_fresh_cross(sine.iloc[:52])
    assert near["flag"] is True, f"cross two bars back read flag False, {near}"
    assert near["bars_since_cross"] == 2, f"cross two bars back counted {near['bars_since_cross']}"
    assert near["cross_bar"] == "2025-05-11", f"cross bar read {near['cross_bar']}"
    assert len(near["last4"]) == 4 and near["last4"][0]["hist"] < 0 < near["last4"][-1]["hist"], \
        "the four-bar tail does not straddle zero"
    far = macd_hist_fresh_cross(sine.iloc[:56])
    assert far["flag"] is False, f"cross six bars back read flag True, {far}"
    assert far["bars_since_cross"] is None, f"stale cross counted {far['bars_since_cross']} bars"
    assert far["cross_bar"] == "2025-05-11" and far["hist"] > 0, \
        "stale cross lost its date or its positive histogram"
    checks.append("weekly MACD(8,21,5) fresh cross: two bars back reads true, six bars back false")

    # ladder port fixture: the site showed the 9.303rd quantile at BTC 77,200 on
    # 2026-09-12, which is what pins this port to the page's own formula.
    qq = price_to_quantile(77200.0078125, date(2026, 9, 12), ladder_days(date(2026, 9, 12)))
    assert abs(qq - 9.303) < 0.01, f"ladder port read {qq:.3f}, the site read 9.303"
    assert ladder_band_label(qq) == "below 10", f"9.3 labelled {ladder_band_label(qq)}"
    assert ladder_band_label(90.0) == "above 75" and ladder_band_label(65.0) == "60 to 75" and ladder_band_label(10.7) == "10 to 60"
    checks.append("ladder port, model v1: 77,200 on 2026-09-12 reads 9.303q, below 10")
    q2 = price_to_quantile_v2(77200.0078125, date(2026, 9, 12))
    assert abs(q2 - 9.808) < 0.01, f"model v2 port read {q2:.3f}, tools/ladder_model.py reads 9.808"
    assert ladder_band_label(q2) == "below 10"
    checks.append("ladder port, model v2: 77,200 on 2026-09-12 reads 9.808q, below 10")

    # ledger normalization: a Yahoo entry no longer blocks the AlphaQuery
    # observation on the same date.
    book = normalize_book({"2026-09-12": {"iv": 0.7, "source": "yahoo_option_chain"}})
    book.setdefault("2026-09-12", {}).setdefault(IV_SERIES_SOURCE, {"iv": 0.68, "source": IV_SERIES_SOURCE})
    assert len(book["2026-09-12"]) == 2, "per-source ledger dropped one of the two sources"
    checks.append("ledger: two sources coexist on one date")

    # projectoption stat block: read by label, so the unrelated 38 on the page
    # is not mistaken for a rank, and the computed 52-week rank is 25, not 38.
    ps = po_iv_stats(
        '<p>an unrelated 38 percent sits above the cards</p>'
        '<div class="iv-metric-card"><div class="iv-metric-label">Current IV (30-Day)</div>'
        ' <div class="iv-metric-value">67.3%</div></div>'
        '<div class="iv-metric-card"><div class="iv-metric-label">IV Rank</div>'
        ' <div class="iv-metric-value iv-rank">25%</div></div>'
        '<div class="iv-metric-card"><div class="iv-metric-label">IV Percentile</div>'
        ' <div class="iv-metric-value">28%</div></div>'
        '<div class="iv-metric-card"><div class="iv-metric-label">52-Week Low IV</div>'
        ' <div class="iv-metric-value iv-low">49.2%</div></div>'
        '<div class="iv-metric-card"><div class="iv-metric-label">52-Week High IV</div>'
        ' <div class="iv-metric-value iv-high">120.6%</div></div>'
        '<p class="stock-iv-data-date">Data as of September 11th, 2026</p>'
    )
    assert ps["as_of"] == "2026-09-11", f"projectoption date read {ps['as_of']}"
    assert abs(ps["iv_30d"] - 0.673) < 1e-9 and abs(ps["low_52w"] - 0.492) < 1e-9
    assert abs(ps["high_52w"] - 1.206) < 1e-9 and ps["printed"] == 25 and ps["percentile"] == 28
    r52 = rank_52w_row(None, ps, None)
    assert round(r52["value"]) == 25, f"52-week rank computed {r52['value']}"
    checks.append("projectoption stat block: IV 67.3 in 49.2 to 120.6 reads rank 25, not 38")

    return checks


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────
def main() -> int:
    for line in self_test():
        print(f"  self-test ok · {line}")

    inputs: dict[str, dict] = {}

    # ---- BTC ----------------------------------------------------------------
    btc = None
    try:
        btc = download(BTC)
    except Exception as exc:
        # btc_price is written as null plus the error rather than omitted: a
        # missing key reads to the page as "never asked for", and the page then
        # has nothing to say the BTC level it is showing did not come from here.
        for k in ("btc_above_200d", "btc_above_200w", "btc_price",
                  "btc_weekly_macd_8_21_5_hist_rising",
                  "btc_weekly_macd_8_21_5_fresh_cross", "ladder_quantile"):
            inputs[k] = failed(k, exc)

    if btc is not None:
        close = btc["Close"].astype(float)
        last_px = float(close.iloc[-1])
        last_dt = dstr(close.index[-1])
        try:
            sma200 = float(close.rolling(200).mean().iloc[-1])
            inputs["btc_above_200d"] = row(
                bool(last_px > sma200),
                passes=bool(last_px > sma200),
                source="yahoo_daily",
                as_of=last_dt,
                btc_close=f(last_px),
                sma_200d=f(sma200),
                gap_pct=f((last_px / sma200 - 1.0) * 100.0),
            )
        except Exception as exc:
            inputs["btc_above_200d"] = failed("btc_above_200d", exc)

        try:
            wk = weekly_closes(close)
            if len(wk) < 200:
                raise RuntimeError(f"only {len(wk)} completed weekly closes, 200 needed")
            sma200w = float(wk.rolling(200).mean().iloc[-1])
            inputs["btc_above_200w"] = row(
                bool(last_px > sma200w),
                passes=bool(last_px > sma200w),
                source="yahoo_weekly",
                as_of=f"{last_dt} price vs week ending {dstr(wk.index[-1])}",
                btc_close=f(last_px),
                sma_200w=f(sma200w),
                gap_pct=f((last_px / sma200w - 1.0) * 100.0),
                weeks=int(len(wk)),
                note="SMA over completed calendar weeks only",
            )
        except Exception as exc:
            inputs["btc_above_200w"] = failed("btc_above_200w", exc)

        # the 9/13 research's weekly leg, on completed Monday-to-Sunday UTC bars
        try:
            wk = weekly_closes(close)
            info = macd_hist_rising(wk)
            inputs["btc_weekly_macd_8_21_5_hist_rising"] = row(
                info["flag"],
                passes=info["flag"],
                source="yahoo_weekly",
                as_of=f"week ending {info['bar']}",
                histogram=f(info["hist"]),
                histogram_prev=f(info["hist_prev"]),
                bar_date=info["bar"],
                prev_bar_date=info["prev_bar"],
                histogram_last16=info["last16"],
                weeks=info["bars"],
                note=(
                    "MACD 8,21,5 on completed Monday to Sunday UTC weekly closes. EMA is seeded on "
                    "the first value. Passes when the last complete bar's histogram is above zero "
                    "and above the prior complete bar's."
                ),
            )
        except Exception as exc:
            inputs["btc_weekly_macd_8_21_5_hist_rising"] = failed(
                "btc_weekly_macd_8_21_5_hist_rising", exc)

        # the entry-timing cell: the same weekly histogram, asked whether it
        # crossed above zero inside the last three complete bars
        try:
            wk = weekly_closes(close)
            info = macd_hist_fresh_cross(wk)
            inputs["btc_weekly_macd_8_21_5_fresh_cross"] = row(
                info["flag"],
                passes=info["flag"],
                source="yahoo_weekly",
                as_of=f"week ending {info['bar']}",
                histogram=f(info["hist"]),
                bar_date=info["bar"],
                cross_bar_date=info["cross_bar"],
                bars_since_cross=info["bars_since_cross"],
                histogram_last4=info["last4"],
                weeks=info["bars"],
                note=(
                    "MACD 8,21,5 uses the same completed Monday to Sunday UTC weekly closes as the histogram rising row. "
                    "EMA is seeded on the first value. The last complete histogram bar must be above zero. "
                    "At least one of the three preceding bars must be at or below zero. "
                    "This marks a bullish cross inside the last three weekly bars. "
                    "cross_bar_date is the first bar after the most recent bar at or below zero. Entry timing, not a hold condition."
                ),
            )
        except Exception as exc:
            inputs["btc_weekly_macd_8_21_5_fresh_cross"] = failed(
                "btc_weekly_macd_8_21_5_fresh_cross", exc)

        # the 9/13 research's ladder leg, from the page's own formula
        try:
            days = ladder_days(date.fromisoformat(last_dt))
            quant_v1 = price_to_quantile_days(last_px, days)
            quant = price_to_quantile_v2(last_px, date.fromisoformat(last_dt))
            days2 = (datetime.fromisoformat(last_dt).replace(tzinfo=timezone.utc) - LADDER2_CLOCK).total_seconds() / 86400.0
            inputs["ladder_quantile"] = row(
                f(quant),
                passes=bool(quant_v1 <= 85.0),
                source="site formula, model v2",
                as_of=last_dt,
                band=ladder_band_label(quant),
                value_model_v1=f(quant_v1),
                btc_close=f(last_px),
                fair_value=f(10 ** (LADDER2_A * math.log10(days2) + LADDER2_B)),
                days_since_clock=f(days2),
                note=(
                    "the page's own priceToQuantile under model v2, ported into this script. The centre line is "
                    "10 ** (5.645315 * log10(days since 2009-01-03) - 16.430264) and the lines are offsets "
                    "c * exp(-age / T) in log10(price / centre). Passes is judged on model v1's quantile, not "
                    "above its 85th band, because the 9/13 research measured that line. It is not the ladder's 75 sell line."
                ),
            )
        except Exception as exc:
            inputs["ladder_quantile"] = failed("ladder_quantile", exc)

        inputs["btc_price"] = row(
            f(last_px), source="yahoo_daily", as_of=last_dt,
            note="Yahoo daily close, not a live quote. The page's own live feed is separate.",
        )

    # ---- MSTR ---------------------------------------------------------------
    mstr = None
    try:
        mstr = download(MSTR)
    except Exception as exc:
        for k in ("mstr_weekly_macd", "mstr_hidden_bull_div", "bollinger_tight",
                  "realized_vol_rank", "mstr_price"):
            inputs[k] = failed(k, exc)

    spot = None
    if mstr is not None:
        mc = mstr["Close"].astype(float)
        spot = float(mc.iloc[-1])
        mstr_dt = dstr(mc.index[-1])
        inputs["mstr_price"] = row(
            f(spot), source="yahoo_daily", as_of=mstr_dt,
            note="Yahoo daily close, delayed. Not a live quote.",
        )

        try:
            wk = weekly_closes(mc)
            if len(wk) < 40:
                raise RuntimeError(f"only {len(wk)} completed weekly closes")
            ema12 = wk.ewm(span=12, adjust=False).mean()
            ema26 = wk.ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            sig = macd.ewm(span=9, adjust=False).mean()
            m, s = float(macd.iloc[-1]), float(sig.iloc[-1])
            inputs["mstr_weekly_macd"] = row(
                bool(m > s),
                passes=bool(m > s),
                source="yahoo_weekly",
                as_of=f"week ending {dstr(wk.index[-1])}",
                macd=f(m),
                signal=f(s),
                histogram=f(m - s),
                note="MACD(12,26,9) on completed weekly closes",
            )
        except Exception as exc:
            inputs["mstr_weekly_macd"] = failed("mstr_weekly_macd", exc)

        try:
            div = hidden_bull_div(mstr)
            inputs["mstr_hidden_bull_div"] = row(
                bool(div["flag"]),
                passes=bool(div["flag"]),
                source="yahoo_daily",
                as_of=mstr_dt,
                matches=div["matches"],
                n_matches=div["n_matches"],
                note=(
                    "higher swing low with lower RSI(14) at the two lows, swing = lowest low "
                    "with 5 bars each side, 20-bar pair window, confirmed inside the last 10 bars"
                ),
            )
        except Exception as exc:
            inputs["mstr_hidden_bull_div"] = failed("mstr_hidden_bull_div", exc)

        try:
            mid = mc.rolling(20).mean()
            sd = mc.rolling(20).std(ddof=0)
            width = (4.0 * sd) / mid
            pctile, nobs = pct_rank(width)
            if pctile is None:
                raise RuntimeError("not enough Bollinger observations")
            tight = pctile < 20.0
            inputs["bollinger_tight"] = row(
                bool(tight),
                passes=bool(tight),
                source="yahoo_daily",
                as_of=mstr_dt,
                width_pct=f(pctile),
                width=f(float(width.iloc[-1])),
                upper=f(float(mid.iloc[-1] + 2 * sd.iloc[-1])),
                lower=f(float(mid.iloc[-1] - 2 * sd.iloc[-1])),
                n_obs=int(nobs),
                note="20-day, 2 sigma, width = (upper - lower) / mid, percentile over trailing 252 days, tight = below 20",
            )
        except Exception as exc:
            inputs["bollinger_tight"] = failed("bollinger_tight", exc)

        try:
            ret = np.log(mc).diff()
            rv = ret.rolling(20).std(ddof=1) * math.sqrt(252.0)
            pctile, nobs = pct_rank(rv)
            if pctile is None:
                raise RuntimeError("not enough realized-vol observations")
            inputs["realized_vol_rank"] = row(
                f(pctile),
                source="yahoo_daily",
                as_of=mstr_dt,
                rv_20d_annualized=f(float(rv.iloc[-1])),
                n_obs=int(nobs),
                note="20-day realized vol, annualized at 252, percentile over trailing 252 days. A proxy for IV rank, not IV rank.",
            )
        except Exception as exc:
            inputs["realized_vol_rank"] = failed("realized_vol_rank", exc)

    # ---- MSTX close (the mapping box's "MSTX now" default) ------------------
    try:
        mx = download(MSTX)["Close"].astype(float)
        inputs["mstx_price"] = row(
            f(float(mx.iloc[-1])), source="yahoo_daily", as_of=dstr(mx.index[-1]),
            note="Yahoo daily close, delayed. Not a live quote.",
        )
    except Exception as exc:
        inputs["mstx_price"] = failed("mstx_price", exc)

    # ---- implied vol + ledger ----------------------------------------------
    iv_info, iv_error = None, None
    if spot is not None:
        try:
            iv_info = atm_iv_30d(spot)
        except Exception as exc:
            iv_error = f"{type(exc).__name__}: {exc}"
            ERRORS.append(f"mstr_atm_iv_30d -> {iv_error}")
    else:
        iv_error = "MSTR spot unavailable, option chain not queried"

    inputs["mstr_atm_iv_30d"] = (
        row(
            f(iv_info["iv"]),
            source="yahoo_option_chain",
            as_of=TODAY.isoformat(),
            expiry=iv_info["expiry"],
            dte=iv_info["dte"],
            strike=f(iv_info["call_strike"]),
            call_iv=f(iv_info["call_iv"]),
            put_iv=f(iv_info["put_iv"]),
            spot=f(iv_info["spot"]),
            note="mid of the ATM call and put impliedVolatility Yahoo reports, nearest expiry to 30 days",
        )
        if iv_info
        else row(error=iv_error, source="yahoo_option_chain")
    )

    # AlphaQuery 30-day IV series for MSTR / MSTX / IBIT, merged into the ledger
    series: dict[str, list[tuple[str, float]]] = {}
    iv_errors: dict[str, str] = {}
    for t in IV_TICKERS:
        try:
            series[t] = alphaquery_iv_series(t)
        except Exception as exc:
            iv_errors[t] = f"{type(exc).__name__}: {exc}"
            ERRORS.append(f"alphaquery_iv[{t}] -> {iv_errors[t]}")

    ledger = merge_ledger(series, iv_info)

    # the 52-week leg of the IV read, until the ledger holds a full year itself
    po, po_err = None, None
    try:
        po = projectoption_iv()
    except Exception as exc:
        po_err = f"{type(exc).__name__}: {exc}"
        ERRORS.append(f"projectoption_iv -> {po_err}")

    iv = iv_block(ledger, iv_errors, po, po_err)
    inputs["iv_rank"] = iv_rank_row(iv)

    # ---- events -------------------------------------------------------------
    events_next3: list[dict] = []
    events_upcoming: list[dict] = []
    try:
        raw = load_json(TOOLS / "events.json", [])
        if isinstance(raw, dict):
            raw = raw.get("events", [])
        rows = []
        for e in raw or []:
            if not isinstance(e, dict) or not e.get("date"):
                continue
            try:
                d = date.fromisoformat(str(e["date"]))
            except ValueError:
                ERRORS.append(f"events.json: unparseable date {e.get('date')!r}")
                continue
            dt = (d - TODAY).days
            if dt < 0:
                continue
            rows.append(
                {
                    "date": d.isoformat(),
                    "type": e.get("type", "UNKNOWN"),
                    "label": e.get("label", e.get("type", "event")),
                    "verified": bool(e.get("verified", False)),
                    "source": e.get("source"),
                    "note": e.get("note"),
                    "days_to": dt,
                }
            )
        rows.sort(key=lambda r: r["date"])
        events_next3 = rows[:3]
        events_upcoming = rows[:6]   # the page lists these so unverified rows stay visible
        if events_next3:
            nxt = events_next3[0]
            inputs["days_to_next_event"] = row(
                nxt["days_to"],
                source="tools/events.json",
                as_of=TODAY.isoformat(),
                event=nxt,
                all_verified=all(r["verified"] for r in events_next3),
                note="hand-maintained calendar. verified=false rows are placeholders, confirm before sizing on them.",
            )
        else:
            inputs["days_to_next_event"] = row(
                error="no upcoming events in tools/events.json",
                source="tools/events.json",
            )
    except Exception as exc:
        inputs["days_to_next_event"] = failed("days_to_next_event", exc)

    # ---- rules --------------------------------------------------------------
    rules = load_json(TOOLS / "playbook_rules.json", {})
    if not isinstance(rules, dict):
        rules = {}
        ERRORS.append("playbook_rules.json was not a JSON object")

    out = {
        "generated_at": NOW_ISO,
        "as_of_run_date": TODAY.isoformat(),
        "inputs": inputs,
        "iv": iv,
        "events_next3": events_next3,
        "events_upcoming": events_upcoming,
        "rules": {
            "version": rules.get("version"),
            "as_of": rules.get("as_of"),
            "components": rules.get("components", []),
            "paper_trigger": rules.get("paper_trigger"),
            "paper_trigger_previous": rules.get("paper_trigger_previous"),
            "entry_timing": rules.get("entry_timing"),
            "leaps_unit": rules.get("leaps_unit"),
        },
        "sources": {
            "prices": "Yahoo Finance daily bars via yfinance. Delayed and unofficial.",
            "implied_vol": "AlphaQuery 30-day mean IV (keyless chart endpoint) for the MSTR / MSTX / IBIT series and the IV rank; Yahoo's option-chain impliedVolatility field for the single mstr_atm_iv_30d row. Both delayed, neither a computed mid-market vol.",
            "iv_rank": "Computed over data/iv-ledger.json, the AlphaQuery entries only, trailing 252 entries at most. Labelled with its window length and called a 52-week window only at a full 252 entries. A ticker whose fetch failed keeps its ledger reading, carries an error string with as_of_fetch null, and sets iv.stale.",
            "events": "tools/events.json, hand maintained. Every row carries a verified flag and a source URL.",
            "rule_flags": "tools/playbook_rules.json, hand maintained: backtest status plus the adopted flag plus the current and previous paper triggers.",
            "ladder_quantile": "The page's own priceToQuantile ported into this script, scored at the Yahoo daily close and its own date. Not a second model, the same formula the ladder tab draws.",
            "rule": "No field is ever a fabricated number. A source that fails is written as null with an error string.",
        },
        "errors": ERRORS,
    }
    write_json(DATA / "playbook.json", out)

    def show(key, fmt="{}"):
        r = inputs.get(key) or {}
        v = r.get("value")
        return "null" if v is None else fmt.format(v)

    nxt = events_next3[0] if events_next3 else None
    bb_pct = (inputs.get("bollinger_tight") or {}).get("width_pct")
    ivm = iv.get("mstr") or {}
    ivx = iv.get("mstx") or {}
    ratio = (iv.get("mstx_mstr_iv_ratio") or {}).get("value")
    print(
        "playbook_refresh "
        f"btc={show('btc_price', '${:,.0f}')} >200d={show('btc_above_200d')} >200w={show('btc_above_200w')} "
        f"wkhist8215rising={show('btc_weekly_macd_8_21_5_hist_rising')} "
        f"wkhist8215freshcross={show('btc_weekly_macd_8_21_5_fresh_cross')}"
        f"(barssince={(inputs.get('btc_weekly_macd_8_21_5_fresh_cross') or {}).get('bars_since_cross')}) "
        f"ladderq={show('ladder_quantile', '{:.2f}')}"
        f"({(inputs.get('ladder_quantile') or {}).get('band', '-')}) | "
        f"mstr={show('mstr_price', '${:,.2f}')} mstx={show('mstx_price', '${:,.2f}')} "
        f"macd>sig={show('mstr_weekly_macd')} "
        f"hiddendiv={show('mstr_hidden_bull_div')} bbtight={show('bollinger_tight')}(pct={bb_pct}) "
        f"rvrank={show('realized_vol_rank', '{:.0f}')} | "
        f"aqIV mstr={ivm.get('iv_30d')} mstx={ivx.get('iv_30d')} ratio={ratio} "
        f"ivrank={ivm.get('rank')} ({ivm.get('rank_label')}) stale={iv.get('stale')} | "
        f"next={(nxt or {}).get('type', 'none')} in {(nxt or {}).get('days_to', '-')}d | "
        f"errors={len(ERRORS)}"
    )
    for e in ERRORS:
        print(f"  ! {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

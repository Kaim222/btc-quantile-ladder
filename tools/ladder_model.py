"""ladder_model.py: the site's quantile model in Python, read from data/ladder-model.json (model v2).

The same arithmetic as index.html: a trend line, six offset lines, and a quantile read by straight interpolation between the
lines. Set LADDER_MODEL=v1 in the environment to get the original model (genesis clock, slope 5.82) for comparisons.
"""
import json, math, os
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = json.load(open(os.path.join(ROOT, "data", "ladder-model.json"), encoding="utf-8"))
CLOCK = pd.Timestamp(MODEL["clock_start"])
USE_V1 = os.environ.get("LADDER_MODEL", "").lower() == "v1"


def _ts(day):
    t = pd.Timestamp(day); return t.tz_convert("UTC").tz_localize(None) if t.tzinfo is not None else t


def trend(day):
    days = (_ts(day) - CLOCK).total_seconds() / 86400.0
    return 10 ** (MODEL["slope"] * math.log10(days) + MODEL["intercept"]) if days > 0 else 0.0


def offsets(day):
    age = (_ts(day) - CLOCK).total_seconds() / 86400.0 / 365.25; out = []
    for b in MODEL["bands"]:
        p = b["p"]
        if b["kind"] == "const": o = p[0]
        elif b["kind"] == "exp": o = p[0] * math.exp(-age / p[1])
        else: raise ValueError("unknown band kind %s: the site, the monitor and the Playbook port implement const and exp only" % b["kind"])
        out.append((b["q"], o))
    return out


def _quantile_v2(price, day):
    fv = trend(day)
    if not fv or price <= 0: return 50.0
    res = math.log10(price / fv); off = offsets(day)
    for (qh, oh), (ql, ol) in zip(off, off[1:]):
        if ol <= res <= oh: return ql + (res - ol) / (oh - ol) * (qh - ql)
    if res > off[0][1]: return min(99.99, off[0][0] + (off[0][0] - off[1][0]) / (off[0][1] - off[1][1]) * (res - off[0][1]))
    return max(0.01, off[-1][0] + (off[-2][0] - off[-1][0]) / (off[-2][1] - off[-1][1]) * (res - off[-1][1]))


def _price_at_v2(q, day):
    off = offsets(day)
    for (qh, oh), (ql, ol) in zip(off, off[1:]):
        if ql <= q <= qh: return trend(day) * 10 ** (ol + (q - ql) / (qh - ql) * (oh - ol))
    (q0, o0), (q1, o1) = (off[0], off[1]) if q > off[0][0] else (off[-1], off[-2])        # past either end, the outer pair's slope, as the site does
    return trend(day) * 10 ** (o0 + (o0 - o1) / (q0 - q1) * (q - q0))


def quantile(price, day):
    if USE_V1:
        from ladder_bands_study import quantile as q1
        return q1(price, pd.Timestamp(day))
    return _quantile_v2(price, day)


def price_at(q, day):
    if USE_V1:
        from ladder_bands_study import quantile as q1
        lo, hi = 1e2, 1e8
        for _ in range(80):
            mid = math.sqrt(lo * hi)
            if q1(mid, pd.Timestamp(day)) < q: lo = mid
            else: hi = mid
        return mid
    return _price_at_v2(q, day)


if __name__ == "__main__":
    import sys
    day = sys.argv[1] if len(sys.argv) > 1 else str(pd.Timestamp.utcnow().date())
    print("model", "v1" if USE_V1 else "v2", "on", day, "| trend", round(trend(day)) if not USE_V1 else "-")
    for q in (0.1, 10, 15, 50, 60, 75, 85, 95, 99.9): print("  %5s line  $%s" % (q, format(int(round(price_at(q, day), -2)), ",")))

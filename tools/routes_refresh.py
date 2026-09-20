"""routes_refresh.py: LEAPS units at the end of each route, rebuilt from the live position and the print-based unit price.

Writes data/routes.json, which the Playbook's route table reads. Everything here is MODEL, stated on the page:
  - Position: the Phase 1 spreads in data/paper-ledger.json (each spread carries machine-readable legs). No cash.
  - Unit: long Dec 15 2028 $33 call less short Jan 21 2028 $60 call, Black-Scholes at the vols fitted to real prints
    (data/leaps-cost.json), priced for the day the units are bought. Whole units, at the model mid.
  - MSTX paths: MSTX's own history. For a horizon of h sessions, every overlapping h-session log return since the fund
    listed, with the average taken out (no drift). "Market view" is that. "Your view" is the same prices one dollar higher.
  - Route A: hold Phase 1 to the settlement close (shorts at intrinsic, longs at 100% vol), then buy units the next session
    at that close (the move over the weekend is not modelled).
  - Route B: as A, but the proceeds go into Phase 2 first: 70% into a Jan 15 2027 long one strike above the close against
    a Dec 18 2026 short at about 1.67x the close (the plan's strike map), 30% cash, all at 120% vol; on Dec 18 the short
    settles at intrinsic, the long keeps 28 days, and the total buys units the next session at that close. The short
    strike is never set at or below the long strike.
  - Route C: close today at the model mark (135% vol, the vol that matched his broker's quote on 9/18) less five cents a
    share of slippage on every calendar, and buy units at today's price. The count is fixed once bought.
Runs only while Phase 1 is live and its settlement date is ahead; otherwise it leaves the file alone.
"""
import datetime as dt, json, math, os, sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER, LEAPS, OUT = (os.path.join(ROOT, "data", f) for f in ("paper-ledger.json", "leaps-cost.json", "routes.json"))
R, VOL_SETTLE, VOL_NOW, VOL_P2, SLIP, P2_SHARE, N_DRAWS = 0.04, 1.00, 1.35, 1.20, 0.05, 0.70, 40000
P2_LONG, P2_SHORT = dt.date(2027, 1, 15), dt.date(2026, 12, 18)
HOLIDAYS = ["2026-11-26", "2026-12-25", "2027-01-01"]


def next_session(day):
    d = day + dt.timedelta(days=1)
    while d.weekday() >= 5 or d.isoformat() in HOLIDAYS: d += dt.timedelta(days=1)
    return d


def ncdf(x):
    return 0.5 * (1.0 + np.vectorize(math.erf)(np.asarray(x, dtype=float) / math.sqrt(2.0)))


def call(S, K, T, v):
    S = np.asarray(S, dtype=float)
    if T <= 0:
        return np.maximum(S - K, 0.0)
    K = np.asarray(K, dtype=float)
    d1 = (np.log(S / K) + (R + 0.5 * v * v) * T) / (v * math.sqrt(T))
    return S * ncdf(d1) - K * math.exp(-R * T) * ncdf(d1 - v * math.sqrt(T))


def yrs(a, b):
    return (b - a).days / 365.0


def main():
    led = json.load(open(LEDGER, encoding="utf-8"))
    lc = json.load(open(LEAPS, encoding="utf-8"))
    ph = led["plan"]["phases"][0]
    settle = dt.date.fromisoformat(ph["dates"].split(" to ")[1])
    m = lc["model"]
    today = dt.date.fromisoformat(m["asof"])
    S0 = float(m["mstx_last"])
    spreads = [s for s in ph.get("spreads", []) if isinstance(s.get("long"), dict) and isinstance(s.get("short"), dict)]
    from zoneinfo import ZoneInfo
    clock = dt.datetime.now(ZoneInfo("America/New_York")).date()      # the calendar, not only the data file, decides whether Phase 1 is over
    if not str(ph.get("status", "")).upper().startswith("LIVE") or today >= settle or clock > settle or (clock - today).days > 6 or not spreads:
        print("Phase 1 is not live with a settlement date ahead, or its legs are not machine-readable; routes left alone")
        return 0
    Lg, Sh = m["long"], m["short"]

    def unit(S, day):
        return call(S, Lg["k"], yrs(day, dt.date.fromisoformat(Lg["exp"])), Lg["iv"]) - call(S, Sh["k"], yrs(day, dt.date.fromisoformat(Sh["exp"])), Sh["iv"])

    def units(dollars, S, day):
        return np.floor(np.maximum(dollars, 0.0) / (unit(S, day) * 100.0))

    def phase1(S, day, vol):
        total = np.zeros_like(np.asarray(S, dtype=float))
        for s in spreads:
            n, lo, sh = float(s["contracts"]), s["long"], s["short"]
            total = total + 100.0 * n * (call(S, lo["k"], yrs(day, dt.date.fromisoformat(lo["exp"])), vol)
                                          - call(S, sh["k"], yrs(day, dt.date.fromisoformat(sh["exp"])), vol))
        return total

    # MSTX's own history, overlapping windows, drift removed
    import yfinance as yf
    px = yf.Ticker("MSTX").history(period="max")["Close"].dropna()
    if len(px) < 300:
        print("MSTX history too short (%d rows); routes left alone" % len(px)); return 1
    lp = np.log(px.values)
    h1 = int(np.busday_count(today, settle, holidays=HOLIDAYS))
    h2 = int(np.busday_count(settle, P2_SHORT, holidays=HOLIDAYS))

    def draws(h, rng):
        lr = lp[h:] - lp[:-h]
        return rng.choice(lr - lr.mean(), size=N_DRAWS, replace=True)

    rng = np.random.default_rng(20260919)
    r1, r2 = draws(h1, rng), draws(h2, rng)
    buy_a, buy_b = next_session(settle), next_session(P2_SHORT)   # units are bought the next session, at the settlement close
    n_cal = sum(float(s["contracts"]) for s in spreads)
    now_val = float(phase1(np.array([S0]), today, VOL_NOW)[0])
    c_units = float(units(np.array([now_val - SLIP * 100.0 * n_cal]), np.array([S0]), today)[0])
    out = {}
    for view, bump in (("market", 0.0), ("thesis", 1.0)):
        S1 = S0 * np.exp(r1) + bump
        V1 = phase1(S1, settle, VOL_SETTLE)
        ua = units(V1, S1, buy_a)
        out["a_" + view], out["a_beats_" + view] = float(ua.mean()), float((ua > c_units).mean())
        # Phase 2 off the strike map
        KL = np.floor(S1 + 0.5) + 1.0
        KS = np.maximum(np.round(1.67 * S1), KL + 1.0)
        debit = call(S1, KL, yrs(settle, P2_LONG), VOL_P2) - call(S1, KS, yrs(settle, P2_SHORT), VOL_P2)
        n2 = np.floor(P2_SHARE * V1 / (np.maximum(debit, 0.05) * 100.0))
        cash = V1 - n2 * debit * 100.0
        S2 = (S1 - bump) * np.exp(r2) + bump
        V2 = cash + n2 * 100.0 * (call(S2, KL, yrs(P2_SHORT, P2_LONG), VOL_P2) - np.maximum(S2 - KS, 0.0))
        ub = units(V2, S2, buy_b)
        out["b_" + view], out["b_beats_" + view] = float(ub.mean()), float((ub > c_units).mean())

    md = lambda d: "%d/%d" % (d.month, d.day)
    res = {"as_of": m["asof"], "mstx": round(S0, 2), "unit_now": round(float(unit(np.array([S0]), today)[0]), 2), "position_now": int(round(now_val)),
           "sessions_to_settle": h1, "sessions_phase2": h2, "history_rows": int(len(px)),
           "routes": [
               {"route": "Hold to %s · LEAPS %s" % (md(settle), md(buy_a)), "units_thesis": int(round(out["a_thesis"])), "units_market": int(round(out["a_market"]))},
               {"route": "Hold to %s · Jan/Dec diagonal · LEAPS %s" % (md(settle), md(buy_b)), "units_thesis": int(round(out["b_thesis"])), "units_market": int(round(out["b_market"]))},
               {"route": "Close now · buy LEAPS", "units_thesis": int(c_units), "units_market": int(c_units)}],
           "hold_beats_close_pct": {"market": int(round(100 * out["a_beats_market"])), "thesis": int(round(100 * out["a_beats_thesis"]))},
           "note": ("Holding to %s wins more units in %d%% of market paths. On your view it wins in %d%%. "
                    "Model averages count whole units at the model mid. Units are bought the session after each settlement at the settlement close. A real fill buys fewer. Priced at the %s close. MSTX $%.2f and unit $%.2f. No cash is counted. "
                    "Market view is MSTX's own history. It uses every %d session and %d session move since listing. Drift is removed. Your view is the same prices one dollar higher. "
                    "Phase 1 is marked at 100%% vol at the %s close. Closing now uses 135%% vol, with the position about $%s. Phase 2 uses 120%% vol off the plan's strikes with 30%% held as cash. "
                    "Averages hide the spread. Phase 1 pays most between $16 and $18. It pays little outside $15 to $19. Closing deducts five cents across %d calendars and fixes the unit count.")
                   % (md(settle), round(100 * out["a_beats_market"]), round(100 * out["a_beats_thesis"]), md(today), S0, float(unit(np.array([S0]), today)[0]), h1, h2, md(settle), format(int(round(now_val, -2)), ","), n_cal)}
    json.dump(res, open(OUT, "w", encoding="utf-8", newline="\n"), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in res.items() if k != "note"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

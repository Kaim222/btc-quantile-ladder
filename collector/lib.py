"""Shared signal, composite and scoring logic for the BTC Signals ledger."""
from __future__ import annotations

import json, math, statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONFIG = ROOT / "config"
HOURS = {"h24": 24, "d7": 168, "d30": 720}
DEADBANDS = {"h24": .0075, "d7": .02, "d30": .05}
CAPS = {"h24": .15, "d7": .25, "d30": .30}
PROBABILITY_CAPS = {h: .5 + .5*c for h,c in CAPS.items()}

def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError): return default

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f: json.dump(value, f, indent=2, separators=(",", ": "), allow_nan=False)
    tmp.replace(path)

def write_ledger_recent(ledger):
    """Publish a small UI projection; the append-only source ledger stays complete."""
    rows=[]
    recent=ledger[-250:]
    for i,r in enumerate(recent):
        outcomes={}
        for h,o in r.get("outcomes",{}).items():
            outcomes[h]=None if o is None else {k:o.get(k) for k in ("ret","realized_class","call","hit","abstained")}
        item={"ts":r["ts"],"mode":r.get("mode"),"btc":{"price":r.get("btc",{}).get("price")},
              "composite":r.get("composite",{}),"outcomes":outcomes}
        if i>=len(recent)-2:item["signals"]=r.get("signals",{})
        rows.append(item)
    write_json(DATA/"ledger_recent.json",rows)

def iso(dt): return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
def parse_ts(s): return datetime.fromisoformat(s.replace("Z", "+00:00"))
def clamp(x, lo=-2, hi=2): return max(lo, min(hi, x))
def pct(a, b): return a / b - 1 if a is not None and b else None
def mean(xs):
    xs=[x for x in xs if x is not None]
    return sum(xs)/len(xs) if xs else None
def ret(prices, n): return pct(prices[-1], prices[-1-n]) if len(prices)>n else None
def sma(xs,n): return mean(xs[-n:]) if len(xs)>=n else None

def armed(levels, expected_move, horizon="h24"):
    """Return breakout proximity details for the only armable horizon."""
    if horizon != "h24" or not isinstance(levels, dict): return None
    spot, high, low = levels.get("spot"), levels.get("high_20d"), levels.get("low_20d")
    if not spot or high is None or low is None or expected_move is None: return None
    up=(high-spot)/spot*100; down=(spot-low)/spot*100
    direction="up" if up <= down else "down"; distance=min(up,down)
    if distance > max(.5*expected_move,.5): return None
    return {"armed":True,"direction":direction,"distance_pct":round(distance,2),"level":high if direction=="up" else low}

def verdict(horizon, latest):
    """Canonical Signals v2 verdict engine, also used for snapshot alerts."""
    if not latest: return {"state":"NO DATA","reason":"snapshot unavailable — no verdict"}
    comp=latest.get("composite",{}).get(horizon,{}) or {}; score=comp.get("score")
    regime=latest.get("regime",{}) or {}; event=regime.get("next_event") or {}
    if comp.get("abstain") is True or regime.get("event_window"):
        suffix=f" — {event.get('name')} {event.get('date')}" if event else ""
        return {"state":"STAND ASIDE","reason":"EVENT WINDOW"+suffix,"score":score}
    if regime.get("hy_veto"):
        return {"state":"STAND ASIDE","reason":"HY VETO — credit stress override","score":score}
    if score is None: return {"state":"NO DATA","reason":"snapshot unavailable — no verdict"}
    if abs(score)>=20: state="LONG" if score>0 else "SHORT"
    elif abs(score)>=10: state="LEAN LONG" if score>0 else "LEAN SHORT"
    else:
        arm=armed(latest.get("levels"),latest.get("expected_move",{}).get("h24"),horizon)
        if arm: return {"state":"WATCH TRIGGER","score":score,**arm}
        state="NO TRADE"
    return {"state":state,"score":score}

def corr(a,b):
    pairs=[(x,y) for x,y in zip(a,b) if x is not None and y is not None]
    if len(pairs)<20:return None
    aa,bb=zip(*pairs); ma,mb=mean(aa),mean(bb)
    den=math.sqrt(sum((x-ma)**2 for x in aa)*sum((y-mb)**2 for y in bb))
    return sum((x-ma)*(y-mb) for x,y in pairs)/den if den else 0

def score_sign(v, cuts):
    for test, score in cuts:
        if test(v): return score
    return 0

def powerlaw(date, price):
    genesis=datetime(2009,1,3,tzinfo=timezone.utc)
    days=max(1,(date-genesis).total_seconds()/86400)
    center=10**(5.82*math.log10(days)-17.029); floor=center*10**(-.3403)
    ratio=price/center; f=price/floor
    tr=2 if ratio<.5 else 1 if ratio<.7 else 0 if ratio<1.3 else -1 if ratio<2 else -2
    fs=0 if f<1 else 2 if f<1.15 else 1 if f<1.5 else 0
    return .6*tr+.4*fs, center, floor, f<1

def calculate_signals(ctx, weights, manual, now):
    """Rules from the brief. Missing inputs always produce an abstaining None score."""
    p=ctx.get("prices",[]); dates=ctx.get("dates",[]); out={}
    def add(k,s,reading=None,status=None):
        rule=weights["rules"][k]; ws=rule["weights"]
        out[k]={"raw":ctx.get(k),"score":None if s is None else clamp(s),"reading":reading or "unavailable",
                "pillar":rule["pillar"],"weight_24h":ws["h24"],"weight_7d":ws["d7"],"weight_30d":ws["d30"],
                "status":status or rule.get("status","LIVE")}
    funding=ctx.get("funding_ann")
    add("funding_extreme",None if funding is None else score_sign(funding,[(lambda x:x<-.10,2),(lambda x:x<-.03,1),(lambda x:x<=.15,0),(lambda x:x<=.30,-1),(lambda x:True,-2)]), None if funding is None else f"3d mean {funding:.1%} annualized")
    oi, r1=ctx.get("oi_change_1d"),ret(p,1)
    add("oi_purge_flush",None if oi is None or r1 is None else (2 if oi<=-.04 and r1<=-.05 else 0),None if oi is None else f"OI 24h {oi:+.1%}")
    high20=max(p[-20:]) if len(p)>=20 else None; low20=min(p[-20:]) if len(p)>=20 else None
    add("breakout_20d",None if high20 is None else (2 if p[-1]>=high20 else 1 if p[-1]<=low20 else 0),"20d range unavailable" if high20 is None else f"${low20:,.0f}–${high20:,.0f}")
    box=None
    if len(p)>=30:
        lo,hi=min(p[-30:]),max(p[-30:]); box=2 if p[-1]>hi else -2 if p[-1]<lo else 1 if p[-1]<=lo*1.02 else -1 if p[-1]>=hi*.98 else 0
    add("box_position",box,"30d support/resistance")
    r3=ret(p,3); active=(now.weekday()==6 and now.hour>=23) or (now.weekday()==0 and now.hour<23)
    add("monday_asia",None if r3 is None else ((1 if r3>0 else -1) if active and abs(r3)>.01 else 0),"window active" if active else "outside window")
    rho=None
    if len(p)>=182:
        rs=[p[i]/p[i-1]-1 for i in range(len(p)-181,len(p))]; rho=corr(rs[:-1],rs[1:])
    add("autocorr_gate",None if rho is None else (0 if abs(rho)<.06 else (1 if r1*rho>0 else -1)),None if rho is None else f"ρ1 {rho:+.2f}")
    r7=ret(p,7); add("momentum_7d",None if r7 is None else score_sign(r7,[(lambda x:x>=.07,2),(lambda x:x>=.02,1),(lambda x:x>-.02,0),(lambda x:x>-.07,-1),(lambda x:True,-2)]),None if r7 is None else f"7d {r7:+.1%}")
    sopr,rp=ctx.get("sth_sopr"),ctx.get("sth_rp"); spot=p[-1] if p else None
    ss=None
    if None not in (sopr,rp,spot): ss=2 if spot>rp and sopr<.98 else 1 if spot>rp and sopr<1 else -2 if spot<rp and sopr>=1 else -1 if spot<rp and sopr>=.99 else 0
    add("sth_sopr",ss,None if sopr is None else f"SOPR {sopr:.3f}")
    flow=ctx.get("etf_flow_5d"); add("etf_flow_5d",None if flow is None else score_sign(flow,[(lambda x:x>1e9,2),(lambda x:x>.25e9,1),(lambda x:x>=-.25e9,0),(lambda x:x>=-1e9,-1),(lambda x:True,-2)]),None if flow is None else f"5d ${flow/1e6:+,.0f}M")
    basis=ctx.get("basis_ann"); add("basis_regime",None if basis is None else score_sign(basis,[(lambda x:x<0,2),(lambda x:x<.03,1),(lambda x:x<.10,0),(lambda x:x<.15,-1),(lambda x:True,-2)]),None if basis is None else f"annualized {basis:.1%}")
    oil=ctx.get("oil_ret5"); add("oil_shock",None if oil is None else score_sign(oil,[(lambda x:x>.08,-2),(lambda x:x>.04,-1),(lambda x:x>=-.04,0),(lambda x:x>=-.08,1),(lambda x:True,2)]),None if oil is None else f"WTI 5d {oil:+.1%}")
    dxy,cbd=ctx.get("dxy_ret20"),ctx.get("btc_dxy_corr90"); ds=None if dxy is None or cbd is None else (0 if cbd>=-.2 else score_sign(dxy,[(lambda x:x<=-.025,2),(lambda x:x<=-.01,1),(lambda x:x<.01,0),(lambda x:x<.025,-1),(lambda x:True,-2)]))
    add("dxy_trend",ds,None if dxy is None else f"20d {dxy:+.1%}; corr {cbd if cbd is not None else float('nan'):+.2f}")
    ndx,cbn=ctx.get("ndx_ret10"),ctx.get("btc_ndx_corr60"); ns=None if ndx is None or cbn is None else (0 if cbn<.35 else (-2 if ndx<=-.03 else -1 if ndx<=-.015 else 1 if ndx>=.03 else 0))
    add("nasdaq_risk",ns,None if ndx is None else f"NDX 10d {ndx:+.1%}")
    hy,hyd=ctx.get("hy_oas"),ctx.get("hy_delta20"); hs=None if hy is None or hyd is None else (2 if hyd<=-50 and hy>450 else -2 if hyd>=100 else -1 if hyd>=50 else 1 if hy<300 and abs(hyd)<25 else 0)
    add("hy_spread",hs,None if hy is None else f"OAS {hy:.0f}bp; Δ20d {hyd:+.0f}bp")
    ma200=sma(p,200); r90=ret(p,90); regime=None
    if ma200 and r90 is not None:
        regime=1 if spot>1.01*ma200 else -1 if spot<.99*ma200 else 0
        if regime and (r90>0)==(regime>0): regime+=1 if regime>0 else -1
        mayer=spot/ma200
        if mayer<.9: regime+=1
        if mayer>2.4: regime=-2
    add("regime_stretch",regime,None if ma200 is None else f"Mayer {spot/ma200:.2f}")
    r28=ret(p,28); add("momentum_28d",None if r28 is None else score_sign(r28,[(lambda x:x>=.15,2),(lambda x:x>=.04,1),(lambda x:x>-.04,0),(lambda x:x>-.15,-1),(lambda x:True,-2)]),None if r28 is None else f"28d {r28:+.1%}")
    nl=ctx.get("net_liquidity_4w"); add("net_liquidity",None if nl is None else score_sign(nl,[(lambda x:x>150,2),(lambda x:x>25,1),(lambda x:x>=-25,0),(lambda x:x>=-150,-1),(lambda x:True,-2)]),None if nl is None else f"4w ${nl:+.0f}B")
    st=ctx.get("stable_ret30"); st7=ctx.get("stable_ret7"); sts=None
    if st is not None:
        sts=2 if st>.02 and st7 is not None and st7>0 else 1 if st>.005 else 0 if st>=-.005 else -1 if st>=-.02 else (-2 if st7 is not None and st7<0 else -1)
    add("stablecoin_30d",sts,None if st is None else f"supply 30d {st:+.1%}")
    sr=None
    if rp and len(p)>=3: sr=2 if all(x>rp*1.02 for x in p[-3:]) else -2 if all(x<rp*.98 for x in p[-3:]) else 0
    add("sth_rp_regime",sr,None if rp is None else f"STH RP ${rp:,.0f}")
    fg=ctx.get("fng_mean7"); add("fng_contrarian",None if fg is None else (2 if fg<=10 else 1 if fg<=20 else .5 if fg<=25 else -2 if fg>=85 else -1 if fg>=75 else 0),None if fg is None else f"7d mean {fg:.0f}")
    z=ctx.get("mvrv_z"); add("mvrv_z",None if z is None else (2 if z<0 else 1 if z<.5 else 0 if z<5 else -1 if z<7 else -2),None if z is None else f"Z {z:.2f}")
    hr30,hr60=ctx.get("hash_sma30"),ctx.get("hash_sma60"); add("hash_ribbons",None if hr30 is None or hr60 is None else (-1 if hr30<hr60 else (2 if ctx.get("hash_cross_days",999)<=30 else 1 if ctx.get("hash_cross_days",999)<=60 else 0)),"30/60d hashrate ribbon")
    pl=None
    if spot: pl,center,floor,broken=powerlaw(now,spot)
    add("powerlaw_blend",pl,None if spot is None else f"center ${center:,.0f}; floor ${floor:,.0f}" + (" · MODEL-BREAK" if broken else ""))
    dat=manual.get("dat",{}); mn,sales=dat.get("mnav_est"),dat.get("sale_count_30d",0); dscore=None if mn is None else (-2 if mn<.9 or (mn<1 and sales>=2) else -1 if mn<1 or sales>=2 else 0 if mn<=1.2 else 1 if mn<=1.5 else 2)
    add("dat_stress",dscore,None if mn is None else f"mNAV {mn:.2f}; {sales} sales")
    add("polymarket_ye",manual.get("polymarket_ye"),"operator score")
    wscore=None
    if len(p)>=350:
        ma20w=sma(p,140); old=sma(p[:-28],140); ma200w=sma(p,1400)
        wscore=1 if spot>ma20w else -1 if spot<ma20w else 0
        wscore += -.5 if old and ma20w<old else 0
        wscore += .5 if ma200w and abs(spot/ma200w-1)<=.05 else 0
    add("weekly_structure",wscore,"weekly moving-average structure")
    months=(now.year-2024)*12+now.month-4+(now.day-20)/30.44
    hc=-1 if 17<=months<19 else -2 if 19<=months<25 else -1 if 25<=months<31 else 1 if 31<=months<42 else 2 if 42<=months<50 else 1
    add("halving_clock",hc,f"{months:.1f} months since halving")
    gm=ctx.get("global_m2_delta"); add("global_m2",None if gm is None else (2 if gm>.5 else 1 if gm>.1 else 0 if gm>=-.1 else -1 if gm>=-.5 else -2),None if gm is None else f"YoY 3m Δ {gm:+.2f}pp")
    add("gli_phase",manual.get("gli_phase"),"operator score")
    att=ctx.get("attention_pct"); fgn=ctx.get("fng_current"); r30=ret(p,30); ats=None if att is None else (1 if att<=15 and fgn is not None and fgn<=30 else -2 if att>=95 and r30 is not None and r30>.2 else 1 if att>=95 and r30 is not None and r30<-.15 else 0)
    add("attention_apathy",ats,None if att is None else f"52w percentile {att:.0f}")
    add("cwac_analyst",manual.get("cwac_analyst"),"operator score")
    il,idelta=manual.get("ism_level"),manual.get("ism_delta"); iscore=None if il is None or idelta is None else (2 if il>=55 and idelta>0 else 1 if il>50 and idelta>0 else -2 if il<45 else -1 if il<50 and idelta<0 else 0)
    add("ism_regime",iscore,"manual ISM inputs")
    pi=0 if len(p)<395 else (-2 if sma(p,111)>2*sma(p,350) else 0); add("pi_cycle",pi,"111DMA vs 2×350DMA")
    sweep=None if len(p)<21 else (1 if ctx.get("low_today",p[-1])<min(p[-21:-1]) and p[-1]>min(p[-21:-1]) else 0)
    add("liquidity_sweep",sweep,"incubating; excluded from composite","INCUBATING")
    return out

def composites(signals, now, ctx, weights):
    result={}; rv=ctx.get("rv30",0); pctile=ctx.get("rv_percentile",0)
    mult=1 if pctile<=60 else .75 if pctile<=80 else .5
    event=ctx.get("event_window",False); hy=ctx.get("hy_delta20")
    for h in HOURS:
        weight_key={"h24":"weight_24h","d7":"weight_7d","d30":"weight_30d"}[h]
        vals=[(s["score"],s[weight_key]) for s in signals.values() if s["score"] is not None and s[weight_key]>0]
        denom=sum(abs(w)*2 for _,w in vals); raw=sum(s*w for s,w in vals)
        score=100*raw/denom if denom else 0; score*=mult
        if h in ("d7","d30") and hy is not None and hy>=50: score=min(0,score)
        abstain=h=="h24" and event and abs(raw)<3
        tilt="ABSTAIN" if abstain else "BULL" if score>=20 else "LEAN UP" if score>=10 else "BEAR" if score<=-20 else "LEAN DOWN" if score<=-10 else "FLAT"
        result[h]={"score":round(score,2),"raw_weighted_sum":round(raw,3),"p_up":round(.5+.5*(score/100)*CAPS[h],4),"tilt":tilt,"abstain":abstain}
    return result,mult

def wilson(hits,n,z=1.96):
    if not n:return (None,None)
    p=hits/n; d=1+z*z/n; c=(p+z*z/(2*n))/d; m=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/d
    return c-m,c+m

def recompute_scores(ledger):
    """Rebuild every outcome and statistic under decided-window scoring v2."""
    # Momentum at each snapshot is derived from the ledger itself, without refetching.
    ordered=sorted(ledger,key=lambda r:r["ts"])
    for i,row in enumerate(ordered):
        prior=[x for x in ordered[:i] if parse_ts(x["ts"])<=parse_ts(row["ts"])-timedelta(days=7)]
        entry=row.get("btc",{}).get("price")
        old=prior[-1].get("btc",{}).get("price") if prior else None
        row["momentum_7d_at_snapshot"]=pct(entry,old)
        for h in HOURS:
            o=row.get("outcomes",{}).get(h)
            if not o or o.get("ret") is None:continue
            realized="UP" if o["ret"]>=DEADBANDS[h] else "DOWN" if o["ret"]<=-DEADBANDS[h] else "NO_DECISION"
            c=row.get("composite",{}).get(h,{})
            forced=bool(c.get("abstain") or c.get("tilt")=="ABSTAIN")
            score=c.get("score")
            call="NEUTRAL" if forced or score is None or abs(score)<10 else ("UP" if score>0 else "DOWN")
            o.update({"realized_class":realized,"call":call,"abstained":forced,
                      "hit":call==realized if call in ("UP","DOWN") and realized in ("UP","DOWN") else None})
            o["signals"]={}
            for sid,s in row.get("signals",{}).items():
                v=s.get("score"); sc="NEUTRAL" if v is None or abs(v)<1 else ("UP" if v>0 else "DOWN")
                o["signals"][sid]=sc==realized if sc in ("UP","DOWN") and realized in ("UP","DOWN") else None
    result={"generated_at":iso(datetime.now(timezone.utc)),"scoring":"v2-decided-window","methodology":{"wilson_z":1.96,"composite_call_threshold":10,"signal_call_threshold":1,"brier_window":"decided windows only","weight_change_gate_n":385},"calibration":{},"composite":{},"signals":{}}
    def metric(rows, key, horizon, signal=False):
        obs=[]; brier_obs=[]; resolved=0; calls=0; decided=0; abstained=0
        for r in rows:
            o=r.get("outcomes",{}).get(horizon)
            if not o or o.get("ret") is None:continue
            resolved+=1; abstained+=bool(o.get("abstained")); realized=o.get("realized_class")
            if not signal and not o.get("abstained") and realized in ("UP","DOWN"):
                p=r.get("composite",{}).get(horizon,{}).get("p_up")
                if p is not None:brier_obs.append((p-(realized=="UP"))**2)
            if signal:
                ss=r.get("signals",{}).get(key,{}).get("score")
                if ss is None or abs(ss)<1:continue
                calls+=1
                if realized not in ("UP","DOWN"):continue
                decided+=1; hit=(ss>0)==(realized=="UP"); pred=.5+.5*(ss/2)*CAPS[horizon];brier_obs.append((pred-(realized=="UP"))**2)
            else:
                call=o.get("call"); pred=r.get("composite",{}).get(horizon,{}).get("p_up")
                if call not in ("UP","DOWN"):continue
                calls+=1
                if realized not in ("UP","DOWN") or pred is None:continue
                decided+=1; hit=call==realized
            mom=r.get("momentum_7d_at_snapshot")
            obs.append((r["ts"],hit,pred,realized,mom))
        n=len(obs); hits=sum(x[1] for x in obs); lo,hi=wilson(hits,n); ups=sum(x[3]=="UP" for x in obs)
        base=ups/n if n else None; brier=mean(brier_obs)
        mom=[((x[4]>0)==(x[3]=="UP")) for x in obs if x[4] is not None and x[4]!=0]
        rolling=[]
        for i in range(max(0,n-180),n):
            window=obs[max(0,i-89):i+1]; rolling.append({"ts":obs[i][0],"n":len(window),"hit_rate":sum(x[1] for x in window)/len(window)})
        threshold=max(.5,base or .5)
        status="WARMING_UP" if n<30 else "SIGNIFICANT" if lo is not None and lo>threshold else "BELOW_BASELINE" if hi is not None and hi<threshold else ("PROMISING" if n and hits/n>threshold else "NO_EDGE")
        if n>=90 and rolling[-1]["hit_rate"]<(lo or 0):status="DECAYING"
        directional=sum(1 for r in rows if (r.get("outcomes",{}).get(horizon) or {}).get("realized_class") in ("UP","DOWN"))
        rolling=rolling[-365:]
        if rolling:
            cutoff=parse_ts(rolling[-1]["ts"])-timedelta(days=90); kept=[]; weeks=set()
            for point in rolling:
                dt=parse_ts(point["ts"])
                if dt>=cutoff:kept.append(point)
                else:
                    week=(dt.year,dt.isocalendar().week)
                    if week not in weeks:weeks.add(week);kept.append(point)
            rolling=kept[-365:]
        return {"n":n,"decided_n":decided,"hits":hits,"hit_rate":hits/n if n else None,"wilson_lo":lo,"wilson_hi":hi,"brier":brier,"baseline_alwaysup":base,"baseline_momentum":mean(mom),"call_rate":calls/resolved if resolved else None,"decided_rate":directional/resolved if resolved else None,"abstained_n":abstained,"edge_status":status,"rolling90":rolling}
    for h in HOURS:
        result["composite"][h]={}
        for mode in ("live","backtest","pooled"):
            rows=[r for r in ledger if mode=="pooled" or r.get("mode")==mode]
            result["composite"][h][mode]=metric(rows,"composite",h)
        result["calibration"][h]={}
        for mode in ("live","backtest","pooled"):
            rows=[r for r in ledger if mode=="pooled" or r.get("mode")==mode]; bins={}
            for r in rows:
                o=r.get("outcomes",{}).get(h); p=r.get("composite",{}).get(h,{}).get("p_up")
                if not o or o.get("abstained") or o.get("realized_class") not in ("UP","DOWN") or p is None:continue
                b=round(round(p*20)/20,2); q=bins.setdefault(b,[0,0]);q[0]+=1;q[1]+=o["realized_class"]=="UP"
            result["calibration"][h][mode]=[{"p_up":b,"realized_up":v[1]/v[0],"n":v[0]} for b,v in sorted(bins.items())]
    ids=set(k for r in ledger for k in r.get("signals",{}))
    for sid in ids:
        result["signals"][sid]={}
        for h in HOURS:
            result["signals"][sid][h]={}
            for mode in ("live","backtest","pooled"):
                rows=[r for r in ledger if mode=="pooled" or r.get("mode")==mode]
                result["signals"][sid][h][mode]=metric(rows,sid,h,True)
    write_json(DATA/"scores.json",result); return result

def resolve_row(row, target_prices):
    entry=row["btc"]["price"]
    for h,hours in HOURS.items():
        price=target_prices.get(h)
        if price is None:continue
        r=price/entry-1; db=DEADBANDS[h]; klass="UP" if r>=db else "DOWN" if r<=-db else "NO_DECISION"
        comp=row["composite"][h]; abst=comp.get("abstain") or comp.get("tilt")=="ABSTAIN"
        score=comp.get("score"); call="NEUTRAL" if abst or score is None or abs(score)<10 else ("UP" if score>0 else "DOWN")
        hit=call==klass if call in ("UP","DOWN") and klass in ("UP","DOWN") else None
        ss={}
        for sid,s in row.get("signals",{}).items():
            v=s.get("score"); ss[sid]=None if v is None or abs(v)<1 or klass=="NO_DECISION" else ((v>0)==(klass=="UP"))
        row.setdefault("outcomes",{})[h]={"price":price,"price_source":"cached_daily_close","ret":r,"realized_class":klass,"call":call,"hit":hit,"abstained":abst,"signals":ss}
    return row

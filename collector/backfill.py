#!/usr/bin/env python3
"""Create idempotent daily historical snapshots using only point-in-time inputs."""
from __future__ import annotations
import argparse, csv, io, math, statistics, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests
sys.path.insert(0,str(Path(__file__).parent))
from lib import *

S=requests.Session();S.headers.update({"User-Agent":"btc-quantile-ladder/1.0"})
def candles(start,end):
    cache=read_json(DATA/"pricecache.json",[]); by={x["ts"][:10]:x for x in cache}
    cursor=start-timedelta(days=400)
    chunks=0
    while cursor<=end:
        stop=min(cursor+timedelta(days=299),end+timedelta(days=31))
        try:
            r=S.get("https://api.exchange.coinbase.com/products/BTC-USD/candles",params={"granularity":86400,"start":cursor.isoformat(),"end":stop.isoformat()},timeout=10);r.raise_for_status()
            for x in r.json():by[datetime.fromtimestamp(x[0],timezone.utc).date().isoformat()]={"ts":iso(datetime.fromtimestamp(x[0],timezone.utc)),"low":x[1],"high":x[2],"open":x[3],"close":x[4],"volume":x[5]}
        except Exception as e:print(f"warning: Coinbase chunk {cursor.date()}: {e}",file=sys.stderr)
        cursor=stop+timedelta(days=1);chunks+=1;print(f"Coinbase chunk {chunks}: through {stop.date()}",flush=True);time.sleep(.16)
    print(f"loaded {len(by)} cached candles in {chunks} API chunks",flush=True)
    vals=sorted(by.values(),key=lambda x:x["ts"]);write_json(DATA/"pricecache.json",vals[-4000:]);return vals

def fetch_fng():
    try:
        j=S.get("https://api.alternative.me/fng/?limit=0",timeout=30).json();return {datetime.fromtimestamp(int(x["timestamp"]),timezone.utc).date().isoformat():float(x["value"]) for x in j["data"]}
    except Exception:return {}
def fetch_hash():
    try:
        j=S.get("https://api.blockchain.info/charts/hash-rate?timespan=all&format=json",timeout=40).json();return {datetime.fromtimestamp(x["x"],timezone.utc).date().isoformat():float(x["y"]) for x in j["values"]}
    except Exception:return {}
def fetch_stable():
    try:
        j=S.get("https://stablecoins.llama.fi/stablecoincharts/all",timeout=40).json();return {datetime.fromtimestamp(int(x["date"]),timezone.utc).date().isoformat():float(x["totalCirculatingUSD"]["peggedUSD"]) for x in j}
    except Exception:return {}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--start",default="2019-01-01");args=ap.parse_args()
    start=datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc);today=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
    weights=read_json(CONFIG/"weights.json",{}); ledger=read_json(DATA/"ledger.json",[])
    live=[parse_ts(x["ts"]) for x in ledger if x.get("mode")=="live"];cutoff=min(live) if live else today+timedelta(days=1)
    existing={x["ts"] for x in ledger if x.get("mode")=="backtest"}
    cs=candles(start,today); fng=fetch_fng(); hashes=fetch_hash(); stable=fetch_stable(); print(f"aux history: F&G {len(fng)}, hashrate {len(hashes)}, stablecoin {len(stable)}",flush=True);idx={x["ts"][:10]:i for i,x in enumerate(cs)}; appended=0
    days=[];d=start
    while d<min(today,cutoff):days.append(d);d+=timedelta(days=1)
    for d in days:
        ts=iso(d)
        if ts in existing:continue
        i=idx.get(d.date().isoformat())
        if i is None or i<200 or i+30>=len(cs):continue
        hist=cs[:i+1];p=[x["close"] for x in hist]; rs=[p[j]/p[j-1]-1 for j in range(1,len(p))]
        rv=statistics.stdev(rs[-30:])*math.sqrt(365); rvhist=[statistics.stdev(rs[j-30:j])*math.sqrt(365) for j in range(30,len(rs)+1)]
        fgvals=[];hv=[];sv=[]
        for k in range(max(0,i-90),i+1):
            day=cs[k]["ts"][:10]
            if day in fng:fgvals.append(fng[day])
            if day in hashes:hv.append(hashes[day])
            if day in stable:sv.append(stable[day])
        ctx={"prices":p,"dates":[x["ts"] for x in hist],"fng_mean7":mean(fgvals[-7:]),"fng_current":fgvals[-1] if fgvals else None,
             "rv30":rv,"rv_percentile":100*sum(x<=rv for x in rvhist)/len(rvhist) if rvhist else 0,"event_window":False,
             "hash_sma30":mean(hv[-30:]),"hash_sma60":mean(hv[-60:]),"stable_ret30":sv[-1]/sv[-31]-1 if len(sv)>30 else None,"stable_ret7":sv[-1]/sv[-8]-1 if len(sv)>7 else None,
             "low_today":hist[-1]["low"]}
        # Operator-maintained signals (manual.json) have no per-date history; passing {} keeps
        # backtest rows point-in-time — they score as unavailable and their weight renormalizes away.
        sig=calculate_signals(ctx,weights,{},d);comp,mult=composites(sig,d,ctx,weights)
        ledger_signals={k:{"score":v["score"]} for k,v in sig.items()}
        row={"ts":ts,"mode":"backtest","btc":{"price":p[-1],"source":"Coinbase daily close"},"signals":ledger_signals,"composite":comp,"regime":{"vol_gate":{"multiplier":mult}},"outcomes":{"h24":None,"d7":None,"d30":None}}
        resolve_row(row,{h:cs[i+round(hours/24)]["close"] for h,hours in HOURS.items() if i+round(hours/24)<len(cs)})
        ledger.append(row);appended+=1
        if appended%250==0:print(f"calculated {appended} daily snapshots",flush=True)
    ledger.sort(key=lambda x:x["ts"]);scores=recompute_scores(ledger);write_json(DATA/"ledger.json",ledger);write_ledger_recent(ledger)
    print(f"appended {appended} backtest row(s)")
    print("horizon  n     hit-rate   Wilson 95%       call-rate  decided-rate always-up momentum")
    for h in HOURS:
        m=scores["composite"][h]["backtest"]
        def f(x):return "n/a" if x is None else f"{100*x:5.1f}%"
        values=(h,m["n"],f(m["hit_rate"]),f(m["wilson_lo"]),f(m["wilson_hi"]),f(m["call_rate"]),f(m["decided_rate"]),f(m["baseline_alwaysup"]),f(m["baseline_momentum"]))
        print("%-7s %5d %10s   %s-%s   %9s %12s %9s %8s" % values)
if __name__=="__main__":main()


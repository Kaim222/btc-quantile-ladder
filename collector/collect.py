#!/usr/bin/env python3
"""Fetch a keyless BTC snapshot, calculate signals, and append the live ledger."""
from __future__ import annotations
import csv, io, json, math, re, statistics, sys, time, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import requests
sys.path.insert(0,str(Path(__file__).parent))
from lib import *

S=requests.Session(); S.headers.update({"User-Agent":"btc-quantile-ladder/1.0 (+https://github.com/kaim222/btc-quantile-ladder)"})
sources={}; previous=read_json(DATA/"latest.json",{})
def get(name,url,kind="json",timeout=25):
    try:
        r=S.get(url,timeout=timeout); r.raise_for_status(); sources[name]={"ok":True,"status":r.status_code,"stale":False}
        return r.json() if kind=="json" else r.text
    except Exception as e:
        sources[name]={"ok":False,"error":f"{type(e).__name__}: {str(e)[:180]}","stale":True}; return None

def coinbase_history(days=760):
    end=datetime.now(timezone.utc); start=end-timedelta(days=days); rows=[]
    cursor=start
    while cursor<end:
        stop=min(cursor+timedelta(days=299),end)
        url="https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=86400&start="+cursor.isoformat()+"&end="+stop.isoformat()
        part=get("coinbase_candles",url)
        if not isinstance(part,list):break
        rows.extend(part); cursor=stop+timedelta(seconds=1); time.sleep(.12)
    if not rows:return read_json(DATA/"pricecache.json",[])
    by={int(x[0]):{"ts":iso(datetime.fromtimestamp(x[0],timezone.utc)),"low":x[1],"high":x[2],"open":x[3],"close":x[4],"volume":x[5]} for x in rows if len(x)>=6}
    vals=sorted(by.values(),key=lambda x:x["ts"])[-760:]; write_json(DATA/"pricecache.json",vals); return vals

def fred(sid):
    text=get("fred_"+sid,f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}","text")
    if not text:return []
    out=[]
    for row in csv.DictReader(io.StringIO(text)):
        try:out.append((row.get("DATE") or row["observation_date"],float(row[sid])))
        except (ValueError,KeyError):pass
    return out
def series_ret(x,n): return x[-1][1]/x[-1-n][1]-1 if len(x)>n and x[-1-n][1] else None
def calendar_delta(x, days):
    if not x:return None
    cutoff=datetime.fromisoformat(x[-1][0]).date()-timedelta(days=days)
    prior=[v for d,v in x if datetime.fromisoformat(d).date()<=cutoff]
    return x[-1][1]-prior[-1] if prior else None
def aligned_corr(candles, series, days):
    btc={x["ts"][:10]:x["close"] for x in candles}; ext=dict(series); dates=sorted(set(btc)&set(ext))[-(days+1):]
    if len(dates)<21:return None
    return corr([btc[dates[i]]/btc[dates[i-1]]-1 for i in range(1,len(dates))],
                [ext[dates[i]]/ext[dates[i-1]]-1 for i in range(1,len(dates))])
def growth_delta_3m(series):
    return ((series[-1][1]/series[-13][1]-1)-(series[-4][1]/series[-16][1]-1))*100 if len(series)>=16 else None
def bitcoin_data(name,path):
    url="https://bitcoin-data.com/v1/"+path
    try:
        r=S.get(url,timeout=25)
        if r.status_code==429:
            time.sleep(30);r=S.get(url,timeout=25)
        r.raise_for_status();sources[name]={"ok":True,"status":r.status_code,"stale":False};return r.json()
    except Exception as e:
        sources[name]={"ok":False,"error":f"{type(e).__name__}: {str(e)[:180]}","stale":True};return None

def main():
    DATA.mkdir(exist_ok=True); now=datetime.now(timezone.utc); weights=read_json(CONFIG/"weights.json",{}); manual=read_json(CONFIG/"manual.json",{})
    candles=coinbase_history(); prices=[x["close"] for x in candles]; dates=[x["ts"] for x in candles]
    cg=get("coingecko_spot","https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true")
    spot=change=None; spot_source="CoinGecko"
    if cg and cg.get("bitcoin"):spot=cg["bitcoin"].get("usd");change=cg["bitcoin"].get("usd_24h_change")
    if spot is None:
        bn=get("binance_spot","https://data-api.binance.vision/api/v3/ticker/price?symbol=BTCUSDT")
        if bn:spot=float(bn["price"]);spot_source="Binance Vision"
    if spot is None:
        cb=get("coinbase_spot","https://api.exchange.coinbase.com/products/BTC-USD/ticker")
        if cb:spot=float(cb["price"]);spot_source="Coinbase"
    if spot is None:spot=previous.get("btc",{}).get("price") or (prices[-1] if prices else None);spot_source="previous (stale)"
    if prices and spot:prices[-1]=spot
    fg=get("alternative_fng","https://api.alternative.me/fng/?limit=10"); fgv=[]
    if fg:
        fgv=[float(x["value"]) for x in fg.get("data",[]) if x.get("value")]
    funding=get("okx_funding","https://www.okx.com/api/v5/public/funding-rate-history?instId=BTC-USDT-SWAP&limit=100")
    fr=[]
    if funding:
        fr=[float(x["fundingRate"]) for x in funding.get("data",[])[:9]]
    current_funding=get("okx_current_funding","https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USDT-SWAP")
    oi=get("okx_oi_history","https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-volume?ccy=BTC&period=1D")
    oi_change=None
    try:
        vals=oi["data"]; oi_change=float(vals[0][1])/float(vals[1][1])-1
    except Exception:
        snap=get("okx_oi_snapshot","https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId=BTC-USDT-SWAP")
        cache=read_json(DATA/"oicache.json",[])
        if snap and snap.get("data"):
            v=float(snap["data"][0]["oiUsd"]); cache.append({"ts":iso(now),"value":v}); cache=cache[-400:]; write_json(DATA/"oicache.json",cache)
            if len(cache)>1:oi_change=v/cache[-2]["value"]-1
    startms=int((now-timedelta(days=400)).timestamp()*1000); endms=int(now.timestamp()*1000)
    dvol=get("deribit_dvol",f"https://www.deribit.com/api/v2/public/get_volatility_index_data?currency=BTC&resolution=86400&start_timestamp={startms}&end_timestamp={endms}")
    dv=[]
    try:dv=[float(x[4]) for x in dvol["result"]["data"]]
    except Exception:pass
    fut=get("deribit_futures","https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=future"); basis=None
    try:
        choices=[]
        for x in fut.get("result",[]):
            m=re.search(r"-(\d{1,2}[A-Z]{3}\d{2})$",x["instrument_name"])
            if not m:continue
            exp=datetime.strptime(m.group(1),"%d%b%y").replace(tzinfo=timezone.utc); days=(exp-now).total_seconds()/86400
            index=x.get("index_price") or x.get("estimated_delivery_price")
            if exp.month in (3,6,9,12) and days>=21 and x.get("mark_price") and index:choices.append((days,(float(x["mark_price"])/float(index)-1)*365/days))
        basis=min(choices)[1] if choices else None
    except Exception:pass
    fred_ids=["WALCL","RRPONTSYD","WTREGEN","M2SL","BAMLH0A0HYM2","DFII10","DCOILWTICO","NASDAQ100","DTWEXBGS"]
    fs={k:fred(k) for k in fred_ids}
    nl_parts=[calendar_delta(fs[k],28) for k in ("WALCL","RRPONTSYD","WTREGEN")]
    nl=(nl_parts[0]-nl_parts[1]-nl_parts[2])/1000 if None not in nl_parts else None
    ecb=get("ecb_m2","https://data-api.ecb.europa.eu/service/data/BSI/M.U2.Y.V.M20.X.1.U2.2300.Z01.E?lastNObservations=18&format=csvdata","text")
    ea=[]
    if ecb:
        try:
            for row in csv.DictReader(io.StringIO(ecb)):
                ea.append((row.get("TIME_PERIOD") or row.get("TIME_PERIOD_START"),float(row["OBS_VALUE"])))
            ea.sort()
        except (ValueError,KeyError,TypeError):ea=[]
    stable=get("defillama_stablecoin_history","https://stablecoins.llama.fi/stablecoincharts/all"); stable_series=[]
    try:stable_series=[(datetime.fromtimestamp(int(x["date"]),timezone.utc),float(x["totalCirculatingUSD"]["peggedUSD"])) for x in stable]
    except Exception:pass
    btcdata={}
    for key,path in (("sth_sopr","sth-sopr"),("sth_rp","sth-realized-price"),("mvrv_z","mvrv-zscore")):
        btcdata[key]=bitcoin_data("bitcoin_data_"+key,path)
    hashdata=get("blockchain_hashrate","https://api.blockchain.info/charts/hash-rate?timespan=1year&format=json"); hv=[]
    try:hv=[float(x["y"]) for x in hashdata["values"]]
    except Exception:pass
    etf=get("farside_etf","https://farside.co.uk/btc/","text")
    # Farside changes markup frequently. Abstain, and report health honestly, unless a
    # stable machine-readable row parser is explicitly recognized.
    etf_flow=None
    if etf is not None:
        sources["farside_etf"]={"ok":False,"error":"parse-unrecognized","reason":"parse-unrecognized","stale":True}
    wiki_start=(now-timedelta(days=370)).strftime("%Y%m%d"); wiki_end=now.strftime("%Y%m%d")
    wiki=get("wikipedia_pageviews",f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/Bitcoin/daily/{wiki_start}/{wiki_end}"); views=[]
    try:views=[x["views"] for x in wiki["items"]]
    except Exception:pass
    calendar=read_json(CONFIG/"calendar.json",[]); next_event=None; event_window=False
    for e in calendar:
        if not e.get("date"):continue
        d=datetime.fromisoformat(e["date"]).replace(tzinfo=timezone.utc)
        if d>=now and (next_event is None or d<next_event[0]):next_event=(d,e["name"])
        if timedelta(0)<=d-now<=timedelta(hours=24):event_window=True
    daily_rets=[prices[i]/prices[i-1]-1 for i in range(1,len(prices))] if len(prices)>1 else []
    rv30=statistics.stdev(daily_rets[-30:])*math.sqrt(365) if len(daily_rets)>=30 else 0
    hist=[statistics.stdev(daily_rets[i-30:i])*math.sqrt(365) for i in range(30,len(daily_rets)+1)]
    rv_pct=100*sum(x<=rv30 for x in hist)/len(hist) if hist else 0
    ctx={"prices":prices,"dates":dates,"funding_ann":mean(fr)*3*365 if fr else None,"oi_change_1d":oi_change,"basis_ann":basis,
      "fng_mean7":mean(fgv[:7]),"fng_current":fgv[0] if fgv else None,"rv30":rv30,"rv_percentile":rv_pct,"event_window":event_window,
      "oil_ret5":series_ret(fs["DCOILWTICO"],5),"dxy_ret20":series_ret(fs["DTWEXBGS"],20),"ndx_ret10":series_ret(fs["NASDAQ100"],10),
      "btc_dxy_corr90":aligned_corr(candles,fs["DTWEXBGS"],90),"btc_ndx_corr60":aligned_corr(candles,fs["NASDAQ100"],60),
      "hy_oas":fs["BAMLH0A0HYM2"][-1][1]*100 if fs["BAMLH0A0HYM2"] else None,"hy_delta20":(fs["BAMLH0A0HYM2"][-1][1]-fs["BAMLH0A0HYM2"][-21][1])*100 if len(fs["BAMLH0A0HYM2"])>20 else None,
      "net_liquidity_4w":nl,"etf_flow_5d":etf_flow,"stable_ret30":None,"stable_ret7":None,"hash_sma30":mean(hv[-30:]),"hash_sma60":mean(hv[-60:]),
      "attention_pct":100*sum(v<=views[-1] for v in views)/len(views) if views else None,"low_today":candles[-1]["low"] if candles else None}
    if stable_series:
        cur_t,cur_v=stable_series[-1]
        for days,key in ((30,"stable_ret30"),(7,"stable_ret7")):
            old=[v for t,v in stable_series if t<=cur_t-timedelta(days=days)]
            if old:ctx[key]=cur_v/old[-1]-1
    deltas=[growth_delta_3m(fs["M2SL"]),growth_delta_3m(ea)]
    for region in ("cn","jp"):
        a,b=manual.get(region+"_m2_yoy"),manual.get(region+"_m2_yoy_prev")
        deltas.append(a-b if a is not None and b is not None else None)
    ctx["global_m2_delta"]=mean(deltas) if all(x is not None for x in deltas) else None
    # API payloads vary; accept only recognizable final numeric observations.
    value_fields={"sth_sopr":"sthSopr","sth_rp":"sthRealizedPrice","mvrv_z":"mvrvZscore"}
    for k in ("sth_sopr","sth_rp","mvrv_z"):
        obj=btcdata[k]; val=None
        if isinstance(obj,list) and obj:
            last=obj[-1]; val=last.get("value",last.get(value_fields[k])) if isinstance(last,dict) else None
        elif isinstance(obj,dict):
            seq=obj.get("data") or obj.get("values")
            if isinstance(seq,list) and seq:
                last=seq[-1]; val=last.get("value") if isinstance(last,dict) else (last[-1] if isinstance(last,list) else None)
        try:ctx[k]=float(val)
        except (TypeError,ValueError):ctx[k]=None
        if ctx[k] is None and sources.get("bitcoin_data_"+k,{}).get("ok"):
            sources["bitcoin_data_"+k]={"ok":False,"error":"parse-unrecognized","reason":"parse-unrecognized","stale":True}
    signals=calculate_signals(ctx,weights,manual,now); comp,mult=composites(signals,now,ctx,weights)
    expected={h:round(rv30/math.sqrt(365)*math.sqrt(hours/24)*100,2) for h,hours in HOURS.items()}
    pl_center=pl_floor=None
    if spot: _,pl_center,pl_floor,_=powerlaw(now,spot)
    levels={
      "spot":round(spot) if spot is not None else None,
      "box_floor":round(min(prices[-30:])) if len(prices)>=30 else None,
      "box_ceiling":round(max(prices[-30:])) if len(prices)>=30 else None,
      "low_20d":round(min(prices[-20:])) if len(prices)>=20 else None,
      "high_20d":round(max(prices[-20:])) if len(prices)>=20 else None,
      "dma_50":round(sma(prices,50)) if sma(prices,50) is not None else None,
      "dma_200":round(sma(prices,200)) if sma(prices,200) is not None else None,
      "sth_cost_basis":round(ctx["sth_rp"]) if ctx.get("sth_rp") is not None else None,
      "pl_floor":round(pl_floor) if pl_floor is not None else None,
      "pl_center":round(pl_center) if pl_center is not None else None,
      "prior_day_high":round(candles[-2]["high"]) if len(candles)>=2 else None,
      "prior_day_low":round(candles[-2]["low"]) if len(candles)>=2 else None}
    future_calendar=[]
    for e in calendar:
        try:
            d=datetime.fromisoformat(e["date"]).replace(tzinfo=timezone.utc)
            if now.date() <= d.date() <= (now+timedelta(days=60)).date(): future_calendar.append({"date":e["date"],"name":e["name"]})
        except (KeyError,ValueError,TypeError): pass
    future_calendar.sort(key=lambda e:e["date"])
    plsig=signals["powerlaw_blend"]; floor_watch="MODEL-BREAK" in plsig["reading"] or ("floor $" in plsig["reading"] and False)
    latest={"generated_at":iso(now),"btc":{"price":spot,"change_24h":change,"source":spot_source},"sources":sources,"signals":signals,"composite":comp,
      "regime":{"vol_gate":{"state":"NORMAL" if mult==1 else "ELEVATED" if mult==.75 else "EXTREME","multiplier":mult,"rv_percentile":rv_pct},"dvol_flag":"COMPRESSION" if dv and dv[-1]<35 else "STRESS" if dv and dv[-1]>70 else "NORMAL","dvol":dv[-1] if dv else None,"event_window":event_window,"next_event":{"date":next_event[0].date().isoformat(),"name":next_event[1]} if next_event else None,"hy_veto":ctx.get("hy_delta20") is not None and ctx["hy_delta20"]>=50,"halving_month":signals["halving_clock"]["reading"],"pl_floor_watch":floor_watch},"expected_move":expected,
      "levels":levels,"caps":PROBABILITY_CAPS,"calendar":future_calendar}
    latest["verdict"]={h:verdict(h,latest) for h in HOURS}
    write_json(DATA/"latest.json",latest)
    send_alerts(previous,latest,manual)
    ledger=read_json(DATA/"ledger.json",[])
    if not ledger or (now-parse_ts(ledger[-1]["ts"])).total_seconds()>=4*3600:
        ledger_signals={k:{"score":v["score"]} for k,v in signals.items()}
        ledger.append({"ts":iso(now),"mode":"live","btc":latest["btc"],"signals":ledger_signals,"composite":comp,"regime":latest["regime"],"expected_move":expected,"outcomes":{"h24":None,"d7":None,"d30":None}});write_json(DATA/"ledger.json",ledger)
    write_ledger_recent(ledger)
    collect_news(now)
    print(f"snapshot {latest['generated_at']}: {sum(s['score'] is not None for s in signals.values())} scored signals; ledger rows={len(ledger)}")

def send_alerts(old,new,manual):
    topic=manual.get("ntfy_topic","")
    if not topic or not old:return
    old_v=old.get("verdict") or {h:verdict(h,old) for h in HOURS}
    changes=[h for h in HOURS if (old_v.get(h) or {}).get("state") != new["verdict"][h].get("state")]
    old_armed=(old_v.get("h24") or {}).get("state")=="WATCH TRIGGER"
    new_armed=new["verdict"]["h24"].get("state")=="WATCH TRIGGER"
    old_failed={k for k,v in old.get("sources",{}).items() if not v.get("ok")}
    new_failed={k for k,v in new.get("sources",{}).items() if not v.get("ok")}
    newly_failed=len(new_failed-old_failed)
    reasons=[]
    if changes:reasons.append("verdict changed: "+", ".join(changes))
    if new_armed and not old_armed:reasons.append("WATCH TRIGGER armed")
    if newly_failed>=2:reasons.append(f"{newly_failed} sources newly failed")
    if not reasons:return
    try:S.post("https://ntfy.sh/"+topic,data=("BTC Signals: "+"; ".join(reasons)).encode("utf-8"),headers={"Content-Type":"text/plain"},timeout=10).raise_for_status()
    except Exception as e:print(f"alert failed: {type(e).__name__}",file=sys.stderr)

def collect_news(now):
    feeds=[("CoinDesk","https://www.coindesk.com/arc/outboundfeeds/rss/"),("Bitcoin Magazine","https://bitcoinmagazine.com/feed"),("Decrypt","https://decrypt.co/feed"),("The Block","https://www.theblock.co/rss.xml")]; items=[]
    for name,url in feeds:
        text=get("news_"+name.lower().replace(" ","_"),url,"text")
        if not text:continue
        try:
            root=ET.fromstring(text)
            for x in root.findall(".//item"):
                title=(x.findtext("title") or "").strip(); link=(x.findtext("link") or "").strip(); ds=x.findtext("pubDate")
                try:dt=parsedate_to_datetime(ds).astimezone(timezone.utc)
                except Exception:dt=now
                if title:items.append({"title":title,"url":link,"source":name,"published_at":iso(dt)})
        except Exception:pass
    uniq={}
    for x in sorted(items,key=lambda z:z["published_at"],reverse=True):uniq.setdefault(re.sub(r"\W+"," ",x["title"].lower()).strip(),x)
    kept=list(uniq.values())[:30]; crisis=re.compile(r"war|strike|hormuz|sanction|liquidat|bankrupt|hack|default",re.I)
    recent=sum(bool(crisis.search(x["title"])) and parse_ts(x["published_at"])>=now-timedelta(days=1) for x in kept)
    total=sum(bool(crisis.search(x["title"])) for x in kept); ratio=recent/max(total/30,1/30)
    write_json(DATA/"news.json",{"generated_at":iso(now),"crisis_ratio":ratio,"headlines":kept})

if __name__=="__main__":main()

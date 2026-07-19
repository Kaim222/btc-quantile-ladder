#!/usr/bin/env python3
"""Resolve matured live ledger calls and rebuild measured score statistics."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys, requests
sys.path.insert(0,str(Path(__file__).parent))
from lib import *

def target_price(ts):
    start=int((ts-timedelta(hours=12)).timestamp()); end=int((ts+timedelta(hours=12)).timestamp())
    urls=[("Coinbase",f"https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=3600&start={iso(ts-timedelta(hours=12))}&end={iso(ts+timedelta(hours=12))}"),
          ("CoinGecko",f"https://api.coingecko.com/api/v3/coins/bitcoin/market_chart/range?vs_currency=usd&from={start}&to={end}"),
          ("Binance Vision",f"https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1h&startTime={start*1000}&endTime={end*1000}")]
    for name,url in urls:
        try:
            data=requests.get(url,timeout=25,headers={"User-Agent":"btc-quantile-ladder/1.0"}).json(); pts=[]
            if name=="Coinbase":pts=[(float(x[0]),float(x[4])) for x in data]
            elif name=="CoinGecko":pts=[(x[0]/1000,float(x[1])) for x in data["prices"]]
            else:pts=[(x[0]/1000,float(x[4])) for x in data]
            if pts:return min(pts,key=lambda x:abs(x[0]-ts.timestamp()))[1],name
        except Exception:pass
    return None,None

def main():
    ledger=read_json(DATA/"ledger.json",[]); now=datetime.now(timezone.utc); changed=0
    for row in ledger:
        if row.get("mode")!="live":continue
        base=parse_ts(row["ts"])
        for h,hours in HOURS.items():
            if row.get("outcomes",{}).get(h) is not None or base+timedelta(hours=hours)>now-timedelta(hours=1):continue
            price,source=target_price(base+timedelta(hours=hours))
            if price is None:continue
            resolve_row(row,{h:price}); row["outcomes"][h]["price_source"]=source; changed+=1
    recompute_scores(ledger)
    write_json(DATA/"ledger.json",ledger);write_ledger_recent(ledger)
    print(f"resolved {changed} matured outcome(s); ledger rows={len(ledger)}")
if __name__=="__main__":main()

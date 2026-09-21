"""Reproducible premium study. Decimal premiums; errors and changes in percent.

Full-fit results reproduce the descriptive study, not an out-of-sample claim.
Walk-forward fits exclude the scored origin. Past premiums are recomputed using
that origin's fit. Forecasts freeze origin BPS and use given endpoint BTC/STRC.
Last 120 means origin dates in the last 120 source sessions, not 120 survivors.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from mnav_fit import ROOT, atomic_text, coefficients, target

WINDOWS = (3, 5, 10, 15, 20, 40, 60)
HALVES = (5, 10, 20, 40)
CHOSEN_N = 10
PICK_REASON = ('No window clearly separates on durable contraction across both Bitcoin regimes. '
    'Short windows lower same-day miss but absorb jumps quickly. Frozen-baseline contraction is inconsistent. '
    'Use Alex\'s fallback of 10 sessions, balancing a low miss with a slower baseline.')


def premiums(frame, fit):
    price = frame.btc * frame.bps * target(frame.btc, frame.strc, fit)
    if (price <= 0).any():
        raise ValueError('Nonpositive fitted price')
    return frame.mstr / price - 1


def stats(values):
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    return dict(count=len(v), median=float(np.median(v)) if len(v) else None,
                mean=float(np.mean(v)) if len(v) else None)


def premium_object(frame, fit, n):
    if not isinstance(n, int) or n < 1 or len(frame) <= n:
        raise ValueError('Premium needs more than n completed sessions')
    p = premiums(frame, fit)
    excess = (p - p.shift(1).rolling(n).mean()).dropna()
    miss = 100 * ((1 + p) / (1 + p.shift(1).rolling(n).mean()) - 1).abs().dropna()
    return dict(n=n, average=float(p.tail(n).mean()), **{'from': frame.d.iloc[-n], 'to': frame.d.iloc[-1]},
                **{f'p{q}': float(excess.quantile(q / 100)) for q in (25, 75, 10, 90)},
                median_abs_pct=float(miss.median()), mean_abs_pct=float(miss.mean()), sessions=len(excess))


def lookup_gate(rows, n):
    """A win requires lower median AND mean on BOTH samples at two horizons."""
    by = {(r['horizon'],r['half'],r['sample']):r for r in rows if r['n']==n}
    wins = {}
    for half in HALVES:
        wins[str(half)] = [h for h in (5,20,40) if all(
            by[h,str(half),sample][metric] < by[h,'static',sample][metric]
            for sample in ('all','last120') for metric in ('median','mean'))]
    return dict(changed=any(len(v)>=2 for v in wins.values()), winning_horizons=wins)


def study(frame, btc_daily):
    frame = frame.reset_index(drop=True)
    size = len(frame)
    full = coefficients(frame)
    pfull = premiums(frame, full)
    # At a US close, the current UTC Bitcoin daily bar has not completed.
    btc_daily = btc_daily.sort_index()
    regime = (btc_daily > btc_daily.rolling(50).mean()).shift(1).reindex(pd.to_datetime(frame.d))
    if regime.isna().any():
        raise ValueError('Daily BTC regime data does not cover every source session')
    regimes = np.where(regime.to_numpy(), 'above', 'below')
    out = dict(sessions=size, start=frame.d.iloc[0], end=frame.d.iloc[-1], same_day=[], shrinkage=[], forecasts=[])
    vintages = {i: coefficients(frame.iloc[:i]) for i in range(120, size)}
    series = {}
    for mode in ('full', 'walk'):
        for n in (0,) + WINDOWS:
            errors, excess, raw = np.full(size, np.nan), np.full(size, np.nan), np.full(size, np.nan)
            fair_errors = np.full(size, np.nan)
            for i in range(max(n, 120 if mode == 'walk' else 0), size):
                f = full if mode == 'full' else vintages[i]
                p = pfull.iloc[:i+1] if mode == 'full' else premiums(frame.iloc[:i+1], f)
                average = float(p.iloc[i-n:i].mean()) if n else 0
                errors[i] = 100 * abs((1+average)/(1+p.iloc[i])-1)
                fair_errors[i] = 100 * abs((1+p.iloc[i])/(1+average)-1)
                excess[i], raw[i] = p.iloc[i]-average, p.iloc[i]
            for sample, sl in [('all', slice(None)), ('last120', slice(-120, None))]:
                out['same_day'].append(dict(mode=mode,n=n,sample=sample,**stats(fair_errors[sl]),actual_denominator=stats(errors[sl])))
            if not n:
                continue
            series[mode,n] = excess
            for sign, label in [(1, '+4'), (-1, '-4')]:
                active = sign*excess >= .04
                starts = np.flatnonzero(active & ~np.r_[False, active[:-1]])
                for reg in ('all','above','below'):
                    events = [int(i) for i in starts if reg == 'all' or regimes[i] == reg]
                    row = dict(mode=mode,n=n,side=label,regime=reg,events=len(events))
                    for h in (5,10):
                        valid = [i for i in events if i+h < size]
                        changes = [100*(excess[i+h]-excess[i]) for i in valid]
                        # Endpoint contraction toward baseline, even if it crosses zero.
                        shrink = [sign*c < 0 for c in changes]
                        first = [next((k for k in range(1,h+1) if sign*(excess[i+k]-excess[i]) < 0), None) for i in valid]
                        fixed_changes = []
                        for i in valid:
                            f = full if mode == 'full' else vintages[i]
                            pp = premiums(frame.iloc[[i,i+h]], f)
                            fixed_changes.append(100*(pp.iloc[1]-pp.iloc[0]))
                        row[str(h)] = dict(count=len(valid),shrank=int(sum(shrink)),share=float(np.mean(shrink)) if valid else None,
                            median_change=float(np.median(changes)) if valid else None,
                            within_share=float(np.mean([k is not None for k in first])) if valid else None,
                            median_first=stats([k for k in first if k is not None])['median'],
                            frozen_share=float(np.mean(sign*np.array(fixed_changes)<0)) if valid else None,
                            frozen_median_change=stats(fixed_changes)['median'])
                    out['shrinkage'].append(row)
    for n in WINDOWS:
        for h in (5,20,40):
            errs = {str(k): [] for k in ('static',)+HALVES}
            origins = []
            for i in range(120,size-h):
                f = vintages[i]
                a,b = frame.iloc[i],frame.iloc[i+h]
                p = premiums(frame.iloc[:i+1], f)
                avg, gap = float(p.iloc[i-n:i].mean()),float(p.iloc[i])
                line = b.btc*a.bps*target(b.btc,b.strc,f)
                days = (pd.Timestamp(b.d)-pd.Timestamp(a.d)).days
                predictions = {'static': min(2*b.btc*a.bps, line*(1+gap*2**(-days/28)))}
                predictions.update({str(k): min(2*b.btc*a.bps,line*(1+avg+(gap-avg)*2**(-h/k))) for k in HALVES})
                for k, price in predictions.items():
                    errs[k].append(100*abs(price/b.mstr-1))
                origins.append(i)
            for sample in ('all','last120'):
                mask = np.array(origins) >= (0 if sample == 'all' else size-120)
                for k,values in errs.items():
                    out['forecasts'].append(dict(n=n,horizon=h,half=k,sample=sample,**stats(np.array(values)[mask])))
    out['lines'] = {str(n): premium_object(frame,full,n) for n in WINDOWS}
    excess20 = series['full',20]
    active20 = excess20 >= .04
    complete = [int(i) for i in np.flatnonzero(active20 & ~np.r_[False,active20[:-1]]) if i+10<size]
    out['supplied_replication'] = {str(h): dict(count=len(complete),
        shrank=sum(bool(excess20[i+h]<excess20[i]) for i in complete),
        median_change=float(np.median([100*(excess20[i+h]-excess20[i]) for i in complete]))) for h in (5,10)}
    out['selection'] = dict(n=CHOSEN_N, reason=PICK_REASON, lookup=lookup_gate(out['forecasts'], CHOSEN_N))
    out['notes'] = ['Full sample constants are descriptive only. Walk means at least 120 strictly earlier rows.',
        'Same day headline is abs(actual/fair-1), matching the supplied table. Actual denominator is also reported.',
        'Prior window excludes today. All means all eligible sessions. Last120 selects origin dates.',
        'Shrink share is directional contraction at the endpoint. Within share counts any earlier contraction.',
        'Median change is signed percentage points. First contraction speed is conditional on contraction within the horizon.',
        'Regime uses previous completed UTC BTC day versus its 50 calendar day SMA.',
        'Forecast endpoints overlap. Given future BTC and STRC is conditional valuation, not a tradable forecast.',
        'Window and half life selection on these scores remains model selection, not an untouched holdout.']
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--btc-daily', type=Path, default=ROOT/'data/premium-btc-daily.csv')
    args = p.parse_args()
    frame = pd.read_csv(ROOT/'data/mstr-daily.csv').dropna(subset=['strc']).reset_index(drop=True)
    btc = pd.read_csv(args.btc_daily, index_col=0, parse_dates=True).btc
    result = study(frame, btc)
    atomic_text(ROOT/'data/premium-study.json', json.dumps(result,indent=2,allow_nan=False)+'\n')
    for row in result['same_day']:
        print('MISS',row)
    for row in result['shrinkage']:
        print('SHRINK',row)
    for row in result['forecasts']:
        if row['n']==10: print('FORECAST',row)
    print('LINES',result['lines'])


if __name__ == '__main__':
    main()

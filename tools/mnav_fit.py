"""Fit equity mNAV on Bitcoin and STRC shortfall, with a nonpositive STRC term.

Usage: python tools/mnav_fit.py [data/mstr-config.json] [monitor_config] --write
Walk forward uses coefficients fitted strictly before each origin, at least 120
sessions. Endpoint Bitcoin and STRC are given; Bitcoin per share stays at origin.
Miss is absolute predicted / actual MSTR minus one, in percent. Horizons overlap.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CAP = 2.0


def coefficients(frame):
    x = (frame.btc.to_numpy() - 75000) / 2500
    z = np.maximum(0, 100 - frame.strc.to_numpy())
    y = frame.mstr.to_numpy() / (frame.btc.to_numpy() * frame.bps.to_numpy())
    design = np.column_stack([np.ones(len(frame)), x, z])
    a, b, c = np.linalg.lstsq(design, y, rcond=None)[0]
    if c > 0:
        a, b = np.linalg.lstsq(design[:, :2], y, rcond=None)[0]
        c = 0.0
    return dict(a=float(a), b=float(b), c=float(c), par=100)


def target(btc, strc, fit):
    return np.minimum(CAP, fit['a'] + fit['b'] * (btc - 75000) / 2500
                      + fit['c'] * np.maximum(0, fit['par'] - strc))


def atomic_text(path, text):
    """Replace atomically while preserving the destination's newline convention."""
    path = Path(path)
    raw = path.read_bytes() if path.exists() else b''
    newline = '\r\n' if b'\r\n' in raw else '\n'
    bom = b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
    data = bom + text.replace('\r\n', '\n').replace('\n', newline).encode('utf-8')
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + '.', suffix='.tmp', delete=False) as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
        temp = f.name
    os.replace(temp, path)


def measure(frame):
    fit = coefficients(frame)
    y = frame.mstr / (frame.btc * frame.bps)
    raw = fit['a'] + fit['b'] * (frame.btc - 75000) / 2500 + fit['c'] * np.maximum(0, 100 - frame.strc)
    gap = 100 * (y / target(frame.btc, frame.strc, fit) - 1)
    fit.update(sessions=len(frame), **{'from': frame.d.iloc[0], 'to': frame.d.iloc[-1]},
               fitted_on=dt.date.today().isoformat(),
               r2=float(1 - np.sum((y - raw) ** 2) / np.sum((y - y.mean()) ** 2)),
               p25=float(np.percentile(gap, 25)), p75=float(np.percentile(gap, 75)),
               median_abs_gap_pct=float(np.median(np.abs(gap))))
    scores = {h: {'fair_value': [], 'gap_carry': []} for h in (5, 20, 40)}
    for i in range(120, len(frame)):
        vintage = coefficients(frame.iloc[:i])
        origin = frame.iloc[i]
        origin_fair = origin.btc * origin.bps * target(origin.btc, origin.strc, vintage)
        if origin_fair <= 0:
            raise ValueError('Nonpositive origin fair value')
        origin_gap = origin.mstr / origin_fair - 1
        for h, score in scores.items():
            if i + h >= len(frame):
                continue
            end = frame.iloc[i + h]
            fair = end.btc * origin.bps * target(end.btc, end.strc, vintage)
            days = (pd.Timestamp(end.d) - pd.Timestamp(origin.d)).days
            # The same valuation cap applies to the gap carrying estimate.
            best = min(CAP * end.btc * origin.bps, fair * (1 + origin_gap * 0.5 ** (days / 28)))
            for key, value in [('fair_value', fair), ('gap_carry', best)]:
                score[key].append(100 * abs(value / end.mstr - 1))
    fit['walk_forward'] = {
        str(h): {key: {'sessions': len(values), 'median_abs_pct': float(np.median(values)),
                      'mean_abs_pct': float(np.mean(values))} for key, values in score.items()}
        for h, score in scores.items()}
    fit['walk_forward_note'] = ('At least 120 earlier sessions per fit. Origin excluded from training. '
        'Endpoint Bitcoin and STRC given. Origin Bitcoin per share held fixed. '
        'Absolute miss as percent of actual MSTR. Overlapping horizons. 28 calendar day gap half life. mNAV cap 2.')
    return fit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', nargs='?', type=Path, default=ROOT / 'data/mstr-config.json')
    parser.add_argument('monitor_config', nargs='?', type=Path)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    frame = pd.read_csv(ROOT / 'data/mstr-daily.csv').dropna(subset=['strc']).reset_index(drop=True)
    if frame.d.duplicated().any() or not frame.d.is_monotonic_increasing:
        raise ValueError('Sessions must be unique and ordered')
    if len(frame) <= 160 or not np.isfinite(frame[['btc', 'strc', 'bps', 'mstr']]).all().all() or (frame[['btc', 'bps', 'mstr']] <= 0).any().any():
        raise ValueError('Invalid or insufficient source rows')
    fit = measure(frame)
    cheap, rich = [float(np.round(fit[k] / 0.5) * 0.005) for k in ('p25', 'p75')]
    print(json.dumps(dict(fit=fit, cheap_threshold=cheap, rich_threshold=rich), indent=2, allow_nan=False))
    if args.write:
        for path in [args.config, args.monitor_config]:
            if path is None:
                continue
            config = json.loads(path.read_text(encoding='utf-8-sig'))
            config.update(fit=fit, cheap_threshold=cheap, rich_threshold=rich,
                          btc_slope_per_2500=fit['b'], gap_centre=0, gap_half_life_days=28,
                          updated=fit['fitted_on'],
                          note='Fair value uses a fitted Bitcoin line and a nonpositive STRC shortfall term below par. '
                               'Cheap and Rich are the fitted gap quartiles rounded to half a percent in MSTR terms. '
                               'MSTX alert thresholds are twice these values. The lag signal is unchanged.',
                          lookup_note='Projected uses the fitted line capped at mNAV 2. Best estimate carries today\'s gap with a 28 calendar day half life.')
            atomic_text(path, json.dumps(config, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()

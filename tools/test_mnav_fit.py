"""Regression checks for the fitted valuation and its chronological evaluation."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from mnav_fit import atomic_text, coefficients, measure, target


def panel(c):
    rng = np.random.default_rng(412)
    btc = rng.uniform(60000, 125000, 170)
    strc = rng.uniform(80, 105, 170)
    bps = np.full(170, .0018)
    mnav = .93 + .03 * (btc - 75000) / 2500 + c * np.maximum(0, 100 - strc)
    return pd.DataFrame(dict(d=pd.bdate_range('2025-01-01', periods=170).strftime('%Y-%m-%d'),
                             btc=btc, strc=strc, bps=bps, mstr=mnav * btc * bps))


def test_negative_shortfall_and_above_par():
    fit = coefficients(panel(-.003))
    assert [fit[k] for k in ('a', 'b', 'c')] == pytest.approx([.93, .03, -.003])
    assert target(100000, 100, fit) == target(100000, 110, fit)
    assert target(200000, 98, fit) == 2


def test_positive_shortfall_refits_both_other_coefficients():
    frame = panel(.01)
    fit = coefficients(frame)
    ab = np.linalg.lstsq(np.column_stack([np.ones(len(frame)), (frame.btc-75000)/2500]),
                         frame.mstr/(frame.btc*frame.bps), rcond=None)[0]
    assert fit['c'] == 0
    assert [fit['a'], fit['b']] == pytest.approx(ab)
    assert fit['a'] != pytest.approx(.93)


def test_walk_forward_origin_excluded_and_origin_bps_frozen(monkeypatch):
    import mnav_fit
    frame = panel(-.003)
    # Vary future holdings so a destination BPS leak visibly changes every score.
    frame.loc[120:, 'bps'] *= np.linspace(1, 1.4, 50)
    calls = []
    original = mnav_fit.coefficients
    def checked(rows):
        calls.append(len(rows))
        return original(rows)
    monkeypatch.setattr(mnav_fit, 'coefficients', checked)
    result = measure(frame)
    assert calls == [170] + list(range(120, 170))
    for h in (5, 20, 40):
        errors = {'fair_value': [], 'gap_carry': []}
        for i in range(120, len(frame)-h):
            f = original(frame.iloc[:i])
            a, b = frame.iloc[i], frame.iloc[i+h]
            origin = a.btc*a.bps*target(a.btc,a.strc,f)
            fair = b.btc*a.bps*target(b.btc,b.strc,f)
            days = (pd.Timestamp(b.d)-pd.Timestamp(a.d)).days
            best = min(2*b.btc*a.bps, fair*(1+(a.mstr/origin-1)*2**(-days/28)))
            for k, price in [('fair_value', fair), ('gap_carry', best)]:
                errors[k].append(100*abs(price/b.mstr-1))
        for k, values in errors.items():
            actual = result['walk_forward'][str(h)][k]
            assert actual['sessions'] == len(values)
            assert actual['mean_abs_pct'] == pytest.approx(np.mean(values))
            assert actual['median_abs_pct'] == pytest.approx(np.median(values))


@pytest.mark.parametrize('newline', [b'\n', b'\r\n'])
def test_atomic_write_preserves_line_endings(tmp_path, newline):
    path = tmp_path/'config.json'
    path.write_bytes(b'{'+newline+b'}'+newline)
    atomic_text(path, '{\n  "a": 1\n}\n')
    assert path.read_bytes() == b'{'+newline+b'  "a": 1'+newline+b'}'+newline
    assert json.loads(path.read_bytes()) == {'a': 1}


def test_checked_in_fit_matches_source():
    root = Path(__file__).resolve().parents[1]
    cfg = json.loads((root/'data/mstr-config.json').read_text())
    frame = pd.read_csv(root/'data/mstr-daily.csv').dropna(subset=['strc'])
    result = measure(frame)
    for key in ('a', 'b', 'c', 'r2', 'p25', 'p75'):
        assert cfg['fit'][key] == pytest.approx(result[key])
    assert cfg['gap_centre'] == 0
    assert cfg['btc_slope_per_2500'] == cfg['fit']['b']
    for key, quantile in [('cheap_threshold','p25'), ('rich_threshold','p75')]:
        assert cfg[key] == pytest.approx(cfg['premium'][quantile])

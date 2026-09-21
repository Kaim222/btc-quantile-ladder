"""Causality and integration checks for the premium baseline."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from mnav_fit import coefficients, target
from premium_test import premium_object, premiums, study, lookup_gate
from test_mnav_fit import panel


def test_completed_window_and_additive_excess():
    f = panel(-.003)
    fit = coefficients(f)
    p = np.linspace(-.12, .12, len(f))
    f['mstr'] *= 1+p
    value = premium_object(f, fit, 10)
    assert value['average'] == pytest.approx(p[-10:].mean())
    assert value['from'] == f.d.iloc[-10]
    assert value['to'] == f.d.iloc[-1]
    excess = p[10:] - pd.Series(p).shift().rolling(10).mean().to_numpy()[10:]
    assert value['p25'] == pytest.approx(np.quantile(excess,.25))
    assert value['median_abs_pct'] == pytest.approx(np.median(100*np.abs(excess/(1+p[10:]-excess))))


def test_walk_forward_does_not_see_future(monkeypatch):
    import premium_test
    f = panel(-.003)
    f['mstr'] *= 1 + .07*np.sin(np.arange(len(f)) / 9)
    dates = pd.date_range('2024-01-01','2026-01-01')
    btc = pd.Series(90000.0,index=dates)
    calls=[]
    original=coefficients
    def fit(rows):
        calls.append(len(rows))
        return original(rows)
    monkeypatch.setattr(premium_test,'coefficients',fit)
    a=study(f,btc)
    assert calls == [len(f)] + list(range(120,len(f)))
    changed=f.copy()
    changed.loc[len(f)-1,'mstr'] *= 2
    b=study(changed,btc)
    # The only forecasts reaching the changed close are the final endpoint.
    # Directly check the state used at a chosen origin excludes its own close.
    i=130
    fit_a=original(f.iloc[:i]); fit_b=original(changed.iloc[:i])
    assert fit_a == fit_b
    assert premiums(f.iloc[:i],fit_a).tail(10).mean() == premiums(changed.iloc[:i],fit_b).tail(10).mean()
    assert len(a['forecasts']) == len(b['forecasts']) == 210
    for r in a['forecasts']:
        if r['sample']=='all': assert r['count']==len(f)-120-r['horizon']


def test_refresh_publishes_configured_premium():
    from model_refresh import build_model
    root=Path(__file__).resolve().parents[1]
    config=json.loads((root/'data/mstr-config.json').read_text())
    d=pd.read_csv(root/'data/mstr-daily.csv')
    e,model=build_model(d,config['fit'],config['cheap_threshold']*100,config['premium']['n'])
    assert model['premium'] == premium_object(e,config['fit'],10)
    row=model['series'][-1]
    line=e.proj.iloc[-1]
    prior=e.gap.iloc[-11:-1].mean()
    assert row['fair']==pytest.approx(line*(1+prior))
    assert row['excess']==pytest.approx(100*(e.gap.iloc[-1]-prior))
    assert model['premium']['average'] != pytest.approx(prior)
    assert config['cheap_threshold']==pytest.approx(model['premium']['p25'])
    assert config['rich_threshold']==pytest.approx(model['premium']['p75'])


def test_lookup_gate_requires_both_metrics_samples_and_two_horizons():
    rows=[]
    for h in (5,20,40):
        for sample in ('all','last120'):
            for half in ('static','5','10','20','40'):
                rows.append(dict(n=10,horizon=h,sample=sample,half=half,median=10,mean=12))
    for row in rows:
        if row['half']=='10' and row['horizon'] in (5,20):
            row.update(median=9,mean=11)
    assert lookup_gate(rows,10)['changed']
    row=next(r for r in rows if r['half']=='10' and r['horizon']==20 and r['sample']=='last120')
    row['mean']=12
    assert not lookup_gate(rows,10)['changed']
    assert lookup_gate(rows,10)['winning_horizons']['10']==[5]

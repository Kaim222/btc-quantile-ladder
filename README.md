# BTC Quantile Ladder

A passcode-gated static site in `index.html`: React with browser Babel and inline styles; no build step.

- **Ladder:** the power-law quantile model (v2), monthly-close instrument bands at 10 / 60 / 75, strikes, forward band
  prices, lookups and the chart.
- **Strategy:** the monitor's lag and level reads for MSTX, the alert log, the gap chart, what-if inputs, the Bitcoin price
  lookup and the mNAV history.
- **Playbook:** the data verdict, the evidence, the open Phase 1 position with its exit rules, LEAPS units and the weekly MACD.

Data and writers:

- `data/ladder-model.json`: the quantile model's constants, written by `tools/model_refit.py --write` once a year and copied
  into `index.html`, the monitor and `tools/playbook_refresh.py` by `tools/model_sync.py`. `index.html?model=v1` shows the
  original model.
- `data/ladder-rules.json`: operator-maintained rules and sizing. Its history block comes from `tools/ladder_band_history.py`.
- `data/paper-ledger.json`: operator-maintained positions, phases and settlement values.
- `data/mstr-config.json`: operator-maintained thresholds, gates, slopes and holdings overrides; shared with the monitor.
- Refreshed by `.github/workflows/refresh.yml` on weekdays: `data/leaps-cost.json` (`tools/leaps_cost.py`),
  `data/mstr-daily.csv`, `data/mstr-model.json`, `data/mnav-history.json` and `data/evidence.json` (`tools/model_refresh.py`),
  `data/routes.json` (`tools/routes_refresh.py`), `data/playbook.json` and `data/iv-ledger.json` (`tools/playbook_refresh.py`,
  which uses `tools/playbook_rules.json` and `tools/events.json`).

Studies, not part of the refresh: `tools/model_audit.py`, `tools/model_refit_explore.py`, `tools/ladder_cutpoints_study.py`,
`tools/ladder_bands_study.py`. `tools/measure_ui.js` is the acceptance check in `tools/DESIGN-STANDARD.md`. `BUILD-NOTES.md`
holds the design history. `consider-deleting/` holds files nothing references, kept until the owner removes them.

Serve locally with `python -m http.server`; the browser normally loads CDN libraries and market feeds.

The separate [btc-monitor repository](https://github.com/Kaim222/btc-monitor) runs the alert monitor.
It writes `mstr_state.json` (including `last_run`) and `mstr_ledger.json`, fetched by the Strategy tab.
Notifications originate in that repository, not this site.

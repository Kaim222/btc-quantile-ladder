# BTC Quantile Ladder + Signals

A static GitHub Pages research site with three passcode-gated tabs:

- **Ladder** — the existing BTC power-law quantile and planning dashboard.
- **Signals** — capped 24-hour, 7-day, and 30-day directional estimates with a permanent, self-scoring ledger.
- **EO Tracker** — an anonymized, measured pick ledger and posting-window tracker.

## Optional alerts

Set `ntfy_topic` in `config/manual.json` to a long, random topic string to receive verdict, newly armed, and multi-source-failure alerts. Leave it empty to disable alerts. ntfy topics are public-by-obscurity, and alerts never contain manual configuration values.

## Doctrine

- Honest edges only: probabilities are capped, records include Wilson 95% confidence intervals, fewer than 30 resolved calls are labeled warming up, and intervals spanning the relevant baseline are labeled no edge yet.
- Every snapshot is appended and later resolves at its horizon. Composite and individual signals are scored. Live, backtest, and pooled records remain distinct.
- Every source is free and keyless. The repository contains no secrets.
- The UI never hardcodes accuracy. Displayed records come from `data/scores.json`; outside studies are clearly labeled “published, not ours.”

## Architecture

```text
keyless public APIs + config/*.json
               |
       collector/collect.py  -- every 6h --> data/latest.json
               |                              data/news.json
               +----------------------------> data/ledger.json (append-only)
                                                        |
collector/backfill.py (daily history) ------------------+
                                                        |
                         collector/score.py ------------+--> data/scores.json
                                                               |
                                               signals.html <--+
```

`collector/lib.py` is the shared source for signal computation, composite caps/gates, outcome resolution, Wilson intervals, Brier scores, and score aggregation. `backfill.py` uses only inputs available on each historical date, renormalizes over available signals, and never overwrites live rows. The five operator-maintained signals (dat_stress, polymarket_ye, gli_phase, cwac_analyst, ism_regime) have no per-date history, so they are excluded from backtest rows entirely — backtest composites are computed without them and their weight is renormalized away.

Calls resolve after 24 hours, 7 days, or 30 days using deadbands of ±0.75%, ±2%, and ±5%. BULL must resolve UP, BEAR must resolve DOWN, and FLAT must remain inside its deadband. Abstentions do not enter hit-rate samples. A signal is scored only when its absolute score is at least 1. FLAT counts as not-UP in the composite binary Brier score.

Run locally with Python 3.11+ and `requests`:

```sh
python collector/collect.py
python collector/score.py
python collector/backfill.py
python -m http.server
```

Personal research tool. Not financial advice.

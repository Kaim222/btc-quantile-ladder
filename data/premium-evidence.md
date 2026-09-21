# Recent premium evidence

Source data has 287 STRC era sessions from 2025-07-30 through 2026-09-18.

Daily Bitcoin for regime labels is frozen in premium-btc-daily.csv from the existing Yahoo daily cache at ../mstr-mnav-model/v2/panel_yf_cache.csv. All 506 calendar days from 2025-05-01 through 2026-09-18 are present. The regime uses the previous completed UTC close and its 50 calendar day average.

Source SHA256 2c4b3ea85bc27fcd646d4f5e41135c5c8c7c701e81033e8bbdd6cd5bc4a74c59

Full sample constants are descriptive only. Walk means at least 120 strictly earlier rows.
Same day headline is abs(actual/fair-1), matching the supplied table. Actual denominator is also reported.
Prior window excludes today. All means all eligible sessions. Last120 selects origin dates.
Shrink share is directional contraction at the endpoint. Within share counts any earlier contraction.
Median change is signed percentage points. First contraction speed is conditional on contraction within the horizon.
Regime uses previous completed UTC BTC day versus its 50 calendar day SMA.
Forecast endpoints overlap. Given future BTC and STRC is conditional valuation, not a tradable forecast.
Window and half life selection on these scores remains model selection, not an untouched holdout.

## Same day miss

Cells are median / mean percent. Denominator is fair value, matching the supplied measurements. Full fit is descriptive. Walk forward excludes each scored session and uses at least 120 earlier sessions. Each all sample starts when its window is available. All walk forward rows have 167 sessions and recent rows have 120. The JSON also reports misses with actual MSTR as denominator.

| N | Full all | Full recent | Walk all | Walk recent |
|---|---|---|---|---|
| Static | 9.32 / 9.83 | 5.76 / 6.89 | 8.40 / 13.31 | 6.75 / 7.52 |
| 3 | 2.33 / 2.84 | 2.33 / 2.82 | 2.63 / 3.64 | 2.51 / 2.97 |
| 5 | 2.69 / 3.41 | 2.60 / 3.33 | 2.73 / 4.43 | 2.59 / 3.45 |
| 10 | 3.65 / 4.49 | 3.53 / 4.39 | 3.64 / 6.23 | 3.42 / 4.44 |
| 15 | 4.06 / 5.16 | 4.27 / 4.91 | 4.41 / 7.65 | 4.08 / 4.98 |
| 20 | 4.19 / 5.77 | 4.14 / 5.15 | 4.33 / 8.71 | 4.07 / 5.30 |
| 40 | 6.12 / 8.01 | 4.19 / 5.56 | 5.08 / 11.24 | 4.06 / 6.01 |
| 60 | 7.59 / 9.84 | 5.56 / 6.23 | 7.31 / 13.03 | 5.74 / 6.80 |

## Shrinkage full

Each event is the first session of a separate stretch at or beyond +4 or -4 excess percentage points. Missing future endpoints are excluded from that horizon. Endpoint contraction is signed movement toward the original baseline and may cross zero. Within counts any contraction observed by that horizon. Speed is the median first session of contraction among events that contracted within that horizon. Frozen holds the event baseline and fitted coefficients fixed, distinguishing actual premium contraction from the moving baseline absorbing a jump.

| N | Side | BTC regime | Events | H | Scored | Endpoint share | Median change pp | Within share | First session | Frozen share | Frozen change pp |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | +4 | all | 21 | 5 | 20 | 90.0% | -6.1 | 95.0% | 1.0 | 65.0% | -2.0 |
| 3 | +4 | all | 21 | 10 | 19 | 84.2% | -5.4 | 100.0% | 1.0 | 63.2% | -4.0 |
| 3 | +4 | above | 10 | 5 | 9 | 100.0% | -5.1 | 100.0% | 1.0 | 55.6% | -0.3 |
| 3 | +4 | above | 10 | 10 | 8 | 87.5% | -5.0 | 100.0% | 1.0 | 37.5% | 1.3 |
| 3 | +4 | below | 11 | 5 | 11 | 81.8% | -7.0 | 90.9% | 1.0 | 72.7% | -4.0 |
| 3 | +4 | below | 11 | 10 | 11 | 81.8% | -5.4 | 100.0% | 1.0 | 81.8% | -6.0 |
| 3 | -4 | all | 23 | 5 | 23 | 91.3% | 4.9 | 100.0% | 1.0 | 34.8% | -2.5 |
| 3 | -4 | all | 23 | 10 | 23 | 91.3% | 5.0 | 100.0% | 1.0 | 34.8% | -1.8 |
| 3 | -4 | above | 8 | 5 | 8 | 100.0% | 6.9 | 100.0% | 1.0 | 50.0% | -1.8 |
| 3 | -4 | above | 8 | 10 | 8 | 87.5% | 8.5 | 100.0% | 1.0 | 75.0% | 4.5 |
| 3 | -4 | below | 15 | 5 | 15 | 86.7% | 3.6 | 100.0% | 1.0 | 26.7% | -2.5 |
| 3 | -4 | below | 15 | 10 | 15 | 93.3% | 3.6 | 100.0% | 1.0 | 13.3% | -3.9 |
| 5 | +4 | all | 21 | 5 | 20 | 85.0% | -6.1 | 100.0% | 1.0 | 70.0% | -2.0 |
| 5 | +4 | all | 21 | 10 | 19 | 89.5% | -6.5 | 100.0% | 1.0 | 57.9% | -2.7 |
| 5 | +4 | above | 8 | 5 | 7 | 100.0% | -5.4 | 100.0% | 1.0 | 57.1% | -0.3 |
| 5 | +4 | above | 8 | 10 | 6 | 100.0% | -7.4 | 100.0% | 1.5 | 33.3% | 1.3 |
| 5 | +4 | below | 13 | 5 | 13 | 76.9% | -8.2 | 100.0% | 1.0 | 76.9% | -4.0 |
| 5 | +4 | below | 13 | 10 | 13 | 84.6% | -4.6 | 100.0% | 1.0 | 69.2% | -6.0 |
| 5 | -4 | all | 22 | 5 | 22 | 95.5% | 3.8 | 100.0% | 1.0 | 27.3% | -3.0 |
| 5 | -4 | all | 22 | 10 | 22 | 90.9% | 5.1 | 100.0% | 1.0 | 40.9% | -2.3 |
| 5 | -4 | above | 7 | 5 | 7 | 100.0% | 5.0 | 100.0% | 1.0 | 42.9% | -4.4 |
| 5 | -4 | above | 7 | 10 | 7 | 85.7% | 9.1 | 100.0% | 1.0 | 71.4% | 1.7 |
| 5 | -4 | below | 15 | 5 | 15 | 93.3% | 2.7 | 100.0% | 1.0 | 20.0% | -2.8 |
| 5 | -4 | below | 15 | 10 | 15 | 93.3% | 3.9 | 100.0% | 1.0 | 26.7% | -3.9 |
| 10 | +4 | all | 16 | 5 | 15 | 80.0% | -5.2 | 93.3% | 1.0 | 66.7% | -3.6 |
| 10 | +4 | all | 16 | 10 | 15 | 80.0% | -8.3 | 93.3% | 1.0 | 66.7% | -6.7 |
| 10 | +4 | above | 5 | 5 | 4 | 100.0% | -3.7 | 100.0% | 2.5 | 50.0% | -0.1 |
| 10 | +4 | above | 5 | 10 | 4 | 75.0% | -7.3 | 100.0% | 2.5 | 50.0% | -0.3 |
| 10 | +4 | below | 11 | 5 | 11 | 72.7% | -6.9 | 90.9% | 1.0 | 72.7% | -4.0 |
| 10 | +4 | below | 11 | 10 | 11 | 81.8% | -8.3 | 90.9% | 1.0 | 72.7% | -7.2 |
| 10 | -4 | all | 21 | 5 | 21 | 71.4% | 2.7 | 95.2% | 1.0 | 33.3% | -1.4 |
| 10 | -4 | all | 21 | 10 | 21 | 95.2% | 4.7 | 100.0% | 1.0 | 38.1% | -0.7 |
| 10 | -4 | above | 7 | 5 | 7 | 71.4% | 3.2 | 85.7% | 1.0 | 71.4% | 1.4 |
| 10 | -4 | above | 7 | 10 | 7 | 85.7% | 4.6 | 100.0% | 1.0 | 42.9% | -0.7 |
| 10 | -4 | below | 14 | 5 | 14 | 71.4% | 1.3 | 100.0% | 1.0 | 14.3% | -2.7 |
| 10 | -4 | below | 14 | 10 | 14 | 100.0% | 5.6 | 100.0% | 1.0 | 35.7% | -0.7 |
| 15 | +4 | all | 17 | 5 | 15 | 73.3% | -2.8 | 86.7% | 1.0 | 66.7% | -2.4 |
| 15 | +4 | all | 17 | 10 | 14 | 85.7% | -5.3 | 92.9% | 1.0 | 64.3% | -6.8 |
| 15 | +4 | above | 8 | 5 | 6 | 83.3% | -2.1 | 83.3% | 1.0 | 66.7% | -0.4 |
| 15 | +4 | above | 8 | 10 | 5 | 100.0% | -4.5 | 100.0% | 1.0 | 60.0% | -2.5 |
| 15 | +4 | below | 9 | 5 | 9 | 66.7% | -7.4 | 88.9% | 1.0 | 66.7% | -7.4 |
| 15 | +4 | below | 9 | 10 | 9 | 77.8% | -9.3 | 88.9% | 1.0 | 66.7% | -7.4 |
| 15 | -4 | all | 22 | 5 | 22 | 63.6% | 1.0 | 86.4% | 1.0 | 45.5% | -0.8 |
| 15 | -4 | all | 22 | 10 | 22 | 81.8% | 3.7 | 100.0% | 2.0 | 40.9% | -0.7 |
| 15 | -4 | above | 7 | 5 | 7 | 57.1% | 1.3 | 71.4% | 2.0 | 57.1% | 0.7 |
| 15 | -4 | above | 7 | 10 | 7 | 85.7% | 6.6 | 100.0% | 2.0 | 57.1% | 0.7 |
| 15 | -4 | below | 15 | 5 | 15 | 66.7% | 0.8 | 93.3% | 1.0 | 40.0% | -1.4 |
| 15 | -4 | below | 15 | 10 | 15 | 80.0% | 3.6 | 100.0% | 1.0 | 33.3% | -0.9 |
| 20 | +4 | all | 13 | 5 | 11 | 72.7% | -5.4 | 90.9% | 1.0 | 63.6% | -5.9 |
| 20 | +4 | all | 13 | 10 | 10 | 70.0% | -6.8 | 90.0% | 1.0 | 70.0% | -7.5 |
| 20 | +4 | above | 6 | 5 | 4 | 100.0% | -5.1 | 100.0% | 1.0 | 75.0% | -5.4 |
| 20 | +4 | above | 6 | 10 | 3 | 100.0% | -7.2 | 100.0% | 1.0 | 100.0% | -8.2 |
| 20 | +4 | below | 7 | 5 | 7 | 57.1% | -5.4 | 85.7% | 1.0 | 57.1% | -5.9 |
| 20 | +4 | below | 7 | 10 | 7 | 57.1% | -5.0 | 85.7% | 1.0 | 57.1% | -6.7 |
| 20 | -4 | all | 17 | 5 | 17 | 58.8% | 0.9 | 94.1% | 1.0 | 41.2% | -0.5 |
| 20 | -4 | all | 17 | 10 | 17 | 70.6% | 1.8 | 100.0% | 1.0 | 29.4% | -0.9 |
| 20 | -4 | above | 5 | 5 | 5 | 80.0% | 4.4 | 100.0% | 2.0 | 80.0% | 2.6 |
| 20 | -4 | above | 5 | 10 | 5 | 80.0% | 7.6 | 100.0% | 2.0 | 60.0% | 5.2 |
| 20 | -4 | below | 12 | 5 | 12 | 50.0% | -0.1 | 91.7% | 1.0 | 25.0% | -1.9 |
| 20 | -4 | below | 12 | 10 | 12 | 66.7% | 1.3 | 100.0% | 1.0 | 16.7% | -1.9 |
| 40 | +4 | all | 9 | 5 | 8 | 75.0% | -6.0 | 87.5% | 1.0 | 75.0% | -3.7 |
| 40 | +4 | all | 9 | 10 | 7 | 71.4% | -12.9 | 85.7% | 1.0 | 71.4% | -8.2 |
| 40 | +4 | above | 5 | 5 | 4 | 100.0% | -6.0 | 100.0% | 1.0 | 100.0% | -3.7 |
| 40 | +4 | above | 5 | 10 | 3 | 100.0% | -12.9 | 100.0% | 1.0 | 100.0% | -8.2 |
| 40 | +4 | below | 4 | 5 | 4 | 50.0% | 0.4 | 75.0% | 1.0 | 50.0% | 1.3 |
| 40 | +4 | below | 4 | 10 | 4 | 50.0% | -6.0 | 75.0% | 1.0 | 50.0% | -4.8 |
| 40 | -4 | all | 17 | 5 | 17 | 47.1% | -0.2 | 82.4% | 1.0 | 29.4% | -1.1 |
| 40 | -4 | all | 17 | 10 | 17 | 47.1% | -0.6 | 88.2% | 1.0 | 29.4% | -2.8 |
| 40 | -4 | above | 5 | 5 | 5 | 100.0% | 3.9 | 100.0% | 1.0 | 80.0% | 2.1 |
| 40 | -4 | above | 5 | 10 | 5 | 100.0% | 7.8 | 100.0% | 1.0 | 80.0% | 5.2 |
| 40 | -4 | below | 12 | 5 | 12 | 25.0% | -2.0 | 75.0% | 1.0 | 8.3% | -3.4 |
| 40 | -4 | below | 12 | 10 | 12 | 25.0% | -2.8 | 83.3% | 1.5 | 8.3% | -6.1 |
| 60 | +4 | all | 6 | 5 | 5 | 60.0% | -10.9 | 100.0% | 1.0 | 60.0% | -8.4 |
| 60 | +4 | all | 6 | 10 | 5 | 80.0% | -4.4 | 100.0% | 1.0 | 60.0% | -4.0 |
| 60 | +4 | above | 2 | 5 | 1 | 100.0% | -10.9 | 100.0% | 1.0 | 100.0% | -8.4 |
| 60 | +4 | above | 2 | 10 | 1 | 100.0% | -11.9 | 100.0% | 1.0 | 100.0% | -8.2 |
| 60 | +4 | below | 4 | 5 | 4 | 50.0% | -6.5 | 100.0% | 1.0 | 50.0% | -6.0 |
| 60 | +4 | below | 4 | 10 | 4 | 75.0% | -2.9 | 100.0% | 1.0 | 50.0% | -0.9 |
| 60 | -4 | all | 16 | 5 | 16 | 25.0% | -0.9 | 81.2% | 1.0 | 25.0% | -1.7 |
| 60 | -4 | all | 16 | 10 | 16 | 43.8% | -0.6 | 93.8% | 1.0 | 18.8% | -2.9 |
| 60 | -4 | above | 8 | 5 | 8 | 12.5% | -1.4 | 75.0% | 1.0 | 25.0% | -1.7 |
| 60 | -4 | above | 8 | 10 | 8 | 50.0% | -0.0 | 100.0% | 1.5 | 25.0% | -1.3 |
| 60 | -4 | below | 8 | 5 | 8 | 37.5% | -0.8 | 87.5% | 1.0 | 25.0% | -2.2 |
| 60 | -4 | below | 8 | 10 | 8 | 37.5% | -2.0 | 87.5% | 1.0 | 12.5% | -5.1 |

## Shrinkage walk

Each event is the first session of a separate stretch at or beyond +4 or -4 excess percentage points. Missing future endpoints are excluded from that horizon. Endpoint contraction is signed movement toward the original baseline and may cross zero. Within counts any contraction observed by that horizon. Speed is the median first session of contraction among events that contracted within that horizon. Frozen holds the event baseline and fitted coefficients fixed, distinguishing actual premium contraction from the moving baseline absorbing a jump.

| N | Side | BTC regime | Events | H | Scored | Endpoint share | Median change pp | Within share | First session | Frozen share | Frozen change pp |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | +4 | all | 16 | 5 | 15 | 73.3% | -3.9 | 93.3% | 1.0 | 53.3% | -1.0 |
| 3 | +4 | all | 16 | 10 | 14 | 85.7% | -4.5 | 100.0% | 1.0 | 42.9% | 2.0 |
| 3 | +4 | above | 6 | 5 | 5 | 100.0% | -3.9 | 100.0% | 1.0 | 60.0% | -1.0 |
| 3 | +4 | above | 6 | 10 | 4 | 100.0% | -4.9 | 100.0% | 1.0 | 25.0% | 2.0 |
| 3 | +4 | below | 10 | 5 | 10 | 60.0% | -3.7 | 90.0% | 1.0 | 50.0% | -3.2 |
| 3 | +4 | below | 10 | 10 | 10 | 80.0% | -4.3 | 100.0% | 1.0 | 50.0% | -1.9 |
| 3 | -4 | all | 14 | 5 | 14 | 85.7% | 6.2 | 100.0% | 1.0 | 35.7% | -3.2 |
| 3 | -4 | all | 14 | 10 | 14 | 100.0% | 5.3 | 100.0% | 1.0 | 28.6% | -2.3 |
| 3 | -4 | above | 5 | 5 | 5 | 100.0% | 7.8 | 100.0% | 1.0 | 60.0% | 0.5 |
| 3 | -4 | above | 5 | 10 | 5 | 100.0% | 8.1 | 100.0% | 1.0 | 80.0% | 5.3 |
| 3 | -4 | below | 9 | 5 | 9 | 77.8% | 2.9 | 100.0% | 1.0 | 22.2% | -4.0 |
| 3 | -4 | below | 9 | 10 | 9 | 100.0% | 4.2 | 100.0% | 1.0 | 0.0% | -7.3 |
| 5 | +4 | all | 15 | 5 | 14 | 85.7% | -8.1 | 92.9% | 1.0 | 57.1% | -1.7 |
| 5 | +4 | all | 15 | 10 | 13 | 84.6% | -6.6 | 92.3% | 1.0 | 53.8% | -5.9 |
| 5 | +4 | above | 5 | 5 | 4 | 100.0% | -5.4 | 100.0% | 1.0 | 50.0% | 0.1 |
| 5 | +4 | above | 5 | 10 | 3 | 100.0% | -6.4 | 100.0% | 1.0 | 0.0% | 2.0 |
| 5 | +4 | below | 10 | 5 | 10 | 80.0% | -9.8 | 90.0% | 1.0 | 60.0% | -8.0 |
| 5 | +4 | below | 10 | 10 | 10 | 80.0% | -7.0 | 90.0% | 1.0 | 70.0% | -7.8 |
| 5 | -4 | all | 12 | 5 | 12 | 66.7% | 3.8 | 100.0% | 1.0 | 25.0% | -4.2 |
| 5 | -4 | all | 12 | 10 | 12 | 83.3% | 4.8 | 100.0% | 1.0 | 25.0% | -4.2 |
| 5 | -4 | above | 4 | 5 | 4 | 100.0% | 5.6 | 100.0% | 1.0 | 50.0% | -1.9 |
| 5 | -4 | above | 4 | 10 | 4 | 100.0% | 7.7 | 100.0% | 1.0 | 75.0% | 2.7 |
| 5 | -4 | below | 8 | 5 | 8 | 50.0% | 1.3 | 100.0% | 1.0 | 12.5% | -5.1 |
| 5 | -4 | below | 8 | 10 | 8 | 75.0% | 3.9 | 100.0% | 1.0 | 0.0% | -8.2 |
| 10 | +4 | all | 11 | 5 | 10 | 80.0% | -3.6 | 90.0% | 1.0 | 50.0% | -0.4 |
| 10 | +4 | all | 11 | 10 | 10 | 70.0% | -8.0 | 90.0% | 1.0 | 50.0% | -0.2 |
| 10 | +4 | above | 4 | 5 | 3 | 100.0% | -3.4 | 100.0% | 3.0 | 33.3% | 0.8 |
| 10 | +4 | above | 4 | 10 | 3 | 66.7% | -3.0 | 100.0% | 3.0 | 33.3% | 1.9 |
| 10 | +4 | below | 7 | 5 | 7 | 71.4% | -6.9 | 85.7% | 1.0 | 57.1% | -7.7 |
| 10 | +4 | below | 7 | 10 | 7 | 71.4% | -10.4 | 85.7% | 1.0 | 57.1% | -8.2 |
| 10 | -4 | all | 9 | 5 | 9 | 55.6% | 3.4 | 100.0% | 1.0 | 44.4% | -0.0 |
| 10 | -4 | all | 9 | 10 | 9 | 100.0% | 5.8 | 100.0% | 1.0 | 44.4% | -0.4 |
| 10 | -4 | above | 4 | 5 | 4 | 75.0% | 3.4 | 100.0% | 1.0 | 50.0% | 1.0 |
| 10 | -4 | above | 4 | 10 | 4 | 100.0% | 5.3 | 100.0% | 1.0 | 75.0% | 2.4 |
| 10 | -4 | below | 5 | 5 | 5 | 40.0% | -0.8 | 100.0% | 1.0 | 40.0% | -2.5 |
| 10 | -4 | below | 5 | 10 | 5 | 100.0% | 5.8 | 100.0% | 1.0 | 20.0% | -3.3 |
| 15 | +4 | all | 12 | 5 | 10 | 70.0% | -2.2 | 80.0% | 1.0 | 50.0% | -0.0 |
| 15 | +4 | all | 12 | 10 | 9 | 77.8% | -4.1 | 88.9% | 1.5 | 55.6% | -2.3 |
| 15 | +4 | above | 5 | 5 | 3 | 66.7% | -1.0 | 66.7% | 1.0 | 66.7% | -0.2 |
| 15 | +4 | above | 5 | 10 | 2 | 100.0% | -2.7 | 100.0% | 3.5 | 50.0% | -0.6 |
| 15 | +4 | below | 7 | 5 | 7 | 71.4% | -3.0 | 85.7% | 1.5 | 42.9% | 0.1 |
| 15 | +4 | below | 7 | 10 | 7 | 71.4% | -11.0 | 85.7% | 1.5 | 57.1% | -5.9 |
| 15 | -4 | all | 10 | 5 | 10 | 60.0% | 2.3 | 80.0% | 1.0 | 50.0% | -1.9 |
| 15 | -4 | all | 10 | 10 | 10 | 90.0% | 5.4 | 90.0% | 1.0 | 50.0% | 0.7 |
| 15 | -4 | above | 5 | 5 | 5 | 60.0% | 7.1 | 80.0% | 1.5 | 60.0% | 4.1 |
| 15 | -4 | above | 5 | 10 | 5 | 100.0% | 10.1 | 100.0% | 2.0 | 80.0% | 6.4 |
| 15 | -4 | below | 5 | 5 | 5 | 60.0% | 2.0 | 80.0% | 1.0 | 40.0% | -4.0 |
| 15 | -4 | below | 5 | 10 | 5 | 80.0% | 4.1 | 80.0% | 1.0 | 20.0% | -3.3 |
| 20 | +4 | all | 11 | 5 | 9 | 66.7% | -1.7 | 88.9% | 1.0 | 44.4% | 0.1 |
| 20 | +4 | all | 11 | 10 | 8 | 75.0% | -6.4 | 87.5% | 1.0 | 62.5% | -6.1 |
| 20 | +4 | above | 6 | 5 | 4 | 100.0% | -5.0 | 100.0% | 1.0 | 75.0% | -5.4 |
| 20 | +4 | above | 6 | 10 | 3 | 100.0% | -6.8 | 100.0% | 1.0 | 100.0% | -8.0 |
| 20 | +4 | below | 5 | 5 | 5 | 40.0% | 9.9 | 80.0% | 1.5 | 20.0% | 11.3 |
| 20 | +4 | below | 5 | 10 | 5 | 60.0% | -0.2 | 80.0% | 1.5 | 40.0% | 3.0 |
| 20 | -4 | all | 6 | 5 | 6 | 50.0% | 0.6 | 100.0% | 1.0 | 66.7% | 0.9 |
| 20 | -4 | all | 6 | 10 | 6 | 83.3% | 2.8 | 100.0% | 1.0 | 50.0% | 0.7 |
| 20 | -4 | above | 2 | 5 | 2 | 100.0% | 4.8 | 100.0% | 2.5 | 100.0% | 3.1 |
| 20 | -4 | above | 2 | 10 | 2 | 100.0% | 11.9 | 100.0% | 2.5 | 100.0% | 10.1 |
| 20 | -4 | below | 4 | 5 | 4 | 25.0% | -3.4 | 100.0% | 1.0 | 50.0% | -4.5 |
| 20 | -4 | below | 4 | 10 | 4 | 75.0% | 1.9 | 100.0% | 1.0 | 25.0% | -1.8 |
| 40 | +4 | all | 11 | 5 | 10 | 70.0% | -3.7 | 90.0% | 1.0 | 60.0% | -1.5 |
| 40 | +4 | all | 11 | 10 | 9 | 77.8% | -9.3 | 88.9% | 1.0 | 66.7% | -5.9 |
| 40 | +4 | above | 5 | 5 | 4 | 100.0% | -6.0 | 100.0% | 1.0 | 100.0% | -3.7 |
| 40 | +4 | above | 5 | 10 | 3 | 100.0% | -13.2 | 100.0% | 1.0 | 100.0% | -8.0 |
| 40 | +4 | below | 6 | 5 | 6 | 50.0% | 3.9 | 83.3% | 1.0 | 33.3% | 5.8 |
| 40 | +4 | below | 6 | 10 | 6 | 66.7% | -4.9 | 83.3% | 1.0 | 50.0% | -1.5 |
| 40 | -4 | all | 6 | 5 | 6 | 66.7% | 3.3 | 100.0% | 1.0 | 66.7% | 1.9 |
| 40 | -4 | all | 6 | 10 | 6 | 66.7% | 2.2 | 100.0% | 1.0 | 50.0% | -0.5 |
| 40 | -4 | above | 4 | 5 | 4 | 100.0% | 3.8 | 100.0% | 1.5 | 100.0% | 2.0 |
| 40 | -4 | above | 4 | 10 | 4 | 100.0% | 5.6 | 100.0% | 1.5 | 75.0% | 3.4 |
| 40 | -4 | below | 2 | 5 | 2 | 0.0% | -11.1 | 100.0% | 1.0 | 0.0% | -12.0 |
| 40 | -4 | below | 2 | 10 | 2 | 0.0% | -1.7 | 100.0% | 1.0 | 0.0% | -4.7 |
| 60 | +4 | all | 6 | 5 | 5 | 60.0% | -9.0 | 80.0% | 1.0 | 60.0% | -8.4 |
| 60 | +4 | all | 6 | 10 | 5 | 60.0% | -11.3 | 80.0% | 1.0 | 60.0% | -8.0 |
| 60 | +4 | above | 2 | 5 | 1 | 100.0% | -10.7 | 100.0% | 1.0 | 100.0% | -8.4 |
| 60 | +4 | above | 2 | 10 | 1 | 100.0% | -11.3 | 100.0% | 1.0 | 100.0% | -8.0 |
| 60 | +4 | below | 4 | 5 | 4 | 50.0% | 8.0 | 75.0% | 1.0 | 50.0% | 8.9 |
| 60 | +4 | below | 4 | 10 | 4 | 50.0% | 19.5 | 75.0% | 1.0 | 50.0% | 31.5 |
| 60 | -4 | all | 10 | 5 | 10 | 20.0% | -1.6 | 80.0% | 1.0 | 30.0% | -2.9 |
| 60 | -4 | all | 10 | 10 | 10 | 50.0% | -0.6 | 100.0% | 1.0 | 30.0% | -2.5 |
| 60 | -4 | above | 8 | 5 | 8 | 25.0% | -0.7 | 75.0% | 1.0 | 37.5% | -1.7 |
| 60 | -4 | above | 8 | 10 | 8 | 62.5% | 0.9 | 100.0% | 1.0 | 37.5% | -1.3 |
| 60 | -4 | below | 2 | 5 | 2 | 0.0% | -7.9 | 100.0% | 1.0 | 0.0% | -9.4 |
| 60 | -4 | below | 2 | 10 | 2 | 0.0% | -4.0 | 100.0% | 1.0 | 0.0% | -6.7 |

## Pick

No window clearly separates on durable contraction across both Bitcoin regimes. Short windows lower same-day miss but absorb jumps quickly. Frozen-baseline contraction is inconsistent. Use Alex's fallback of 10 sessions, balancing a low miss with a slower baseline.

The supplied N20 result reproduces exactly on the common cohort of ten events with complete ten-session follow-up. Seven of ten shrink at five sessions with median change -5.99 points. Seven of ten shrink at ten sessions with median change -6.79 points. There are 13 total positive starts, 11 with five future sessions and 10 with ten. Including the additional five-session event gives 8 of 11 at five. The detailed tables use each horizon's available events rather than throwing away that newer observation.

## Dated predictions for N10

Given destination Bitcoin and STRC, origin Bitcoin per share stays fixed. All fits use only earlier rows. Miss is absolute predicted / actual minus one. Half lives 5 through 40 are sessions. Static is the unchanged 28 calendar day decay. Last120 selects origins in the last 120 source rows, leaving 115, 100, and 80 eligible origins at the three horizons. All counts are 162, 147, and 127.

| Horizon | Half life | All median / mean | Recent median / mean |
|---|---|---|---|
| 5 | static | 3.67 / 6.41 | 3.26 / 4.93 |
| 5 | 5 | 4.10 / 7.20 | 3.81 / 5.40 |
| 5 | 10 | 4.35 / 6.63 | 3.67 / 5.06 |
| 5 | 20 | 4.43 / 6.38 | 3.47 / 4.99 |
| 5 | 40 | 4.42 / 6.30 | 3.42 / 4.99 |
| 20 | static | 10.07 / 13.45 | 10.56 / 11.51 |
| 20 | 5 | 8.00 / 12.93 | 7.84 / 9.99 |
| 20 | 10 | 8.07 / 12.49 | 8.00 / 9.84 |
| 20 | 20 | 7.65 / 11.98 | 7.63 / 9.68 |
| 20 | 40 | 7.58 / 11.70 | 7.44 / 9.68 |
| 40 | static | 17.21 / 18.99 | 19.03 / 17.91 |
| 40 | 5 | 14.86 / 17.35 | 19.17 / 18.40 |
| 40 | 10 | 14.80 / 17.22 | 19.21 / 18.29 |
| 40 | 20 | 14.90 / 16.82 | 19.37 / 17.96 |
| 40 | 40 | 14.97 / 16.42 | 19.91 / 17.54 |

All four premium decay candidates win both median and mean on both samples only at 20 sessions. None wins two horizons. The lookup remains unchanged.

## Excess lines and current average

{
  "n": 10,
  "average": -0.04381254162047715,
  "from": "2026-09-04",
  "to": "2026-09-18",
  "p25": -0.04382947459634926,
  "p75": 0.026958919900746836,
  "p10": -0.06655213621042479,
  "p90": 0.05963410756517092,
  "median_abs_pct": 3.6501377255718115,
  "mean_abs_pct": 4.4862809777598445,
  "sessions": 277
}

Quartiles and tails are MSTR premium percentage points in decimal units. MSTX alert thresholds are exactly twice these. They are not percent distances from the adjusted fair price.

The completed window for the next session includes September 18. Historical September 18 tests exclude September 18 from their prior window. This is why the next-session average and the historical Friday baseline differ.

## Limits

No untouched holdout was reserved for choosing N. Short-window contraction partly reflects mechanical baseline movement. Dated horizons overlap. These are conditional valuations with known future Bitcoin and STRC, not forecasts of those inputs. The same-day MSTX tile retains the requested 2x mapping and is not a separately fitted fund model.

Pine calculates the average in a daily MSTR request with the average offset by one completed bar. It uses TradingView daily BTC and STRC feeds and supplied current Bitcoin per share. Its historical feed and BPS conventions can differ from the site source. No authenticated TradingView compiler is available in this workspace.

The offset and lookahead pattern follows [TradingView documentation](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/).

# Model card — motorcycle sold-price regressor

## Intent
Estimate a fair **sold price in IDR** for used motorcycles listed on MotorMarket so buyers can see
whether an asking price is a deal, fair, or rich.

## Algorithm
`sklearn.ensemble.HistGradientBoostingRegressor` with native categorical features.

## Training data
Synthetic but structurally realistic Indonesian market history (`ml/generate.py`).
The generator encodes depreciation, mileage, condition, city premia, and owner count —
the model has to recover those effects from tabular features only.

## Split
time-based 80/20 by listed_at
- train rows: 2000
- test rows: 500

## Holdout metrics
- MAE: Rp 823,441
- RMSE: Rp 2,117,386
- MAPE: 4.87%
- R²: 0.9918

## Top permutation importances (test MAE)
- `model_name`: 9169024.4338
- `mileage_km`: 5327202.5491
- `year`: 3526848.9146
- `make`: 1151471.6210
- `condition`: 649936.4506
- `engine_cc`: 608177.1009
- `segment`: 366936.7059
- `age`: 216483.7296

## Limitations
- Not live scraped listings (legal/ToS-safe for a public portfolio).
- City and condition are coarse categories.
- Does not yet include photo quality, accident history, or service records.

## How to retrain
```bash
python -m ml train --n 4000
```

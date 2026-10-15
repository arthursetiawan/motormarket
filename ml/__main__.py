from __future__ import annotations

import argparse
import json

from ml.drift import compare_distributions
from ml.etl import run_etl
from ml.generate import generate_live_listings
from ml.paths import DATA_GOLD
from ml.score import score_frame
from ml.train import train_price_model


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m ml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_etl = sub.add_parser("etl", help="bronze/silver/gold extract")
    p_etl.add_argument("--n-sold", type=int, default=4000)
    p_etl.add_argument("--n-live", type=int, default=120)

    p_train = sub.add_parser("train", help="train sold-price model")
    p_train.add_argument("--n", type=int, default=4000)
    p_train.add_argument("--seed", type=int, default=42)

    p_score = sub.add_parser("score", help="score live inventory CSV into gold")
    p_score.add_argument("--n-live", type=int, default=120)

    args = parser.parse_args()
    if args.cmd == "etl":
        print(json.dumps(run_etl(n_sold=args.n_sold, n_live=args.n_live), indent=2))
        return
    if args.cmd == "train":
        metrics = train_price_model(n=args.n, seed=args.seed)
        print(json.dumps({k: metrics[k] for k in ("mae_idr", "rmse_idr", "mape_pct", "r2", "n_train", "n_test")}, indent=2))
        return
    if args.cmd == "score":
        live = generate_live_listings(n=args.n_live)
        scored = score_frame(live)
        out = DATA_GOLD / "live_scored.csv"
        scored.to_csv(out, index=False)
        gold_sold = DATA_GOLD / "sold_listings.csv"
        if gold_sold.exists():
            import pandas as pd

            drift = compare_distributions(pd.read_csv(gold_sold), live)
            print(json.dumps({"rows": len(scored), "path": str(out), "drift": drift}, indent=2))
        else:
            print(json.dumps({"rows": len(scored), "path": str(out)}, indent=2))


if __name__ == "__main__":
    main()

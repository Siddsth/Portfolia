"""
Entry point for step 1-2 of the batch job (see handoff doc):
  1. Refresh price data for the portfolio's holdings
  2. Recompute risk metrics -> write a new risk snapshot

Run locally:   python scripts/compute_snapshot.py
Run in CI:     same command, from repo root, on a schedule (see
               .github/workflows/refresh.yml)

Output: output/risk_snapshot.json — this is what the public page reads,
and what step 4 (Q&A generation, not yet built) will read to ground its
prompts in the portfolio's actual numbers.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from risk_engine.data import BENCHMARK_TICKER, fetch_price_history, fetch_sector_map, load_portfolio  # noqa: E402
from risk_engine.metrics import compute_all_metrics  # noqa: E402

PORTFOLIO_CSV = REPO_ROOT / "data" / "portfolio.csv"
OUTPUT_PATH = REPO_ROOT / "output" / "risk_snapshot.json"


def main() -> None:
    print(f"Loading portfolio from {PORTFOLIO_CSV} ...")
    portfolio = load_portfolio(PORTFOLIO_CSV)
    print(f"Holdings ({len(portfolio.tickers)}): {portfolio.tickers}")

    print("Fetching price history (cached where possible)...")
    prices = fetch_price_history(portfolio.tickers, period="3y", include_benchmark=True)

    print("Fetching sector classifications...")
    sector_map = fetch_sector_map(portfolio.tickers)

    print("Computing risk metrics...")
    metrics = compute_all_metrics(prices, portfolio.weights, sector_map, benchmark_ticker=BENCHMARK_TICKER)

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "holdings": portfolio.weights.round(4).to_dict(),
        "metrics": metrics,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(snapshot, indent=2))
    print(f"Wrote {OUTPUT_PATH}")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()

"""
Data layer for the Portfolio Risk Engine.

Responsibilities:
- Load a portfolio definition (ticker, shares OR ticker, weight) from CSV.
- Fetch daily adjusted-close price history for every holding + a benchmark,
  via yfinance (free, no API key). Cached to local parquet so the GitHub
  Actions job doesn't re-download history it already has, and so local dev
  doesn't hammer the free data source.
- Fetch per-ticker sector classification (also cached), used for
  concentration/exposure metrics.

Swappable: if yfinance rate limits or availability become a problem,
Alpha Vantage / Financial Modeling Prep can be dropped in behind the same
`fetch_price_history` / `fetch_sector_map` function signatures.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

BENCHMARK_TICKER = "SPY"  # used for beta calculation
RISK_FREE_TICKER_PROXY_RATE = 0.04  # annualized; see NOTE in metrics.py


@dataclass
class Portfolio:
    """A loaded, normalized portfolio: ticker -> weight (sums to 1.0)."""

    weights: pd.Series  # index: ticker, values: weight (0-1)

    @property
    def tickers(self) -> list[str]:
        return list(self.weights.index)


def load_portfolio(csv_path: str | Path) -> Portfolio:
    """
    Load a portfolio CSV with either:
      ticker,shares   (weights derived from latest market value)
      ticker,weight   (used directly, renormalized to sum to 1.0)
    """
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower() for c in df.columns]
    if "ticker" not in df.columns:
        raise ValueError("Portfolio CSV must have a 'ticker' column.")
    df["ticker"] = df["ticker"].str.strip().str.upper()

    if "weight" in df.columns:
        weights = df.set_index("ticker")["weight"].astype(float)
    elif "shares" in df.columns:
        tickers = df["ticker"].tolist()
        latest_prices = _latest_prices(tickers)
        shares = df.set_index("ticker")["shares"].astype(float)
        market_value = shares * latest_prices.reindex(shares.index)
        weights = market_value
    else:
        raise ValueError("Portfolio CSV must have either a 'shares' or 'weight' column.")

    weights = weights / weights.sum()
    return Portfolio(weights=weights.sort_values(ascending=False))


def _latest_prices(tickers: list[str]) -> pd.Series:
    hist = fetch_price_history(tickers, period="5d")
    return hist.ffill().iloc[-1]


def fetch_price_history(
    tickers: list[str],
    period: str = "3y",
    include_benchmark: bool = False,
) -> pd.DataFrame:
    """
    Return a DataFrame of daily adjusted close prices, columns = tickers,
    index = date. Cached per-ticker as parquet; a cache hit still refreshes
    if the cached file is more than a day old.
    """
    all_tickers = list(tickers)
    if include_benchmark and BENCHMARK_TICKER not in all_tickers:
        all_tickers.append(BENCHMARK_TICKER)

    series = {}
    for t in all_tickers:
        series[t] = _fetch_one_ticker(t, period)

    prices = pd.DataFrame(series)
    prices = prices.sort_index()
    return prices


def _fetch_one_ticker(ticker: str, period: str) -> pd.Series:
    cache_file = CACHE_DIR / f"{ticker}.parquet"
    if cache_file.exists():
        mtime = dt.datetime.fromtimestamp(cache_file.stat().st_mtime)
        if dt.datetime.now() - mtime < dt.timedelta(hours=20):
            cached = pd.read_parquet(cache_file)["close"]
            return cached

    hist = yf.Ticker(ticker).history(period=period, auto_adjust=True)
    if hist.empty:
        raise ValueError(f"No price data returned for ticker '{ticker}'.")
    closes = hist["Close"].rename("close")
    closes.index = closes.index.tz_localize(None)
    closes.to_frame().to_parquet(cache_file)
    return closes


def fetch_sector_map(tickers: list[str]) -> pd.Series:
    """
    ticker -> sector (e.g. 'Technology'). Cached to a single small parquet
    file since sector rarely changes and yfinance's `.info` call is slow
    and its own rate-limit-sensitive endpoint.
    """
    cache_file = CACHE_DIR / "sectors.parquet"
    cached = pd.read_parquet(cache_file)["sector"] if cache_file.exists() else pd.Series(dtype=str)

    missing = [t for t in tickers if t not in cached.index]
    for t in missing:
        try:
            info = yf.Ticker(t).info
            cached.loc[t] = info.get("sector", "Unknown")
        except Exception:
            cached.loc[t] = "Unknown"

    cached.to_frame(name="sector").to_parquet(cache_file)
    return cached.reindex(tickers)

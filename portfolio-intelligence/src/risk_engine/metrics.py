"""
Risk metric calculations for the Portfolio Risk Engine.

All functions take plain pandas/numpy structures in and return plain
Python floats/dicts out, so this module has no dependency on how the
data was fetched (data.py) or how the result gets written (scripts/).

NOTE on risk-free rate: hardcoded via RISK_FREE_RATE rather than fetched
live, to avoid another API dependency for one slow-moving number. Update
by hand every few months, or wire to FRED's free API later if desired.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE = 0.04  # annualized; see NOTE above


def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change().dropna(how="all")


def portfolio_returns(returns: pd.DataFrame, weights: pd.Series) -> pd.Series:
    """Weighted daily return series for the whole portfolio."""
    aligned = returns[weights.index]
    return (aligned * weights).sum(axis=1)


def annualized_volatility(port_returns: pd.Series) -> float:
    return float(port_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR))


def annualized_return(port_returns: pd.Series) -> float:
    cumulative = (1 + port_returns).prod()
    n_years = len(port_returns) / TRADING_DAYS_PER_YEAR
    if n_years <= 0:
        return 0.0
    return float(cumulative ** (1 / n_years) - 1)


def sharpe_ratio(port_returns: pd.Series) -> float:
    vol = annualized_volatility(port_returns)
    if vol == 0:
        return 0.0
    ann_ret = annualized_return(port_returns)
    return float((ann_ret - RISK_FREE_RATE) / vol)


def max_drawdown(port_returns: pd.Series) -> float:
    """Returns a negative fraction, e.g. -0.23 for a 23% peak-to-trough drop."""
    cumulative = (1 + port_returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = cumulative / running_max - 1
    return float(drawdown.min())


def beta(port_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    aligned = pd.concat([port_returns, benchmark_returns], axis=1).dropna()
    aligned.columns = ["portfolio", "benchmark"]
    cov = aligned["portfolio"].cov(aligned["benchmark"])
    var = aligned["benchmark"].var()
    if var == 0:
        return 0.0
    return float(cov / var)


def correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    return returns.corr()


def value_at_risk(
    port_returns: pd.Series,
    confidence: float = 0.95,
    method: str = "historical",
) -> float:
    """
    One-day VaR as a positive fraction of portfolio value, e.g. 0.032 means
    a 5% chance of losing more than 3.2% of the portfolio in a single day.

    method="historical": empirical percentile of realized returns.
    method="parametric": assumes normally-distributed returns (mean/std).
    """
    if method == "historical":
        cutoff = port_returns.quantile(1 - confidence)
        return float(-cutoff)
    elif method == "parametric":
        from scipy.stats import norm

        mu, sigma = port_returns.mean(), port_returns.std()
        z = norm.ppf(1 - confidence)
        return float(-(mu + z * sigma))
    else:
        raise ValueError(f"Unknown VaR method: {method}")


def sector_exposure(weights: pd.Series, sector_map: pd.Series) -> dict[str, float]:
    """ticker weights + ticker->sector -> sector -> total weight."""
    df = pd.DataFrame({"weight": weights, "sector": sector_map.reindex(weights.index)})
    grouped = df.groupby("sector")["weight"].sum().sort_values(ascending=False)
    return grouped.round(4).to_dict()


def concentration_metrics(weights: pd.Series, top_n: int = 5) -> dict:
    """
    Herfindahl-Hirschman Index (sum of squared weights) as a single-number
    concentration score, plus the top-N holdings by weight for display.
    A fully diversified 20-stock equal-weight portfolio has HHI = 0.05;
    a single-stock portfolio has HHI = 1.0.
    """
    hhi = float((weights ** 2).sum())
    top = weights.sort_values(ascending=False).head(top_n).round(4).to_dict()
    return {"hhi": round(hhi, 4), "top_holdings": top}


def compute_all_metrics(
    prices: pd.DataFrame,
    weights: pd.Series,
    sector_map: pd.Series,
    benchmark_ticker: str = "SPY",
) -> dict:
    """Convenience wrapper: run every metric and return one flat dict,
    suitable for json.dump straight into a risk snapshot file."""
    returns = daily_returns(prices)
    port_ret = portfolio_returns(returns, weights)
    bench_ret = returns[benchmark_ticker] if benchmark_ticker in returns.columns else None

    result = {
        "as_of": str(prices.index.max().date()),
        "n_observations": int(len(port_ret)),
        "volatility_annualized": round(annualized_volatility(port_ret), 4),
        "return_annualized": round(annualized_return(port_ret), 4),
        "sharpe_ratio": round(sharpe_ratio(port_ret), 4),
        "max_drawdown": round(max_drawdown(port_ret), 4),
        "var_95_historical": round(value_at_risk(port_ret, 0.95, "historical"), 4),
        "var_95_parametric": round(value_at_risk(port_ret, 0.95, "parametric"), 4),
        "concentration": concentration_metrics(weights),
        "sector_exposure": sector_exposure(weights, sector_map),
    }
    if bench_ret is not None:
        result["beta_vs_spy"] = round(beta(port_ret, bench_ret), 4)

    corr = correlation_matrix(returns[weights.index])
    result["correlation_matrix"] = corr.round(3).to_dict()

    return result

# Portfolio Intelligence

Batch-computed portfolio risk metrics + (upcoming) SEC filing RAG assistant,
designed to run entirely on free tiers and be displayed on a static public
page. See the project handoff doc for full architecture/constraints — the
short version: **nothing a visitor does triggers an LLM call or a paid API
call.** Everything public-facing is precomputed by a GitHub Actions cron job.

## Status

- [x] Portfolio Risk Engine (this repo, working, unit-tested against synthetic data)
- [ ] SEC Filing RAG Assistant (not started)
- [ ] Combined prompt injection (risk JSON + filing chunks -> LLM)
- [ ] Public static page rendering `output/risk_snapshot.json`
- [ ] Gated live "ask anything" path (future, owner-only/rate-limited)

## Layout

```
data/
  portfolio.csv          # your holdings: ticker,shares OR ticker,weight
  cache/                 # price history + sector cache (gitignored except sectors.parquet)
src/risk_engine/
  data.py                # load portfolio, fetch+cache prices/sectors via yfinance
  metrics.py             # volatility, Sharpe, max drawdown, beta, VaR, correlation, concentration
scripts/
  compute_snapshot.py    # orchestrator: portfolio -> output/risk_snapshot.json
output/
  risk_snapshot.json     # what the public page reads (generated, not committed by hand)
.github/workflows/
  refresh.yml            # cron job: the only place API calls happen
```

## Run it locally

```bash
pip install -r requirements.txt
python scripts/compute_snapshot.py
```

Edit `data/portfolio.csv` with your real holdings first. First run will be
slower (no price cache yet); subsequent runs within ~20h reuse cached prices.

## Design notes / open decisions carried from the handoff doc

- **Market data source:** using `yfinance` (free, unofficial, no API key) as
  the default in `data.py` rather than Alpha Vantage/FMP — it has no request
  quota to manage for a handful of tickers refreshed daily, which is simpler
  for a single-portfolio scope. If Yahoo's endpoint gets flaky, swap the
  implementation of `fetch_price_history`/`fetch_sector_map` for an
  Alpha Vantage or FMP client behind the same signatures — nothing else
  in the codebase needs to change.
- **Risk-free rate** is a hardcoded constant in `metrics.py` (update by hand
  periodically) rather than fetched live, to avoid a third data dependency
  for a slow-moving number.
- **Storage:** still flat files (CSV in, JSON out) — no DB wired up yet.
  Matches the handoff doc's lean toward "fully static," given single-portfolio
  scope. Revisit if/when filing_chunks (RAG) volume makes a DB worth it.
- **Not yet decided from the handoff's open items:** GitHub Actions cadence
  (workflow currently defaults to daily — trivial to change to weekly), the
  EDGAR section-splitting regex, and the gated live-query path. None of
  those block the risk engine, which is why this pass started there.

## Next up

1. `scripts/ingest_filings.py` — SEC EDGAR fetch + Item 1A/Item 7 section
   splitting + chunking + local embedding, writing to `data/filing_chunks/`.
2. `scripts/generate_insights.py` — retrieval + Groq call, injecting
   `output/risk_snapshot.json` alongside retrieved chunks, writing curated
   Q&A to `output/insights.json`.
3. The static page itself, reading both JSON outputs.

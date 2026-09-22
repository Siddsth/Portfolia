# Portfolia
A CS x Finance project which uses AI powered portfolio risk analysis and SEC filing intelligence platform combining quantitative risk metrics with RAG_based Financial insights.

#

Given a set of stock holdings, it computes real risk metrics (volatility, Sharpe ratio, max drawdown, beta, correlation, VaR, sector concentration) and answers natural-language questions about the companies you hold by retrieving and citing the actual language from their SEC filings — grounding every answer in both your real numbers and real disclosed text.

## Features

- Portfolio risk engine — volatility, Sharpe ratio, max drawdown, beta vs. benchmark, correlation matrix, Value at Risk, sector/concentration exposure
- SEC filing RAG assistant — natural-language Q&A over 10-K/10-Q filings with citations back to the exact section and page
- Combined synthesis — risk-engine output is injected alongside retrieved filing text, so answers like "explain my biggest risk" are grounded in both your actual holdings and real disclosed risk factors
- Zero-cost by design — no live per-visitor LLM calls; all analysis is precomputed on a schedule and served as static output

## Architecture

```
Holdings (CSV/manual entry)
        │
        ▼
  Risk Engine ──────────────┐
  (pandas/numpy)            │
        │                   ▼
        │            LLM synthesis ──▶ Answer + citations
        │                   ▲
        ▼                   │
  Risk snapshot      Retrieved filing chunks
                             ▲
                             │
                     Vector similarity search
                             ▲
                             │
                 SEC EDGAR filings ──▶ Parse ──▶ Chunk ──▶ Embed
```

All computation (price refresh, risk recalculation, filing ingestion, Q&A generation) runs on a schedule via GitHub Actions — never on-demand from a site visitor. The public page reads precomputed, static results only.

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python |
| Backend framework | FastAPI |
| Scheduled compute | GitHub Actions (cron workflow) |
| Storage | Versioned JSON, or Postgres + pgvector (Neon/Supabase) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (local, free) |
| LLM | Groq free tier |
| Market data | Free-tier market data API + SEC EDGAR API |
| Frontend | Static HTML, hosted on GitHub Pages |

## Database schema

- `companies(id, ticker, name, sector)`
- `portfolios(id, user_id, name)`
- `portfolio_holdings(id, portfolio_id, company_id, weight)`
- `price_history(id, company_id, date, close)`
- `risk_snapshots(id, portfolio_id, date, sharpe, volatility, max_drawdown, var_95)`
- `filings(id, company_id, filing_type, filing_date, accession_number)`
- `filing_chunks(id, filing_id, section, page, chunk_text, embedding)`

## Getting started

```bash
git clone <repo-url>
cd portfolio-intelligence
pip install -r requirements.txt
cp .env.example .env   # add your free-tier API keys
python scripts/refresh.py   # runs the full pipeline locally
uvicorn app.main:app --reload
```

## Portfolio input format

Holdings are provided as a simple CSV — no brokerage account integration:

```csv
ticker,shares
AAPL,10
MSFT,5
NVDA,3
```

## Roadmap

- [ ] Price + risk snapshot refresh pipeline
- [ ] SEC filing ingestion + chunking
- [ ] Embedding + retrieval pipeline
- [ ] LLM synthesis with citations
- [ ] Static site generation
- [ ] GitHub Actions scheduling
- [ ] Gated live-query mode (future, rate-limited, not public by default)

## License

MIT


# FinPath AI

A financial advisor POC for beginners. Two flows:

1. **Savings Path** — given an amount, risk profile, monthly expenses, and time horizon, recommend an allocation across emergency fund, term deposit, and index fund.
2. **Fixed vs Floating** — compare 1y / 2y / 3y / 5y fixed mortgage strategies against floating, including a "what if rates move ±1%" sensitivity to make the *opportunity cost* concrete.

Every financial term in the UI is paired with a plain-English tooltip and a glossary modal. Rates are NZ-flavored (NZD, OCR, KiwiSaver-style framing).

## Architecture

- **Backend:** FastAPI (Python 3.11), Pydantic v2, async `httpx`. The `ExternalRatesService` uses a Provider Pattern — `MockProvider` (hardcoded 2026 rates) and `LiveProvider` (API Ninjas) — selected via `RATE_PROVIDER_TYPE`. All live calls fall back to mock data on any error so the demo never breaks.
- **Frontend:** React + Vite + Tailwind. Single-page dashboard, no router. A `<Term id="...">` component handles every financial term.
- **Infra:** Docker Compose (separate dev/prod files), Makefile entrypoints.

## Getting started

```bash
cp .env.example dev.env       # local-only; edit if needed
make dev                      # http://localhost:5173 (FE), http://localhost:8000 (BE)
make test                     # backend unit tests
make prod                     # production-optimized stack
make clean                    # tear down both stacks + volumes
```

## Live rates

Set in `prod.env` (or override `dev.env`):

```
RATE_PROVIDER_TYPE=live
API_NINJAS_KEY=your-key-here
```

Get a key at <https://api-ninjas.com>. If the key is missing or the API errors, the service logs a warning and serves mock data.

## Layout

```
backend/
  app/services/rates.py   Provider Pattern + TTL cache
  app/logic/finance.py    Pure financial math
  app/routers/            health, rates, investment, loan
  tests/                  pytest for math + rate providers
frontend/
  src/components/         Dashboard, RatesPanel, InvestmentAdvisor, LoanComparison, Term, ...
  src/data/glossary.js    All financial terms used in the UI
```

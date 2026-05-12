---
name: api-contract
description: Verify the React client in frontend/src/api/client.js matches the FastAPI backend's actual routes and Pydantic request/response shapes. Use after any change to backend/app/routers/*.py, backend/app/models/*.py, frontend/src/api/client.js, or any frontend component that calls the API. Reports path/method/payload-key drift between the two sides.
---

# api-contract

The backend exposes a small REST surface (4 routes) under `/api/*`. The React app calls it through one thin wrapper (`frontend/src/api/client.js`). The two move independently, and drift between them is silent — fetches succeed at the HTTP layer but the JSON shape is wrong. This skill catches that.

## When to run

- Any edit to `backend/app/routers/*.py` (added/removed/renamed endpoints).
- Any edit to `backend/app/models/investment.py`, `loan.py`, or `rates.py` (request/response fields changed).
- Any edit to `frontend/src/api/client.js` or to a component that builds request payloads (`InvestmentAdvisor.jsx`, `LoanComparison.jsx`, `useMarketRates.js`).

## What to do

1. **Enumerate backend endpoints.** Read every router file under `backend/app/routers/` and list each route as `(method, path, request_model, response_model)`. Paths get the `/api` prefix from `backend/app/main.py`.

2. **Resolve the Pydantic shapes.** For each `request_model` / `response_model`, read the referenced class in `backend/app/models/*.py`. Record field names, types, required-vs-optional (defaults), and any `Literal` constraints (e.g. `RiskLevel`, `StrategyKey`).

3. **Enumerate frontend calls.**
   - Read `frontend/src/api/client.js` — the `api` object lists the canonical call sites.
   - For each call, find where its payload is constructed (grep for `api.savingsPath(`, `api.loanCompare(`, `api.rates(`). Capture the keys actually sent.
   - For responses, grep where the returned object is destructured/read (e.g. `response.slices`, `response.results`) to confirm the frontend uses the fields the backend says it returns.

4. **Diff.** For every endpoint produce a row:
   - Path/method: do they match? (Frontend path includes `/api`.)
   - Request body: every required backend field present in the frontend payload? Any extras the backend will reject? Any `Literal` value the frontend sends that isn't allowed?
   - Response: every field the frontend reads actually returned?

5. **Report.** Group findings by endpoint. For each mismatch say which side to change and why. If everything matches, say so explicitly and list the endpoints verified.

## Notes

- The backend uses `from __future__ import annotations` — types are strings at runtime. Read the source, don't try to introspect.
- `MarketSnapshot` is large and nested (`mortgage`, `savings`, scalars). The frontend `RatesPanel` and `useMarketRates` consume specific subfields — check those.
- Don't run the backend just to hit `/openapi.json`; reading the models is faster and equivalent for this codebase.
- This is read-only. Don't propose edits unless the user asks — the output is a diff report.

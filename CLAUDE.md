# Moa — Money Optimiser Advisor

NZ holistic financial advisor POC. One unified intake (`FinancialProfile` — cash flow, debts, mortgage, KiwiSaver, lump sum, goals), one deterministic waterfall engine (financial order of operations), one LLM-generated conversational narrative.

## Stack

- **Backend**: FastAPI 0.115, Pydantic v2, httpx, pytest + pytest-asyncio + respx, ruff. Python 3.11.
- **Frontend**: React 18 + Vite 5 + Tailwind 3. ESLint 9 (config-less; lint target tolerated via Makefile `-`).
- **Infra**: Docker Compose (`docker-compose.yml` dev, `docker-compose.prod.yml` prod). Makefile is the entrypoint.

## Run

```
make            # show targets
make dev        # FE :5173, BE :8000
make test       # backend pytest in dev container
make lint       # ruff (clean) + eslint (no-op)
make prod       # detached prod stack
make clean      # tear both stacks down
```

Tests run inside the backend container — `--env-file dev.env` is required by compose, so `dev.env` must exist locally (copy from `.env.example`).

## Layout

```
backend/app/
  main.py               FastAPI factory + CORS + advisor/health/rates routers under /api
  config.py             Settings; gates LLM narrative off if OLLAMA_BASE_URL is unset
  routers/
    health.py           /api/health
    rates.py            /api/rates (market snapshot)
    advisor.py          /api/advisor/plan, /api/advisor/whatif/mortgage
  models/
    profile.py          FinancialProfile, PlanStep, RecommendedPlan, AdvisorPlanResponse, MortgageOverride
    investment.py       AllocationSlice, ProviderSuggestion, RiskLevel (used by the leaf)
    loan.py             LoanCompareRequest/Response, StrategyKey (used by the waterfall)
    rates.py            MarketSnapshot, MortgageRates, SavingsRates
  logic/
    nz_tax.py           PAYE FY26 brackets, ACC levy, KiwiSaver, MTC, PIE / RWT helpers
    finance.py          Primitive math: amortization, compound growth, fix-vs-float compare, taxable leaf
    waterfall.py        7-step financial order of operations → RecommendedPlan
  services/
    rates.py            Mock/Live provider pattern + TTL cache + graceful fallback
    advisor_llm.py      Ollama-backed narrative service + templated fallback
frontend/src/
  api/client.js         fetch wrapper hitting /api/*
  hooks/                useMarketRates, useAdvisorPlan, useWhatIfMortgage
  components/
    AdvisorPage.jsx     top-level — intake then plan, single scroll, no tabs
    AdvisorIntake/      5 collapsible sections + soft-validated "Build my plan" CTA
    AdvisorPlan/        narrative + prioritised PlanStepCards + horizon table
    AdvisorNarrative/   prose with auto-wrapped <Term> tooltips + fallback ribbon
    WhatIfMortgage/     debounced, cached re-fetch of /whatif/mortgage
    MarketContext.jsx   sticky strip (OCR + 3y fixed + 12mo TD)
    Term.jsx            tooltip primitive
    GlossaryModal.jsx   alphabetical reference modal
  data/glossary.js      Every financial term, keyed by kebab-case id
```

## Non-obvious rules

- **The demo must never break.** Both the rates provider (`services/rates.py`) and the LLM narrative service (`services/advisor_llm.py`) catch every exception and return mock/fallback data with `source="live-fallback"` / `narrative_source="fallback"`. Don't tighten the broad `except Exception` in either file.
- **The LLM never invents numbers.** `AdvisorLLM.narrate` only paraphrases the structured `RecommendedPlan`. Numbers ship verbatim in `PlanStep.rationale.numeric_facts` and `expected_outcome`; the system prompt forbids restating them differently. Whenever you touch the LLM prompt, keep this rule explicit.
- **All rates are decimals**, never percentages (`0.0695`, not `6.95`). Amounts are NZD.
- **`backend/app/logic/finance.py` is the primitive layer**: `monthly_payment`, `remaining_balance`, `compound_growth`, `compare_loan_strategies`, `recommend_allocation_leaf`. No I/O, no globals, no holistic logic.
- **`backend/app/logic/waterfall.py` is the only place EF sizing, debt prioritisation, and mortgage-vs-invest live.** Each step consumes from a shared `(remaining_lump, remaining_monthly)` pool — invariant: `unallocated_lump_sum + Σ step.amount_today == lump_sum_available ± $0.01`.
- **High-interest threshold is 8%** (`HIGH_INTEREST_THRESHOLD` in waterfall.py). Mortgage debt is excluded from that step.
- **Mortgage-vs-invest crossover** uses *after-PIE expected index return − 1.5% risk premium* vs the nominal mortgage rate (NZ owner-occupier interest isn't deductible). The risk premium is `MORTGAGE_RISK_PREMIUM = 0.015`.
- **Emergency fund is not compounded over the horizon.** It's a buffer that gets dipped into and refilled.
- **Singletons** for both the rate provider and the AdvisorLLM live in their service modules; `tests/conftest.py` resets both via an autouse fixture.
- **`RATE_PROVIDER_TYPE`** env toggles mock vs live (default mock). Live requires `API_NINJAS_KEY`.
- **`OLLAMA_BASE_URL`** unset → `advisor_narrative_enabled` is force-disabled by a `model_validator` in `config.py`. The frontend renders an amber "live advisor offline" ribbon; numbers are identical.
- **API base path is `/api`.** Backend routers are mounted under it; frontend `client.js` hardcodes `/api/...`. In prod, nginx proxies `/api` → backend.
- **PAYE thresholds in `nz_tax.PAYE_BRACKETS_FY26`** reflect the post-July-2024 IRD changes for FY 2025/26. Re-verify before each new tax year.

## Env files

- `.env.example` — committed template.
- `dev.env`, `prod.env` — local-only, gitignored. `prod.env` may contain a real API Ninjas key.

## Available automations

- Skill `/api-contract` — verify frontend client matches backend OpenAPI / Pydantic models.
- Skill `/moa-rates-check` — smoke-test mock + live rate providers (user-only).
- Subagent `finance-math-reviewer` — audits `logic/finance.py`, `logic/waterfall.py`, and `logic/nz_tax.py` on change.

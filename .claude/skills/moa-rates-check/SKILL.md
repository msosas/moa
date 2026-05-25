---
name: moa-rates-check
description: Smoke-test the mock and live rate providers, including the "live API failed, fall back to mock" path that the demo relies on. Use when the user runs /moa-rates-check or asks to verify the rates pipeline is healthy. Reports provider behavior and TTL cache state, never modifies code.
disable-model-invocation: true
---

# moa-rates-check

`ExternalRatesService` is the only place this POC talks to the outside world. The README's hard rule is **the demo must never break** — `LiveProvider` swallows every exception and returns mock data tagged `source="live-fallback"`. This skill verifies that contract still holds and that the cached singleton wiring isn't subtly broken.

## What to do

1. **Run the targeted rates test suite** through the dev container so the environment matches `make test`:

   ```
   docker compose -p moa-dev --env-file dev.env run --rm --no-deps backend \
     pytest tests/test_rates.py -v
   ```

   Report pass/fail per case. The key cases to highlight:
   - `test_get_provider_default_is_mock` — singleton defaults correctly.
   - `test_live_provider_falls_back_when_no_key` — `source == "live-fallback"`, no raise.
   - `test_live_provider_falls_back_on_http_error` — 500 from API Ninjas → fallback.
   - `test_live_provider_parses_nz_payload` — happy path returns `source == "live"` and applies the documented OCR spreads.
   - `test_cache_hit_avoids_repeat_fetch` — inner provider called once across N reads inside the TTL.

2. **Hit the running backend (if up).** If `make dev` is running, curl `http://localhost:8000/api/rates` and report the `source` field. `mock` or `live-fallback` is expected when no key is configured; `live` only when `RATE_PROVIDER_TYPE=live` and a real `API_NINJAS_KEY` is set.

   ```
   curl -s http://localhost:8000/api/rates | python -m json.tool | head -40
   ```

   If the backend isn't running, say so and skip — don't start it.

3. **Live-key sanity check (optional).** Only if the user has explicitly set `RATE_PROVIDER_TYPE=live` and a non-placeholder `API_NINJAS_KEY` in `dev.env` or `prod.env`, run a one-shot via the container:

   ```
   docker compose -p moa-dev --env-file dev.env run --rm --no-deps backend \
     python -c "import asyncio; from app.services.rates import LiveProvider; \
                import os; \
                snap = asyncio.run(LiveProvider(api_key=os.environ.get('API_NINJAS_KEY')).get_market_snapshot()); \
                print('source:', snap.source, 'ocr:', snap.central_bank_rate)"
   ```

   Report the returned `source`. `live` confirms the key works. `live-fallback` means the call failed gracefully — print the logged warning so the user can decide whether to investigate or accept the fallback.

4. **Summarize.** Three lines:
   - Test result (X/Y passing).
   - Backend `/api/rates` source (or "not running").
   - Live key status (or "not configured").

## Notes

- This skill is read-only. Don't edit `services/rates.py` or any test, even if a failure looks like a one-line fix — surface it to the user instead.
- `reset_provider()` is wired as an autouse fixture in `tests/conftest.py`; you don't need to clear caches manually around the pytest run.
- If the dev container image isn't built yet, `make build` is the right preflight — don't silently rebuild during the check.

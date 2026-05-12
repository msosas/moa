"""LLM narrative service.

Turns a structured ``RecommendedPlan`` into a conversational advisor-style
explanation. Two providers are supported:

- ``anthropic``: Anthropic Messages API (Claude). Uses prompt-cached system
  blocks for cost efficiency.
- ``ollama``: a local Ollama instance (default ``http://host.docker.internal:11434``).
  Useful for offline / private use and zero API spend.

The cardinal rule for both: the LLM never invents numbers — it only paraphrases
what the waterfall already computed.

The demo-never-breaks contract extends here: any provider failure (missing key,
5xx, timeout, schema drift) returns a templated narrative built from each
step's ``RationaleBlock``, with ``source="fallback"``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, ClassVar, Literal

import anthropic
import httpx

from app.models.profile import FinancialProfile, NarrativeSource, RecommendedPlan

logger = logging.getLogger(__name__)

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
DEFAULT_OLLAMA_BASE_URL = "http://host.docker.internal:11434"

NarrativeProvider = Literal["anthropic", "ollama", "templated"]


_PERSONA = """\
You are a New Zealand financial-planning explainer. Your reader has little or no financial
background — you are talking to a smart friend, not a colleague.

Voice and language rules:
- Address the user directly in second person ("you").
- Use everyday words. Imagine you're explaining it over coffee.
- Never use these terms without immediately defining them in everyday language:
  "principal", "amortization", "after-tax return", "after-PIE", "after-RWT", "opportunity cost",
  "sensitivity", "compound", "yield", "APR". Prefer plainer replacements ("the amount you still
  owe", "your monthly payment", "what you actually keep after tax", etc.).
- Prefer numbers in dollars over percentages where both make sense ("$200 a month" beats "2.5%").
- Short paragraphs. Short sentences. No bullet lists.
- Never invent numbers — only quote the figures present in the plan you are given. If a number
  isn't in the plan, don't put a number in your reply.
- Do not add disclaimers or "consult a professional" trailers. The host UI handles those.
- Always frame each step as a chunk of the user's monthly surplus or lump sum being
  allocated. The user is mentally asking "I have $X spare each month, where should it go?" —
  open the reply by stating their monthly surplus (from `cash_flow.monthly_surplus`), then
  walk through each step as "$Y of that goes to…". The amounts you allocate across all steps
  should reconcile to the surplus.
- When describing the mortgage step specifically: lead with how much *extra* per month the
  user is putting against the mortgage (`extra_per_month`) and what share of their monthly
  surplus that is. Only after that, mention that their *minimum* required payment changes to
  `new_minimum_payment` because of the refix. The `total_monthly_payment` is a derived total
  worth one line of context — never the headline. Never describe an extra payment without
  grounding it in the user's surplus, and never name a payment "new" without saying whether
  it's the bare minimum or the recommendation.\
"""

_NZ_PRIMER = """\
New Zealand context, useful when explaining the plan:
- KiwiSaver is the opt-in retirement scheme. Minimum employer contribution is 3% if the
  employee contributes at least 3%. Members who contribute $1,042.86 a year get the full
  $521.43 Member Tax Credit.
- PIE (Portfolio Investment Entity) funds — most KiwiSaver funds and most low-fee index
  funds in NZ — are taxed at the user's PIR (Prescribed Investor Rate), capped at 28%.
- Term deposits and ordinary bank interest are taxed at RWT (Resident Withholding Tax),
  commonly 33% for most adults.
- There is no general capital gains tax for residents on owner-occupier homes or PIE income.
- The OCR (Official Cash Rate) is the Reserve Bank's policy lever; floating mortgages move
  with it.\
"""

_PLAN_SCHEMA = """\
The plan you'll receive has this shape:
- steps: ordered list. Each step has priority (1..N), band (must_do/recommended/optional),
  kind, action (one-line imperative), amount_today, monthly_amount, expected_outcome (a
  dict of named numeric outcomes), rationale (primary_reason + numeric_facts + citations),
  confidence, references.
- cash_flow: gross_annual_income, net_monthly_income, total_monthly_expenses,
  monthly_surplus, savings_rate.
- horizon_projection: emergency_fund, kiwisaver, taxable_investments, debt_remaining,
  total_net_worth — the user's net worth at their chosen time horizon.
- market_snapshot: the current rates the recommendation is grounded in.\
"""

_CONSTRAINTS = """\
Hard constraints for every reply:
1. Walk the steps in priority order.
2. Every step in the plan must be referenced at least once.
3. Quote numeric_facts and expected_outcome values verbatim — never round, scale, or
   restate them differently.
4. Do not introduce recommendations not in the plan.
5. Aim for 250–400 words. Use short paragraphs, not bullet lists.\
"""

# Pre-joined system text for providers that don't support multi-block systems.
_SYSTEM_COMBINED = "\n\n".join([_PERSONA, _NZ_PRIMER, _PLAN_SCHEMA, _CONSTRAINTS])


@dataclass
class NarrativeResult:
    text: str
    source: NarrativeSource              # "llm" | "fallback"
    provider: NarrativeProvider | None = None
    model: str | None = None
    cache_read_tokens: int | None = None


@dataclass
class ModelInfo:
    id: str
    label: str
    provider: NarrativeProvider


class AdvisorLLM:
    """Dispatches narrative generation to Anthropic, a local Ollama, or the templated fallback."""

    DEFAULT_ANTHROPIC_MODEL: ClassVar[str] = DEFAULT_ANTHROPIC_MODEL

    def __init__(
        self,
        *,
        anthropic_api_key: str | None = None,
        ollama_base_url: str | None = None,
        anthropic_model: str = DEFAULT_ANTHROPIC_MODEL,
        enabled: bool = True,
        max_output_tokens: int = 800,
        anthropic_client: anthropic.AsyncAnthropic | None = None,
        ollama_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._anthropic_api_key = anthropic_api_key
        self._ollama_base_url = (ollama_base_url or "").rstrip("/") or None
        self._anthropic_model = anthropic_model
        self._enabled = enabled
        self._max_output_tokens = max_output_tokens
        self._anthropic_client = anthropic_client
        self._ollama_client = ollama_client

    # --- Public API ----------------------------------------------------------

    async def narrate(
        self,
        profile: FinancialProfile,
        plan: RecommendedPlan,
        *,
        provider: NarrativeProvider | None = None,
        model: str | None = None,
    ) -> NarrativeResult:
        if not self._enabled:
            return _fallback_result(profile, plan, reason="disabled")

        chosen = self._resolve_provider(provider)
        if chosen == "anthropic":
            return await self._narrate_anthropic(profile, plan, model or self._anthropic_model)
        if chosen == "ollama":
            return await self._narrate_ollama(profile, plan, model)
        return _fallback_result(profile, plan, reason="no provider configured")

    async def list_models(self, provider: NarrativeProvider) -> list[ModelInfo]:
        """Return the models available for the given provider.

        For Anthropic this is a hardcoded preset list. For Ollama we hit
        ``/api/tags`` on the configured base URL.
        """
        if provider == "anthropic":
            if not self._anthropic_api_key:
                return []
            return [
                ModelInfo(id="claude-opus-4-7",    label="Claude Opus 4.7",    provider="anthropic"),
                ModelInfo(id="claude-sonnet-4-6",  label="Claude Sonnet 4.6",  provider="anthropic"),
                ModelInfo(id="claude-haiku-4-5",   label="Claude Haiku 4.5",   provider="anthropic"),
            ]
        if provider == "ollama":
            if not self._ollama_base_url:
                return []
            return await self._fetch_ollama_models()
        if provider == "templated":
            return [ModelInfo(id="templated", label="Templated (no LLM)", provider="templated")]
        return []

    # --- Resolution helpers --------------------------------------------------

    def _resolve_provider(self, provider: NarrativeProvider | None) -> NarrativeProvider | None:
        """Pick a provider: the explicit one if usable, else best-available default."""
        if provider == "templated":
            return None  # signals fallback
        if provider == "anthropic" and self._anthropic_api_key:
            return "anthropic"
        if provider == "ollama" and self._ollama_base_url:
            return "ollama"
        if provider is None:
            if self._anthropic_api_key:
                return "anthropic"
            if self._ollama_base_url:
                return "ollama"
        return None

    # --- Anthropic -----------------------------------------------------------

    async def _narrate_anthropic(
        self, profile: FinancialProfile, plan: RecommendedPlan, model: str,
    ) -> NarrativeResult:
        try:
            client = self._anthropic_client or anthropic.AsyncAnthropic(api_key=self._anthropic_api_key)
            resp = await client.messages.create(
                model=model,
                max_tokens=self._max_output_tokens,
                system=[
                    {"type": "text", "text": _PERSONA,     "cache_control": {"type": "ephemeral"}},
                    {"type": "text", "text": _NZ_PRIMER,   "cache_control": {"type": "ephemeral"}},
                    {"type": "text", "text": _PLAN_SCHEMA, "cache_control": {"type": "ephemeral"}},
                    {"type": "text", "text": _CONSTRAINTS, "cache_control": {"type": "ephemeral"}},
                ],
                messages=[{"role": "user", "content": _user_turn(profile, plan)}],
            )
            text = "".join(
                block.text for block in resp.content
                if getattr(block, "type", None) == "text"
            )
            usage = getattr(resp, "usage", None)
            cache_read = getattr(usage, "cache_read_input_tokens", None) if usage else None
            return NarrativeResult(
                text=text.strip(),
                source="llm",
                provider="anthropic",
                model=model,
                cache_read_tokens=cache_read,
            )
        except Exception as exc:  # noqa: BLE001 — demo must not crash
            logger.warning("Anthropic narrate failed (%s); falling back", exc)
            return _fallback_result(profile, plan, reason=f"anthropic error: {exc}")

    # --- Ollama --------------------------------------------------------------

    async def _narrate_ollama(
        self, profile: FinancialProfile, plan: RecommendedPlan, model: str | None,
    ) -> NarrativeResult:
        assert self._ollama_base_url is not None  # guarded by _resolve_provider
        client, owns = self._get_ollama_client()
        try:
            chosen_model = model or await self._first_available_ollama_model(client)
            if not chosen_model:
                return _fallback_result(profile, plan, reason="no ollama models available")
            payload = {
                "model": chosen_model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_COMBINED},
                    {"role": "user",   "content": _user_turn(profile, plan)},
                ],
                "stream": False,
                "options": {"num_predict": self._max_output_tokens},
            }
            resp = await client.post(f"{self._ollama_base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            text = (data.get("message") or {}).get("content", "").strip()
            if not text:
                return _fallback_result(profile, plan, reason="empty ollama response")
            return NarrativeResult(
                text=text,
                source="llm",
                provider="ollama",
                model=chosen_model,
            )
        except Exception as exc:  # noqa: BLE001 — demo must not crash
            logger.warning("Ollama narrate failed (%s); falling back", exc)
            return _fallback_result(profile, plan, reason=f"ollama error: {exc}")
        finally:
            if owns:
                await client.aclose()

    async def _fetch_ollama_models(self) -> list[ModelInfo]:
        assert self._ollama_base_url is not None
        client, owns = self._get_ollama_client()
        try:
            resp = await client.get(f"{self._ollama_base_url}/api/tags")
            resp.raise_for_status()
            tags = resp.json().get("models", [])
            return [
                ModelInfo(
                    id=t["name"],
                    label=_friendly_ollama_label(t),
                    provider="ollama",
                )
                for t in tags
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Ollama list_models failed: %s", exc)
            return []
        finally:
            if owns:
                await client.aclose()

    async def _first_available_ollama_model(self, client: httpx.AsyncClient) -> str | None:
        try:
            resp = await client.get(f"{self._ollama_base_url}/api/tags")
            resp.raise_for_status()
            tags = resp.json().get("models", [])
            return tags[0]["name"] if tags else None
        except Exception:  # noqa: BLE001
            return None

    def _get_ollama_client(self) -> tuple[httpx.AsyncClient, bool]:
        """Return (client, owns_it). Caller closes only if owns_it is True."""
        if self._ollama_client is not None:
            return self._ollama_client, False
        return httpx.AsyncClient(timeout=httpx.Timeout(120.0)), True


# --- Fallback narrative -----------------------------------------------------

def _user_turn(profile: FinancialProfile, plan: RecommendedPlan) -> str:
    payload = {
        "profile": profile.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
    }
    return (
        "Here is the user's holistic profile and the structured plan computed by "
        "the waterfall engine. Write a 250–400 word reply in second person, in "
        f"{profile.narration_style} voice, walking the steps in priority order. "
        "Quote the numeric facts verbatim.\n\n"
        + json.dumps(payload, default=str)
    )


def _fallback_result(
    profile: FinancialProfile, plan: RecommendedPlan, *, reason: str | None = None,
) -> NarrativeResult:
    if reason:
        logger.info("AdvisorLLM serving fallback narrative: %s", reason)
    return NarrativeResult(
        text=_fallback_narrative(profile, plan),
        source="fallback",
        provider="templated",
    )


def _fallback_narrative(profile: FinancialProfile, plan: RecommendedPlan) -> str:
    """Deterministic templated narrative built from each step's RationaleBlock."""
    parts: list[str] = []
    parts.append(
        f"Based on what you've shared — ${profile.net_monthly_income:,.0f}/month after tax, "
        f"${profile.total_monthly_expenses:,.0f}/month in expenses, "
        f"a savings rate of {profile.savings_rate * 100:.0f}% — here's the order I'd tackle "
        "things in:"
    )
    band_prefix = {"must_do": "Must do", "recommended": "Recommended", "optional": "Nice to have"}
    for s in plan.steps:
        prefix = band_prefix[s.band]
        parts.append(
            f"**Step {s.priority} — {prefix}.** {s.action} {s.rationale.primary_reason}"
        )
    if plan.unallocated_monthly > 0:
        parts.append(
            f"You'll still have ${plan.unallocated_monthly:,.0f}/month uncommitted — use it "
            "for short-term goals, lifestyle, or to accelerate any of the steps above."
        )
    return "\n\n".join(parts)


def _friendly_ollama_label(tag: dict[str, Any]) -> str:
    """e.g. ``llama3.2:3b`` → ``Llama 3.2 (3b)``."""
    name = tag.get("name", "unknown")
    if ":" in name:
        base, variant = name.split(":", 1)
        if variant.lower() == "latest":
            return base
        return f"{base} ({variant})"
    return name


# --- Singleton wiring -------------------------------------------------------

_advisor_llm_singleton: AdvisorLLM | None = None


def get_advisor_llm(settings: Any | None = None) -> AdvisorLLM:
    """Process-wide singleton. Tests should call :func:`reset_advisor_llm` between cases."""
    global _advisor_llm_singleton
    if _advisor_llm_singleton is None:
        from app.config import get_settings
        s = settings or get_settings()
        _advisor_llm_singleton = AdvisorLLM(
            anthropic_api_key=getattr(s, "anthropic_api_key", None),
            ollama_base_url=getattr(s, "ollama_base_url", DEFAULT_OLLAMA_BASE_URL),
            anthropic_model=getattr(s, "advisor_model", DEFAULT_ANTHROPIC_MODEL),
            enabled=getattr(s, "advisor_narrative_enabled", True),
            max_output_tokens=getattr(s, "advisor_max_output_tokens", 800),
        )
    return _advisor_llm_singleton


def reset_advisor_llm() -> None:
    global _advisor_llm_singleton
    _advisor_llm_singleton = None

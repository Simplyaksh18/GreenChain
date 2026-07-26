"""
ai_provider.py — Phase 18 AI Provider Abstraction.

Two providers:
  rules  (default) — deterministic rule-based engine, no external deps
  groq             — Groq cloud LLM API (llama-3.3-70b-versatile)

Provider is selected by AI_MODE in settings.
Groq falls back to RulesAIProvider automatically if the API is unavailable
or if GROQ_API_KEY is not configured.

SAFETY INVARIANTS (never break these):
  * Providers NEVER modify any database records.
  * Providers NEVER change credit amounts, report status, or approval state.
  * Providers NEVER auto-approve or auto-reject verifications.
  * Providers return text/structured insight only.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any

logger = logging.getLogger(__name__)


# ── Abstract interface ─────────────────────────────────────────────────────────

class AIProvider(ABC):
    """Stable interface for all AI generation operations."""

    @abstractmethod
    def generate(self, prompt: str, context: Dict[str, Any]) -> str:
        """
        Generate a plain-English response given a structured prompt and context.
        Must not modify any state. Returns a string.
        """

    @property
    @abstractmethod
    def mode_name(self) -> str:
        """Human-readable provider name returned in API responses."""


# ── Rules provider ─────────────────────────────────────────────────────────────

class RulesAIProvider(AIProvider):
    """
    Deterministic rule-based provider.
    Generates insights by pattern-matching against structured context dicts.
    No network calls, no randomness, completely reproducible.
    """

    @property
    def mode_name(self) -> str:
        return "rules"

    def generate(self, prompt: str, context: Dict[str, Any]) -> str:
        """
        For the rules provider, 'prompt' is a logical operation key.
        Context is the structured data dict gathered by the service layer.
        Returns a pre-built deterministic string for that operation.
        """
        op = context.get("_operation", "generic")
        if op == "mrv_summary":
            return self._mrv_summary(context)
        if op == "verification_assist":
            return self._verification_assist(context)
        if op == "fpo_action_summary":
            return self._fpo_action_summary(context)
        if op == "farmer_help":
            return self._farmer_help(context)
        return "AI analysis is not available for this operation."

    # ── MRV Summary ─────────────────────────────────────────────────────────

    def _mrv_summary(self, ctx: Dict[str, Any]) -> str:
        farm_name     = ctx.get("farm_name", "this farm")
        readings      = ctx.get("sensor_reading_count", 0)
        has_report    = ctx.get("has_carbon_report", False)
        has_soc       = ctx.get("has_soc_estimate", False)
        credits       = ctx.get("estimated_credits", 0)
        report_status = ctx.get("report_status", "")
        sat_count     = ctx.get("satellite_count", 0)
        drone_count   = ctx.get("drone_count", 0)
        evidence      = ctx.get("evidence_count", 0)
        soc_conf      = ctx.get("soc_confidence", 0.0)
        avg_ndvi      = ctx.get("avg_ndvi")

        parts = [f"MRV status for {farm_name}:"]

        if not has_report:
            parts.append(
                "No carbon report has been generated yet. "
                "Add sensor readings, SOC data, and satellite observations first."
            )
            return " ".join(parts)

        # Report status
        if report_status == "VERIFIED":
            parts.append(
                f"Carbon report is VERIFIED with {credits:.2f} credit(s) confirmed."
            )
        elif report_status == "SUBMITTED":
            parts.append("Carbon report is submitted and under review.")
        elif report_status == "REJECTED":
            parts.append("Carbon report was REJECTED — check verifier notes and resubmit with corrections.")
        else:
            if credits > 0:
                parts.append(f"Carbon report drafted with {credits:.2f} estimated credit(s).")
            else:
                parts.append(
                    "Carbon credits are zero — emissions reduction is below the 1 tCO₂e "
                    "threshold or sensor/SOC data is incomplete."
                )

        # Sensor
        if readings >= 14:
            parts.append(f"Sensor coverage is complete ({readings} readings).")
        elif readings > 0:
            parts.append(f"Sensor data is partial ({readings}/{14} recommended readings).")
        else:
            parts.append("No sensor readings recorded — MRV cannot be independently verified.")

        # Satellite + drone
        if sat_count >= 3:
            ndvi_str = f", avg NDVI {avg_ndvi:.2f}" if avg_ndvi is not None else ""
            parts.append(f"Satellite data looks good ({sat_count} observations{ndvi_str}).")
        elif sat_count > 0:
            parts.append(f"Limited satellite data ({sat_count} observation(s)) — more coverage recommended.")
        else:
            parts.append("No satellite observations — draw farm boundary to enable collection.")
        if drone_count > 0:
            parts.append(f"Drone survey present ({drone_count} observation(s)).")

        # SOC
        if has_soc:
            conf_str = f"{soc_conf * 100:.0f}% confidence" if soc_conf > 0 else "confidence unknown"
            parts.append(f"Soil Organic Carbon data is available ({conf_str}).")
        else:
            parts.append("SOC data is missing — request a measurement from your FPO.")

        # Evidence
        if evidence >= 3:
            parts.append(f"Evidence looks sufficient ({evidence} files).")
        elif evidence > 0:
            parts.append(f"Evidence is minimal ({evidence} file(s)) — upload 3+ for stronger verification.")
        else:
            parts.append("No evidence files uploaded — add photos, invoices, or field notes.")

        return " ".join(parts)

    # ── Verification Assist ──────────────────────────────────────────────────

    def _verification_assist(self, ctx: Dict[str, Any]) -> str:
        evidence_count = ctx.get("evidence_file_count", 0)
        readings       = ctx.get("sensor_reading_count", 0)
        risk_level     = ctx.get("risk_level", "MEDIUM")
        farm_approved  = ctx.get("farm_approved", False)

        parts = [f"Verification risk level: {risk_level}."]

        if evidence_count == 0:
            parts.append("No evidence files have been uploaded — this is high risk.")
        elif evidence_count < 3:
            parts.append(
                f"Only {evidence_count} evidence file(s) uploaded; "
                "3+ files are recommended."
            )
        else:
            parts.append(f"{evidence_count} evidence files uploaded.")

        if not farm_approved:
            parts.append("Farm has not been formally approved — verify farm legitimacy.")

        if readings < 14:
            parts.append(
                f"Sensor reading density is low ({readings} readings). "
                "Verify sensor deployment."
            )

        return " ".join(parts)

    # ── FPO Action Summary ───────────────────────────────────────────────────

    def _fpo_action_summary(self, ctx: Dict[str, Any]) -> str:
        pending_farms     = ctx.get("pending_farm_approvals", 0)
        mintable          = ctx.get("mintable_report_count", 0)
        initiated_payouts = ctx.get("initiated_payout_count", 0)
        active_listings   = ctx.get("active_listing_count", 0)
        evidence_gaps     = ctx.get("evidence_gap_count", 0)

        items = []
        if pending_farms:
            items.append(f"{pending_farms} farm(s) awaiting approval")
        if mintable:
            items.append(f"{mintable} report(s) ready to mint")
        if initiated_payouts:
            items.append(f"{initiated_payouts} payout(s) pending")
        if active_listings:
            items.append(f"{active_listings} active marketplace listing(s)")
        if evidence_gaps:
            items.append(f"{evidence_gaps} farm(s) with missing evidence")

        if not items:
            return "All FPO operations are up to date. No immediate actions required."
        return "Action required: " + "; ".join(items) + "."

    # ── Farmer Help ──────────────────────────────────────────────────────────

    def _farmer_help(self, ctx: Dict[str, Any]) -> str:
        topic    = ctx.get("topic", "general")
        credits  = ctx.get("estimated_credits", 0)
        readings = ctx.get("sensor_reading_count", 0)

        explanations = {
            "explain_credits": (
                "Carbon credits represent the reduction in greenhouse gas emissions "
                "from your farm compared to a baseline. Each credit equals 1 tonne of "
                "CO₂ equivalent (tCO₂e) that your farming practices have "
                "prevented from entering the atmosphere. Credits are minted as digital "
                "tokens on the Polygon blockchain and can be sold on the marketplace."
            ),
            "why_zero_credits": (
                f"Your farm currently shows {credits} credits. "
                "Zero credits occur when: (1) the measured CO₂e reduction is "
                "below the 1 tCO₂e minimum threshold; (2) sensor readings are "
                "insufficient (you have " + str(readings) + " readings; 14+ recommended); "
                "or (3) the carbon report has not been generated yet."
            ),
            "missing_data": (
                "To improve your MRV quality: ensure your FPO's sensors are recording "
                "readings for your active crop cycle, upload at least 3 evidence files "
                "(photos, invoices, field notes), and make sure your farm boundary has "
                "been drawn. Satellite observations are collected automatically once "
                "your farm boundary is set."
            ),
            "improve_mrv": (
                "To increase your carbon credits: (1) maintain consistent sensor "
                "coverage throughout the crop cycle; (2) apply verified low-emission "
                "practices (reduced tillage, crop residue retention, cover crops); "
                "(3) keep detailed records of inputs and practices as evidence; "
                "(4) ensure your soil organic carbon baseline is measured."
            ),
            "general": (
                "GreenChain helps farmers earn carbon credits by measuring and "
                "verifying emission reductions on your farm. Your FPO manages the "
                "minting and marketplace process. Contact your FPO for specific "
                "questions about your farm's status."
            ),
        }
        return explanations.get(topic, explanations["general"])


# ── Groq provider ──────────────────────────────────────────────────────────────

class GroqAIProvider(AIProvider):
    """
    Groq cloud LLM provider (llama-3.3-70b-versatile by default).

    Falls back to RulesAIProvider if:
      - GROQ_API_KEY is not configured
      - The Groq API is unreachable or returns an error

    API key is read exclusively from settings (loaded from .env).
    It is never hardcoded and never logged.
    """

    # Groq OpenAI-compatible chat completions endpoint
    _API_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self) -> None:
        self._fallback = RulesAIProvider()

    @property
    def mode_name(self) -> str:
        return "groq"

    def generate(self, prompt: str, context: Dict[str, Any]) -> str:
        from app.config import settings
        import urllib.request
        import json

        api_key = settings.GROQ_API_KEY
        if not api_key:
            logger.warning(
                "GroqAIProvider: GROQ_API_KEY not configured, falling back to rules."
            )
            return self._fallback.generate(prompt, context)

        payload = {
            "model": settings.GROQ_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an AI assistant for GreenChain, a carbon credit MRV "
                        "platform. You provide advisory insights only. You never modify "
                        "database records, never approve or reject reports automatically, "
                        "never mint tokens, and never trigger payouts. Be concise."
                    ),
                },
                {
                    "role": "user",
                    "content": self._build_user_message(prompt, context),
                },
            ],
            "temperature": 0.3,
            "max_tokens": 512,
        }

        try:
            req = urllib.request.Request(
                self._API_URL,
                data=json.dumps(payload).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                return (
                    data["choices"][0]["message"]["content"].strip()
                )
        except Exception as exc:
            logger.warning(
                "GroqAIProvider: API call failed (%s), falling back to rules.", exc
            )
            return self._fallback.generate(prompt, context)

    def _build_user_message(self, prompt: str, context: Dict[str, Any]) -> str:
        op = context.get("_operation", "generic")
        ctx_str = "\n".join(
            f"  {k}: {v}"
            for k, v in context.items()
            if not k.startswith("_")
        )
        return (
            f"Operation: {op}\n"
            f"Context data:\n{ctx_str}\n\n"
            f"Task: {prompt}\n\n"
            "Respond in 2-4 plain-English sentences. "
            "Do not modify any values. "
            "Do not approve or reject any report or verification automatically."
        )


# ── Provider factory ───────────────────────────────────────────────────────────

_provider_instance: AIProvider | None = None


def get_ai_provider() -> AIProvider:
    """Return the active AI provider singleton (reads AI_MODE on first call)."""
    global _provider_instance
    if _provider_instance is None:
        from app.config import settings
        mode = (settings.AI_MODE or "rules").strip().lower()
        if mode == "groq":
            _provider_instance = GroqAIProvider()
        else:
            _provider_instance = RulesAIProvider()
        logger.info("AI provider initialised: %s", type(_provider_instance).__name__)
    return _provider_instance


def reset_ai_provider() -> None:
    """Reset cached provider — used in tests."""
    global _provider_instance
    _provider_instance = None

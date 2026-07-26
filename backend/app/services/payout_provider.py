"""
Payout Provider — Phase 10A / Phase 10B.

Provider pattern for future RazorpayX integration.

Providers:
  MockPayoutProvider      — simulated ledger, no real money (default)
  RazorpayXPayoutProvider — test-mode skeleton, raises NotImplementedError until wired

Usage:
  from app.services.payout_provider import get_payout_provider
  provider = get_payout_provider()
  result = provider.process_payout(request)

SECURITY RULES (enforced throughout this file):
  - No real payment API calls in MockPayoutProvider.
  - RazorpayX credentials MUST come from environment variables only.
  - Never log raw bank account numbers, UPI IDs, or API secrets.
  - Never hardcode any payment credentials.
  - Never expose key/secret in API responses or logs.
  - idempotency_key must be set on Payout before calling process_payout().
  - RazorpayX execution is disabled by default even in test mode.
    Set RAZORPAY_ENABLE_TEST_PAYOUTS=true to allow test payout execution.

═══════════════════════════════════════════════════════════════════════════════
FUTURE RAZORPAYX LIVE PAYOUT FLOW (do not implement until explicitly enabled):
═══════════════════════════════════════════════════════════════════════════════

Step 1: Create Contact
  POST https://api.razorpay.com/v1/contacts
  Body: { name, email, contact, type="vendor" }
  Returns: { id: "cont_XXXX" }

Step 2: Create Fund Account
  POST https://api.razorpay.com/v1/fund_accounts
  Body: {
    contact_id: "cont_XXXX",
    account_type: "vpa" (UPI) | "bank_account",
    vpa: { address: "<upi_id>" }               ← UPI path
    OR
    bank_account: {                             ← Bank path
      name: "<holder_name>",
      ifsc: "<IFSC>",
      account_number: "<account_no>"
    }
  }
  Returns: { id: "fa_XXXX" }

Step 3: (Optional) Validate Fund Account
  POST https://api.razorpay.com/v1/fund_accounts/validations
  Body: { account_number: "<RazorpayX_account>", fund_account: { id: "fa_XXXX" }, amount: 100 }
  This performs a ₹1 penny-drop to verify account is live.

Step 4: Create Payout
  POST https://api.razorpay.com/v1/payouts
  Headers: { "X-Payout-Idempotency": "<idempotency_key>" }
  Body: {
    account_number: "<RAZORPAY_ACCOUNT_NUMBER>",
    fund_account_id: "fa_XXXX",
    amount: <paise>,
    currency: "INR",
    mode: "UPI" | "NEFT" | "IMPS",
    purpose: "payout",
    queue_if_low_balance: true,
    reference_id: "<internal_payout_id>",
    narration: "GreenChain Carbon Credit Payout"
  }
  Returns: { id: "pout_XXXX", status: "queued"|"processing"|"processed" }
  Store pout_XXXX as provider_reference_id.

Step 5: Receive Webhook (POST /webhooks/razorpay)
  Event: payout.processed → mark Payout.status = COMPLETED
  Event: payout.failed    → mark Payout.status = FAILED
  Verify webhook signature using RAZORPAY_WEBHOOK_SECRET.
  NEVER implement webhooks until webhook secret is in env.

Step 6: Store UTR (Unique Transaction Reference)
  Available in webhook payload as entity.utr.
  Store as provider_reference_id if pout_XXXX is not yet set.

Notes:
  - Always use idempotency key to avoid double payouts on retry.
  - Never retry a payout without checking current status first.
  - Never log the fund_account_id or contact_id alongside PII.
  - Keep RAZORPAY_KEY_SECRET server-side only; never in mobile bundle.
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import requests  # stdlib-compatible; razorpay SDK also available but requests keeps it simple

from app.config import settings   # pydantic-settings reads .env; os.environ.get() alone does NOT

logger = logging.getLogger(__name__)


def _razorpay_env(key: str, default: str = "") -> str:
    """
    Read a Razorpay config value.

    Priority:
      1. os.environ — set by process environment, Docker/systemd env-vars, or test monkeypatch.
      2. settings   — loaded from .env by pydantic-settings (uvicorn without --env-file flag).

    This two-tier lookup is intentional:
      - Tests use pytest monkeypatch.setenv / monkeypatch.delenv, which sets os.environ only.
        settings is @lru_cache-ed and ignores monkeypatches, so we must check os.environ first.
      - Production (uvicorn): RAZORPAY_* vars are typically in .env only, not in the OS env,
        so pydantic-settings (via settings.*) is the correct fallback.
    """
    return os.environ.get(key) or getattr(settings, key, default) or default


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class PayoutRequest:
    """
    Encapsulates a single payout request.

    Public fields are safe to log (masked).
    _raw_* fields are for RazorpayX API calls ONLY — never log them.
    """
    payout_id: int               # DB Payout.id
    idempotency_key: str
    amount_paise: int            # amount in paise (= credits × price_per_credit)
    currency: str                # "INR"
    payout_method: str           # "UPI" | "BANK_TRANSFER"
    masked_destination: str      # e.g. "r***@okicici" or "****1234" — safe to log
    farmer_name: str
    remarks: Optional[str] = None

    # ── Raw payment fields — used by RazorpayX only; NEVER log these ──────────
    farmer_email: Optional[str] = field(default=None, repr=False)
    farmer_phone: Optional[str] = field(default=None, repr=False)
    # UPI path
    _raw_upi_id: Optional[str] = field(default=None, repr=False)
    # Bank path (all four required together)
    _raw_bank_account_number: Optional[str] = field(default=None, repr=False)
    _raw_ifsc_code: Optional[str] = field(default=None, repr=False)
    _raw_bank_account_holder_name: Optional[str] = field(default=None, repr=False)


@dataclass
class PayoutResult:
    success: bool
    provider_reference_id: Optional[str]   # RazorpayX payout_id when live; mock ref when simulated
    message: str
    simulated: bool = True


# ── Abstract base ─────────────────────────────────────────────────────────────

class BasePayoutProvider(ABC):
    @abstractmethod
    def process_payout(self, request: PayoutRequest) -> PayoutResult:
        """Initiate or simulate a payout. Returns PayoutResult."""
        ...

    @abstractmethod
    def check_status(self, provider_reference_id: str) -> str:
        """Return canonical status: INITIATED | PROCESSING | COMPLETED | FAILED."""
        ...

    @abstractmethod
    def get_config_status(self) -> dict:
        """Return safe (no secrets) config status for /system/payment-status."""
        ...


# ── Mock provider ─────────────────────────────────────────────────────────────

class MockPayoutProvider(BasePayoutProvider):
    """
    Simulated payout ledger for development and MVP.
    No real money moves. All payouts are immediately 'completed' in the simulation.
    """

    def process_payout(self, request: PayoutRequest) -> PayoutResult:
        mock_ref = f"MOCK-PAY-{request.payout_id}-{uuid.uuid4().hex[:8].upper()}"
        logger.info(
            "MockPayoutProvider.process_payout | payout_id=%s idempotency_key=%s "
            "amount_paise=%s method=%s destination=%s mock_ref=%s",
            request.payout_id,
            request.idempotency_key,
            request.amount_paise,
            request.payout_method,
            request.masked_destination,   # masked — safe to log
            mock_ref,
        )
        return PayoutResult(
            success=True,
            provider_reference_id=mock_ref,
            message=f"Simulated payout of ₹{request.amount_paise / 100:.2f} to {request.masked_destination}",
            simulated=True,
        )

    def check_status(self, provider_reference_id: str) -> str:
        if provider_reference_id.startswith("MOCK-PAY-"):
            return "COMPLETED"
        return "FAILED"

    def get_config_status(self) -> dict:
        return {
            "provider": "mock",
            "mode": "mock",
            "configured": True,
            "execution_enabled": True,
            "simulated": True,
        }


# ── RazorpayX provider (test-mode skeleton) ───────────────────────────────────

class RazorpayXPayoutProvider(BasePayoutProvider):
    """
    RazorpayX payout provider — test-mode skeleton (Phase 10B).

    Configuration (all via environment variables — never hardcode):
      RAZORPAY_KEY_ID             — RazorpayX API key ID
      RAZORPAY_KEY_SECRET         — RazorpayX API key secret (NEVER log this)
      RAZORPAY_MODE               — "test" | "live"
      RAZORPAY_ACCOUNT_NUMBER     — RazorpayX source account number
      RAZORPAY_ENABLE_TEST_PAYOUTS— "true" to allow test payout execution (default: false)

    Status:
      - Configuration is validated at __init__ (checks key_id and mode exist).
      - Actual payout execution requires RAZORPAY_ENABLE_TEST_PAYOUTS=true.
      - In Phase 10B, only config validation is implemented.
      - Full RazorpayX SDK integration follows the flow documented above.
    """

    def __init__(self) -> None:
        # _razorpay_env: os.environ first (test monkeypatches), settings fallback (.env in prod).
        self.key_id          = _razorpay_env("RAZORPAY_KEY_ID") or None
        self.mode            = _razorpay_env("RAZORPAY_MODE", "test").strip().lower()
        self.account_number  = _razorpay_env("RAZORPAY_ACCOUNT_NUMBER") or None  # declared in Settings; also readable from os.environ for test monkeypatches
        # RAZORPAY_KEY_SECRET intentionally not stored as attribute — retrieved fresh when needed
        # to reduce accidental logging risk.
        self._execution_enabled = (
            _razorpay_env("RAZORPAY_ENABLE_TEST_PAYOUTS", "false").strip().lower() == "true"
        )
        self._configured = bool(self.key_id)

        if not self._configured:
            logger.warning(
                "RazorpayXPayoutProvider: RAZORPAY_KEY_ID not set. "
                "Payouts will fail until credentials are configured in environment variables."
            )
        else:
            logger.info(
                "RazorpayXPayoutProvider initialized | mode=%s configured=True execution_enabled=%s",
                self.mode,
                self._execution_enabled,
            )

    def _get_secret(self) -> Optional[str]:
        """Retrieve secret fresh — never store or log it."""
        secret = _razorpay_env("RAZORPAY_KEY_SECRET")
        return secret if secret else None

    def _validate_config(self) -> None:
        """Raise RuntimeError if configuration is incomplete."""
        if not self._configured:
            raise RuntimeError(
                "RazorpayX not configured: RAZORPAY_KEY_ID missing. "
                "Set credentials in environment variables."
            )
        if not self._get_secret():
            raise RuntimeError(
                "RazorpayX not configured: RAZORPAY_KEY_SECRET missing."
            )

    # ── RazorpayX API helpers ──────────────────────────────────────────────────

    def _auth(self) -> tuple:
        """Return (key_id, key_secret) for requests.auth — never store secret."""
        return (self.key_id, self._get_secret())

    def _razorpay_post(self, path: str, body: dict, idempotency_key: Optional[str] = None) -> dict:
        """
        POST to RazorpayX API.
        Raises RuntimeError on HTTP error or network failure.
        Never logs secrets, raw body for payout (only payout_id/key).
        """
        url = f"https://api.razorpay.com/v1{path}"
        headers = {"Content-Type": "application/json"}
        if idempotency_key:
            headers["X-Payout-Idempotency"] = idempotency_key

        try:
            resp = requests.post(
                url,
                json=body,
                auth=self._auth(),
                headers=headers,
                timeout=30,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"RazorpayX network error on {path}: {exc}") from exc

        if not resp.ok:
            # Parse error safely — body may contain PII (fund_account etc.) so log only code/description
            try:
                err = resp.json().get("error", {})
                code = err.get("code", "UNKNOWN")
                description = err.get("description", resp.text[:200])
            except Exception:
                code = "UNKNOWN"
                description = resp.text[:200]
            raise RuntimeError(
                f"RazorpayX {path} failed [{resp.status_code}] code={code}: {description}"
            )

        return resp.json()

    def _create_contact(self, request: PayoutRequest) -> str:
        """Create a RazorpayX Contact. Returns contact_id."""
        body = {
            "name": request.farmer_name,
            "type": "vendor",
        }
        if request.farmer_email:
            body["email"] = request.farmer_email
        if request.farmer_phone:
            body["contact"] = request.farmer_phone

        logger.info("RazorpayX creating contact | payout_id=%s", request.payout_id)
        result = self._razorpay_post("/contacts", body)
        contact_id = result["id"]
        logger.info("RazorpayX contact created | payout_id=%s", request.payout_id)
        return contact_id

    def _create_fund_account(self, contact_id: str, request: PayoutRequest) -> str:
        """Create a RazorpayX Fund Account. Returns fund_account_id."""
        if request._raw_upi_id:
            body = {
                "contact_id": contact_id,
                "account_type": "vpa",
                "vpa": {"address": request._raw_upi_id},
            }
            logger.info("RazorpayX creating fund account (UPI) | payout_id=%s", request.payout_id)
        elif (
            request._raw_bank_account_number
            and request._raw_ifsc_code
            and request._raw_bank_account_holder_name
        ):
            body = {
                "contact_id": contact_id,
                "account_type": "bank_account",
                "bank_account": {
                    "name": request._raw_bank_account_holder_name,
                    "ifsc": request._raw_ifsc_code,
                    "account_number": request._raw_bank_account_number,
                },
            }
            logger.info("RazorpayX creating fund account (bank) | payout_id=%s", request.payout_id)
        else:
            raise RuntimeError(
                "RazorpayX fund account: no UPI ID or bank account details available."
            )

        result = self._razorpay_post("/fund_accounts", body)
        fa_id = result["id"]
        logger.info("RazorpayX fund account created | payout_id=%s", request.payout_id)
        return fa_id

    def _dispatch_payout(self, fund_account_id: str, request: PayoutRequest) -> dict:
        """Dispatch payout. Returns full Razorpay payout object."""
        mode = "UPI" if request._raw_upi_id else "NEFT"
        body = {
            "account_number": self.account_number,
            "fund_account_id": fund_account_id,
            "amount": request.amount_paise,
            "currency": request.currency,
            "mode": mode,
            "purpose": "payout",
            "queue_if_low_balance": True,
            "reference_id": str(request.payout_id),
            "narration": "GreenChain Carbon Credit Payout",
        }
        if request.remarks:
            body["narration"] = f"GreenChain Credit Payout - {request.remarks[:50]}"

        logger.info(
            "RazorpayX dispatching payout | payout_id=%s mode=%s amount_paise=%s idempotency_key=%s",
            request.payout_id, mode, request.amount_paise, request.idempotency_key,
        )
        result = self._razorpay_post(
            "/payouts",
            body,
            idempotency_key=request.idempotency_key,
        )
        return result

    # ── Main process_payout ────────────────────────────────────────────────────

    def process_payout(self, request: PayoutRequest) -> PayoutResult:
        """
        Execute RazorpayX payout: Contact → Fund Account → Payout.

        Only runs when RAZORPAY_ENABLE_TEST_PAYOUTS=true and RAZORPAY_MODE=test.
        Never runs in mock provider.
        Returns PayoutResult with provider_reference_id = RazorpayX payout_id.
        """
        self._validate_config()

        if not self._execution_enabled:
            logger.info(
                "RazorpayXPayoutProvider.process_payout | execution disabled | payout_id=%s",
                request.payout_id,
            )
            return PayoutResult(
                success=False,
                provider_reference_id=None,
                message=(
                    f"Razorpay {self.mode} mode configured — execution disabled. "
                    "Set RAZORPAY_ENABLE_TEST_PAYOUTS=true to enable test payouts."
                ),
                simulated=False,
            )

        if not self.account_number:
            logger.warning("RazorpayX account number missing | payout_id=%s", request.payout_id)
            return PayoutResult(
                success=False,
                provider_reference_id=None,
                message="RazorpayX account number missing. Set RAZORPAY_ACCOUNT_NUMBER.",
                simulated=False,
            )

        # Check payment details availability
        has_upi = bool(request._raw_upi_id)
        has_bank = bool(
            request._raw_bank_account_number
            and request._raw_ifsc_code
            and request._raw_bank_account_holder_name
        )
        if not has_upi and not has_bank:
            return PayoutResult(
                success=False,
                provider_reference_id=None,
                message=(
                    "No payment destination available for this farmer. "
                    "FPO must add UPI ID or bank account details before initiating payout."
                ),
                simulated=False,
            )

        try:
            contact_id = self._create_contact(request)
            fund_account_id = self._create_fund_account(contact_id, request)
            payout_result = self._dispatch_payout(fund_account_id, request)

            razorpay_payout_id = payout_result.get("id", "")
            razorpay_status = payout_result.get("status", "queued")

            # Summarize status safely — never include fund_account_id in response
            status_summary = f"RazorpayX payout {razorpay_status}"

            logger.info(
                "RazorpayX payout dispatched | payout_id=%s razorpay_status=%s",
                request.payout_id, razorpay_status,
            )

            return PayoutResult(
                success=True,
                provider_reference_id=razorpay_payout_id,
                message=f"{status_summary}. Destination: {request.masked_destination}",
                simulated=False,
            )

        except RuntimeError as exc:
            logger.error(
                "RazorpayX payout failed | payout_id=%s error=%s",
                request.payout_id, str(exc),
            )
            return PayoutResult(
                success=False,
                provider_reference_id=None,
                message=f"RazorpayX payout failed: {str(exc)}",
                simulated=False,
            )

    def check_status(self, provider_reference_id: str) -> str:
        """
        Fetch payout status from RazorpayX.
        Returns canonical status: INITIATED | PROCESSING | COMPLETED | FAILED.
        """
        self._validate_config()

        url = f"https://api.razorpay.com/v1/payouts/{provider_reference_id}"
        try:
            resp = requests.get(url, auth=self._auth(), timeout=30)
            if not resp.ok:
                logger.warning("RazorpayX check_status %s → %s", provider_reference_id, resp.status_code)
                return "FAILED"
            data = resp.json()
            razorpay_status = data.get("status", "").lower()
            # Map RazorpayX statuses to our canonical statuses
            status_map = {
                "queued": "INITIATED",
                "pending": "PROCESSING",
                "processing": "PROCESSING",
                "processed": "COMPLETED",
                "reversed": "FAILED",
                "failed": "FAILED",
                "cancelled": "FAILED",
            }
            return status_map.get(razorpay_status, "INITIATED")
        except requests.RequestException as exc:
            logger.warning("RazorpayX check_status network error: %s", exc)
            return "INITIATED"  # don't mark failed on transient network error

    def get_config_status(self) -> dict:
        """Return safe config status — never includes secret."""
        secret_set = bool(self._get_secret())
        return {
            "provider": "razorpayx",
            "mode": self.mode,
            "configured": self._configured and secret_set,
            "key_id_set": bool(self.key_id),
            "secret_set": secret_set,       # bool only — never the actual value
            "account_number_set": bool(self.account_number),
            "execution_enabled": self._execution_enabled,
            "simulated": False,
        }


# ── Factory ───────────────────────────────────────────────────────────────────

def get_payout_provider() -> BasePayoutProvider:
    """
    Return the active payout provider based on RAZORPAY_MODE env var.

    RAZORPAY_MODE values:
      "mock" (default) → MockPayoutProvider (simulated, no real money)
      "test"           → RazorpayXPayoutProvider in test mode (requires credentials)
      "live"           → RazorpayXPayoutProvider in live mode (requires live credentials)

    The actual payout will only execute if RAZORPAY_ENABLE_TEST_PAYOUTS=true (test)
    or the SDK is fully wired for live mode.
    """
    # _razorpay_env: os.environ first (test monkeypatches), then settings (.env in production).
    mode = _razorpay_env("RAZORPAY_MODE", "mock").strip().lower()
    if mode == "mock":
        return MockPayoutProvider()
    return RazorpayXPayoutProvider()

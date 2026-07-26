"""
System status router — Phase 8 / Phase 10B.

GET /system/status          — public, no auth required
GET /system/payment-status  — authenticated (any role), no secrets exposed
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.config import settings
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.mobile_schema import SystemStatusResponse
from app.services.payout_provider import get_payout_provider

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/status", response_model=SystemStatusResponse)
def system_status(db: Session = Depends(get_db)):
    """
    Returns live API and database health, blockchain mode, and route count.
    No authentication required — safe for mobile health checks.
    """
    # Test DB connectivity
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    # Blockchain configuration check
    mode = settings.BLOCKCHAIN_MODE.strip().lower()
    if mode == "web3":
        configured = bool(
            settings.WEB3_RPC_URL
            and settings.WEB3_PRIVATE_KEY
            and settings.WEB3_CONTRACT_ADDRESS
        )
    else:
        configured = True  # mock is always "configured"

    # Count registered routes (import lazily to avoid circular at module load)
    from app.main import app as _app
    total_routes = len([r for r in _app.routes])

    return SystemStatusResponse(
        api_status="ok",
        database_status=db_status,
        blockchain_mode=mode,
        blockchain_configured=configured,
        total_routes=total_routes,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/payment-status")
def payment_status(
    current_user: User = Depends(get_current_user),
):
    """
    Payment provider configuration status.
    Authenticated endpoint — returns boolean flags only, NEVER exposes credentials.

    Response fields:
      provider         — "mock" | "razorpayx"
      mode             — "mock" | "test" | "live"
      configured       — true when all required env vars are present
      execution_enabled— true when RAZORPAY_ENABLE_TEST_PAYOUTS=true
      simulated        — true for MockPayoutProvider
      key_id_set       — (RazorpayX only) true when RAZORPAY_KEY_ID is set
      secret_set       — (RazorpayX only) true when RAZORPAY_KEY_SECRET is set
                         NOTE: the actual secret value is NEVER returned
      account_number_set — (RazorpayX only) true when RAZORPAY_ACCOUNT_NUMBER is set
    """
    provider = get_payout_provider()
    return provider.get_config_status()

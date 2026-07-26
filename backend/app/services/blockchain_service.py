"""
blockchain_service.py — Public API shim (Phase 5 → Phase 6 refactor).

All functions delegate to the active BlockchainProvider so callers
(routers, token_service, tests) do not need to change.

The provider is selected via BLOCKCHAIN_MODE env variable:
    mock  (default)  →  MockBlockchainProvider   (no network required)
    web3             →  Web3BlockchainProvider    (real Polygon/Sepolia)

generate_mock_tx_hash() is kept for backward compatibility and direct
use by MockBlockchainProvider.
"""

import secrets
from typing import Optional
from sqlalchemy.orm import Session

from app.models.blockchain_transaction import BlockchainTransaction
from app.models.carbon_report import CarbonReport


# ── Hash utility (kept public for backward compat) ─────────────────────────────

def generate_mock_tx_hash() -> str:
    """Return a realistic-looking 0x-prefixed 64-hex-char transaction hash."""
    return "0x" + secrets.token_bytes(32).hex()


# ── Delegating functions ───────────────────────────────────────────────────────

def anchor_report_hash(
    carbon_report: CarbonReport, db: Session
) -> BlockchainTransaction:
    from app.services.blockchain_provider import get_blockchain_provider
    return get_blockchain_provider().anchor_report_hash(carbon_report, db)


def mint_token_transaction(
    carbon_report: CarbonReport,
    token_id: str,
    credit_amount: int,
    db: Session,
    *,
    fpo_wallet: Optional[str] = None,
    beneficiary_ref: Optional[str] = None,
) -> BlockchainTransaction:
    from app.services.blockchain_provider import get_blockchain_provider
    return get_blockchain_provider().mint_token_transaction(
        carbon_report, token_id, credit_amount, db,
        fpo_wallet=fpo_wallet,
        beneficiary_ref=beneficiary_ref,
    )


def retire_token_transaction(token, db: Session) -> BlockchainTransaction:
    from app.services.blockchain_provider import get_blockchain_provider
    return get_blockchain_provider().retire_token_transaction(token, db)


def suspend_token_transaction(token, db: Session) -> BlockchainTransaction:
    from app.services.blockchain_provider import get_blockchain_provider
    return get_blockchain_provider().suspend_token_transaction(token, db)

"""
Tokenization Service — Phase 5 / Phase 9 Custodial Update.

Public interface:
    create_token_id(carbon_report_id, year) -> str
    mint_carbon_token(carbon_report, farmer_id, db, *, fpo_id, beneficiary_farmer_id) -> CarbonToken
    retire_token(token, db) -> CarbonToken
    suspend_token(token, db) -> CarbonToken

Phase 9 changes:
    - mint_carbon_token now accepts optional fpo_id & beneficiary_farmer_id
    - When fpo_id is provided, a FarmerCreditBalance is automatically created
    - custodial_owner_type defaults to "FPO"
    - Zero-credit reports (estimated_credits == 0) receive a DB-only certificate
      record (no blockchain transaction) since ERC1155 cannot mint 0 tokens.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.carbon_report import CarbonReport, ReportStatus
from app.models.carbon_token import CarbonToken, TokenStatus, TOKEN_STANDARD
from app.services.blockchain_service import (
    mint_token_transaction,
    retire_token_transaction,
    suspend_token_transaction,
)

logger = logging.getLogger(__name__)


class TokenMintError(ValueError):
    """Raised when a token cannot be minted."""


# ── Token ID generation ────────────────────────────────────────────────────────

def create_token_id(carbon_report_id: int, year: int | None = None) -> str:
    """
    Generate a deterministic, human-readable token ID.
    Format: GC-CARBON-{report_id}-{year}
    """
    if year is None:
        year = datetime.now(timezone.utc).year
    return f"GC-CARBON-{carbon_report_id}-{year}"


# ── Mint ───────────────────────────────────────────────────────────────────────

def mint_carbon_token(
    carbon_report: CarbonReport,
    farmer_id: int,
    db: Session,
    *,
    fpo_id: Optional[int] = None,
    beneficiary_farmer_id: Optional[int] = None,
) -> CarbonToken:
    """
    Mint a CarbonToken for a VERIFIED carbon report.

    Raises TokenMintError if:
      - report is not VERIFIED
      - a token already exists for this report
    """
    logger.info(
        "mint_carbon_token | report_id=%s report_status=%s farm_id=%s "
        "farmer_id=%s fpo_id=%s estimated_credits=%s",
        carbon_report.id,
        carbon_report.status.value if carbon_report.status else "None",
        carbon_report.farm_id,
        farmer_id,
        fpo_id,
        carbon_report.estimated_credits,
    )

    if carbon_report.status != ReportStatus.VERIFIED:
        raise TokenMintError("Report is not verified")

    existing = (
        db.query(CarbonToken)
        .filter(CarbonToken.carbon_report_id == carbon_report.id)
        .first()
    )
    if existing:
        raise TokenMintError(
            f"Token already minted for this report (token_id: {existing.token_id})"
        )

    now = datetime.now(timezone.utc)
    token_id = create_token_id(carbon_report.id, now.year)

    # Resolve FPO wallet for custodial minting path
    fpo_wallet: Optional[str] = None
    beneficiary_ref: Optional[str] = None
    fpo_wallet_address_raw: Optional[str] = None
    if fpo_id is not None:
        from app.models.fpo import FPOProfile
        fpo_profile = db.query(FPOProfile).filter(FPOProfile.id == fpo_id).first()
        fpo_wallet_address_raw = fpo_profile.wallet_address if fpo_profile else None
        if fpo_profile and fpo_profile.wallet_address:
            fpo_wallet = fpo_profile.wallet_address
            beneficiary_ref = f"farmer:{beneficiary_farmer_id or farmer_id}"

    credit_amount = carbon_report.estimated_credits

    logger.info(
        "mint_carbon_token | token_id=%s fpo_wallet=%s credit_amount=%s",
        token_id, fpo_wallet or "(none)", credit_amount,
    )

    # ── Zero-credit certificate path ──────────────────────────────────────────
    # ERC1155 contracts cannot mint 0 tokens (would revert). For reports below
    # the 1 tCO₂e threshold, we create a DB-only certificate record with a
    # synthetic hash and no on-chain transaction.
    if credit_amount == 0:
        logger.info(
            "mint_carbon_token | report_id=%s credit_amount=0 — issuing "
            "DB-only zero-credit certificate (no blockchain tx)",
            carbon_report.id,
        )
        from app.models.blockchain_transaction import BlockchainTransaction, ActionType
        import secrets
        synthetic_hash = "0xcert-" + secrets.token_hex(28)
        tx = BlockchainTransaction(
            carbon_report_id=carbon_report.id,
            tx_hash=synthetic_hash,
            blockchain_network="CERTIFICATE_ONLY",
            contract_address="0x0000000000000000000000000000000000000000",
            action_type=ActionType.TOKEN_MINT,
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
    else:
        # Create TOKEN_MINT blockchain record first (gets tx_hash)
        try:
            tx = mint_token_transaction(
                carbon_report=carbon_report,
                token_id=token_id,
                credit_amount=credit_amount,
                db=db,
                fpo_wallet=fpo_wallet,
                beneficiary_ref=beneficiary_ref,
            )
        except RuntimeError as exc:
            error_str = str(exc)
            logger.error(
                "mint_carbon_token blockchain error | report_id=%s error=%s",
                carbon_report.id, error_str,
            )
            raise TokenMintError(error_str) from exc

    token = CarbonToken(
        carbon_report_id=carbon_report.id,
        farmer_id=farmer_id,
        token_id=token_id,
        token_standard=TOKEN_STANDARD,
        credit_amount=carbon_report.estimated_credits,
        status=TokenStatus.MINTED,
        minted_tx_hash=tx.tx_hash,
        minted_at=now,
        # Phase 9 custodial fields
        fpo_id=fpo_id,
        beneficiary_farmer_id=beneficiary_farmer_id or farmer_id,
        custodial_owner_type="FPO",
    )
    db.add(token)
    db.commit()
    db.refresh(token)

    # Phase 9: create the digital-twin credit balance when FPO is present
    if fpo_id is not None:
        from app.models.farmer_credit_balance import FarmerCreditBalance, CreditBalanceStatus
        credit_amount = carbon_report.estimated_credits
        balance = FarmerCreditBalance(
            farmer_id=beneficiary_farmer_id or farmer_id,
            fpo_id=fpo_id,
            carbon_report_id=carbon_report.id,
            carbon_token_id=token.id,
            credits_earned=credit_amount,
            credits_distributed=0,
            credits_available=credit_amount,
            status=CreditBalanceStatus.TOKENIZED,
        )
        db.add(balance)
        db.commit()

    return token


# ── Retire ─────────────────────────────────────────────────────────────────────

def retire_token(token: CarbonToken, db: Session) -> CarbonToken:
    """
    Mark a token as RETIRED and record the blockchain transaction.
    """
    retire_token_transaction(token, db)
    token.status = TokenStatus.RETIRED
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


# ── Suspend ────────────────────────────────────────────────────────────────────

def suspend_token(token: CarbonToken, db: Session) -> CarbonToken:
    """
    Mark a token as SUSPENDED and record the blockchain transaction.
    """
    suspend_token_transaction(token, db)
    token.status = TokenStatus.SUSPENDED
    db.add(token)
    db.commit()
    db.refresh(token)
    return token

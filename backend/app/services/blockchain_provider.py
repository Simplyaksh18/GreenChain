"""
Blockchain Provider Abstraction — Phase 6.

Defines the provider interface and two implementations:
  - MockBlockchainProvider   (default, no network required)
  - Web3BlockchainProvider   (real Polygon/Ethereum via web3.py)

Usage
-----
>>> from app.services.blockchain_provider import get_blockchain_provider
>>> provider = get_blockchain_provider()
>>> tx = provider.anchor_report_hash(report, db)

Environment
-----------
BLOCKCHAIN_MODE=mock   (default)  → MockBlockchainProvider
BLOCKCHAIN_MODE=web3              → Web3BlockchainProvider

Call reset_provider() between unit tests that change BLOCKCHAIN_MODE.
"""

import secrets
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.blockchain_transaction import (
    BlockchainTransaction,
    ActionType,
    MOCK_NETWORK,
    MOCK_CONTRACT_ADDRESS,
)
from app.models.carbon_report import CarbonReport, ReportStatus


# ── Abstract interface ─────────────────────────────────────────────────────────

class BlockchainProvider(ABC):
    """
    Stable interface for all blockchain operations.
    Phase 6 only requires these four methods; Phase 7+ may extend.
    All implementations must persist a BlockchainTransaction row to `db`.
    """

    @abstractmethod
    def anchor_report_hash(
        self, carbon_report: CarbonReport, db: Session
    ) -> BlockchainTransaction:
        """Anchor a verified report's hash. Idempotent."""

    @abstractmethod
    def mint_token_transaction(
        self,
        carbon_report: CarbonReport,
        token_id: str,
        credit_amount: int,
        db: Session,
        *,
        fpo_wallet: Optional[str] = None,
        beneficiary_ref: Optional[str] = None,
    ) -> BlockchainTransaction:
        """Record a token-mint operation.

        When fpo_wallet is provided the custodial minting path is used:
        the token is sent to the FPO vault address instead of the farmer.
        beneficiary_ref is an opaque string stored on-chain (e.g. 'farmer:42').
        """

    @abstractmethod
    def retire_token_transaction(self, token, db: Session) -> BlockchainTransaction:
        """Record a token-retire operation."""

    @abstractmethod
    def suspend_token_transaction(self, token, db: Session) -> BlockchainTransaction:
        """Record a token-suspend operation."""


# ── Mock provider ──────────────────────────────────────────────────────────────

class MockBlockchainProvider(BlockchainProvider):
    """
    In-process mock — generates realistic-looking tx hashes without any
    network connectivity. Used for local development, CI, and unit tests.
    """

    # Keep this a module-level helper so test_blockchain_service.py can
    # still import `generate_mock_tx_hash` from blockchain_service.py.
    @staticmethod
    def _new_tx_hash() -> str:
        return "0x" + secrets.token_bytes(32).hex()

    def anchor_report_hash(
        self, carbon_report: CarbonReport, db: Session
    ) -> BlockchainTransaction:
        if carbon_report.status != ReportStatus.VERIFIED:
            raise ValueError(
                f"Only VERIFIED reports can be anchored. "
                f"Current status: {carbon_report.status.value}"
            )
        # Idempotency check
        existing = (
            db.query(BlockchainTransaction)
            .filter(
                BlockchainTransaction.carbon_report_id == carbon_report.id,
                BlockchainTransaction.action_type == ActionType.REPORT_HASH,
            )
            .first()
        )
        if existing:
            return existing

        tx = BlockchainTransaction(
            carbon_report_id=carbon_report.id,
            tx_hash=self._new_tx_hash(),
            blockchain_network=MOCK_NETWORK,
            contract_address=MOCK_CONTRACT_ADDRESS,
            action_type=ActionType.REPORT_HASH,
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        return tx

    def mint_token_transaction(
        self,
        carbon_report: CarbonReport,
        token_id: str,
        credit_amount: int,
        db: Session,
        *,
        fpo_wallet: Optional[str] = None,
        beneficiary_ref: Optional[str] = None,
    ) -> BlockchainTransaction:
        # Mock mode ignores fpo_wallet — the tx hash is simulated regardless
        tx = BlockchainTransaction(
            carbon_report_id=carbon_report.id,
            tx_hash=self._new_tx_hash(),
            blockchain_network=MOCK_NETWORK,
            contract_address=MOCK_CONTRACT_ADDRESS,
            action_type=ActionType.TOKEN_MINT,
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        return tx

    def retire_token_transaction(self, token, db: Session) -> BlockchainTransaction:
        tx = BlockchainTransaction(
            carbon_report_id=token.carbon_report_id,
            tx_hash=self._new_tx_hash(),
            blockchain_network=MOCK_NETWORK,
            contract_address=MOCK_CONTRACT_ADDRESS,
            action_type=ActionType.TOKEN_RETIRE,
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        return tx

    def suspend_token_transaction(self, token, db: Session) -> BlockchainTransaction:
        tx = BlockchainTransaction(
            carbon_report_id=token.carbon_report_id,
            tx_hash=self._new_tx_hash(),
            blockchain_network=MOCK_NETWORK,
            contract_address=MOCK_CONTRACT_ADDRESS,
            action_type=ActionType.TOKEN_SUSPEND,
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        return tx


# ── Provider factory ───────────────────────────────────────────────────────────

_provider_instance: BlockchainProvider | None = None


def get_blockchain_provider() -> BlockchainProvider:
    """
    Return the active provider singleton.
    Reads BLOCKCHAIN_MODE from settings on first call.
    Call reset_provider() to force re-initialisation (useful in tests).
    """
    global _provider_instance
    if _provider_instance is None:
        from app.config import settings
        mode = (settings.BLOCKCHAIN_MODE or "mock").strip().lower()
        if mode == "web3":
            from app.services.web3_blockchain_provider import Web3BlockchainProvider
            _provider_instance = Web3BlockchainProvider()
        else:
            _provider_instance = MockBlockchainProvider()
    return _provider_instance


def reset_provider() -> None:
    """Reset the cached provider instance. Call between tests that change BLOCKCHAIN_MODE."""
    global _provider_instance
    _provider_instance = None

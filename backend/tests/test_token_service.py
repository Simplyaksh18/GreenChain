"""
Phase 5 — Token service unit tests.
"""
import re
import pytest
from app.services.token_service import (
    create_token_id,
    mint_carbon_token,
    retire_token,
    suspend_token,
    TokenMintError,
)
from app.models.carbon_token import TokenStatus
from app.models.blockchain_transaction import BlockchainTransaction, ActionType

# Standard mock tx hash pattern
TX_PATTERN = re.compile(r"^0x[0-9a-f]{64}$")
# Certificate-only hash pattern (used when estimated_credits == 0)
CERT_PATTERN = re.compile(r"^0xcert-[0-9a-f]{56}$")


def valid_tx_hash(h: str) -> bool:
    """Accept both regular mock tx hashes and zero-credit certificate hashes."""
    return bool(TX_PATTERN.match(h) or CERT_PATTERN.match(h))


class TestCreateTokenId:
    def test_format(self):
        tid = create_token_id(42, 2026)
        assert tid == "GC-CARBON-42-2026"

    def test_uses_current_year_by_default(self):
        from datetime import datetime, timezone
        tid = create_token_id(1)
        year = datetime.now(timezone.utc).year
        assert tid == f"GC-CARBON-1-{year}"

    def test_different_ids_produce_different_tokens(self):
        assert create_token_id(1, 2026) != create_token_id(2, 2026)


class TestMintCarbonToken:
    def test_verified_report_mints_token(self, db, verified_report, farmer_user):
        token = mint_carbon_token(verified_report, farmer_user.id, db)
        assert token.id is not None
        assert token.status == TokenStatus.MINTED
        assert token.carbon_report_id == verified_report.id
        assert token.farmer_id == farmer_user.id
        assert token.credit_amount == verified_report.estimated_credits
        assert token.token_id.startswith("GC-CARBON-")
        assert valid_tx_hash(token.minted_tx_hash), f"Unexpected tx hash: {token.minted_tx_hash}"
        assert token.minted_at is not None

    def test_token_standard_is_erc1155_mock(self, db, verified_report, farmer_user):
        token = mint_carbon_token(verified_report, farmer_user.id, db)
        assert token.token_standard == "ERC1155_MOCK"

    def test_unverified_report_raises(self, db, carbon_report_draft, farmer_user):
        with pytest.raises(TokenMintError, match="not verified"):
            mint_carbon_token(carbon_report_draft, farmer_user.id, db)

    def test_duplicate_mint_raises(self, db, verified_report, farmer_user):
        mint_carbon_token(verified_report, farmer_user.id, db)
        with pytest.raises(TokenMintError, match="already minted"):
            mint_carbon_token(verified_report, farmer_user.id, db)

    def test_mint_creates_blockchain_transaction(self, db, verified_report, farmer_user):
        token = mint_carbon_token(verified_report, farmer_user.id, db)
        tx = (
            db.query(BlockchainTransaction)
            .filter(
                BlockchainTransaction.carbon_report_id == verified_report.id,
                BlockchainTransaction.action_type == ActionType.TOKEN_MINT,
            )
            .first()
        )
        assert tx is not None
        assert tx.tx_hash == token.minted_tx_hash

    def test_zero_credit_report_mints_certificate(self, db, zero_credit_verified_report, farmer_user):
        token = mint_carbon_token(zero_credit_verified_report, farmer_user.id, db)
        assert token.credit_amount == 0
        assert token.status == TokenStatus.MINTED


class TestRetireToken:
    def test_retire_changes_status(self, db, minted_token):
        token = retire_token(minted_token, db)
        assert token.status == TokenStatus.RETIRED

    def test_retire_creates_blockchain_transaction(self, db, minted_token):
        retire_token(minted_token, db)
        tx = (
            db.query(BlockchainTransaction)
            .filter(
                BlockchainTransaction.carbon_report_id == minted_token.carbon_report_id,
                BlockchainTransaction.action_type == ActionType.TOKEN_RETIRE,
            )
            .first()
        )
        assert tx is not None
        assert TX_PATTERN.match(tx.tx_hash)


class TestSuspendToken:
    def test_suspend_changes_status(self, db, minted_token):
        token = suspend_token(minted_token, db)
        assert token.status == TokenStatus.SUSPENDED

    def test_suspend_creates_blockchain_transaction(self, db, minted_token):
        suspend_token(minted_token, db)
        tx = (
            db.query(BlockchainTransaction)
            .filter(
                BlockchainTransaction.carbon_report_id == minted_token.carbon_report_id,
                BlockchainTransaction.action_type == ActionType.TOKEN_SUSPEND,
            )
            .first()
        )
        assert tx is not None
        assert TX_PATTERN.match(tx.tx_hash)

"""
Phase 5 — Blockchain service unit tests.
"""
import re
import pytest
from app.services.blockchain_service import (
    generate_mock_tx_hash,
    anchor_report_hash,
)
from app.models.blockchain_transaction import ActionType, MOCK_NETWORK, MOCK_CONTRACT_ADDRESS
from app.models.carbon_report import ReportStatus

TX_PATTERN = re.compile(r"^0x[0-9a-f]{64}$")


class TestGenerateMockTxHash:
    def test_format_is_valid(self):
        h = generate_mock_tx_hash()
        assert TX_PATTERN.match(h), f"Invalid hash: {h}"

    def test_is_unique(self):
        hashes = {generate_mock_tx_hash() for _ in range(50)}
        assert len(hashes) == 50

    def test_length_is_66(self):
        h = generate_mock_tx_hash()
        assert len(h) == 66

    def test_starts_with_0x(self):
        assert generate_mock_tx_hash().startswith("0x")


class TestAnchorReportHash:
    def test_verified_report_creates_transaction(self, db, verified_report):
        from app.models.blockchain_transaction import BlockchainTransaction
        tx = anchor_report_hash(verified_report, db)
        assert tx.id is not None
        assert tx.action_type == ActionType.REPORT_HASH
        assert TX_PATTERN.match(tx.tx_hash)
        assert tx.blockchain_network == MOCK_NETWORK
        assert tx.contract_address == MOCK_CONTRACT_ADDRESS
        assert tx.carbon_report_id == verified_report.id

    def test_non_verified_report_raises(self, db, carbon_report_draft):
        with pytest.raises(ValueError, match="VERIFIED"):
            anchor_report_hash(carbon_report_draft, db)

    def test_idempotent_returns_same_transaction(self, db, verified_report):
        tx1 = anchor_report_hash(verified_report, db)
        tx2 = anchor_report_hash(verified_report, db)
        assert tx1.id == tx2.id
        assert tx1.tx_hash == tx2.tx_hash

    def test_duplicate_anchor_no_extra_row(self, db, verified_report):
        from app.models.blockchain_transaction import BlockchainTransaction
        anchor_report_hash(verified_report, db)
        anchor_report_hash(verified_report, db)
        count = (
            db.query(BlockchainTransaction)
            .filter(
                BlockchainTransaction.carbon_report_id == verified_report.id,
                BlockchainTransaction.action_type == ActionType.REPORT_HASH,
            )
            .count()
        )
        assert count == 1

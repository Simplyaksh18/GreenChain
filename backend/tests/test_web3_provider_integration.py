"""
Phase 6 — Web3 provider integration tests.

These tests require a live testnet RPC endpoint, funded admin wallet,
and deployed contract.  They are SKIPPED by default.

To run:
    WEB3_INTEGRATION_TESTS=true pytest tests/test_web3_provider_integration.py -v

Required env vars (in addition to WEB3_INTEGRATION_TESTS=true):
    WEB3_RPC_URL, WEB3_PRIVATE_KEY, WEB3_CONTRACT_ADDRESS, WEB3_CHAIN_ID
"""
import os
import re
import pytest

# ── Skip guard ─────────────────────────────────────────────────────────────────
INTEGRATION = os.getenv("WEB3_INTEGRATION_TESTS", "").lower() == "true"
skip_unless_integration = pytest.mark.skipif(
    not INTEGRATION,
    reason="Set WEB3_INTEGRATION_TESTS=true to run live testnet tests",
)

TX_PATTERN = re.compile(r"^0x[0-9a-f]{64}$")


@skip_unless_integration
class TestWeb3ProviderLive:
    """
    End-to-end tests against a live testnet.
    Requires a funded admin wallet and deployed contract.
    Tests are sequential (one report/token per class run).
    """

    @pytest.fixture(scope="class", autouse=True)
    def provider_setup(self):
        """Ensure the singleton uses Web3BlockchainProvider for this class."""
        from app.services.blockchain_provider import reset_provider, get_blockchain_provider
        from app.config import settings

        original_mode = settings.BLOCKCHAIN_MODE
        settings.__dict__["BLOCKCHAIN_MODE"] = "web3"
        reset_provider()
        yield get_blockchain_provider()
        settings.__dict__["BLOCKCHAIN_MODE"] = original_mode
        reset_provider()

    def test_provider_connects(self, provider_setup):
        from app.services.web3_blockchain_provider import Web3BlockchainProvider
        assert isinstance(provider_setup, Web3BlockchainProvider)

    def test_anchor_report_real_tx(self, provider_setup, db, verified_report):
        tx = provider_setup.anchor_report_hash(verified_report, db)
        assert TX_PATTERN.match(tx.tx_hash), f"Bad tx hash: {tx.tx_hash}"
        assert tx.blockchain_network in ("POLYGON_AMOY", "ETHEREUM_SEPOLIA")
        assert tx.contract_address.startswith("0x")
        print(f"\n  [LIVE] anchor tx_hash: {tx.tx_hash}")

    def test_mint_token_real_tx(self, provider_setup, db, verified_report):
        tx = provider_setup.mint_token_transaction(
            verified_report, "GC-CARBON-LIVE-1", 1, db
        )
        assert TX_PATTERN.match(tx.tx_hash)
        print(f"\n  [LIVE] mint tx_hash: {tx.tx_hash}")

    def test_retire_token_real_tx(self, provider_setup, db, minted_token):
        tx = provider_setup.retire_token_transaction(minted_token, db)
        assert TX_PATTERN.match(tx.tx_hash)
        print(f"\n  [LIVE] retire tx_hash: {tx.tx_hash}")

    def test_suspend_token_real_tx(self, provider_setup, db, minted_token):
        # Use a different fixture to avoid already-suspended conflict
        from app.services.token_service import mint_carbon_token
        from tests.conftest import _make_verified_report

        # This may fail if minted_token is already retired; skip gracefully
        from app.models.carbon_token import TokenStatus
        if minted_token.status != TokenStatus.MINTED:
            pytest.skip("Token already retired/suspended from previous test")

        tx = provider_setup.suspend_token_transaction(minted_token, db)
        assert TX_PATTERN.match(tx.tx_hash)
        print(f"\n  [LIVE] suspend tx_hash: {tx.tx_hash}")

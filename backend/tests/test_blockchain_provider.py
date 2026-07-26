"""
Phase 6 — Blockchain provider unit tests.

Tests the provider factory, MockBlockchainProvider behaviour,
and Web3BlockchainProvider config validation.
Private key exposure tests are included.
"""
import os
import re
import pytest
from unittest.mock import patch

from app.services.blockchain_provider import (
    BlockchainProvider,
    MockBlockchainProvider,
    get_blockchain_provider,
    reset_provider,
)
from app.models.blockchain_transaction import ActionType, MOCK_NETWORK, MOCK_CONTRACT_ADDRESS

TX_PATTERN = re.compile(r"^0x[0-9a-f]{64}$")


# ── Always reset the singleton between tests ───────────────────────────────────
@pytest.fixture(autouse=True)
def _reset():
    reset_provider()
    yield
    reset_provider()


# ── Provider factory ───────────────────────────────────────────────────────────

class TestProviderFactory:
    def test_returns_mock_by_default(self):
        p = get_blockchain_provider()
        assert isinstance(p, MockBlockchainProvider)

    def test_returns_mock_when_mode_is_mock(self):
        with patch.object(__import__("app.config", fromlist=["settings"]).settings,
                          "BLOCKCHAIN_MODE", "mock"):
            reset_provider()
            p = get_blockchain_provider()
        assert isinstance(p, MockBlockchainProvider)

    def test_returns_same_singleton(self):
        p1 = get_blockchain_provider()
        p2 = get_blockchain_provider()
        assert p1 is p2

    def test_reset_clears_singleton(self):
        p1 = get_blockchain_provider()
        reset_provider()
        p2 = get_blockchain_provider()
        assert p1 is not p2

    def test_mock_is_blockchain_provider_subclass(self):
        p = get_blockchain_provider()
        assert isinstance(p, BlockchainProvider)


# ── Web3 provider config validation ───────────────────────────────────────────

class TestWeb3ProviderConfigValidation:
    def test_missing_rpc_url_raises_config_error(self):
        from app.services.web3_blockchain_provider import Web3BlockchainProvider, Web3ConfigError
        from app.config import settings

        with patch.multiple(
            settings,
            WEB3_RPC_URL="",
            WEB3_PRIVATE_KEY="0x" + "a" * 64,
            WEB3_CONTRACT_ADDRESS="0x" + "b" * 40,
        ):
            with pytest.raises(Web3ConfigError, match="WEB3_RPC_URL"):
                Web3BlockchainProvider()

    def test_missing_private_key_raises_config_error(self):
        from app.services.web3_blockchain_provider import Web3BlockchainProvider, Web3ConfigError
        from app.config import settings

        with patch.multiple(
            settings,
            WEB3_RPC_URL="https://rpc.example.com",
            WEB3_PRIVATE_KEY="",
            WEB3_CONTRACT_ADDRESS="0x" + "b" * 40,
        ):
            with pytest.raises(Web3ConfigError, match="WEB3_PRIVATE_KEY"):
                Web3BlockchainProvider()

    def test_missing_contract_address_raises_config_error(self):
        from app.services.web3_blockchain_provider import Web3BlockchainProvider, Web3ConfigError
        from app.config import settings

        with patch.multiple(
            settings,
            WEB3_RPC_URL="https://rpc.example.com",
            WEB3_PRIVATE_KEY="0x" + "a" * 64,
            WEB3_CONTRACT_ADDRESS="",
        ):
            with pytest.raises(Web3ConfigError, match="WEB3_CONTRACT_ADDRESS"):
                Web3BlockchainProvider()

    def test_factory_with_web3_mode_and_missing_vars_raises_error(self):
        from app.config import settings
        from app.services.web3_blockchain_provider import Web3ConfigError

        with patch.multiple(
            settings,
            BLOCKCHAIN_MODE="web3",
            WEB3_RPC_URL="",
            WEB3_PRIVATE_KEY="",
            WEB3_CONTRACT_ADDRESS="",
        ):
            reset_provider()
            with pytest.raises(Web3ConfigError):
                get_blockchain_provider()


# ── Private key safety ─────────────────────────────────────────────────────────

class TestPrivateKeySafety:
    def test_mock_provider_repr_has_no_key(self):
        p = get_blockchain_provider()
        assert "PRIVATE" not in repr(p).upper()
        assert "SECRET" not in repr(p).upper()

    def test_web3_provider_repr_has_no_key(self):
        """
        Build a Web3BlockchainProvider with all env vars set but mock the
        actual web3 connection so no network is needed.
        """
        from unittest.mock import MagicMock, patch
        from app.config import settings
        from app.services.web3_blockchain_provider import Web3BlockchainProvider

        fake_private_key = "0x" + "dead" * 16

        mock_w3 = MagicMock()
        mock_w3.is_connected.return_value = True
        mock_w3.eth.account.from_key.return_value = MagicMock(address="0xAdminAddress123")
        mock_w3.eth.contract.return_value = MagicMock()

        with patch.multiple(
            settings,
            WEB3_RPC_URL="https://rpc.example.com",
            WEB3_PRIVATE_KEY=fake_private_key,
            WEB3_CONTRACT_ADDRESS="0x" + "c" * 40,
            WEB3_CHAIN_ID=80002,
            WEB3_ACCOUNT_ADDRESS="",
        ):
            with patch("app.services.web3_blockchain_provider.Web3") as MockWeb3:
                MockWeb3.return_value = mock_w3
                MockWeb3.HTTPProvider = MagicMock()
                MockWeb3.to_checksum_address = lambda x: x
                provider = Web3BlockchainProvider()

        representation = repr(provider)
        assert "dead" not in representation.lower()
        assert fake_private_key not in representation


# ── MockBlockchainProvider functional tests ────────────────────────────────────

class TestMockBlockchainProviderFunctional:
    def test_anchor_report_creates_tx(self, db, verified_report):
        p = get_blockchain_provider()
        tx = p.anchor_report_hash(verified_report, db)
        assert tx.action_type == ActionType.REPORT_HASH
        assert TX_PATTERN.match(tx.tx_hash)
        assert tx.blockchain_network == MOCK_NETWORK
        assert tx.contract_address == MOCK_CONTRACT_ADDRESS

    def test_anchor_is_idempotent(self, db, verified_report):
        p = get_blockchain_provider()
        tx1 = p.anchor_report_hash(verified_report, db)
        tx2 = p.anchor_report_hash(verified_report, db)
        assert tx1.id == tx2.id

    def test_anchor_non_verified_raises(self, db, carbon_report_draft):
        p = get_blockchain_provider()
        with pytest.raises(ValueError, match="VERIFIED"):
            p.anchor_report_hash(carbon_report_draft, db)

    def test_mint_token_creates_tx(self, db, verified_report):
        p = get_blockchain_provider()
        tx = p.mint_token_transaction(verified_report, "GC-CARBON-1-2026", 5, db)
        assert tx.action_type == ActionType.TOKEN_MINT
        assert TX_PATTERN.match(tx.tx_hash)

    def test_retire_creates_tx(self, db, minted_token):
        p = get_blockchain_provider()
        tx = p.retire_token_transaction(minted_token, db)
        assert tx.action_type == ActionType.TOKEN_RETIRE
        assert TX_PATTERN.match(tx.tx_hash)

    def test_suspend_creates_tx(self, db, minted_token):
        p = get_blockchain_provider()
        tx = p.suspend_token_transaction(minted_token, db)
        assert tx.action_type == ActionType.TOKEN_SUSPEND
        assert TX_PATTERN.match(tx.tx_hash)

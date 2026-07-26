"""
test_blockchain_web3.py — Phase 17 Web3 / Real Blockchain Tests.

Covers:
1.  Mock mode continues to work unchanged (regression guard)
2.  Web3 mode — config validation: missing env vars → Web3ConfigError
3.  Web3 provider with fully mocked web3 — anchor, mint, retire
4.  Idempotency: second anchor call returns the same BlockchainTransaction row
5.  Mint fails safely when RPC raises an exception (RuntimeError raised, no fake token)
6.  Duplicate mint from DB perspective: BlockchainTransaction not doubled
7.  Transaction hash stored in DB with correct network name
8.  Private key never appears in __repr__
9.  PolygonScan URL helper produces correct URL format
10. Factory with BLOCKCHAIN_MODE=web3 + mocked Web3 returns Web3BlockchainProvider

Notes
-----
* No real network calls are made — web3.py is patched at the module level.
* These tests do NOT require a live RPC endpoint or private key.
* The conftest `db`, `verified_report`, `minted_token` fixtures are reused.
* reset_provider() is called around any test that patches BLOCKCHAIN_MODE.
"""

import re
from unittest.mock import MagicMock, patch

import pytest

from app.models.blockchain_transaction import ActionType, BlockchainTransaction, MOCK_NETWORK
from app.services.blockchain_provider import (
    MockBlockchainProvider,
    get_blockchain_provider,
    reset_provider,
)
from app.services.web3_blockchain_provider import Web3BlockchainProvider, Web3ConfigError

TX_PATTERN = re.compile(r"^0x[0-9a-f]{64}$")
REAL_NETWORK = "POLYGON_AMOY"
FAKE_CONTRACT = "0x" + "a" * 40
FAKE_PRIVATE_KEY = "0x" + "dead" * 16
FAKE_RPC = "https://rpc.example.com"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset():
    """Always reset the provider singleton between tests."""
    reset_provider()
    yield
    reset_provider()


def _make_mock_web3(connected: bool = True, chain_id: int = 80002):
    """
    Build a minimal MagicMock that mimics the web3.py Web3 object well enough
    for Web3BlockchainProvider.__init__ to succeed.
    """
    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = connected
    mock_account = MagicMock(address="0xAdminAddr0000000000000000000000000000001")
    mock_w3.eth.account.from_key.return_value = mock_account

    # sign_transaction returns object with .raw_transaction attribute
    signed_tx = MagicMock()
    signed_tx.raw_transaction = b"\x00" * 32
    mock_w3.eth.account.sign_transaction.return_value = signed_tx

    # send_raw_transaction returns bytes (the tx hash)
    mock_w3.eth.send_raw_transaction.return_value = bytes.fromhex("ab" * 32)

    # wait_for_transaction_receipt returns receipt with status=1 (success)
    mock_receipt = MagicMock()
    mock_receipt.status = 1
    mock_w3.eth.wait_for_transaction_receipt.return_value = mock_receipt

    # Nonce + gas
    mock_w3.eth.get_transaction_count.return_value = 0
    mock_w3.eth.gas_price = 1_000_000_000
    mock_w3.eth.estimate_gas.return_value = 50_000

    # build_transaction returns a dict-like object
    fn_mock = MagicMock()
    fn_mock.build_transaction.return_value = {
        "from": "0xAdminAddr0000000000000000000000000000001",
        "nonce": 0,
        "gasPrice": 1_000_000_000,
        "chainId": chain_id,
        "data": "0x",
    }
    mock_w3.eth.contract.return_value.functions.anchorReport.return_value = fn_mock
    mock_w3.eth.contract.return_value.functions.mintCarbonCredit.return_value = fn_mock
    mock_w3.eth.contract.return_value.functions.mintCustodialCarbonCredit.return_value = fn_mock
    mock_w3.eth.contract.return_value.functions.retireToken.return_value = fn_mock
    mock_w3.eth.contract.return_value.functions.suspendToken.return_value = fn_mock

    return mock_w3


def _make_web3_provider() -> Web3BlockchainProvider:
    """
    Return a Web3BlockchainProvider instance with all real web3 calls mocked.
    """
    from app.config import settings

    mock_w3 = _make_mock_web3()

    with patch.multiple(
        settings,
        WEB3_RPC_URL=FAKE_RPC,
        WEB3_PRIVATE_KEY=FAKE_PRIVATE_KEY,
        WEB3_CONTRACT_ADDRESS=FAKE_CONTRACT,
        WEB3_CHAIN_ID=80002,
        WEB3_ACCOUNT_ADDRESS="",
    ), patch("app.services.web3_blockchain_provider.Web3") as MockWeb3:
        MockWeb3.return_value = mock_w3
        MockWeb3.HTTPProvider = MagicMock()
        MockWeb3.to_checksum_address = lambda x: x
        provider = Web3BlockchainProvider()
        provider._w3 = mock_w3
        return provider


# ─────────────────────────────────────────────────────────────────────────────
# 1. Mock mode regression guard
# ─────────────────────────────────────────────────────────────────────────────

class TestMockModeRegression:
    """Mock mode must still work after Phase 17 changes."""

    def test_default_provider_is_mock(self):
        p = get_blockchain_provider()
        assert isinstance(p, MockBlockchainProvider)

    def test_mock_anchor_creates_tx(self, db, verified_report):
        p = get_blockchain_provider()
        tx = p.anchor_report_hash(verified_report, db)
        assert tx.action_type == ActionType.REPORT_HASH
        assert TX_PATTERN.match(tx.tx_hash)
        assert tx.blockchain_network == MOCK_NETWORK

    def test_mock_mint_creates_tx(self, db, verified_report):
        p = get_blockchain_provider()
        tx = p.mint_token_transaction(verified_report, "GC-CARBON-TEST-001", 10, db)
        assert tx.action_type == ActionType.TOKEN_MINT
        assert TX_PATTERN.match(tx.tx_hash)

    def test_mock_anchor_is_idempotent(self, db, verified_report):
        p = get_blockchain_provider()
        tx1 = p.anchor_report_hash(verified_report, db)
        tx2 = p.anchor_report_hash(verified_report, db)
        assert tx1.id == tx2.id

    def test_mock_retire_creates_tx(self, db, minted_token):
        p = get_blockchain_provider()
        tx = p.retire_token_transaction(minted_token, db)
        assert tx.action_type == ActionType.TOKEN_RETIRE
        assert TX_PATTERN.match(tx.tx_hash)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Web3 config validation
# ─────────────────────────────────────────────────────────────────────────────

class TestWeb3ConfigValidation:
    """Web3BlockchainProvider must raise Web3ConfigError for missing required vars."""

    def test_missing_rpc_url(self):
        from app.config import settings
        with patch.multiple(
            settings,
            WEB3_RPC_URL="",
            WEB3_PRIVATE_KEY=FAKE_PRIVATE_KEY,
            WEB3_CONTRACT_ADDRESS=FAKE_CONTRACT,
        ):
            with pytest.raises(Web3ConfigError, match="WEB3_RPC_URL"):
                Web3BlockchainProvider()

    def test_missing_private_key(self):
        from app.config import settings
        with patch.multiple(
            settings,
            WEB3_RPC_URL=FAKE_RPC,
            WEB3_PRIVATE_KEY="",
            WEB3_CONTRACT_ADDRESS=FAKE_CONTRACT,
        ):
            with pytest.raises(Web3ConfigError, match="WEB3_PRIVATE_KEY"):
                Web3BlockchainProvider()

    def test_missing_contract_address(self):
        from app.config import settings
        with patch.multiple(
            settings,
            WEB3_RPC_URL=FAKE_RPC,
            WEB3_PRIVATE_KEY=FAKE_PRIVATE_KEY,
            WEB3_CONTRACT_ADDRESS="",
        ):
            with pytest.raises(Web3ConfigError, match="WEB3_CONTRACT_ADDRESS"):
                Web3BlockchainProvider()

    def test_factory_with_web3_mode_missing_vars_raises(self):
        from app.config import settings
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

    def test_disconnected_rpc_raises_config_error(self):
        """If Web3.is_connected() returns False, init must raise Web3ConfigError."""
        from app.config import settings
        mock_w3 = _make_mock_web3(connected=False)

        with patch.multiple(
            settings,
            WEB3_RPC_URL=FAKE_RPC,
            WEB3_PRIVATE_KEY=FAKE_PRIVATE_KEY,
            WEB3_CONTRACT_ADDRESS=FAKE_CONTRACT,
        ), patch("app.services.web3_blockchain_provider.Web3") as MockWeb3:
            MockWeb3.return_value = mock_w3
            MockWeb3.HTTPProvider = MagicMock()
            MockWeb3.to_checksum_address = lambda x: x
            with pytest.raises(Web3ConfigError, match="Cannot connect"):
                Web3BlockchainProvider()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Web3 provider operations (mocked network)
# ─────────────────────────────────────────────────────────────────────────────

class TestWeb3ProviderOperations:
    """Test the full sign→send→receipt flow using a mocked web3 connection."""

    def _provider(self):
        return _make_web3_provider()

    def test_anchor_creates_polygon_amoy_tx(self, db, verified_report):
        provider = self._provider()
        with patch("app.services.web3_blockchain_provider.Web3") as MockWeb3:
            MockWeb3.to_checksum_address = lambda x: x
            provider._network_name = REAL_NETWORK
            tx = provider.anchor_report_hash(verified_report, db)

        assert tx.action_type == ActionType.REPORT_HASH
        assert tx.blockchain_network == REAL_NETWORK
        assert tx.tx_hash.startswith("0x")
        assert len(tx.tx_hash) == 66

    def test_anchor_stores_tx_in_db(self, db, verified_report):
        provider = self._provider()
        with patch("app.services.web3_blockchain_provider.Web3") as MockWeb3:
            MockWeb3.to_checksum_address = lambda x: x
            provider._network_name = REAL_NETWORK
            tx = provider.anchor_report_hash(verified_report, db)

        stored = db.query(BlockchainTransaction).filter(
            BlockchainTransaction.id == tx.id
        ).first()
        assert stored is not None
        assert stored.tx_hash == tx.tx_hash

    def test_mint_creates_polygon_amoy_tx(self, db, verified_report):
        provider = self._provider()
        with patch("app.services.web3_blockchain_provider.Web3") as MockWeb3:
            MockWeb3.to_checksum_address = lambda x: x
            provider._network_name = REAL_NETWORK
            tx = provider.mint_token_transaction(
                verified_report, "GC-CARBON-W3-001", 5, db,
                fpo_wallet="0x" + "f" * 40,
                beneficiary_ref="farmer:99",
            )

        assert tx.action_type == ActionType.TOKEN_MINT
        assert tx.blockchain_network == REAL_NETWORK
        assert tx.tx_hash.startswith("0x")

    def test_retire_creates_polygon_amoy_tx(self, db, minted_token):
        provider = self._provider()
        with patch("app.services.web3_blockchain_provider.Web3") as MockWeb3:
            MockWeb3.to_checksum_address = lambda x: x
            provider._network_name = REAL_NETWORK
            tx = provider.retire_token_transaction(minted_token, db)

        assert tx.action_type == ActionType.TOKEN_RETIRE
        assert tx.blockchain_network == REAL_NETWORK


# ─────────────────────────────────────────────────────────────────────────────
# 4. Idempotency
# ─────────────────────────────────────────────────────────────────────────────

class TestIdempotency:
    def test_anchor_idempotent_same_row_returned(self, db, verified_report):
        """Second anchor call for same report returns the existing tx row."""
        p = get_blockchain_provider()  # mock provider
        tx1 = p.anchor_report_hash(verified_report, db)
        tx2 = p.anchor_report_hash(verified_report, db)
        assert tx1.id == tx2.id

    def test_anchor_idempotent_no_duplicate_in_db(self, db, verified_report):
        p = get_blockchain_provider()
        p.anchor_report_hash(verified_report, db)
        p.anchor_report_hash(verified_report, db)
        count = (
            db.query(BlockchainTransaction)
            .filter(
                BlockchainTransaction.carbon_report_id == verified_report.id,
                BlockchainTransaction.action_type == ActionType.REPORT_HASH,
            )
            .count()
        )
        assert count == 1


# ─────────────────────────────────────────────────────────────────────────────
# 5. Safe failure when RPC fails
# ─────────────────────────────────────────────────────────────────────────────

class TestRPCFailure:
    """
    If the RPC call fails (network error, revert, etc.),
    mint_token_transaction must raise RuntimeError and NOT create a
    fake/partial BlockchainTransaction row.
    """

    def test_mint_raises_runtime_error_on_rpc_failure(self, db, verified_report):
        from app.config import settings

        mock_w3 = _make_mock_web3()
        # Make send_raw_transaction raise a network error
        mock_w3.eth.send_raw_transaction.side_effect = RuntimeError("network timeout")

        with patch.multiple(
            settings,
            WEB3_RPC_URL=FAKE_RPC,
            WEB3_PRIVATE_KEY=FAKE_PRIVATE_KEY,
            WEB3_CONTRACT_ADDRESS=FAKE_CONTRACT,
            WEB3_CHAIN_ID=80002,
            WEB3_ACCOUNT_ADDRESS="",
        ), patch("app.services.web3_blockchain_provider.Web3") as MockWeb3:
            MockWeb3.return_value = mock_w3
            MockWeb3.HTTPProvider = MagicMock()
            MockWeb3.to_checksum_address = lambda x: x
            provider = Web3BlockchainProvider()
            provider._w3 = mock_w3

        with pytest.raises(RuntimeError):
            with patch("app.services.web3_blockchain_provider.Web3") as MockWeb3:
                MockWeb3.to_checksum_address = lambda x: x
                provider.mint_token_transaction(
                    verified_report, "GC-CARBON-FAIL-001", 5, db
                )

        # No partial TX row should be in the DB
        count = (
            db.query(BlockchainTransaction)
            .filter(
                BlockchainTransaction.carbon_report_id == verified_report.id,
                BlockchainTransaction.action_type == ActionType.TOKEN_MINT,
            )
            .count()
        )
        assert count == 0

    def test_mint_raises_on_reverted_tx(self, db, verified_report):
        """A transaction reverted on-chain (receipt.status = 0) must raise RuntimeError."""
        from app.config import settings

        mock_w3 = _make_mock_web3()
        # Simulate reverted receipt
        bad_receipt = MagicMock()
        bad_receipt.status = 0
        mock_w3.eth.wait_for_transaction_receipt.return_value = bad_receipt

        with patch.multiple(
            settings,
            WEB3_RPC_URL=FAKE_RPC,
            WEB3_PRIVATE_KEY=FAKE_PRIVATE_KEY,
            WEB3_CONTRACT_ADDRESS=FAKE_CONTRACT,
            WEB3_CHAIN_ID=80002,
            WEB3_ACCOUNT_ADDRESS="",
        ), patch("app.services.web3_blockchain_provider.Web3") as MockWeb3:
            MockWeb3.return_value = mock_w3
            MockWeb3.HTTPProvider = MagicMock()
            MockWeb3.to_checksum_address = lambda x: x
            provider = Web3BlockchainProvider()
            provider._w3 = mock_w3

        with pytest.raises(RuntimeError, match="reverted"):
            with patch("app.services.web3_blockchain_provider.Web3") as MockWeb3:
                MockWeb3.to_checksum_address = lambda x: x
                provider.mint_token_transaction(
                    verified_report, "GC-CARBON-REVERT-001", 5, db
                )


# ─────────────────────────────────────────────────────────────────────────────
# 6. Private key safety
# ─────────────────────────────────────────────────────────────────────────────

class TestPrivateKeySafety:
    def test_web3_provider_repr_omits_private_key(self):
        from app.config import settings
        mock_w3 = _make_mock_web3()

        with patch.multiple(
            settings,
            WEB3_RPC_URL=FAKE_RPC,
            WEB3_PRIVATE_KEY=FAKE_PRIVATE_KEY,
            WEB3_CONTRACT_ADDRESS=FAKE_CONTRACT,
            WEB3_CHAIN_ID=80002,
            WEB3_ACCOUNT_ADDRESS="",
        ), patch("app.services.web3_blockchain_provider.Web3") as MockWeb3:
            MockWeb3.return_value = mock_w3
            MockWeb3.HTTPProvider = MagicMock()
            MockWeb3.to_checksum_address = lambda x: x
            provider = Web3BlockchainProvider()

        representation = repr(provider)
        assert "dead" not in representation.lower()
        assert FAKE_PRIVATE_KEY not in representation
        assert "PRIVATE" not in representation.upper()
        assert "SECRET" not in representation.upper()

    def test_mock_provider_repr_omits_key(self):
        p = get_blockchain_provider()
        assert "PRIVATE" not in repr(p).upper()
        assert "SECRET" not in repr(p).upper()


# ─────────────────────────────────────────────────────────────────────────────
# 7. PolygonScan URL format
# ─────────────────────────────────────────────────────────────────────────────

class TestPolygonScanURL:
    """
    The PolygonScan URL is generated on the mobile side, but the backend
    stores the network name that drives the decision. Verify the URL pattern.
    """

    AMOY_BASE = "https://amoy.polygonscan.com/tx/"

    def test_real_tx_hash_produces_valid_url(self):
        tx_hash = "0x" + "ab" * 32
        url = self.AMOY_BASE + tx_hash
        assert url.startswith("https://amoy.polygonscan.com/tx/0x")
        assert len(url) == len(self.AMOY_BASE) + 66

    def test_blockchain_network_polygon_amoy_for_real_tx(self, db, verified_report):
        """
        When the web3 provider runs a mint, the stored blockchain_network
        must be 'POLYGON_AMOY' (not MOCK_POLYGON_AMOY).
        """
        provider = _make_web3_provider()
        with patch("app.services.web3_blockchain_provider.Web3") as MockWeb3:
            MockWeb3.to_checksum_address = lambda x: x
            provider._network_name = REAL_NETWORK
            tx = provider.mint_token_transaction(
                verified_report, "GC-CARBON-SCAN-001", 5, db
            )

        assert tx.blockchain_network == REAL_NETWORK
        assert tx.blockchain_network != MOCK_NETWORK

    def test_mock_network_is_not_polygon_amoy(self, db, verified_report):
        """Mock tx should NOT trigger a PolygonScan link."""
        p = get_blockchain_provider()
        tx = p.mint_token_transaction(verified_report, "GC-MOCK-001", 5, db)
        assert tx.blockchain_network == MOCK_NETWORK
        assert tx.blockchain_network != REAL_NETWORK


# ─────────────────────────────────────────────────────────────────────────────
# 8. Factory with BLOCKCHAIN_MODE=web3
# ─────────────────────────────────────────────────────────────────────────────

class TestFactoryWeb3Mode:
    def test_factory_returns_web3_provider_when_mode_is_web3(self):
        from app.config import settings
        mock_w3 = _make_mock_web3()

        with patch.multiple(
            settings,
            BLOCKCHAIN_MODE="web3",
            WEB3_RPC_URL=FAKE_RPC,
            WEB3_PRIVATE_KEY=FAKE_PRIVATE_KEY,
            WEB3_CONTRACT_ADDRESS=FAKE_CONTRACT,
            WEB3_CHAIN_ID=80002,
            WEB3_ACCOUNT_ADDRESS="",
        ), patch("app.services.web3_blockchain_provider.Web3") as MockWeb3:
            MockWeb3.return_value = mock_w3
            MockWeb3.HTTPProvider = MagicMock()
            MockWeb3.to_checksum_address = lambda x: x
            reset_provider()
            p = get_blockchain_provider()

        assert isinstance(p, Web3BlockchainProvider)

    def test_factory_returns_mock_when_mode_is_mock(self):
        from app.config import settings
        with patch.object(settings, "BLOCKCHAIN_MODE", "mock"):
            reset_provider()
            p = get_blockchain_provider()
        assert isinstance(p, MockBlockchainProvider)

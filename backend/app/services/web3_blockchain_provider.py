"""
Web3BlockchainProvider — Phase 6.

Real blockchain integration using web3.py.
Calls the deployed GreenChainCarbonCredit smart contract on
Polygon Amoy testnet or Ethereum Sepolia testnet.

Required environment variables (BLOCKCHAIN_MODE=web3):
    WEB3_RPC_URL           — HTTPS RPC endpoint (Alchemy / Infura / public)
    WEB3_PRIVATE_KEY       — 0x-prefixed hex private key of the admin wallet
    WEB3_CONTRACT_ADDRESS  — deployed contract address
    WEB3_CHAIN_ID          — 80002 (Amoy) or 11155111 (Sepolia)
    WEB3_ACCOUNT_ADDRESS   — admin wallet address (derived from key if omitted)

Security:
    * Private key is read once from settings and never logged or returned.
    * __repr__ / __str__ intentionally omit the key.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.blockchain_transaction import (
    BlockchainTransaction,
    ActionType,
    MOCK_NETWORK,
    MOCK_CONTRACT_ADDRESS,
)
from app.models.carbon_report import CarbonReport, ReportStatus
from app.services.blockchain_provider import BlockchainProvider

logger = logging.getLogger(__name__)

# web3 is imported at module level so tests can patch
# app.services.web3_blockchain_provider.Web3
try:
    from web3 import Web3
    WEB3_AVAILABLE = True
except ImportError:                                # pragma: no cover
    WEB3_AVAILABLE = False
    Web3 = None  # type: ignore[assignment,misc]

# ── ABI (embedded from compiled GreenChainCarbonCredit.sol) ───────────────────
# Loaded at import time; only the functions we call are strictly needed
# but the full ABI is included for correctness.
GREENCHAIN_ABI = [
    {"inputs": [], "stateMutability": "nonpayable", "type": "constructor"},
    # ── errors ────────────────────────────────────────────────────────────────
    {"inputs": [{"internalType": "address", "name": "sender", "type": "address"}, {"internalType": "uint256", "name": "balance", "type": "uint256"}, {"internalType": "uint256", "name": "needed", "type": "uint256"}, {"internalType": "uint256", "name": "tokenId", "type": "uint256"}], "name": "ERC1155InsufficientBalance", "type": "error"},
    {"inputs": [{"internalType": "address", "name": "approver", "type": "address"}], "name": "ERC1155InvalidApprover", "type": "error"},
    {"inputs": [{"internalType": "uint256", "name": "idsLength", "type": "uint256"}, {"internalType": "uint256", "name": "valuesLength", "type": "uint256"}], "name": "ERC1155InvalidArrayLength", "type": "error"},
    {"inputs": [{"internalType": "address", "name": "operator", "type": "address"}], "name": "ERC1155InvalidOperator", "type": "error"},
    {"inputs": [{"internalType": "address", "name": "receiver", "type": "address"}], "name": "ERC1155InvalidReceiver", "type": "error"},
    {"inputs": [{"internalType": "address", "name": "sender", "type": "address"}], "name": "ERC1155InvalidSender", "type": "error"},
    {"inputs": [{"internalType": "address", "name": "operator", "type": "address"}, {"internalType": "address", "name": "owner", "type": "address"}], "name": "ERC1155MissingApprovalForAll", "type": "error"},
    {"inputs": [{"internalType": "address", "name": "owner", "type": "address"}], "name": "OwnableInvalidOwner", "type": "error"},
    {"inputs": [{"internalType": "address", "name": "account", "type": "address"}], "name": "OwnableUnauthorizedAccount", "type": "error"},
    # ── events ────────────────────────────────────────────────────────────────
    {"anonymous": False, "inputs": [{"indexed": True, "internalType": "address", "name": "account", "type": "address"}, {"indexed": True, "internalType": "address", "name": "operator", "type": "address"}, {"indexed": False, "internalType": "bool", "name": "approved", "type": "bool"}], "name": "ApprovalForAll", "type": "event"},
    {"anonymous": False, "inputs": [{"indexed": True, "internalType": "uint256", "name": "reportId", "type": "uint256"}, {"indexed": True, "internalType": "uint256", "name": "tokenId", "type": "uint256"}, {"indexed": True, "internalType": "address", "name": "farmer", "type": "address"}, {"indexed": False, "internalType": "uint256", "name": "creditAmount", "type": "uint256"}, {"indexed": False, "internalType": "string", "name": "reportHash", "type": "string"}], "name": "CarbonCreditMinted", "type": "event"},
    {"anonymous": False, "inputs": [{"indexed": True, "internalType": "uint256", "name": "tokenId", "type": "uint256"}, {"indexed": True, "internalType": "address", "name": "retiredBy", "type": "address"}], "name": "CarbonCreditRetired", "type": "event"},
    {"anonymous": False, "inputs": [{"indexed": True, "internalType": "uint256", "name": "tokenId", "type": "uint256"}, {"indexed": True, "internalType": "address", "name": "suspendedBy", "type": "address"}], "name": "CarbonCreditSuspended", "type": "event"},
    {"anonymous": False, "inputs": [{"indexed": True, "internalType": "address", "name": "previousOwner", "type": "address"}, {"indexed": True, "internalType": "address", "name": "newOwner", "type": "address"}], "name": "OwnershipTransferred", "type": "event"},
    {"anonymous": False, "inputs": [{"indexed": True, "internalType": "uint256", "name": "reportId", "type": "uint256"}, {"indexed": False, "internalType": "string", "name": "reportHash", "type": "string"}, {"indexed": True, "internalType": "address", "name": "anchoredBy", "type": "address"}], "name": "ReportAnchored", "type": "event"},
    {"anonymous": False, "inputs": [{"indexed": True, "internalType": "address", "name": "operator", "type": "address"}, {"indexed": True, "internalType": "address", "name": "from", "type": "address"}, {"indexed": True, "internalType": "address", "name": "to", "type": "address"}, {"indexed": False, "internalType": "uint256[]", "name": "ids", "type": "uint256[]"}, {"indexed": False, "internalType": "uint256[]", "name": "values", "type": "uint256[]"}], "name": "TransferBatch", "type": "event"},
    {"anonymous": False, "inputs": [{"indexed": True, "internalType": "address", "name": "operator", "type": "address"}, {"indexed": True, "internalType": "address", "name": "from", "type": "address"}, {"indexed": True, "internalType": "address", "name": "to", "type": "address"}, {"indexed": False, "internalType": "uint256", "name": "id", "type": "uint256"}, {"indexed": False, "internalType": "uint256", "name": "value", "type": "uint256"}], "name": "TransferSingle", "type": "event"},
    {"anonymous": False, "inputs": [{"indexed": False, "internalType": "string", "name": "value", "type": "string"}, {"indexed": True, "internalType": "uint256", "name": "id", "type": "uint256"}], "name": "URI", "type": "event"},
    # ── functions ─────────────────────────────────────────────────────────────
    {"inputs": [{"internalType": "uint256", "name": "reportId", "type": "uint256"}, {"internalType": "string", "name": "reportHash", "type": "string"}], "name": "anchorReport", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "account", "type": "address"}, {"internalType": "uint256", "name": "id", "type": "uint256"}], "name": "balanceOf", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "uint256", "name": "reportId", "type": "uint256"}], "name": "getReportHash", "outputs": [{"internalType": "string", "name": "", "type": "string"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "uint256", "name": "reportId", "type": "uint256"}], "name": "isReportAnchored", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}], "name": "isTokenRetired", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}], "name": "isTokenSuspended", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "uint256", "name": "reportId", "type": "uint256"}, {"internalType": "address", "name": "farmer", "type": "address"}, {"internalType": "uint256", "name": "creditAmount", "type": "uint256"}, {"internalType": "string", "name": "reportHash", "type": "string"}], "name": "mintCarbonCredit", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "uint256", "name": "reportId", "type": "uint256"}, {"internalType": "address", "name": "fpoVault", "type": "address"}, {"internalType": "uint256", "name": "creditAmount", "type": "uint256"}, {"internalType": "string", "name": "reportHash", "type": "string"}, {"internalType": "string", "name": "beneficiaryRef", "type": "string"}], "name": "mintCustodialCarbonCredit", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"anonymous": False, "inputs": [{"indexed": True, "internalType": "uint256", "name": "reportId", "type": "uint256"}, {"indexed": True, "internalType": "uint256", "name": "tokenId", "type": "uint256"}, {"indexed": True, "internalType": "address", "name": "fpoVault", "type": "address"}, {"indexed": False, "internalType": "uint256", "name": "creditAmount", "type": "uint256"}, {"indexed": False, "internalType": "string", "name": "beneficiaryRef", "type": "string"}, {"indexed": False, "internalType": "string", "name": "reportHash", "type": "string"}], "name": "CustodialCarbonCreditMinted", "type": "event"},
    {"inputs": [], "name": "owner", "outputs": [{"internalType": "address", "name": "", "type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "renounceOwnership", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}], "name": "retireToken", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}], "name": "suspendToken", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "newOwner", "type": "address"}], "name": "transferOwnership", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "name": "uri", "outputs": [{"internalType": "string", "name": "", "type": "string"}], "stateMutability": "view", "type": "function"},
]

# Canonical network names stored in DB when web3 mode is active
_NETWORK_NAMES = {
    80002: "POLYGON_AMOY",
    11155111: "ETHEREUM_SEPOLIA",
}


class Web3ConfigError(RuntimeError):
    """Raised when required web3 environment variables are missing."""


class Web3BlockchainProvider(BlockchainProvider):
    """
    Production blockchain provider.

    Connects to the deployed GreenChainCarbonCredit contract and
    sends signed transactions from the configured admin wallet.

    Transaction flow for each operation:
        1. Build EVM transaction via contract function
        2. Estimate gas
        3. Sign with admin private key
        4. Broadcast raw transaction
        5. Wait for on-chain confirmation (receipt)
        6. Persist BlockchainTransaction row with real tx_hash
        7. Return BlockchainTransaction

    The `db` parameter is the active SQLAlchemy session — the same
    pattern used by MockBlockchainProvider so callers are unchanged.
    """

    def __init__(self) -> None:
        self._validate_config()
        self._init_web3()

    # ── Config validation ──────────────────────────────────────────────────────

    def _validate_config(self) -> None:
        missing = []
        if not settings.WEB3_RPC_URL:
            missing.append("WEB3_RPC_URL")
        if not settings.WEB3_PRIVATE_KEY:
            missing.append("WEB3_PRIVATE_KEY")
        if not settings.WEB3_CONTRACT_ADDRESS:
            missing.append("WEB3_CONTRACT_ADDRESS")
        if missing:
            raise Web3ConfigError(
                f"BLOCKCHAIN_MODE=web3 requires these env vars to be set: "
                f"{', '.join(missing)}.  "
                f"Set them in your .env file or switch to BLOCKCHAIN_MODE=mock."
            )

    # ── Web3 initialisation ────────────────────────────────────────────────────

    def _init_web3(self) -> None:
        self._w3 = Web3(Web3.HTTPProvider(settings.WEB3_RPC_URL))
        if not self._w3.is_connected():
            raise Web3ConfigError(
                f"Cannot connect to RPC endpoint: {settings.WEB3_RPC_URL}"
            )

        # Derive account address from private key if not explicitly set
        account = self._w3.eth.account.from_key(settings.WEB3_PRIVATE_KEY)
        self._account_address: str = (
            settings.WEB3_ACCOUNT_ADDRESS
            or account.address
        )

        self._contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(settings.WEB3_CONTRACT_ADDRESS),
            abi=GREENCHAIN_ABI,
        )

        chain_id = settings.WEB3_CHAIN_ID
        self._network_name: str = _NETWORK_NAMES.get(chain_id, f"CHAIN_{chain_id}")
        self._chain_id: int = chain_id

        logger.info(
            "Web3BlockchainProvider connected | network=%s chain_id=%s contract=%s account=%s",
            self._network_name,
            self._chain_id,
            settings.WEB3_CONTRACT_ADDRESS,
            self._account_address,
        )
        # NEVER log private key

    # ── Internal: sign + broadcast + confirm ──────────────────────────────────

    @staticmethod
    def _decode_revert_reason(exc: Exception) -> str:
        """
        Try to extract a human-readable revert reason from a web3.py exception.
        Handles ContractLogicError (eth_call revert), ContractCustomError, and raw strings.
        """
        msg = str(exc)
        exc_type = type(exc).__name__

        # web3.py >= 6: ContractLogicError has .message attribute
        if hasattr(exc, "message") and exc.message:  # type: ignore[attr-defined]
            return str(exc.message)  # type: ignore[attr-defined]

        # ContractLogicError string format: "execution reverted: <reason>"
        if "execution reverted:" in msg:
            return msg.split("execution reverted:", 1)[-1].strip() or msg

        # ContractCustomError — Solidity custom error names
        if "ContractCustomError" in exc_type or "custom error" in msg.lower():
            return f"Contract custom error: {msg}"

        return msg

    def _send_tx(self, contract_fn) -> str:
        """
        Build, sign, send, and wait for a contract function call.
        Returns the transaction hash as a 0x-prefixed hex string.

        Raises RuntimeError with a decoded revert reason on failure.
        """
        nonce = self._w3.eth.get_transaction_count(self._account_address, "pending")
        gas_price = self._w3.eth.gas_price

        raw_tx = contract_fn.build_transaction({
            "from":     self._account_address,
            "nonce":    nonce,
            "gasPrice": gas_price,
            "chainId":  self._chain_id,
        })

        # Estimate gas via eth_call — this catches reverts BEFORE spending gas.
        # add 20 % buffer on success.
        try:
            estimated = self._w3.eth.estimate_gas(raw_tx)
            raw_tx["gas"] = int(estimated * 1.2)
        except Exception as gas_exc:
            reason = self._decode_revert_reason(gas_exc)
            logger.error(
                "_send_tx gas estimation failed | account=%s reason=%s",
                self._account_address, reason,
            )
            raise RuntimeError(f"Smart contract reverted: {reason}") from gas_exc

        signed = self._w3.eth.account.sign_transaction(
            raw_tx, private_key=settings.WEB3_PRIVATE_KEY
        )
        tx_hash_bytes = self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=180)

        if receipt.status != 1:
            tx_hex = "0x" + tx_hash_bytes.hex()
            logger.error(
                "_send_tx on-chain revert | tx=%s account=%s", tx_hex, self._account_address,
            )
            raise RuntimeError(
                f"Transaction reverted on-chain: {tx_hex}"
            )

        return "0x" + tx_hash_bytes.hex()

    # ── Private key safety ─────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"<Web3BlockchainProvider network={self._network_name} "
            f"contract={settings.WEB3_CONTRACT_ADDRESS} "
            f"account={self._account_address}>"
        )

    # Private key intentionally excluded from __repr__ and __str__

    # ── BlockchainProvider interface ───────────────────────────────────────────

    def anchor_report_hash(
        self, carbon_report: CarbonReport, db: Session
    ) -> BlockchainTransaction:
        if carbon_report.status != ReportStatus.VERIFIED:
            raise ValueError(
                f"Only VERIFIED reports can be anchored. "
                f"Current status: {carbon_report.status.value}"
            )

        # Idempotency: check DB first to avoid double transaction fee
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

        tx_hash = self._send_tx(
            self._contract.functions.anchorReport(
                carbon_report.id, carbon_report.report_hash
            )
        )
        logger.info("anchorReport tx=%s report_id=%s", tx_hash, carbon_report.id)

        tx = BlockchainTransaction(
            carbon_report_id=carbon_report.id,
            tx_hash=tx_hash,
            blockchain_network=self._network_name,
            contract_address=settings.WEB3_CONTRACT_ADDRESS,
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
        # Validate contract address
        try:
            contract_addr = Web3.to_checksum_address(settings.WEB3_CONTRACT_ADDRESS)
        except Exception:
            raise RuntimeError(f"Contract address invalid: {settings.WEB3_CONTRACT_ADDRESS}")

        logger.info(
            "mint_token_transaction | report_id=%s credit_amount=%s fpo_wallet=%s "
            "signer=%s contract=%s network=%s",
            carbon_report.id, credit_amount, fpo_wallet or "(none)",
            self._account_address, contract_addr, self._network_name,
        )

        try:
            if fpo_wallet:
                # ── Custodial path: mint to FPO vault ─────────────────────────────
                vault_address = Web3.to_checksum_address(fpo_wallet)
                ref = beneficiary_ref or ""
                tx_hash = self._send_tx(
                    self._contract.functions.mintCustodialCarbonCredit(
                        carbon_report.id,
                        vault_address,
                        credit_amount,
                        carbon_report.report_hash,
                        ref,
                    )
                )
                logger.info(
                    "mintCustodialCarbonCredit tx=%s report_id=%s fpo_vault=%s",
                    tx_hash, carbon_report.id, vault_address,
                )
            else:
                # ── Legacy path: admin wallet as placeholder (no farmer wallet) ───
                recipient = Web3.to_checksum_address(self._account_address)
                tx_hash = self._send_tx(
                    self._contract.functions.mintCarbonCredit(
                        carbon_report.id,
                        recipient,
                        credit_amount,
                        carbon_report.report_hash,
                    )
                )
                logger.info("mintCarbonCredit tx=%s report_id=%s", tx_hash, carbon_report.id)
        except RuntimeError:
            raise  # already decoded in _send_tx
        except Exception as exc:
            reason = self._decode_revert_reason(exc)
            logger.error(
                "mint_token_transaction failed | report_id=%s error=%s",
                carbon_report.id, reason,
            )
            raise RuntimeError(f"Web3 transaction failed: {reason}") from exc

        tx = BlockchainTransaction(
            carbon_report_id=carbon_report.id,
            tx_hash=tx_hash,
            blockchain_network=self._network_name,
            contract_address=settings.WEB3_CONTRACT_ADDRESS,
            action_type=ActionType.TOKEN_MINT,
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        return tx

    def retire_token_transaction(self, token, db: Session) -> BlockchainTransaction:
        tx_hash = self._send_tx(
            self._contract.functions.retireToken(token.carbon_report_id)
        )
        logger.info("retireToken tx=%s token_id=%s", tx_hash, token.id)

        tx = BlockchainTransaction(
            carbon_report_id=token.carbon_report_id,
            tx_hash=tx_hash,
            blockchain_network=self._network_name,
            contract_address=settings.WEB3_CONTRACT_ADDRESS,
            action_type=ActionType.TOKEN_RETIRE,
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        return tx

    def suspend_token_transaction(self, token, db: Session) -> BlockchainTransaction:
        tx_hash = self._send_tx(
            self._contract.functions.suspendToken(token.carbon_report_id)
        )
        logger.info("suspendToken tx=%s token_id=%s", tx_hash, token.id)

        tx = BlockchainTransaction(
            carbon_report_id=token.carbon_report_id,
            tx_hash=tx_hash,
            blockchain_network=self._network_name,
            contract_address=settings.WEB3_CONTRACT_ADDRESS,
            action_type=ActionType.TOKEN_SUSPEND,
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        return tx

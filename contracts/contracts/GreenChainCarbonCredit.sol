// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "@openzeppelin/contracts/token/ERC1155/ERC1155.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title  GreenChainCarbonCredit
 * @notice On-chain registry for GreenChain carbon credit MRV data.
 *         - Anchors SHA-256 carbon report hashes immutably on-chain.
 *         - Mints ERC-1155 carbon credit tokens (tokenId == reportId).
 *         - Supports retirement and suspension of tokens.
 * @dev    All state-changing functions are restricted to the contract owner
 *         (the GreenChain admin wallet). Designed to be upgraded to a proxy
 *         pattern in a future phase.
 */
contract GreenChainCarbonCredit is ERC1155, Ownable {

    // ── Events ─────────────────────────────────────────────────────────────────

    /// @notice Emitted when a carbon report hash is anchored on-chain.
    event ReportAnchored(
        uint256 indexed reportId,
        string  reportHash,
        address indexed anchoredBy
    );

    /// @notice Emitted when a carbon credit token is minted (direct farmer custody).
    event CarbonCreditMinted(
        uint256 indexed reportId,
        uint256 indexed tokenId,
        address indexed farmer,
        uint256 creditAmount,
        string  reportHash
    );

    /// @notice Emitted when a custodial carbon credit token is minted to an FPO vault.
    ///         The FPO holds the on-chain token; the beneficiary farmer holds off-chain
    ///         credit balance tracked in the GreenChain database.
    event CustodialCarbonCreditMinted(
        uint256 indexed reportId,
        uint256 indexed tokenId,
        address indexed fpoVault,
        uint256 creditAmount,
        string  beneficiaryRef,
        string  reportHash
    );

    /// @notice Emitted when a token is retired (permanent offset).
    event CarbonCreditRetired(
        uint256 indexed tokenId,
        address indexed retiredBy
    );

    /// @notice Emitted when a token is suspended (administrative hold).
    event CarbonCreditSuspended(
        uint256 indexed tokenId,
        address indexed suspendedBy
    );

    // ── Storage ────────────────────────────────────────────────────────────────

    /// report_id  →  SHA-256 hash string
    mapping(uint256 => string) private _reportHashes;

    /// report_id  →  anchored flag
    mapping(uint256 => bool) private _anchoredReports;

    /// report_id  →  token-minted flag  (tokenId == reportId)
    mapping(uint256 => bool) private _mintedTokens;

    /// token_id   →  retired flag
    mapping(uint256 => bool) private _retiredTokens;

    /// token_id   →  suspended flag
    mapping(uint256 => bool) private _suspendedTokens;

    // ── Constructor ────────────────────────────────────────────────────────────

    constructor() ERC1155("") Ownable(msg.sender) {}

    // ── Owner-only state-changing functions ────────────────────────────────────

    /**
     * @notice Anchor a carbon report hash on-chain.
     * @param reportId   Back-end database id of the carbon report.
     * @param reportHash SHA-256 hex digest of the report data (64 chars).
     */
    function anchorReport(
        uint256 reportId,
        string  memory reportHash
    ) external onlyOwner {
        require(!_anchoredReports[reportId], "GCC: report already anchored");
        require(bytes(reportHash).length > 0, "GCC: empty report hash");

        _anchoredReports[reportId] = true;
        _reportHashes[reportId]    = reportHash;

        emit ReportAnchored(reportId, reportHash, msg.sender);
    }

    /**
     * @notice Mint an ERC-1155 carbon credit token for a verified report.
     * @param reportId     Back-end database id (also used as the ERC-1155 tokenId).
     * @param farmer       Wallet address that will receive the token.
     * @param creditAmount Number of carbon credits (may be 0 for cert-style tokens).
     * @param reportHash   SHA-256 hex digest for metadata integrity.
     */
    function mintCarbonCredit(
        uint256 reportId,
        address farmer,
        uint256 creditAmount,
        string  memory reportHash
    ) external onlyOwner {
        require(!_mintedTokens[reportId], "GCC: token already minted for this report");
        require(farmer != address(0),     "GCC: zero address farmer");

        _mintedTokens[reportId] = true;

        // ERC-1155 amount must be > 0; for zero-credit certs we mint 1 unit.
        uint256 mintAmount = creditAmount > 0 ? creditAmount : 1;
        _mint(farmer, reportId, mintAmount, "");

        emit CarbonCreditMinted(reportId, reportId, farmer, creditAmount, reportHash);
    }

    /**
     * @notice Permanently retire a carbon credit token (marks offset as used).
     * @param tokenId  ERC-1155 token id (== reportId).
     */
    function retireToken(uint256 tokenId) external onlyOwner {
        require(_mintedTokens[tokenId],    "GCC: token does not exist");
        require(!_retiredTokens[tokenId],  "GCC: token already retired");

        _retiredTokens[tokenId] = true;

        emit CarbonCreditRetired(tokenId, msg.sender);
    }

    /**
     * @notice Administratively suspend a carbon credit token.
     * @param tokenId  ERC-1155 token id (== reportId).
     */
    function suspendToken(uint256 tokenId) external onlyOwner {
        require(_mintedTokens[tokenId],      "GCC: token does not exist");
        require(!_suspendedTokens[tokenId],  "GCC: token already suspended");

        _suspendedTokens[tokenId] = true;

        emit CarbonCreditSuspended(tokenId, msg.sender);
    }

    /**
     * @notice Mint an ERC-1155 carbon credit token to an FPO vault wallet (custodial model).
     *         The FPO acts as custodian; the actual beneficiary farmer is recorded
     *         off-chain in the GreenChain database and referenced here as a string.
     * @param reportId       Back-end database id (also used as the ERC-1155 tokenId).
     * @param fpoVault       FPO wallet address that will hold the token on behalf of the farmer.
     * @param creditAmount   Number of carbon credits (may be 0 for cert-style tokens).
     * @param reportHash     SHA-256 hex digest for metadata integrity.
     * @param beneficiaryRef Opaque reference to the beneficiary farmer (e.g. "farmer:42").
     */
    function mintCustodialCarbonCredit(
        uint256 reportId,
        address fpoVault,
        uint256 creditAmount,
        string  memory reportHash,
        string  memory beneficiaryRef
    ) external onlyOwner {
        require(!_mintedTokens[reportId], "GCC: token already minted for this report");
        require(fpoVault != address(0),   "GCC: zero address fpoVault");

        _mintedTokens[reportId] = true;

        uint256 mintAmount = creditAmount > 0 ? creditAmount : 1;
        _mint(fpoVault, reportId, mintAmount, "");

        emit CustodialCarbonCreditMinted(
            reportId,
            reportId,
            fpoVault,
            creditAmount,
            beneficiaryRef,
            reportHash
        );
    }

    // ── View functions ─────────────────────────────────────────────────────────

    /// @return True if the report has been anchored.
    function isReportAnchored(uint256 reportId) external view returns (bool) {
        return _anchoredReports[reportId];
    }

    /// @return True if the token has been retired.
    function isTokenRetired(uint256 tokenId) external view returns (bool) {
        return _retiredTokens[tokenId];
    }

    /// @return True if the token has been suspended.
    function isTokenSuspended(uint256 tokenId) external view returns (bool) {
        return _suspendedTokens[tokenId];
    }

    /// @return The anchored SHA-256 hash for a given reportId (empty if not anchored).
    function getReportHash(uint256 reportId) external view returns (string memory) {
        return _reportHashes[reportId];
    }
}

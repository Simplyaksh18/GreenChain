const { expect }          = require("chai");
const { ethers }          = require("hardhat");
const { loadFixture }     = require("@nomicfoundation/hardhat-toolbox/network-helpers");

// ── Fixture ─────────────────────────────────────────────────────────────────────
async function deployFixture() {
  const [owner, otherAccount, farmerAccount] = await ethers.getSigners();

  const Factory  = await ethers.getContractFactory("GreenChainCarbonCredit");
  const contract = await Factory.deploy();
  await contract.waitForDeployment();

  return { contract, owner, otherAccount, farmerAccount };
}

// ── Test suite ───────────────────────────────────────────────────────────────────
describe("GreenChainCarbonCredit", function () {

  // ── Deployment ──────────────────────────────────────────────────────────────
  describe("Deployment", function () {
    it("should set the owner to the deployer", async function () {
      const { contract, owner } = await loadFixture(deployFixture);
      expect(await contract.owner()).to.equal(owner.address);
    });
  });

  // ── anchorReport ────────────────────────────────────────────────────────────
  describe("anchorReport", function () {
    it("owner can anchor a report", async function () {
      const { contract } = await loadFixture(deployFixture);
      const reportId   = 1;
      const reportHash = "a".repeat(64);

      await expect(contract.anchorReport(reportId, reportHash))
        .to.emit(contract, "ReportAnchored")
        .withArgs(reportId, reportHash, (await ethers.getSigners())[0].address);

      expect(await contract.isReportAnchored(reportId)).to.equal(true);
      expect(await contract.getReportHash(reportId)).to.equal(reportHash);
    });

    it("non-owner cannot anchor", async function () {
      const { contract, otherAccount } = await loadFixture(deployFixture);
      await expect(
        contract.connect(otherAccount).anchorReport(1, "a".repeat(64))
      ).to.be.revertedWithCustomError(contract, "OwnableUnauthorizedAccount");
    });

    it("duplicate anchor is rejected", async function () {
      const { contract } = await loadFixture(deployFixture);
      await contract.anchorReport(1, "a".repeat(64));
      await expect(
        contract.anchorReport(1, "b".repeat(64))
      ).to.be.revertedWith("GCC: report already anchored");
    });

    it("empty report hash is rejected", async function () {
      const { contract } = await loadFixture(deployFixture);
      await expect(
        contract.anchorReport(1, "")
      ).to.be.revertedWith("GCC: empty report hash");
    });

    it("unanchored report returns false and empty hash", async function () {
      const { contract } = await loadFixture(deployFixture);
      expect(await contract.isReportAnchored(999)).to.equal(false);
      expect(await contract.getReportHash(999)).to.equal("");
    });
  });

  // ── mintCarbonCredit ─────────────────────────────────────────────────────────
  describe("mintCarbonCredit", function () {
    it("owner can mint a carbon credit token", async function () {
      const { contract, farmerAccount } = await loadFixture(deployFixture);
      const reportId = 10;
      const hash     = "c".repeat(64);

      await expect(
        contract.mintCarbonCredit(reportId, farmerAccount.address, 5, hash)
      )
        .to.emit(contract, "CarbonCreditMinted")
        .withArgs(reportId, reportId, farmerAccount.address, 5, hash);

      expect(await contract.balanceOf(farmerAccount.address, reportId)).to.equal(5);
    });

    it("non-owner cannot mint", async function () {
      const { contract, otherAccount, farmerAccount } = await loadFixture(deployFixture);
      await expect(
        contract.connect(otherAccount).mintCarbonCredit(1, farmerAccount.address, 5, "a".repeat(64))
      ).to.be.revertedWithCustomError(contract, "OwnableUnauthorizedAccount");
    });

    it("duplicate mint is blocked", async function () {
      const { contract, farmerAccount } = await loadFixture(deployFixture);
      await contract.mintCarbonCredit(1, farmerAccount.address, 5, "a".repeat(64));
      await expect(
        contract.mintCarbonCredit(1, farmerAccount.address, 3, "a".repeat(64))
      ).to.be.revertedWith("GCC: token already minted for this report");
    });

    it("zero-credit certificate mints 1 unit for valid ERC-1155", async function () {
      const { contract, farmerAccount } = await loadFixture(deployFixture);
      await contract.mintCarbonCredit(42, farmerAccount.address, 0, "d".repeat(64));
      // ERC-1155 mint amount is 1 when creditAmount is 0
      expect(await contract.balanceOf(farmerAccount.address, 42)).to.equal(1);
    });

    it("zero address farmer is rejected", async function () {
      const { contract } = await loadFixture(deployFixture);
      await expect(
        contract.mintCarbonCredit(1, ethers.ZeroAddress, 5, "a".repeat(64))
      ).to.be.revertedWith("GCC: zero address farmer");
    });
  });

  // ── retireToken ─────────────────────────────────────────────────────────────
  describe("retireToken", function () {
    async function mintedFixture() {
      const f = await deployFixture();
      await f.contract.mintCarbonCredit(1, f.farmerAccount.address, 5, "e".repeat(64));
      return f;
    }

    it("owner can retire a token", async function () {
      const { contract, owner } = await loadFixture(mintedFixture);
      await expect(contract.retireToken(1))
        .to.emit(contract, "CarbonCreditRetired")
        .withArgs(1, owner.address);
      expect(await contract.isTokenRetired(1)).to.equal(true);
    });

    it("non-owner cannot retire", async function () {
      const { contract, otherAccount } = await loadFixture(mintedFixture);
      await expect(
        contract.connect(otherAccount).retireToken(1)
      ).to.be.revertedWithCustomError(contract, "OwnableUnauthorizedAccount");
    });

    it("double retirement is blocked", async function () {
      const { contract } = await loadFixture(mintedFixture);
      await contract.retireToken(1);
      await expect(contract.retireToken(1)).to.be.revertedWith("GCC: token already retired");
    });

    it("retiring non-existent token reverts", async function () {
      const { contract } = await loadFixture(deployFixture);
      await expect(contract.retireToken(999)).to.be.revertedWith("GCC: token does not exist");
    });
  });

  // ── suspendToken ─────────────────────────────────────────────────────────────
  describe("suspendToken", function () {
    async function mintedFixture() {
      const f = await deployFixture();
      await f.contract.mintCarbonCredit(2, f.farmerAccount.address, 3, "f".repeat(64));
      return f;
    }

    it("owner can suspend a token", async function () {
      const { contract, owner } = await loadFixture(mintedFixture);
      await expect(contract.suspendToken(2))
        .to.emit(contract, "CarbonCreditSuspended")
        .withArgs(2, owner.address);
      expect(await contract.isTokenSuspended(2)).to.equal(true);
    });

    it("non-owner cannot suspend", async function () {
      const { contract, otherAccount } = await loadFixture(mintedFixture);
      await expect(
        contract.connect(otherAccount).suspendToken(2)
      ).to.be.revertedWithCustomError(contract, "OwnableUnauthorizedAccount");
    });

    it("double suspension is blocked", async function () {
      const { contract } = await loadFixture(mintedFixture);
      await contract.suspendToken(2);
      await expect(contract.suspendToken(2)).to.be.revertedWith("GCC: token already suspended");
    });

    it("suspending non-existent token reverts", async function () {
      const { contract } = await loadFixture(deployFixture);
      await expect(contract.suspendToken(999)).to.be.revertedWith("GCC: token does not exist");
    });
  });

  // ── Read functions ────────────────────────────────────────────────────────────
  describe("Read functions", function () {
    it("isTokenRetired returns false for non-retired token", async function () {
      const { contract, farmerAccount } = await loadFixture(deployFixture);
      await contract.mintCarbonCredit(5, farmerAccount.address, 1, "g".repeat(64));
      expect(await contract.isTokenRetired(5)).to.equal(false);
    });

    it("isTokenSuspended returns false for non-suspended token", async function () {
      const { contract, farmerAccount } = await loadFixture(deployFixture);
      await contract.mintCarbonCredit(6, farmerAccount.address, 1, "h".repeat(64));
      expect(await contract.isTokenSuspended(6)).to.equal(false);
    });
  });
});

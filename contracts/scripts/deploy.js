/**
 * deploy.js — Deploy GreenChainCarbonCredit to the selected network.
 *
 * Usage:
 *   npx hardhat run scripts/deploy.js --network amoy
 *   npx hardhat run scripts/deploy.js --network sepolia
 *   npx hardhat run scripts/deploy.js --network localhost
 *
 * After deployment this script writes two files so the Python backend
 * can pick them up automatically:
 *
 *   contracts/deployments/<network>.json   — address, chainId, txHash, timestamp
 *   contracts/artifacts/abi.json           — flattened ABI for backend use
 */

const { ethers, network, artifacts } = require("hardhat");
const fs   = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await ethers.getSigners();
  const balance    = await ethers.provider.getBalance(deployer.address);

  console.log("=".repeat(60));
  console.log("  GreenChain — Deploying GreenChainCarbonCredit");
  console.log("=".repeat(60));
  console.log(`  Network    : ${network.name}`);
  console.log(`  Chain ID   : ${network.config.chainId ?? "unknown"}`);
  console.log(`  Deployer   : ${deployer.address}`);
  console.log(`  Balance    : ${ethers.formatEther(balance)} ETH/MATIC`);
  console.log("-".repeat(60));

  // ── Deploy ──────────────────────────────────────────────────────────────────
  const Factory  = await ethers.getContractFactory("GreenChainCarbonCredit");
  const contract = await Factory.deploy();
  await contract.waitForDeployment();

  const contractAddress = await contract.getAddress();
  const deployTx        = contract.deploymentTransaction();
  const txHash          = deployTx ? deployTx.hash : "n/a";

  console.log(`  Contract   : ${contractAddress}`);
  console.log(`  Tx hash    : ${txHash}`);
  console.log("=".repeat(60));

  // ── Save deployment record ──────────────────────────────────────────────────
  const deploymentsDir = path.join(__dirname, "..", "deployments");
  if (!fs.existsSync(deploymentsDir)) fs.mkdirSync(deploymentsDir, { recursive: true });

  const deploymentData = {
    network:         network.name,
    chainId:         network.config.chainId ?? null,
    contractAddress: contractAddress,
    deployerAddress: deployer.address,
    txHash:          txHash,
    deployedAt:      new Date().toISOString(),
  };

  const deployFile = path.join(deploymentsDir, `${network.name}.json`);
  fs.writeFileSync(deployFile, JSON.stringify(deploymentData, null, 2));
  console.log(`  Deployment info saved → ${deployFile}`);

  // ── Save flat ABI for Python backend ────────────────────────────────────────
  const artifact = await artifacts.readArtifact("GreenChainCarbonCredit");
  const abiDir   = path.join(__dirname, "..", "abi");
  if (!fs.existsSync(abiDir)) fs.mkdirSync(abiDir, { recursive: true });

  const abiFile = path.join(abiDir, "GreenChainCarbonCredit.json");
  fs.writeFileSync(abiFile, JSON.stringify(artifact.abi, null, 2));
  console.log(`  ABI saved              → ${abiFile}`);
  console.log("=".repeat(60));

  // ── Print env vars for .env ──────────────────────────────────────────────────
  console.log("\n  Add these to your backend .env file:");
  console.log(`  BLOCKCHAIN_MODE=web3`);
  console.log(`  WEB3_CONTRACT_ADDRESS=${contractAddress}`);
  console.log(`  WEB3_CHAIN_ID=${network.config.chainId ?? ""}`);
  console.log("=".repeat(60));
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });

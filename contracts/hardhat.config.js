require("@nomicfoundation/hardhat-toolbox");

// Load .env from project root (one level up) so the same .env
// file used by the Python backend also drives Hardhat.
const path = require("path");
require("dotenv").config({ path: path.resolve(__dirname, "../backend/.env") });

const RPC_URL     = process.env.WEB3_RPC_URL      || "";
const PRIVATE_KEY = process.env.WEB3_PRIVATE_KEY  || "";
const ETHERSCAN_KEY = process.env.ETHERSCAN_API_KEY || "";

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.28",
    settings: {
      optimizer:  { enabled: true, runs: 200 },
      evmVersion: "cancun",
    },
  },

  networks: {
    // Polygon Amoy testnet  (chainId 80002)
    amoy: {
      url: RPC_URL,
      accounts: PRIVATE_KEY ? [PRIVATE_KEY] : [],
      chainId: 80002,
      gasPrice: "auto",
    },
    // Ethereum Sepolia testnet (chainId 11155111)
    sepolia: {
      url: RPC_URL,
      accounts: PRIVATE_KEY ? [PRIVATE_KEY] : [],
      chainId: 11155111,
      gasPrice: "auto",
    },
    // Local Hardhat node (for development / integration tests)
    localhost: {
      url: "http://127.0.0.1:8545",
      chainId: 31337,
    },
  },

  etherscan: {
    apiKey: {
      polygonAmoy: ETHERSCAN_KEY,
      sepolia:     ETHERSCAN_KEY,
    },
  },

  paths: {
    sources:   "./contracts",
    tests:     "./test",
    cache:     "./cache",
    artifacts: "./artifacts",
  },
};

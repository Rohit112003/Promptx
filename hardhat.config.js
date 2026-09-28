require("@nomicfoundation/hardhat-ethers");
require("@nomicfoundation/hardhat-chai-matchers");
require("solidity-coverage");

/**
 * Hardhat config for the Tokenised Fund Servicing Platform.
 * The `localhost` network targets `npx hardhat node` (CHAIN_MODE=hardhat).
 */
module.exports = {
  solidity: {
    version: "0.8.24",
    settings: {
      optimizer: { enabled: true, runs: 200 },
      viaIR: true,
    },
  },
  paths: {
    sources: "./contracts",
    tests: "./test",
    artifacts: "./artifacts",
  },
  networks: {
    hardhat: {
      chainId: 31337,
    },
    localhost: {
      url: "http://127.0.0.1:8545",
      chainId: 31337,
    },
    docker: {
      url: "http://hardhat:8545",
      chainId: 31337,
    },
  },
};

// Export ABI + bytecode from the Hardhat build into the shared deployments artifact
// (deployments/local.json) that the Python backend reads. Address is filled in at deploy.
const fs = require("fs");
const path = require("path");

const artifactPath = path.join(
  __dirname, "..", "artifacts", "contracts",
  "TokenisedFundServicing.sol", "TokenisedFundServicing.json"
);
const art = JSON.parse(fs.readFileSync(artifactPath, "utf8"));

const out = {
  chainId: 31337,
  contractName: "TokenisedFundServicing",
  address: null,
  abi: art.abi,
  bytecode: art.bytecode,
  note: "ABI+bytecode exported from Hardhat; address is set on deploy (hardhat or inmemory).",
};

const dir = path.join(__dirname, "..", "deployments");
fs.mkdirSync(dir, { recursive: true });
fs.writeFileSync(path.join(dir, "local.json"), JSON.stringify(out, null, 2));
console.log("Wrote deployments/local.json (abi + bytecode)");

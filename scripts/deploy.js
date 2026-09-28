const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

/**
 * Deploy TokenisedFundServicing, assign roles to dev accounts, and write a shared
 * artifact (deployments/local.json) that the Python backend reads for address + ABI.
 */
async function main() {
  const ethers = hre.ethers;
  const signers = await ethers.getSigners();
  const [admin, transferAgent, custodian, auditor] = signers;

  const FUND_NAME = "Global Tech Fund";
  const INITIAL_UNIT_PRICE = 100n * 10n ** 8n; // 100.00000000 (PRICE_SCALE = 1e8)

  const Factory = await ethers.getContractFactory("TokenisedFundServicing");
  const fund = await Factory.deploy(FUND_NAME, INITIAL_UNIT_PRICE, admin.address);
  await fund.waitForDeployment();
  const address = await fund.getAddress();

  // Assign operational roles to distinct dev accounts.
  await (await fund.grantRole(await fund.TRANSFER_AGENT_ROLE(), transferAgent.address)).wait();
  await (await fund.grantRole(await fund.CUSTODIAN_ROLE(), custodian.address)).wait();
  await (await fund.grantRole(await fund.AUDITOR_ROLE(), auditor.address)).wait();
  // Admin also acts as transfer agent/custodian for single-signer demos.
  await (await fund.grantRole(await fund.TRANSFER_AGENT_ROLE(), admin.address)).wait();
  await (await fund.grantRole(await fund.CUSTODIAN_ROLE(), admin.address)).wait();

  const artifact = await hre.artifacts.readArtifact("TokenisedFundServicing");
  const out = {
    chainId: Number((await ethers.provider.getNetwork()).chainId),
    contractName: "TokenisedFundServicing",
    address,
    deployer: admin.address,
    roles: {
      admin: admin.address,
      transfer_agent: transferAgent.address,
      custodian: custodian.address,
      auditor: auditor.address,
    },
    abi: artifact.abi,
    bytecode: artifact.bytecode,
    deployedAt: new Date().toISOString(),
  };

  const dir = path.join(__dirname, "..", "deployments");
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "local.json"), JSON.stringify(out, null, 2));

  console.log("TokenisedFundServicing deployed to:", address);
  console.log("Artifact written to deployments/local.json");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

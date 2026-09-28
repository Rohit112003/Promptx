const { expect } = require("chai");
const { ethers } = require("hardhat");
const { loadFixture } = require("@nomicfoundation/hardhat-network-helpers");

const PRICE_SCALE = 10n ** 8n;
const INITIAL_PRICE = 100n * PRICE_SCALE;

// KYC enum: NONE=0, PENDING=1, APPROVED=2, REJECTED=3
// OrderType: SUBSCRIPTION=0, REDEMPTION=1 | OrderStatus: PENDING=0, SETTLED=1, CANCELLED=2
// CustodyActionType: LOCK=0, RELEASE=1, TRANSFER=2

describe("TokenisedFundServicing", function () {
  async function deployFixture() {
    const [admin, agent, custodian, auditor, alice, bob, mallory] =
      await ethers.getSigners();
    const Factory = await ethers.getContractFactory("TokenisedFundServicing");
    const fund = await Factory.deploy("Global Tech Fund", INITIAL_PRICE, admin.address);
    await fund.waitForDeployment();

    await fund.grantRole(await fund.TRANSFER_AGENT_ROLE(), agent.address);
    await fund.grantRole(await fund.CUSTODIAN_ROLE(), custodian.address);
    await fund.grantRole(await fund.AUDITOR_ROLE(), auditor.address);

    return { fund, admin, agent, custodian, auditor, alice, bob, mallory };
  }

  async function approvedInvestor(fund, agent, who, juris = "US") {
    await fund.connect(agent).registerInvestor(who.address, juris, ethers.ZeroHash);
    await fund.connect(agent).approveKyc(who.address);
  }

  describe("Roles", function () {
    it("assigns roles at deploy and via grant", async function () {
      const { fund, admin, agent, custodian, auditor } = await loadFixture(deployFixture);
      expect(await fund.hasRole(await fund.ADMIN_ROLE(), admin.address)).to.equal(true);
      expect(await fund.hasRole(await fund.TRANSFER_AGENT_ROLE(), agent.address)).to.equal(true);
      expect(await fund.hasRole(await fund.CUSTODIAN_ROLE(), custodian.address)).to.equal(true);
      expect(await fund.hasRole(await fund.AUDITOR_ROLE(), auditor.address)).to.equal(true);
    });

    it("blocks non-agents from KYC actions", async function () {
      const { fund, mallory, alice } = await loadFixture(deployFixture);
      await expect(
        fund.connect(mallory).registerInvestor(alice.address, "US", ethers.ZeroHash)
      ).to.be.revertedWithCustomError(fund, "AccessControlUnauthorizedAccount");
    });
  });

  describe("KYC lifecycle", function () {
    it("registers as PENDING then approves/rejects/revokes", async function () {
      const { fund, agent, alice } = await loadFixture(deployFixture);
      await fund.connect(agent).registerInvestor(alice.address, "US", ethers.ZeroHash);
      let inv = await fund.getInvestor(alice.address);
      expect(inv.exists).to.equal(true);
      expect(inv.kycStatus).to.equal(1); // PENDING

      await fund.connect(agent).approveKyc(alice.address);
      expect((await fund.getInvestor(alice.address)).kycStatus).to.equal(2); // APPROVED

      await fund.connect(agent).revokeKyc(alice.address);
      expect((await fund.getInvestor(alice.address)).kycStatus).to.equal(3); // REJECTED
    });

    it("reverts KYC on unregistered investor", async function () {
      const { fund, agent, alice } = await loadFixture(deployFixture);
      await expect(fund.connect(agent).approveKyc(alice.address))
        .to.be.revertedWithCustomError(fund, "NotRegistered");
    });
  });

  describe("Order lifecycle", function () {
    it("subscribes, settles, and mints units at NAV price", async function () {
      const { fund, agent, alice } = await loadFixture(deployFixture);
      await approvedInvestor(fund, agent, alice);

      await expect(fund.connect(alice).createSubscriptionOrder(10))
        .to.emit(fund, "OrderCreated");
      await expect(fund.connect(agent).settleOrder(1))
        .to.emit(fund, "OrderSettled")
        .and.to.emit(fund, "UnitsPurchased");

      expect(await fund.investorBalance(alice.address)).to.equal(10);
      expect(await fund.totalSupply()).to.equal(10);
      // NAV grew by 10 units * $100 = $1000 (whole base-currency units)
      expect(await fund.navTotal()).to.equal(1000n);
      expect(await fund.unitPrice()).to.equal(INITIAL_PRICE);
    });

    it("redeems and burns units", async function () {
      const { fund, agent, alice } = await loadFixture(deployFixture);
      await approvedInvestor(fund, agent, alice);
      await fund.connect(alice).createSubscriptionOrder(10);
      await fund.connect(agent).settleOrder(1);

      await fund.connect(alice).createRedemptionOrder(4);
      await fund.connect(agent).settleOrder(2);
      expect(await fund.investorBalance(alice.address)).to.equal(6);
      expect(await fund.totalSupply()).to.equal(6);
    });

    it("blocks redemption beyond free balance", async function () {
      const { fund, agent, alice } = await loadFixture(deployFixture);
      await approvedInvestor(fund, agent, alice);
      await expect(fund.connect(alice).createRedemptionOrder(1))
        .to.be.revertedWithCustomError(fund, "InsufficientUnlocked");
    });

    it("cancels a pending order", async function () {
      const { fund, agent, alice } = await loadFixture(deployFixture);
      await approvedInvestor(fund, agent, alice);
      await fund.connect(alice).createSubscriptionOrder(5);
      await expect(fund.connect(alice).cancelOrder(1)).to.emit(fund, "OrderCancelled");
      await expect(fund.connect(agent).settleOrder(1))
        .to.be.revertedWithCustomError(fund, "OrderNotPending");
    });

    it("prevents non-approved investors from subscribing", async function () {
      const { fund, agent, alice } = await loadFixture(deployFixture);
      await fund.connect(agent).registerInvestor(alice.address, "US", ethers.ZeroHash);
      await expect(fund.connect(alice).createSubscriptionOrder(5))
        .to.be.revertedWithCustomError(fund, "NotApproved");
    });
  });

  describe("NAV bounds", function () {
    it("allows first NAV set then bounds subsequent changes to 20%", async function () {
      const { fund, agent, alice } = await loadFixture(deployFixture);
      await approvedInvestor(fund, agent, alice);
      await fund.connect(alice).createSubscriptionOrder(100);
      await fund.connect(agent).settleOrder(1); // NAV = 10000 * scale

      const nav = await fund.navTotal();
      // +20% ok
      await expect(fund.connect(agent).updateNAV((nav * 12n) / 10n)).to.emit(fund, "NAVUpdated");
      const nav2 = await fund.navTotal();
      // +21% rejected
      await expect(fund.connect(agent).updateNAV((nav2 * 121n) / 100n))
        .to.be.revertedWithCustomError(fund, "NavChangeTooLarge");
    });

    it("rejects zero NAV and non-agent updates", async function () {
      const { fund, agent, mallory } = await loadFixture(deployFixture);
      await expect(fund.connect(agent).updateNAV(0))
        .to.be.revertedWithCustomError(fund, "InvalidAmount");
      await expect(fund.connect(mallory).updateNAV(100))
        .to.be.revertedWithCustomError(fund, "AccessControlUnauthorizedAccount");
    });
  });

  describe("Pause & freeze", function () {
    it("pauses subscriptions", async function () {
      const { fund, admin, agent, alice } = await loadFixture(deployFixture);
      await approvedInvestor(fund, agent, alice);
      await fund.connect(admin).pause();
      await expect(fund.connect(alice).createSubscriptionOrder(5))
        .to.be.revertedWithCustomError(fund, "EnforcedPause");
      await fund.connect(admin).unpause();
      await expect(fund.connect(alice).createSubscriptionOrder(5)).to.emit(fund, "OrderCreated");
    });

    it("freezes an investor", async function () {
      const { fund, agent, alice } = await loadFixture(deployFixture);
      await approvedInvestor(fund, agent, alice);
      await fund.connect(agent).setFrozen(alice.address, true);
      await expect(fund.connect(alice).createSubscriptionOrder(5))
        .to.be.revertedWithCustomError(fund, "IsFrozen");
    });
  });

  describe("Transfers", function () {
    it("transfers between approved investors and blocks unverified recipient", async function () {
      const { fund, agent, alice, bob } = await loadFixture(deployFixture);
      await approvedInvestor(fund, agent, alice);
      await fund.connect(alice).createSubscriptionOrder(10);
      await fund.connect(agent).settleOrder(1);

      await expect(fund.connect(alice).transferUnits(bob.address, 3))
        .to.be.revertedWithCustomError(fund, "NotRegistered");

      await approvedInvestor(fund, agent, bob);
      await expect(fund.connect(alice).transferUnits(bob.address, 3))
        .to.emit(fund, "UnitsTransferred");
      expect(await fund.investorBalance(bob.address)).to.equal(3);
      expect(await fund.investorBalance(alice.address)).to.equal(7);
    });
  });

  describe("Custody", function () {
    it("locks and releases units and records actions", async function () {
      const { fund, agent, custodian, alice } = await loadFixture(deployFixture);
      await approvedInvestor(fund, agent, alice);
      await fund.connect(alice).createSubscriptionOrder(10);
      await fund.connect(agent).settleOrder(1);

      await expect(
        fund.connect(custodian).recordCustodyAction(0, alice.address, 4, "ISIN:US123", "collateral")
      ).to.emit(fund, "CustodyActionRecorded");
      expect(await fund.lockedUnits(alice.address)).to.equal(4);

      // locked units cannot be redeemed
      await expect(fund.connect(alice).createRedemptionOrder(8))
        .to.be.revertedWithCustomError(fund, "InsufficientUnlocked");

      await fund.connect(custodian).recordCustodyAction(1, alice.address, 4, "ISIN:US123", "release");
      expect(await fund.lockedUnits(alice.address)).to.equal(0);
    });

    it("blocks non-custodians", async function () {
      const { fund, mallory, alice } = await loadFixture(deployFixture);
      await expect(
        fund.connect(mallory).recordCustodyAction(0, alice.address, 1, "x", "y")
      ).to.be.revertedWithCustomError(fund, "AccessControlUnauthorizedAccount");
    });
  });

  describe("Pagination", function () {
    it("returns bounded transaction pages", async function () {
      const { fund, agent, alice } = await loadFixture(deployFixture);
      await approvedInvestor(fund, agent, alice);
      for (let i = 0; i < 3; i++) {
        await fund.connect(alice).createSubscriptionOrder(1);
        await fund.connect(agent).settleOrder(i + 1);
      }
      expect(await fund.transactionCount(alice.address)).to.equal(3);
      const page = await fund.getTransactions(alice.address, 1, 10);
      expect(page.length).to.equal(2);
    });
  });
});

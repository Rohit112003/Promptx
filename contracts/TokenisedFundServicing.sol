// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title Tokenised Fund Servicing Platform
/// @notice On-chain fund servicing: role-gated KYC, NAV-priced subscription/redemption
///         orders, transfer restrictions, and a custody action log. The chain is the
///         source of truth; no PII is stored on chain (only address, KYC status, hashes).
/// @dev OpenZeppelin v5. Prices are fixed-point with `PRICE_SCALE` decimals of precision.
contract TokenisedFundServicing is AccessControl, Pausable, ReentrancyGuard {
    // ============ ROLES ============
    /// @notice Full administrative control (role management, pause).
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    /// @notice Transfer agency: KYC decisions, NAV updates, order settlement, freezes.
    bytes32 public constant TRANSFER_AGENT_ROLE = keccak256("TRANSFER_AGENT_ROLE");
    /// @notice Custody operations: LOCK / RELEASE / TRANSFER custody actions.
    bytes32 public constant CUSTODIAN_ROLE = keccak256("CUSTODIAN_ROLE");
    /// @notice Read-only auditor (no on-chain mutating power; used off-chain for RBAC).
    bytes32 public constant AUDITOR_ROLE = keccak256("AUDITOR_ROLE");

    // ============ CONSTANTS ============
    /// @notice Fixed-point scale for unit price (1 unit price == PRICE_SCALE).
    uint256 public constant PRICE_SCALE = 1e8;
    /// @notice Maximum allowed NAV change per update, in basis points (2000 = 20%).
    uint256 public constant MAX_NAV_CHANGE_BPS = 2000;
    uint256 private constant BPS_DENOMINATOR = 10000;

    // ============ ENUMS ============
    enum KycStatus {
        NONE,
        PENDING,
        APPROVED,
        REJECTED
    }
    enum OrderType {
        SUBSCRIPTION,
        REDEMPTION
    }
    enum OrderStatus {
        PENDING,
        SETTLED,
        CANCELLED
    }
    enum CustodyActionType {
        LOCK,
        RELEASE,
        TRANSFER
    }

    // ============ STRUCTS ============
    struct Investor {
        KycStatus kycStatus;
        bool frozen;
        bool exists;
        string jurisdiction; // e.g. "US", "UK" — jurisdiction is not PII
        bytes32 kycHash; // hash of off-chain KYC dossier
    }

    struct Order {
        uint256 id;
        address investor;
        OrderType orderType;
        OrderStatus status;
        uint256 units;
        uint256 createdAt;
        uint256 settledAt;
        uint256 settledUnitPrice; // unit price applied at settlement (PRICE_SCALE)
    }

    struct CustodyRecord {
        uint256 id;
        address custodian;
        CustodyActionType actionType;
        address investor;
        uint256 units;
        string assetRef;
        string reason;
        uint256 timestamp;
    }

    struct Transaction {
        string transactionType; // "SUBSCRIBE" | "REDEEM" | "TRANSFER_IN" | "TRANSFER_OUT"
        uint256 units;
        uint256 unitPrice; // PRICE_SCALE
        uint256 timestamp;
    }

    // ============ STATE ============
    string public fundName;
    uint256 public navTotal; // total net asset value in whole base-currency units (USD)
    uint256 public totalSupply; // total units in issue
    uint256 public initialUnitPrice; // price used when totalSupply == 0 (PRICE_SCALE-scaled)

    mapping(address => uint256) public investorBalance;
    mapping(address => uint256) public lockedUnits; // units under custody lock
    mapping(address => Investor) private _investors;
    mapping(address => Transaction[]) private _transactions;

    mapping(uint256 => Order) private _orders;
    uint256 public nextOrderId = 1;

    mapping(uint256 => CustodyRecord) private _custodyRecords;
    uint256 public nextCustodyId = 1;

    // ============ EVENTS ============
    event InvestorRegistered(address indexed investor, string jurisdiction, bytes32 kycHash);
    event KycStatusChanged(address indexed investor, KycStatus status, address indexed agent);
    event InvestorFrozen(address indexed investor, bool frozen, address indexed agent);
    event NAVUpdated(uint256 newNAV, uint256 unitPrice, uint256 timestamp);
    event OrderCreated(
        uint256 indexed orderId, address indexed investor, OrderType orderType, uint256 units
    );
    event OrderSettled(
        uint256 indexed orderId,
        address indexed investor,
        OrderType orderType,
        uint256 units,
        uint256 unitPrice
    );
    event OrderCancelled(uint256 indexed orderId, address indexed by);
    event UnitsTransferred(address indexed from, address indexed to, uint256 units);
    event CustodyActionRecorded(
        uint256 indexed actionId,
        address indexed custodian,
        CustodyActionType actionType,
        address indexed investor,
        uint256 units,
        string assetRef,
        string reason
    );
    // Legacy-compatible events (mapped from the order flow) for existing consumers.
    event UnitsPurchased(address indexed investor, uint256 amount, uint256 timestamp);
    event UnitsRedeemed(address indexed investor, uint256 amount, uint256 timestamp);

    // ============ CUSTOM ERRORS ============
    error NotRegistered(address investor);
    error NotApproved(address investor);
    error IsFrozen(address investor);
    error InvalidAmount();
    error InsufficientBalance(uint256 available, uint256 requested);
    error InsufficientUnlocked(uint256 available, uint256 requested);
    error NavChangeTooLarge(uint256 currentNav, uint256 proposedNav);
    error OrderNotFound(uint256 orderId);
    error OrderNotPending(uint256 orderId);
    error NotOrderOwner();
    error ZeroAddress();

    // ============ CONSTRUCTOR ============
    /// @param _fundName Human-readable fund name.
    /// @param _initialUnitPrice Starting unit price (PRICE_SCALE-scaled) used when supply is 0.
    /// @param admin Address granted ADMIN_ROLE and DEFAULT_ADMIN_ROLE.
    constructor(string memory _fundName, uint256 _initialUnitPrice, address admin) {
        if (admin == address(0)) revert ZeroAddress();
        if (_initialUnitPrice == 0) revert InvalidAmount();
        fundName = _fundName;
        initialUnitPrice = _initialUnitPrice;

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ADMIN_ROLE, admin);
        _setRoleAdmin(TRANSFER_AGENT_ROLE, ADMIN_ROLE);
        _setRoleAdmin(CUSTODIAN_ROLE, ADMIN_ROLE);
        _setRoleAdmin(AUDITOR_ROLE, ADMIN_ROLE);
    }

    // ============ MODIFIERS ============
    modifier onlyApproved(address account) {
        Investor storage inv = _investors[account];
        if (!inv.exists) revert NotRegistered(account);
        if (inv.kycStatus != KycStatus.APPROVED) revert NotApproved(account);
        if (inv.frozen) revert IsFrozen(account);
        _;
    }

    // ============ INVESTOR REGISTRATION & KYC (TRANSFER_AGENT) ============

    /// @notice Register an investor with jurisdiction + KYC dossier hash (status PENDING).
    /// @dev Only address, jurisdiction, status and a hash are stored — no PII.
    function registerInvestor(address investor, string calldata jurisdiction, bytes32 kycHash)
        external
        onlyRole(TRANSFER_AGENT_ROLE)
    {
        if (investor == address(0)) revert ZeroAddress();
        Investor storage inv = _investors[investor];
        inv.exists = true;
        inv.jurisdiction = jurisdiction;
        inv.kycHash = kycHash;
        if (inv.kycStatus == KycStatus.NONE) {
            inv.kycStatus = KycStatus.PENDING;
        }
        emit InvestorRegistered(investor, jurisdiction, kycHash);
        emit KycStatusChanged(investor, inv.kycStatus, msg.sender);
    }

    /// @notice Approve an investor's KYC.
    function approveKyc(address investor) external onlyRole(TRANSFER_AGENT_ROLE) {
        _setKyc(investor, KycStatus.APPROVED);
    }

    /// @notice Reject an investor's KYC.
    function rejectKyc(address investor) external onlyRole(TRANSFER_AGENT_ROLE) {
        _setKyc(investor, KycStatus.REJECTED);
    }

    /// @notice Revoke a previously approved KYC (sets status back to REJECTED).
    function revokeKyc(address investor) external onlyRole(TRANSFER_AGENT_ROLE) {
        _setKyc(investor, KycStatus.REJECTED);
    }

    function _setKyc(address investor, KycStatus status) private {
        Investor storage inv = _investors[investor];
        if (!inv.exists) revert NotRegistered(investor);
        inv.kycStatus = status;
        emit KycStatusChanged(investor, status, msg.sender);
    }

    /// @notice Freeze / unfreeze a single investor (blocks orders & transfers).
    function setFrozen(address investor, bool frozen)
        external
        onlyRole(TRANSFER_AGENT_ROLE)
    {
        Investor storage inv = _investors[investor];
        if (!inv.exists) revert NotRegistered(investor);
        inv.frozen = frozen;
        emit InvestorFrozen(investor, frozen, msg.sender);
    }

    // ============ NAV / PRICING (TRANSFER_AGENT) ============

    /// @notice Current unit price (PRICE_SCALE-scaled). Derived from NAV / supply.
    function unitPrice() public view returns (uint256) {
        if (totalSupply == 0) return initialUnitPrice;
        return (navTotal * PRICE_SCALE) / totalSupply;
    }

    /// @notice Update total NAV (whole base-currency units). Bounded to +/- MAX_NAV_CHANGE_BPS.
    /// @dev The first NAV set (from 0) is unbounded; subsequent updates are bounded.
    function updateNAV(uint256 _newNAV) external onlyRole(TRANSFER_AGENT_ROLE) {
        if (_newNAV == 0) revert InvalidAmount();
        if (navTotal != 0) {
            uint256 maxDelta = (navTotal * MAX_NAV_CHANGE_BPS) / BPS_DENOMINATOR;
            uint256 delta = _newNAV > navTotal ? _newNAV - navTotal : navTotal - _newNAV;
            if (delta > maxDelta) revert NavChangeTooLarge(navTotal, _newNAV);
        }
        navTotal = _newNAV;
        emit NAVUpdated(_newNAV, unitPrice(), block.timestamp);
    }

    // ============ ORDERS (SUBSCRIBE / REDEEM) ============

    /// @notice Create a subscription (buy) order at current NAV. Settled by a transfer agent.
    function createSubscriptionOrder(uint256 units)
        external
        whenNotPaused
        onlyApproved(msg.sender)
        returns (uint256 orderId)
    {
        if (units == 0) revert InvalidAmount();
        orderId = _createOrder(msg.sender, OrderType.SUBSCRIPTION, units);
    }

    /// @notice Create a redemption (sell) order. Requires sufficient unlocked balance.
    function createRedemptionOrder(uint256 units)
        external
        whenNotPaused
        onlyApproved(msg.sender)
        returns (uint256 orderId)
    {
        if (units == 0) revert InvalidAmount();
        uint256 free = investorBalance[msg.sender] - lockedUnits[msg.sender];
        if (free < units) revert InsufficientUnlocked(free, units);
        orderId = _createOrder(msg.sender, OrderType.REDEMPTION, units);
    }

    function _createOrder(address investor, OrderType orderType, uint256 units)
        private
        returns (uint256 orderId)
    {
        orderId = nextOrderId++;
        _orders[orderId] = Order({
            id: orderId,
            investor: investor,
            orderType: orderType,
            status: OrderStatus.PENDING,
            units: units,
            createdAt: block.timestamp,
            settledAt: 0,
            settledUnitPrice: 0
        });
        emit OrderCreated(orderId, investor, orderType, units);
    }

    /// @notice Settle a pending order at the current unit price (transfer agent only).
    function settleOrder(uint256 orderId)
        external
        whenNotPaused
        nonReentrant
        onlyRole(TRANSFER_AGENT_ROLE)
    {
        Order storage order = _orders[orderId];
        if (order.id == 0) revert OrderNotFound(orderId);
        if (order.status != OrderStatus.PENDING) revert OrderNotPending(orderId);

        Investor storage inv = _investors[order.investor];
        if (inv.kycStatus != KycStatus.APPROVED) revert NotApproved(order.investor);
        if (inv.frozen) revert IsFrozen(order.investor);

        uint256 price = unitPrice();
        uint256 cashValue = (order.units * price) / PRICE_SCALE;

        if (order.orderType == OrderType.SUBSCRIPTION) {
            investorBalance[order.investor] += order.units;
            totalSupply += order.units;
            navTotal += cashValue;
            _pushTx(order.investor, "SUBSCRIBE", order.units, price);
            emit UnitsPurchased(order.investor, order.units, block.timestamp);
        } else {
            uint256 free = investorBalance[order.investor] - lockedUnits[order.investor];
            if (free < order.units) revert InsufficientUnlocked(free, order.units);
            investorBalance[order.investor] -= order.units;
            totalSupply -= order.units;
            navTotal = navTotal > cashValue ? navTotal - cashValue : 0;
            _pushTx(order.investor, "REDEEM", order.units, price);
            emit UnitsRedeemed(order.investor, order.units, block.timestamp);
        }

        order.status = OrderStatus.SETTLED;
        order.settledAt = block.timestamp;
        order.settledUnitPrice = price;
        emit OrderSettled(orderId, order.investor, order.orderType, order.units, price);
    }

    /// @notice Cancel a pending order (order owner or a transfer agent).
    function cancelOrder(uint256 orderId) external {
        Order storage order = _orders[orderId];
        if (order.id == 0) revert OrderNotFound(orderId);
        if (order.status != OrderStatus.PENDING) revert OrderNotPending(orderId);
        if (msg.sender != order.investor && !hasRole(TRANSFER_AGENT_ROLE, msg.sender)) {
            revert NotOrderOwner();
        }
        order.status = OrderStatus.CANCELLED;
        emit OrderCancelled(orderId, msg.sender);
    }

    // ============ TRANSFERS (COMPLIANCE-GATED) ============

    /// @notice Transfer units to another approved investor (both sides compliance-checked).
    function transferUnits(address to, uint256 units)
        external
        whenNotPaused
        nonReentrant
        onlyApproved(msg.sender)
        onlyApproved(to)
        returns (bool)
    {
        if (units == 0) revert InvalidAmount();
        uint256 free = investorBalance[msg.sender] - lockedUnits[msg.sender];
        if (free < units) revert InsufficientUnlocked(free, units);

        investorBalance[msg.sender] -= units;
        investorBalance[to] += units;

        uint256 price = unitPrice();
        _pushTx(msg.sender, "TRANSFER_OUT", units, price);
        _pushTx(to, "TRANSFER_IN", units, price);
        emit UnitsTransferred(msg.sender, to, units);
        return true;
    }

    // ============ CUSTODY (CUSTODIAN) ============

    /// @notice Record a custody action. LOCK/RELEASE adjust an investor's locked units.
    function recordCustodyAction(
        CustodyActionType actionType,
        address investor,
        uint256 units,
        string calldata assetRef,
        string calldata reason
    ) external onlyRole(CUSTODIAN_ROLE) returns (uint256 actionId) {
        if (investor == address(0)) revert ZeroAddress();

        if (actionType == CustodyActionType.LOCK) {
            uint256 free = investorBalance[investor] - lockedUnits[investor];
            if (free < units) revert InsufficientUnlocked(free, units);
            lockedUnits[investor] += units;
        } else if (actionType == CustodyActionType.RELEASE) {
            if (lockedUnits[investor] < units) {
                revert InsufficientBalance(lockedUnits[investor], units);
            }
            lockedUnits[investor] -= units;
        }

        actionId = nextCustodyId++;
        _custodyRecords[actionId] = CustodyRecord({
            id: actionId,
            custodian: msg.sender,
            actionType: actionType,
            investor: investor,
            units: units,
            assetRef: assetRef,
            reason: reason,
            timestamp: block.timestamp
        });
        emit CustodyActionRecorded(
            actionId, msg.sender, actionType, investor, units, assetRef, reason
        );
    }

    // ============ PAUSE (ADMIN) ============

    function pause() external onlyRole(ADMIN_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(ADMIN_ROLE) {
        _unpause();
    }

    // ============ VIEWS (paginated — no unbounded returns) ============

    function getInvestor(address investor)
        external
        view
        returns (
            bool exists,
            KycStatus kycStatus,
            bool frozen,
            string memory jurisdiction,
            bytes32 kycHash,
            uint256 balance,
            uint256 locked
        )
    {
        Investor storage inv = _investors[investor];
        return (
            inv.exists,
            inv.kycStatus,
            inv.frozen,
            inv.jurisdiction,
            inv.kycHash,
            investorBalance[investor],
            lockedUnits[investor]
        );
    }

    /// @notice Portfolio value (PRICE_SCALE-scaled) = balance * unitPrice.
    function portfolioValue(address investor) external view returns (uint256) {
        return (investorBalance[investor] * unitPrice()) / PRICE_SCALE;
    }

    function getOrder(uint256 orderId) external view returns (Order memory) {
        Order storage o = _orders[orderId];
        if (o.id == 0) revert OrderNotFound(orderId);
        return o;
    }

    function getCustodyRecord(uint256 actionId) external view returns (CustodyRecord memory) {
        return _custodyRecords[actionId];
    }

    function transactionCount(address investor) external view returns (uint256) {
        return _transactions[investor].length;
    }

    /// @notice Paginated transaction history (bounded by `limit`).
    function getTransactions(address investor, uint256 offset, uint256 limit)
        external
        view
        returns (Transaction[] memory page)
    {
        Transaction[] storage all = _transactions[investor];
        uint256 len = all.length;
        if (offset >= len) return new Transaction[](0);
        uint256 end = offset + limit;
        if (end > len) end = len;
        page = new Transaction[](end - offset);
        for (uint256 i = offset; i < end; i++) {
            page[i - offset] = all[i];
        }
    }

    /// @notice Fund summary snapshot.
    function getFundStatus()
        external
        view
        returns (
            string memory name,
            uint256 nav,
            uint256 totalUnits,
            uint256 price,
            uint256 totalValue
        )
    {
        return (fundName, navTotal, totalSupply, unitPrice(), navTotal);
    }

    function _pushTx(address investor, string memory kind, uint256 units, uint256 price)
        private
    {
        _transactions[investor].push(
            Transaction({
                transactionType: kind,
                units: units,
                unitPrice: price,
                timestamp: block.timestamp
            })
        );
    }
}

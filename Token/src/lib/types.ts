export type Role = 'admin' | 'agent' | 'custodian' | 'auditor' | 'investor1' | 'investor2' | 'investor3' | 'investor4' | 'investor5';
export type OrderStatus = 'PENDING' | 'SETTLED' | 'CANCELLED';
export type Investor = { address: string; name: string; email: string; kyc: 'APPROVED' | 'PENDING' | 'REJECTED' | 'REVOKED'; frozen: boolean; units: number; joined: string };
export type Order = { id: string; investor: string; type: 'SUBSCRIBE' | 'REDEEM'; units: number; amount: number; status: OrderStatus; date: string; txHash?: string | undefined; blockNumber?: number | undefined };
export type NavPoint = { date: string; nav: number; unitPrice: number };
export type AuditEvent = { id: string; action: string; actor: string; date: string; txHash: string; blockNumber: number; status: string };
/** Custody is recorded on chain against an investor in UNITS; `amount` is the USD value (x1e8) for display. */
export type CustodyAction = { id: string; type: 'LOCK' | 'RELEASE' | 'TRANSFER'; asset: string; investor: string; units: number; amount: number; reason: string; date: string; txHash: string; blockNumber?: number | undefined };
/** Per-investor custody position, straight from the contract. */
export type CustodyPosition = { investor: string; name: string; balance: number; locked: number; free: number };
export type FundStatus = { name: string; ticker: string; paused: boolean; nav: number; unitPrice: number; totalUnits: number; investors: number; asOf: string };
export type FundSummary = { subscriptions: number; redemptions: number; aumChange: number; pendingOrders: number; settledOrders: number };
export type DemoUser = { username: Role; name: string; address: string };
export type Session = { access_token: string; user: DemoUser };
export type TxResult = { txHash: string; blockNumber?: number | undefined; message: string };
export type ApiError = { error: { code: string; message: string; detail?: string; request_id?: string } };

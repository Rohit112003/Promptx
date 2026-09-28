import type { AuditEvent, CustodyAction, CustodyPosition, DemoUser, FundStatus, FundSummary, Investor, NavPoint, Order, Role, Session, TxResult } from './types';

export const PRICE_SCALE = 1e8;
export const formatPrice = (value: number) => new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value / PRICE_SCALE);
export const formatMoney = (value: number) => '$' + formatPrice(value);
export const shortAddress = (value: string) => value.length > 18 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value;

const BASE = import.meta.env['VITE_API_BASE_URL'] || 'http://localhost:8000/api/v1';
export const WS_URL = import.meta.env['VITE_WS_URL'] || 'ws://localhost:8000/ws/events';

/* ------------------------------------------------------------------ *
 * Session storage
 *
 * Versioned keys: anything stored by an older build (including the old
 * offline demo data) is ignored and purged, so a stale fake session can
 * never lock you out of the login screen.
 * ------------------------------------------------------------------ */
export const TOKEN_KEY = 'fund_token_v2';
export const USER_KEY = 'fund_user_v2';
const LEGACY_KEYS = ['fund_token', 'fund_user'];

export function clearSession(): void {
  if (typeof window === 'undefined') return;
  for (const key of [TOKEN_KEY, USER_KEY, ...LEGACY_KEYS]) window.localStorage.removeItem(key);
}
/** Drop sessions written by older builds. Called once on boot. */
export function purgeLegacySession(): void {
  if (typeof window === 'undefined') return;
  for (const key of LEGACY_KEYS) window.localStorage.removeItem(key);
}
function storedUser(): DemoUser | null {
  if (typeof window === 'undefined') return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw) as DemoUser; } catch { return null; }
}

/* ------------------------------------------------------------------ *
 * Account labels (derived from the backend's roles — no invented people)
 * ------------------------------------------------------------------ */
const ROLE_LABELS: Record<string, string> = {
  admin: 'Fund Administrator', agent: 'Transfer Agent', custodian: 'Custodian', auditor: 'Auditor',
};
const ROLE_TO_USERNAME: Record<string, string> = {
  ADMIN: 'admin', TRANSFER_AGENT: 'agent', CUSTODIAN: 'custodian', AUDITOR: 'auditor',
};
const accountLabel = (username: string) =>
  ROLE_LABELS[username] ?? (username.startsWith('investor') ? `Investor ${username.slice('investor'.length)}` : username);

/* ------------------------------------------------------------------ *
 * Transport
 * ------------------------------------------------------------------ */
export function errorMessage(error: unknown) { if (error && typeof error === 'object' && 'error' in error) { const e = (error as { error?: { message?: string } }).error; if (e?.message) return e.message; } return error instanceof Error ? error.message : 'Something went wrong'; }

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = typeof window !== 'undefined' ? window.localStorage.getItem(TOKEN_KEY) : null;
  const response = await fetch(`${BASE}${path}`, { ...init, headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers } });
  if (response.status === 401 && typeof window !== 'undefined') { clearSession(); window.dispatchEvent(new Event('fund:unauthorized')); }
  if (!response.ok) { const data = await response.json().catch(() => null); throw data?.error ? data : { error: { message: `Request failed (${response.status})` } }; }
  const contentType = response.headers.get('content-type') || '';
  return (contentType.includes('application/json') ? await response.json() : await response.text()) as T;
}
/** Download a binary/text export (CSV, PDF) straight from the API with auth. */
async function download(path: string, filename: string): Promise<void> {
  const token = typeof window !== 'undefined' ? window.localStorage.getItem(TOKEN_KEY) : null;
  const response = await fetch(`${BASE}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!response.ok) { const data = await response.json().catch(() => null); throw data?.error ? data : { error: { message: `Export failed (${response.status})` } }; }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}
const json = (body: unknown): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
const postEmpty = (): RequestInit => ({ method: 'POST' });

/* ------------------------------------------------------------------ *
 * Backend payload shapes (snake_case, as returned by FastAPI)
 * ------------------------------------------------------------------ */
type Paged<T> = { items: T[]; total: number; limit: number; offset: number };
type BReceipt = { tx_hash: string; block_number: number; status: string; gas_used: number };
type BInvestor = { address: string; name: string | null; email: string | null; jurisdiction: string; kyc_status: string; frozen: boolean; exists_on_chain: boolean; kyc_hash: string | null; balance: number; locked: number; portfolio_value: number; created_at: string | null };
type BOrder = { id: number; investor: string; order_type: string; status: string; units: number; created_at: number; settled_at: number; settled_unit_price: number; note: string | null; tx_hash: string | null; block_number: number | null };
type BFundStatus = { fund_name: string; nav_total: number; total_supply: number; unit_price: number; total_value: number; paused: boolean; contract_address: string };
type BSummary = { fund_name: string; nav_total: number; total_supply: number; unit_price: number; total_value: number; investor_count: number; approved_investors: number; pending_orders: number; settled_orders: number; generated_at: string };
type BNavPoint = { nav_total: number; unit_price: number; timestamp: number; block_number: number; tx_hash: string };
type BPerfPoint = { timestamp: number; unit_price: number; nav_total: number; return_pct: number };
type BCustody = { id: number; custodian: string; action_type: string; investor: string; units: number; asset_ref: string; reason: string; timestamp: number; tx_hash: string | null; block_number: number | null };
type BPosition = { investor: string; balance: number; locked: number; free: number };
type BAuditEvent = { event: string; tx_hash: string; block_number: number; log_index: number; timestamp: number | null; args: Record<string, unknown> };
type BRole = { role: string; address: string; label: string };
type BDemoUsers = Record<string, { role: string; address: string; password: string }>;

/* ------------------------------------------------------------------ *
 * Mappers: backend -> UI types
 *
 * SCALING RULES (important):
 *  - backend `nav_total` / `portfolio_value` are WHOLE dollars  -> x PRICE_SCALE for the UI
 *  - backend `unit_price` is already scaled by 1e8              -> pass through unchanged
 *  - UI `amount` = units x unitPrice  (dollars x 1e8)
 * ------------------------------------------------------------------ */
const now = () => new Date().toISOString();
const isoFrom = (unixSeconds: number | null | undefined): string =>
  unixSeconds && unixSeconds > 0 ? new Date(unixSeconds * 1000).toISOString() : now();

const KYC_MAP: Record<string, Investor['kyc']> = { NONE: 'PENDING', PENDING: 'PENDING', APPROVED: 'APPROVED', REJECTED: 'REJECTED' };

function toInvestor(b: BInvestor): Investor {
  return {
    address: b.address,
    name: b.name ?? shortAddress(b.address),
    email: b.email ?? '',
    kyc: KYC_MAP[b.kyc_status] ?? 'PENDING',
    frozen: b.frozen,
    units: b.balance,
    joined: b.created_at ?? now(),
  };
}

function toOrder(b: BOrder, currentUnitPrice: number): Order {
  const price = b.settled_unit_price > 0 ? b.settled_unit_price : currentUnitPrice;
  return {
    id: String(b.id),
    investor: b.investor,
    type: b.order_type === 'REDEMPTION' ? 'REDEEM' : 'SUBSCRIBE',
    units: b.units,
    amount: b.units * price,
    status: b.status === 'SETTLED' ? 'SETTLED' : b.status === 'CANCELLED' ? 'CANCELLED' : 'PENDING',
    date: isoFrom(b.created_at),
    txHash: b.tx_hash ?? undefined,
    blockNumber: b.block_number ?? undefined,
  };
}

function toCustodyAction(b: BCustody, unitPrice: number): CustodyAction {
  const type: CustodyAction['type'] = b.action_type === 'RELEASE' ? 'RELEASE' : b.action_type === 'TRANSFER' ? 'TRANSFER' : 'LOCK';
  return {
    id: String(b.id), type, asset: b.asset_ref || '—', investor: b.investor, units: b.units,
    amount: b.units * unitPrice, reason: b.reason, date: isoFrom(b.timestamp),
    txHash: b.tx_hash ?? '', blockNumber: b.block_number ?? undefined,
  };
}

/** Readable labels for the contract's events (falls back to a generic de-camel-case). */
const EVENT_LABELS: Record<string, string> = {
  InvestorRegistered: 'Investor registered', KycStatusChanged: 'KYC status changed',
  InvestorFrozen: 'Investor freeze changed', NAVUpdated: 'NAV published',
  OrderCreated: 'Order created', OrderSettled: 'Order settled', OrderCancelled: 'Order cancelled',
  UnitsTransferred: 'Units transferred', CustodyActionRecorded: 'Custody action recorded',
  UnitsPurchased: 'Units issued', UnitsRedeemed: 'Units redeemed',
  Paused: 'Fund paused', Unpaused: 'Fund resumed',
  RoleGranted: 'Role granted', RoleRevoked: 'Role revoked',
};
const humanise = (event: string) => {
  const label = EVENT_LABELS[event];
  if (label) return label;
  const spaced = event.replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2').replace(/([a-z0-9])([A-Z])/g, '$1 $2').replace(/_/g, ' ');
  return spaced.charAt(0).toUpperCase() + spaced.slice(1).toLowerCase();
};
/** Pick the most meaningful address from an event's arguments to show as the actor. */
function actorOf(args: Record<string, unknown>): string {
  for (const key of ['investor', 'agent', 'custodian', 'from', 'account', 'by']) {
    const value = args[key];
    if (typeof value === 'string' && value.startsWith('0x')) return shortAddress(value);
  }
  for (const value of Object.values(args)) {
    if (typeof value === 'string' && value.startsWith('0x') && value.length === 42) return shortAddress(value);
  }
  return 'Fund contract';
}

function toAuditEvent(b: BAuditEvent): AuditEvent {
  return {
    id: `${b.tx_hash.slice(0, 10)}-${b.log_index}`,
    action: humanise(b.event),
    actor: actorOf(b.args ?? {}),
    date: isoFrom(b.timestamp),
    txHash: b.tx_hash,
    blockNumber: b.block_number,
    status: 'MATCH',
  };
}

/** Map a payload pushed over the WebSocket into an AuditEvent (null if not an event). */
export function mapWsEvent(payload: unknown): AuditEvent | null {
  if (!payload || typeof payload !== 'object') return null;
  const message = payload as { type?: string; data?: BAuditEvent };
  if (message.type !== 'event' || !message.data) return null;
  try { return toAuditEvent(message.data); } catch { return null; }
}

const receiptToTx = (r: BReceipt, message: string): TxResult => ({ txHash: r.tx_hash, blockNumber: r.block_number, message });

/** Current unit price, used to value units consistently across the console. */
async function unitPriceNow(): Promise<number> {
  try { return (await request<BFundStatus>('/fund/status')).unit_price; } catch { return 100 * PRICE_SCALE; }
}

/* ------------------------------------------------------------------ *
 * Public API — every call goes to the live backend
 * ------------------------------------------------------------------ */
export const api = {
  getDemoUsers: async (): Promise<DemoUser[]> => {
    const map = await request<BDemoUsers>('/auth/demo-users');
    return Object.entries(map).map(([username, info]) => ({ username: username as Role, name: accountLabel(username), address: info.address }));
  },

  login: async (username: string, password: string): Promise<Session> => {
    const body = new URLSearchParams({ username, password });
    const result = await request<{ access_token: string; role: string; address: string }>('/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body });
    return { access_token: result.access_token, user: { username: username as Role, name: accountLabel(username), address: result.address } };
  },

  getFundStatus: async (): Promise<FundStatus> => {
    const status = await request<BFundStatus>('/fund/status');
    let investorCount = 0;
    try { investorCount = (await request<BSummary>('/reports/fund/summary')).investor_count; } catch { investorCount = 0; }
    return {
      name: status.fund_name,
      ticker: 'ADCF',
      paused: status.paused,
      nav: status.nav_total * PRICE_SCALE,   // backend NAV is whole dollars
      unitPrice: status.unit_price,          // already 1e8-scaled
      totalUnits: status.total_supply,
      investors: investorCount,
      asOf: now(),
    };
  },

  getFundSummary: async (): Promise<FundSummary> => {
    const summary = await request<BSummary>('/reports/fund/summary');
    // Subscriptions / redemptions are derived from settled orders.
    let subscriptions = 0, redemptions = 0;
    try {
      const page = await request<Paged<BOrder>>('/orders?limit=500');
      for (const o of page.items) {
        if (o.status !== 'SETTLED') continue;
        const value = o.units * (o.settled_unit_price > 0 ? o.settled_unit_price : summary.unit_price);
        if (o.order_type === 'REDEMPTION') redemptions += value; else subscriptions += value;
      }
    } catch { /* orders unavailable for this role — leave totals at zero */ }
    let aumChange = 0;
    try { const perf = await request<BPerfPoint[]>('/reports/nav-performance'); aumChange = perf.at(-1)?.return_pct ?? 0; } catch { aumChange = 0; }
    return { subscriptions, redemptions, aumChange: Number(aumChange.toFixed(2)), pendingOrders: summary.pending_orders, settledOrders: summary.settled_orders };
  },

  getNavPerformance: async (): Promise<NavPoint[]> => {
    const perf = await request<BPerfPoint[]>('/reports/nav-performance');
    const points = perf
      .map(p => ({ date: isoFrom(p.timestamp), nav: p.nav_total * PRICE_SCALE, unitPrice: p.unit_price }))
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
    if (points.length) return points;
    // The event indexer may not have caught up yet — show the current valuation.
    const status = await request<BFundStatus>('/fund/status');
    return [{ date: now(), nav: status.nav_total * PRICE_SCALE, unitPrice: status.unit_price }];
  },

  getInvestors: async (): Promise<Investor[]> => {
    try {
      const page = await request<Paged<BInvestor>>('/investors?limit=200');
      return page.items.map(toInvestor);
    } catch {
      // Investor logins may not list the whole registry — fall back to their own record.
      const me = storedUser();
      if (!me?.address) return [];
      try { return [toInvestor(await request<BInvestor>(`/investors/${me.address}`))]; } catch { return []; }
    }
  },

  registerInvestor: async (input: { name: string; email: string; address: string }): Promise<Investor> => {
    const result = await request<{ investor: BInvestor; receipt: BReceipt }>('/investors', json({ ...input, jurisdiction: 'US' }));
    return toInvestor(result.investor);
  },

  getInvestor: async (address: string): Promise<Investor> =>
    toInvestor(await request<BInvestor>(`/investors/${address}`)),

  updateKyc: async (address: string, action: 'approve' | 'reject' | 'revoke'): Promise<TxResult> => {
    const result = await request<{ kyc_status: string; receipt: BReceipt }>(`/kyc/${address}/${action}`, postEmpty());
    return receiptToTx(result.receipt, `KYC ${action}d`);
  },

  setInvestorFreeze: async (address: string, freeze: boolean): Promise<TxResult> => {
    const result = await request<{ message: string; receipt: BReceipt }>(`/admin/${freeze ? 'freeze' : 'unfreeze'}/${address}`, postEmpty());
    return receiptToTx(result.receipt, result.message);
  },

  getOrders: async (): Promise<Order[]> => {
    const price = await unitPriceNow();
    const page = await request<Paged<BOrder>>('/orders?limit=200');
    return page.items.map(o => toOrder(o, price));
  },

  submitOrder: async (type: 'subscribe' | 'redeem', input: { investor: string; units: number }): Promise<Order> => {
    const key = (typeof crypto !== 'undefined' && 'randomUUID' in crypto) ? crypto.randomUUID() : String(Date.now());
    const result = await request<{ order: BOrder; receipt: BReceipt }>(`/orders/${type}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key },
      body: JSON.stringify(input),
    });
    const price = result.order.settled_unit_price > 0 ? result.order.settled_unit_price : await unitPriceNow();
    return toOrder(result.order, price);
  },

  settleOrder: async (id: string): Promise<TxResult> => {
    const result = await request<{ order: BOrder; receipt: BReceipt }>(`/orders/${id}/settle`, postEmpty());
    return receiptToTx(result.receipt, 'Order settled');
  },

  cancelOrder: async (id: string): Promise<TxResult> => {
    const result = await request<{ order: BOrder; receipt: BReceipt }>(`/orders/${id}/cancel`, postEmpty());
    return receiptToTx(result.receipt, 'Order cancelled');
  },

  getNavHistory: async (): Promise<NavPoint[]> => {
    const page = await request<Paged<BNavPoint>>('/fund/nav/history?limit=200');
    const points = page.items
      .map(p => ({ date: isoFrom(p.timestamp), nav: p.nav_total * PRICE_SCALE, unitPrice: p.unit_price }))
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
    if (points.length) return points;
    // No NAV updates published yet — show the current valuation as a single point.
    const status = await request<BFundStatus>('/fund/status');
    return [{ date: now(), nav: status.nav_total * PRICE_SCALE, unitPrice: status.unit_price }];
  },

  /** `nav` arrives from the UI as dollars x PRICE_SCALE; the API expects whole dollars. */
  updateNav: async (nav: number): Promise<TxResult> => {
    const newNav = Math.max(1, Math.round(nav / PRICE_SCALE));
    const result = await request<{ new_nav: number; unit_price: number; receipt: BReceipt }>('/fund/nav', json({ new_nav: newNav }));
    return receiptToTx(result.receipt, 'NAV published');
  },

  transfer: async (input: { from: string; to: string; units: number }): Promise<TxResult> => {
    const result = await request<{ receipt: BReceipt }>('/transfers', json(input));
    return receiptToTx(result.receipt, 'Transfer completed');
  },

  getCustodyActions: async (): Promise<CustodyAction[]> => {
    const price = await unitPriceNow();
    const page = await request<Paged<BCustody>>('/custody/actions?limit=200');
    return page.items.map(c => toCustodyAction(c, price));
  },

  getCustodyPositions: async (): Promise<CustodyPosition[]> => {
    const page = await request<Paged<BPosition>>('/custody/positions?limit=200');
    let names: Record<string, string> = {};
    try {
      const list = await request<Paged<BInvestor>>('/investors?limit=200');
      names = Object.fromEntries(list.items.map(i => [i.address.toLowerCase(), i.name ?? shortAddress(i.address)]));
    } catch { names = {}; }
    return page.items.map(p => ({ investor: p.investor, name: names[p.investor.toLowerCase()] ?? shortAddress(p.investor), balance: p.balance, locked: p.locked, free: p.free }));
  },

  createCustodyAction: async (input: { type: CustodyAction['type']; investor: string; units: number; assetRef: string; reason: string }): Promise<TxResult> => {
    const result = await request<{ action: BCustody; receipt: BReceipt }>('/custody/actions', json({
      action_type: input.type, investor: input.investor, units: input.units, asset_ref: input.assetRef, reason: input.reason,
    }));
    return receiptToTx(result.receipt, `Custody ${input.type.toLowerCase()} recorded`);
  },

  setFundPause: async (pause: boolean): Promise<TxResult> => {
    const result = await request<{ message: string; receipt: BReceipt }>(`/admin/${pause ? 'pause' : 'unpause'}`, postEmpty());
    return receiptToTx(result.receipt, result.message);
  },

  getAdminRoles: async (): Promise<DemoUser[]> => {
    const roles = await request<BRole[]>('/admin/roles');
    return roles.map(r => {
      const username = ROLE_TO_USERNAME[r.role] ?? r.role.toLowerCase();
      return { username: username as Role, name: accountLabel(username), address: r.address };
    });
  },

  getInvestorStatement: async (address: string, style: string, format: string): Promise<unknown> => {
    const query = `?style=${encodeURIComponent(style)}&format=${encodeURIComponent(format)}`;
    if (format === 'csv' || format === 'pdf') {
      await download(`/reports/investor/${address}/statement${query}`, `statement-${address.slice(0, 8)}.${format}`);
      return { downloaded: true, format, style, address, message: `${format.toUpperCase()} statement downloaded.` };
    }
    return request(`/reports/investor/${address}/statement${query}`);
  },

  getTransactions: async (): Promise<Order[]> => {
    const price = await unitPriceNow();
    const page = await request<Paged<BOrder>>('/orders?status=SETTLED&limit=200');
    return page.items.map(o => toOrder(o, price));
  },

  getAuditEvents: async (): Promise<AuditEvent[]> => {
    const page = await request<Paged<BAuditEvent>>('/audit/events?limit=100');
    return page.items.map(toAuditEvent);
  },

  verifyOnChain: async (txHash: string): Promise<{ match: boolean; txHash: string; blockNumber?: number | undefined }> => {
    const result = await request<{ tx_hash: string; matches: boolean; detail: { block_number?: number } }>(`/audit/verify/${txHash}`);
    return { match: result.matches, txHash: result.tx_hash, blockNumber: result.detail?.block_number };
  },
};

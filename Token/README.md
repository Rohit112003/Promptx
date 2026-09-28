# Token — Fund Servicing Console

The frontend for the **Tokenised Fund Servicing Platform**. A TanStack Start + React +
TypeScript app styled with Tailwind and Shadcn UI, wired to the FastAPI backend in
`../backend`.

## Running it (two terminals)

**1. Backend** (from the repo root, `..`):

```sh
cd backend
../.venv/Scripts/python -m app        # Windows
../.venv/bin/python -m app            # macOS/Linux
```

Optionally seed demo data (5 investors, orders, NAV, custody):

```sh
python backend/scripts/seed_demo_data.py
```

**2. Frontend** (from this folder):

```sh
npm install
npm run dev
```

Open **http://localhost:5173** and sign in with any demo account — password `demo`:
`admin`, `agent`, `custodian`, `auditor`, `investor1`…`investor5`.

> Start with **agent** — it can drive almost the whole workflow.

## Configuration

`.env` in this folder controls the backend connection:

| Variable | Default | Meaning |
|----------|---------|---------|
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | REST base URL |
| `VITE_WS_URL` | `ws://localhost:8000/ws/events` | Live event stream |

Restart `npm run dev` after changing these. There is **no mock/offline mode** — every
screen reads live data from the backend, so the backend must be running.

## How the frontend talks to the backend

Everything lives in **`src/lib/api.ts`** (per `AGENTS.md`), with the shared contracts in
`src/lib/types.ts`. Every method calls the live API — there is no mock data in the app.

- **Auth** — `POST /auth/login` (form-encoded) returns a JWT, stored in `localStorage`
  under `fund_token` and attached as `Authorization: Bearer …` on every request. A `401`
  clears the session and fires a `fund:unauthorized` event so the console returns to login.
- **Mapping** — the API speaks `snake_case` and the UI speaks `camelCase`, so `api.ts`
  translates every payload. Two scaling rules matter:
  - `nav_total` / `portfolio_value` are **whole dollars** → multiplied by `PRICE_SCALE` (1e8) for display.
  - `unit_price` is **already 1e8-scaled** → passed through unchanged.
  - An order's `amount` is derived as `units × unitPrice`.
- **Pagination** — backend list endpoints return `{items, total, limit, offset}`; the
  adapter unwraps `items`.
- **Live feed** — `/ws/events` pushes `{type: 'event', data: {...}}`; `mapWsEvent()`
  converts each into the console's `AuditEvent` shape.
- **Exports** — CSV and PDF statements are fetched with the auth header and downloaded as
  a blob (`format=csv|pdf`); JSON renders in the preview panel.
- **Role fallback** — investor logins can't list the whole registry, so `getInvestors()`
  falls back to that investor's own record instead of erroring.

## Page → endpoint map

| Page | Backend endpoints |
|------|-------------------|
| Overview | `/fund/status`, `/reports/fund/summary`, `/reports/nav-performance`, `/orders`, `/audit/events` |
| Investors | `/investors`, `/investors/{address}`, `/kyc/{address}/{approve\|reject\|revoke}`, `/admin/freeze/{address}` |
| Orders | `/orders`, `/orders/subscribe`, `/orders/redeem`, `/orders/{id}/settle`, `/orders/{id}/cancel` |
| NAV | `/fund/nav/history`, `/fund/nav` |
| Transfers | `/transfers` |
| Custody | `/custody/positions`, `/custody/actions` |
| Reports | `/reports/investor/{address}/statement`, `/orders?status=SETTLED` |
| Audit | `/audit/events`, `/audit/verify/{txHash}` |
| Live feed | `ws://…/ws/events` |
| Administration | `/admin/roles`, `/admin/pause`, `/admin/unpause` |

Note: custody is recorded **on chain against an investor, in fund units** (not as a USD
asset balance), so the Custody page selects an investor and an amount in units. Locked
units cannot be redeemed or transferred.

## Scripts

```sh
npm run dev      # dev server on :5173
npm run build    # production build
npm run lint     # eslint
```

## Stack

TanStack Start · React 19 · TypeScript · Tailwind CSS v4 · Shadcn UI · TanStack Query

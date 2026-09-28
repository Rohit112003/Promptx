"""Seed demo data through the running API so the frontend has real data to show.

Creates 5 investors, approves KYC, runs subscription/redemption orders with
settlement, updates NAV, records custody actions, and does an investor transfer.

Usage (backend must be running):
    python backend/scripts/seed_demo_data.py
    API_URL=http://localhost:8000 python backend/scripts/seed_demo_data.py
"""
from __future__ import annotations

import os
import sys
import time

import httpx

API_URL = os.environ.get("API_URL", "http://localhost:8000")
V1 = f"{API_URL}/api/v1"

INVESTORS = [
    {"key": "investor1", "name": "Alice Advisors LLC", "jurisdiction": "US"},
    {"key": "investor2", "name": "Bob Capital Partners", "jurisdiction": "UK"},
    {"key": "investor3", "name": "Carol Wealth Pte", "jurisdiction": "SG"},
    {"key": "investor4", "name": "David Family Office", "jurisdiction": "DE"},
    {"key": "investor5", "name": "Eve Pension Fund", "jurisdiction": "JP"},
]


def _login(client: httpx.Client, username: str) -> str:
    resp = client.post(f"{V1}/auth/login",
                       data={"username": username, "password": "demo"})
    resp.raise_for_status()
    return resp.json()["access_token"]


def _hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _wait_for_api(client: httpx.Client, attempts: int = 30) -> None:
    for _ in range(attempts):
        try:
            if client.get(f"{V1}/health").status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    print("API did not become ready; is the backend running?", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    with httpx.Client(timeout=60) as client:
        _wait_for_api(client)
        agent = _login(client, "agent")
        custodian = _login(client, "custodian")
        users = client.get(f"{V1}/auth/demo-users").json()

        # 1) Register + approve KYC for 5 investors.
        addresses = {}
        for inv in INVESTORS:
            addr = users[inv["key"]]["address"]
            addresses[inv["key"]] = addr
            r = client.post(f"{V1}/investors", headers=_hdr(agent), json={
                "address": addr, "name": inv["name"], "jurisdiction": inv["jurisdiction"],
            })
            print(f"register {inv['key']:9} {addr} -> {r.status_code}")
            r = client.post(f"{V1}/kyc/{addr}/approve", headers=_hdr(agent))
            print(f"approve  {inv['key']:9} -> {r.status_code}")

        # 2) Subscriptions (agent acts on behalf) + settlement.
        sub_units = {"investor1": 500, "investor2": 300, "investor3": 250,
                     "investor4": 400, "investor5": 150}
        for key, units in sub_units.items():
            r = client.post(f"{V1}/orders/subscribe", headers=_hdr(agent),
                           json={"investor": addresses[key], "units": units})
            oid = r.json()["order"]["id"]
            s = client.post(f"{V1}/orders/{oid}/settle", headers=_hdr(agent))
            print(f"subscribe {key:9} {units} units order#{oid} settle->{s.status_code}")

        # 3) NAV update (fund up ~8%).
        status = client.get(f"{V1}/fund/status", headers=_hdr(agent)).json()
        new_nav = int(status["nav_total"] * 1.08)
        r = client.post(f"{V1}/fund/nav", headers=_hdr(agent), json={"new_nav": new_nav})
        print(f"nav update -> {new_nav} ({r.status_code})")

        # 4) A redemption + settle.
        r = client.post(f"{V1}/orders/redeem", headers=_hdr(agent),
                       json={"investor": addresses["investor1"], "units": 100})
        oid = r.json()["order"]["id"]
        client.post(f"{V1}/orders/{oid}/settle", headers=_hdr(agent))
        print(f"redeem investor1 100 units order#{oid} settled")

        # 5) Custody lock on investor2.
        r = client.post(f"{V1}/custody/actions", headers=_hdr(custodian), json={
            "action_type": "LOCK", "investor": addresses["investor2"], "units": 50,
            "asset_ref": "ISIN:US0000001", "reason": "Collateral pledge",
        })
        print(f"custody lock investor2 50 units -> {r.status_code}")

        # 6) Investor-to-investor transfer (agent acts on behalf).
        r = client.post(f"{V1}/transfers", headers=_hdr(agent), json={
            "from": addresses["investor4"], "to": addresses["investor5"], "units": 75,
        })
        print(f"transfer investor4 -> investor5 75 units -> {r.status_code}")

        # 7) Second NAV tick for a performance series.
        status = client.get(f"{V1}/fund/status", headers=_hdr(agent)).json()
        client.post(f"{V1}/fund/nav", headers=_hdr(agent),
                    json={"new_nav": int(status["nav_total"] * 1.05)})
        summary = client.get(f"{V1}/reports/fund/summary", headers=_hdr(agent)).json()
        print("\nSeed complete. Fund summary:")
        print(f"  NAV total      : {summary['nav_total']}")
        print(f"  Total supply   : {summary['total_supply']} units")
        print(f"  Unit price     : {summary['unit_price'] / 1e8:.4f} USD")
        print(f"  Investors      : {summary['investor_count']} "
              f"({summary['approved_investors']} approved)")
        print(f"  Settled orders : {summary['settled_orders']}")


if __name__ == "__main__":
    main()

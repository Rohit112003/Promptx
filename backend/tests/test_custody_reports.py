import time

from tests.conftest import hdr


def _approved_with_units(client, agent, users, key, units):
    addr = users[key]["address"]
    client.post("/api/v1/investors", headers=hdr(agent),
                json={"address": addr, "name": key, "jurisdiction": "US"})
    client.post(f"/api/v1/kyc/{addr}/approve", headers=hdr(agent))
    r = client.post("/api/v1/orders/subscribe", headers=hdr(agent),
                    json={"investor": addr, "units": units})
    oid = r.json()["order"]["id"]
    client.post(f"/api/v1/orders/{oid}/settle", headers=hdr(agent))
    return addr


def test_custody_lock_blocks_redemption(client, agent, custodian, users):
    addr = _approved_with_units(client, agent, users, "investor4", 100)
    lock = client.post("/api/v1/custody/actions", headers=hdr(custodian), json={
        "action_type": "LOCK", "investor": addr, "units": 90,
        "asset_ref": "ISIN:US1", "reason": "collateral",
    })
    assert lock.status_code == 201
    # only 10 free now
    r = client.post("/api/v1/orders/redeem", headers=hdr(agent),
                    json={"investor": addr, "units": 50})
    assert r.status_code == 409


def test_nav_bounds_enforced(client, agent):
    status = client.get("/api/v1/fund/status", headers=hdr(agent)).json()
    too_big = int(status["nav_total"] * 2)  # +100% > 20%
    r = client.post("/api/v1/fund/nav", headers=hdr(agent), json={"new_nav": too_big})
    assert r.status_code == 400


def test_reports_and_audit(client, agent, users):
    addr = _approved_with_units(client, agent, users, "investor5", 30)
    time.sleep(2.5)  # allow the event listener to index

    summary = client.get("/api/v1/reports/fund/summary", headers=hdr(agent))
    assert summary.status_code == 200 and summary.json()["total_supply"] > 0

    csv = client.get(f"/api/v1/reports/investor/{addr}/statement?format=csv", headers=hdr(agent))
    assert csv.status_code == 200 and "Investor Statement" in csv.text

    pdf = client.get(f"/api/v1/reports/investor/{addr}/statement?format=pdf", headers=hdr(agent))
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"

    events = client.get("/api/v1/audit/events", headers=hdr(agent)).json()
    assert events["total"] > 0
    tx = events["items"][0]["tx_hash"]
    verify = client.get(f"/api/v1/audit/verify/{tx}", headers=hdr(agent)).json()
    assert verify["on_chain"] is True and verify["off_chain"] is True and verify["matches"] is True

import uuid

from tests.conftest import hdr


def _approved(client, agent, users, key):
    addr = users[key]["address"]
    client.post("/api/v1/investors", headers=hdr(agent),
                json={"address": addr, "name": key, "jurisdiction": "US"})
    client.post(f"/api/v1/kyc/{addr}/approve", headers=hdr(agent))
    return addr


def test_subscribe_settle_updates_balance(client, agent, users):
    addr = _approved(client, agent, users, "investor2")
    before = client.get(f"/api/v1/investors/{addr}", headers=hdr(agent)).json()["balance"]

    r = client.post("/api/v1/orders/subscribe", headers=hdr(agent),
                    json={"investor": addr, "units": 200})
    assert r.status_code == 201
    oid = r.json()["order"]["id"]
    assert r.json()["order"]["status"] == "PENDING"

    s = client.post(f"/api/v1/orders/{oid}/settle", headers=hdr(agent))
    assert s.status_code == 200 and s.json()["order"]["status"] == "SETTLED"

    after = client.get(f"/api/v1/investors/{addr}", headers=hdr(agent)).json()["balance"]
    assert after == before + 200


def test_redeem_beyond_balance_conflicts(client, agent, users):
    addr = _approved(client, agent, users, "investor2")
    r = client.post("/api/v1/orders/redeem", headers=hdr(agent),
                    json={"investor": addr, "units": 999999})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "contract_revert"


def test_idempotent_subscribe(client, agent, users):
    addr = _approved(client, agent, users, "investor3")
    key = str(uuid.uuid4())
    h = {**hdr(agent), "Idempotency-Key": key}
    r1 = client.post("/api/v1/orders/subscribe", headers=h, json={"investor": addr, "units": 10})
    r2 = client.post("/api/v1/orders/subscribe", headers=h, json={"investor": addr, "units": 10})
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["order"]["id"] == r2.json()["order"]["id"]


def test_cancel_pending(client, agent, users):
    addr = _approved(client, agent, users, "investor2")
    r = client.post("/api/v1/orders/subscribe", headers=hdr(agent),
                    json={"investor": addr, "units": 5})
    oid = r.json()["order"]["id"]
    c = client.post(f"/api/v1/orders/{oid}/cancel", headers=hdr(agent))
    assert c.status_code == 200 and c.json()["order"]["status"] == "CANCELLED"
    # settling a cancelled order now conflicts
    s = client.post(f"/api/v1/orders/{oid}/settle", headers=hdr(agent))
    assert s.status_code == 409

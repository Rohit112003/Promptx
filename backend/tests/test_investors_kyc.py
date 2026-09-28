from tests.conftest import hdr


def test_register_approve_and_fetch(client, agent, users):
    addr = users["investor1"]["address"]
    r = client.post("/api/v1/investors", headers=hdr(agent),
                    json={"address": addr, "name": "Bob Capital", "jurisdiction": "UK"})
    assert r.status_code == 201
    assert r.json()["investor"]["kyc_status"] == "PENDING"
    assert r.json()["receipt"]["tx_hash"].startswith("0x")

    ap = client.post(f"/api/v1/kyc/{addr}/approve", headers=hdr(agent))
    assert ap.status_code == 200 and ap.json()["kyc_status"] == "APPROVED"

    got = client.get(f"/api/v1/investors/{addr}", headers=hdr(agent)).json()
    assert got["kyc_status"] == "APPROVED"
    assert got["name"] == "Bob Capital"  # PII stays off-chain
    assert got["exists_on_chain"] is True


def test_invalid_address_rejected(client, agent):
    r = client.post("/api/v1/investors", headers=hdr(agent),
                    json={"address": "0x1234", "name": "Bad"})
    assert r.status_code == 422


def test_list_investors_pagination(client, agent):
    r = client.get("/api/v1/investors?limit=1&offset=0", headers=hdr(agent))
    assert r.status_code == 200
    body = r.json()
    assert body["limit"] == 1 and "total" in body and len(body["items"]) <= 1

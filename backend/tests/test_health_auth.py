from tests.conftest import hdr


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["chain"]["status"] == "ok"
    assert body["database"]["status"] == "ok"
    assert body["chain"]["detail"]["contract_address"]


def test_login_and_bad_password(client):
    ok = client.post("/api/v1/auth/login", data={"username": "agent", "password": "demo"})
    assert ok.status_code == 200 and ok.json()["role"] == "TRANSFER_AGENT"
    bad = client.post("/api/v1/auth/login", data={"username": "agent", "password": "nope"})
    assert bad.status_code == 401


def test_protected_requires_token(client):
    assert client.get("/api/v1/fund/status").status_code == 401


def test_role_enforced(client, auditor, users):
    # Auditor cannot register investors (transfer-agent only).
    r = client.post("/api/v1/investors", headers=hdr(auditor),
                    json={"address": users["investor1"]["address"], "name": "X"})
    assert r.status_code == 403

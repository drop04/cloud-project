from fastapi.testclient import TestClient
import app as svc

client = TestClient(svc.app)


def test_health_and_readiness():
    assert client.get("/healthz").status_code == 200
    svc.state["ready"] = False
    assert client.get("/readyz").status_code == 503
    svc.state["ready"] = True
    assert client.get("/readyz").status_code == 200


def test_valid_output_and_headers(monkeypatch):
    svc.state["ready"] = True
    monkeypatch.setenv("MODEL_VERSION", "v1")
    monkeypatch.setattr(svc, "generate", lambda t: '{"intent": "alarm_set", "date": null, "time": "six am", "place": null}')
    r = client.post("/parse", json={"text": "set alarm six am"})
    assert r.status_code == 200 and r.json()["time"] == "six am"
    assert r.headers["X-Model-Version"] == "v1" and "X-Served-By" in r.headers


def test_fault_inject_returns_500(monkeypatch):
    svc.state["ready"] = True
    monkeypatch.setenv("FAULT_INJECT", "1")
    r = client.post("/parse", json={"text": "x"})
    assert r.status_code == 500 and r.json() == {"error": "invalid_model_output"}


def test_validator_rejects_bad_shapes():
    assert svc.validate_output('{"intent": "alarm_set", "date": 1, "time": null, "place": null}') is None
    assert svc.validate_output('{"intent": "nope", "date": null, "time": null, "place": null}') is None
    assert svc.validate_output('{"intent": "alarm_set"}') is None
    assert svc.validate_output('{"intent": "alarm_set", "date": null') is None

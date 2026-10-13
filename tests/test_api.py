from fastapi.testclient import TestClient
from app.main import app
from app import main

class FakeKube:
    def set_deployment_image(self, namespace, deployment, container_name, image):
        return {"namespace": namespace, "deployment": deployment, "image_requested": image}

def test_preview_is_not_execution():
    response = TestClient(app).post("/remediation/preview")
    assert response.status_code == 200
    assert response.json()["requires_human_approval"] is True

def test_remediation_rejects_missing_approval(monkeypatch):
    monkeypatch.setattr(main, "kube_client", lambda: FakeKube())
    response = TestClient(app).post("/remediation/execute", json={
        "approved": False, "reason": "I reviewed the incident"})
    assert response.status_code == 403

def test_remediation_requires_reason(monkeypatch):
    monkeypatch.setattr(main, "kube_client", lambda: FakeKube())
    response = TestClient(app).post("/remediation/execute", json={
        "approved": True, "reason": "ok"})
    assert response.status_code == 422

def test_approved_remediation_uses_allowlisted_action(monkeypatch):
    monkeypatch.setattr(main, "kube_client", lambda: FakeKube())
    response = TestClient(app).post("/remediation/execute", json={
        "approved": True,
        "reason": "Reviewed the lab incident and approved restoring the image"})
    assert response.status_code == 200
    assert response.json()["status"] == "submitted"
    assert response.json()["action"]["namespace"] == "incident-lab"

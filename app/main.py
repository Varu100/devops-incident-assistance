import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from kubernetes.client.exceptions import ApiException
from app.config import (
    ALLOWED_NAMESPACE, ALLOWED_REMEDIATION_DEPLOYMENT,
    ALLOWED_REMEDIATION_CONTAINER, ALLOWED_REMEDIATION_IMAGE,
    OLLAMA_BASE_URL, OLLAMA_MODEL,
)
from app.kube import KubeEvidence
from app.llm import analyze_evidence
from app.policy import Remediation, allowed_remediation, validate_remediation

app = FastAPI(
    title="AI DevOps Incident Assistant", version="0.1.0",
    description="Local-first incident diagnosis with allowlisted human-approved remediation.",
)

class ApprovalRequest(BaseModel):
    approved: bool
    reason: str = Field(min_length=8, max_length=500)

def kube_client():
    try:
        return KubeEvidence()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Kubernetes client initialization failed: {type(exc).__name__}")

@app.get("/health")
def health():
    try:
        ollama_ok = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3.0).status_code == 200
    except Exception:
        ollama_ok = False
    return {"api": "ok", "ollama": "ok" if ollama_ok else "unavailable",
            "model": OLLAMA_MODEL, "allowed_namespace": ALLOWED_NAMESPACE}

@app.get("/incidents/{namespace}/{pod_name}")
def get_incident(namespace: str, pod_name: str):
    try:
        return {"evidence": kube_client().collect(namespace, pod_name)}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ApiException as exc:
        raise HTTPException(status_code=exc.status or 500, detail=exc.reason)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Evidence collection failed: {type(exc).__name__}")

@app.post("/analyze/{namespace}/{pod_name}")
def analyze(namespace: str, pod_name: str):
    try:
        evidence = kube_client().collect(namespace, pod_name)
        return {"evidence": evidence, "diagnosis": analyze_evidence(evidence)}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ApiException as exc:
        raise HTTPException(status_code=exc.status or 500, detail=exc.reason)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {type(exc).__name__}")

@app.post("/remediation/preview")
def remediation_preview():
    return {"requires_human_approval": True, "action": allowed_remediation().__dict__,
            "warning": "Preview only; no changes have been made."}

@app.post("/remediation/execute")
def remediation_execute(request: ApprovalRequest):
    if not request.approved:
        raise HTTPException(status_code=403, detail="Human approval is required.")
    action = Remediation(
        namespace=ALLOWED_NAMESPACE, deployment=ALLOWED_REMEDIATION_DEPLOYMENT,
        container=ALLOWED_REMEDIATION_CONTAINER, image=ALLOWED_REMEDIATION_IMAGE)
    try:
        validate_remediation(action)
        result = kube_client().set_deployment_image(
            action.namespace, action.deployment, action.container, action.image)
        return {"status": "submitted", "approval_reason": request.reason,
                "action": action.__dict__, "result": result,
                "note": "Verify rollout and application health; patch acceptance is not proof of recovery."}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ApiException as exc:
        raise HTTPException(status_code=exc.status or 500, detail=exc.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Remediation failed: {type(exc).__name__}")

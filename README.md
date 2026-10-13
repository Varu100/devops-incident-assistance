# AI-Powered DevOps Incident Assistant (MVP)

A local-first Kubernetes incident assistant for a kind cluster. It collects evidence with the Kubernetes Python client, asks a local Ollama model to explain likely causes, and exposes a remediation endpoint that accepts only one preconfigured action after explicit human approval.

**Lab only:** do not point this MVP at production. The LLM is advisory; it cannot choose arbitrary shell commands or arbitrary Kubernetes mutations.

## Prerequisites
- Docker running, `kubectl`, `kind`, Python 3.11+
- Ollama installed and running on the host
- Enough RAM for your local model (example: `qwen2.5:3b`)

Official docs: [kind quick start](https://kind.sigs.k8s.io/docs/user/quick-start/), [Kubernetes RBAC good practices](https://kubernetes.io/docs/concepts/security/rbac-good-practices/), [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md).

## 1. Create cluster and namespace

```bash
kind create cluster --name incident-lab --wait 120s
kubectl cluster-info --context kind-incident-lab
kubectl create namespace incident-lab
```

Skip cluster creation if it already exists. If the namespace already exists, continue.

## 2. Start local model

Install Ollama from https://ollama.com/download, then:

```bash
ollama pull qwen2.5:3b
ollama run qwen2.5:3b
```

Exit with `/bye`; keep the Ollama service running. Verify `curl http://localhost:11434/api/tags`. Set `OLLAMA_MODEL` to use a different locally installed model.

## 3. Deploy test app and RBAC

```bash
kubectl apply -f k8s/demo-deployment.yaml
kubectl apply -f k8s/rbac.yaml
kubectl -n incident-lab rollout status deployment/incident-demo
kubectl -n incident-lab get pods
```

RBAC is limited to `incident-lab`. It permits reading pods/logs/events/deployments and patching deployments for the single allowlisted remediation.

## 4. Install Python dependencies and create restricted kubeconfig

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/create_assistant_kubeconfig.py
```

The helper creates `.assistant-kubeconfig` using a short-lived ServiceAccount token, current cluster endpoint, and CA. Treat it as a credential; it is git-ignored. Rerun after token expiry.

Verify least privilege:

```bash
KUBECONFIG="$PWD/.assistant-kubeconfig" kubectl auth can-i get pods -n incident-lab
KUBECONFIG="$PWD/.assistant-kubeconfig" kubectl auth can-i patch deployments -n incident-lab
KUBECONFIG="$PWD/.assistant-kubeconfig" kubectl auth can-i get pods -n default
```

Expected: `yes`, `yes`, `no`. PowerShell: `$env:KUBECONFIG="$PWD\.assistant-kubeconfig"`.

## 5. Configure and run API

```bash
cp .env.example .env
export KUBECONFIG="$PWD/.assistant-kubeconfig"
set -a; source .env; set +a
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

For Windows, set the variables in `.env` in your PowerShell session, then run `uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`.

Open http://127.0.0.1:8000/docs. The API binds to loopback only; do not expose it publicly.

## 6. Create a test incident

```bash
kubectl -n incident-lab set image deployment/incident-demo nginx=nginx:does-not-exist
kubectl -n incident-lab get pods -w
```

Stop watching with Ctrl+C after `ImagePullBackOff` appears. Get the pod name with `kubectl -n incident-lab get pods`.

Collect evidence (replace `<pod-name>`):

```bash
curl -s http://127.0.0.1:8000/incidents/incident-lab/<pod-name> | python -m json.tool
```

Ask Ollama to analyze it:

```bash
curl -s -X POST http://127.0.0.1:8000/analyze/incident-lab/<pod-name> | python -m json.tool
```

Check the evidence yourself; local models can be wrong.

## 7. Preview and approve remediation

Preview only describes the server-configured action:

```bash
curl -s -X POST http://127.0.0.1:8000/remediation/preview | python -m json.tool
```

Explicitly approve the single allowlisted action:

```bash
curl -s -X POST http://127.0.0.1:8000/remediation/execute \
  -H 'Content-Type: application/json' \
  -d '{"approved": true, "reason": "Reviewed ImagePullBackOff evidence; restore known-good lab image"}' | python -m json.tool
```

Verify recovery:

```bash
kubectl -n incident-lab rollout status deployment/incident-demo
kubectl -n incident-lab get pods
```

The `approved` boolean is only a local-lab approval mechanism, not enterprise identity proof. Production needs authentication, an expiring approval bound to the exact action, durable audit logs, and separate read/write services.

## API endpoints
- `GET /health`
- `GET /incidents/{namespace}/{pod_name}`
- `POST /analyze/{namespace}/{pod_name}`
- `POST /remediation/preview`
- `POST /remediation/execute`

## Tests

```bash
pytest -q
```

## Troubleshooting
- Ollama refused connection: ensure service is running and `/api/tags` responds.
- Model missing: run `ollama pull qwen2.5:3b`.
- Kubernetes forbidden: check kubeconfig, token expiry and `kubectl auth can-i`.
- `ImagePullBackOff` may have no useful container logs; pod events are the key evidence.
- Cleanup: `kind delete cluster --name incident-lab`.

import base64
import json
import os
import subprocess
from pathlib import Path

def run(command):
    return subprocess.check_output(command, text=True).strip()

def main():
    current = json.loads(run([
        "kubectl", "config", "view", "--minify", "--raw", "-o", "json"
    ]))
    cluster = current["clusters"][0]["cluster"]
    server = cluster["server"]
    ca_data = cluster.get("certificate-authority-data")
    if not ca_data and cluster.get("certificate-authority"):
        ca_path = Path(cluster["certificate-authority"]).expanduser().resolve()
        ca_data = base64.b64encode(ca_path.read_bytes()).decode("ascii")
    if not ca_data:
        raise SystemExit("Could not find certificate authority data in current kubeconfig.")
    token = run([
        "kubectl", "-n", "incident-lab", "create", "token",
        "incident-assistant", "--duration=24h"
    ])
    output = {
        "apiVersion": "v1", "kind": "Config",
        "clusters": [{"name": "kind-incident-lab",
                      "cluster": {"server": server, "certificate-authority-data": ca_data}}],
        "users": [{"name": "incident-assistant", "user": {"token": token}}],
        "contexts": [{"name": "incident-assistant",
                      "context": {"cluster": "kind-incident-lab",
                                  "user": "incident-assistant", "namespace": "incident-lab"}}],
        "current-context": "incident-assistant",
    }
    destination = Path(__file__).resolve().parents[1] / ".assistant-kubeconfig"
    destination.write_text(json.dumps(output, indent=2), encoding="utf-8")
    try:
        os.chmod(destination, 0o600)
    except OSError:
        pass
    print(f"Wrote {destination}")
    print("Treat this file as a credential; token expires and must not be committed.")

if __name__ == "__main__":
    main()

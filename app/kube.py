import os
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from app.config import ALLOWED_NAMESPACE

class KubeEvidence:
    def __init__(self):
        kubeconfig = os.getenv("KUBECONFIG")
        try:
            if kubeconfig:
                config.load_kube_config(config_file=kubeconfig)
            else:
                config.load_kube_config()
        except Exception:
            config.load_incluster_config()
        self.core = client.CoreV1Api()
        self.apps = client.AppsV1Api()

    @staticmethod
    def _check_namespace(namespace: str):
        if namespace != ALLOWED_NAMESPACE:
            raise PermissionError(f"Only namespace {ALLOWED_NAMESPACE!r} is allowed.")

    def collect(self, namespace: str, pod_name: str) -> dict:
        self._check_namespace(namespace)
        pod = self.core.read_namespaced_pod(name=pod_name, namespace=namespace)
        statuses = []
        for status in (pod.status.container_statuses or []):
            state = status.state
            waiting = getattr(state, "waiting", None) if state else None
            terminated = getattr(state, "terminated", None) if state else None
            last_state = status.last_state
            last_terminated = getattr(last_state, "terminated", None) if last_state else None
            statuses.append({
                "name": status.name, "ready": status.ready,
                "restart_count": status.restart_count, "image": status.image,
                "waiting_reason": getattr(waiting, "reason", None),
                "waiting_message": getattr(waiting, "message", None),
                "terminated_reason": getattr(terminated, "reason", None),
                "last_terminated_reason": getattr(last_terminated, "reason", None),
                "last_exit_code": getattr(last_terminated, "exit_code", None),
            })
        logs, previous_logs = {}, {}
        for status in (pod.status.container_statuses or []):
            try:
                logs[status.name] = self.core.read_namespaced_pod_log(
                    name=pod_name, namespace=namespace, container=status.name,
                    tail_lines=150, timestamps=True)
            except ApiException as exc:
                logs[status.name] = f"Log collection unavailable: HTTP {exc.status}"
            if status.restart_count:
                try:
                    previous_logs[status.name] = self.core.read_namespaced_pod_log(
                        name=pod_name, namespace=namespace, container=status.name,
                        previous=True, tail_lines=150, timestamps=True)
                except ApiException:
                    previous_logs[status.name] = ""
        event_items = self.core.list_namespaced_event(
            namespace=namespace, field_selector=f"involvedObject.name={pod_name}", limit=100
        ).items
        events = [{
            "type": item.type, "reason": item.reason, "message": item.message,
            "count": item.count,
            "last_timestamp": str(item.last_timestamp or item.event_time or ""),
        } for item in event_items]
        owners = pod.metadata.owner_references or []
        return {
            "namespace": namespace, "pod": pod_name, "phase": pod.status.phase,
            "node": pod.spec.node_name, "labels": pod.metadata.labels or {},
            "owners": [{"kind": owner.kind, "name": owner.name} for owner in owners],
            "container_statuses": statuses, "logs": logs,
            "previous_logs": previous_logs, "events": events,
        }

    def set_deployment_image(self, namespace: str, deployment: str,
                             container_name: str, image: str) -> dict:
        self._check_namespace(namespace)
        body = {"spec": {"template": {"spec": {"containers": [
            {"name": container_name, "image": image}
        ]}}}}
        result = self.apps.patch_namespaced_deployment(
            name=deployment, namespace=namespace, body=body)
        return {
            "namespace": namespace, "deployment": result.metadata.name,
            "generation": result.metadata.generation, "image_requested": image,
        }

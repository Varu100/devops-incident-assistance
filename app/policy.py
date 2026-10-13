from dataclasses import dataclass
from app import config

@dataclass(frozen=True)
class Remediation:
    namespace: str
    deployment: str
    container: str
    image: str

def allowed_remediation() -> Remediation:
    return Remediation(
        namespace=config.ALLOWED_NAMESPACE,
        deployment=config.ALLOWED_REMEDIATION_DEPLOYMENT,
        container=config.ALLOWED_REMEDIATION_CONTAINER,
        image=config.ALLOWED_REMEDIATION_IMAGE,
    )

def validate_remediation(requested: Remediation) -> None:
    """Reject any action that is not the single administrator-configured action."""
    if requested != allowed_remediation():
        raise ValueError("Requested remediation does not match the server-side allowlist.")

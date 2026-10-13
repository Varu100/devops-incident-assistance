import pytest
from app.policy import Remediation, allowed_remediation, validate_remediation

def test_server_configured_action_is_allowed():
    validate_remediation(allowed_remediation())

@pytest.mark.parametrize("field,value", [
    ("namespace", "default"),
    ("deployment", "kube-system-component"),
    ("container", "sidecar"),
    ("image", "attacker.example/evil:latest"),
])
def test_any_action_outside_allowlist_is_rejected(field, value):
    proposed = allowed_remediation().__dict__.copy()
    proposed[field] = value
    with pytest.raises(ValueError):
        validate_remediation(Remediation(**proposed))

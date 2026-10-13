import os
from dotenv import load_dotenv

load_dotenv()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
ALLOWED_NAMESPACE = os.getenv("ALLOWED_NAMESPACE", "incident-lab")
ALLOWED_REMEDIATION_DEPLOYMENT = os.getenv("ALLOWED_REMEDIATION_DEPLOYMENT", "incident-demo")
ALLOWED_REMEDIATION_CONTAINER = os.getenv("ALLOWED_REMEDIATION_CONTAINER", "nginx")
ALLOWED_REMEDIATION_IMAGE = os.getenv("ALLOWED_REMEDIATION_IMAGE", "nginx:1.27.5")

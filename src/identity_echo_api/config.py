import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

TENANT_ID: str = os.getenv("ENTRA_TENANT_ID", "")
RESOURCE_API_CLIENT_ID: str = os.getenv("ENTRA_RESOURCE_API_CLIENT_ID", "")
AGENT_USER_UPN: str = os.getenv("ENTRA_AGENT_ID_USER_UPN", "")

ENTRA_JWKS_URL: str = (
    f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
)
ENTRA_ISSUER: str = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
EXPECTED_AUDIENCE: str = RESOURCE_API_CLIENT_ID

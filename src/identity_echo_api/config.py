import os

from dotenv import load_dotenv

load_dotenv()

TENANT_ID: str = os.getenv("TENANT_ID", "")
RESOURCE_API_CLIENT_ID: str = os.getenv("RESOURCE_API_CLIENT_ID", "")
AGENT_USER_UPN: str = os.getenv("AGENT_USER_UPN", "")

ENTRA_JWKS_URL: str = (
    f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
)
ENTRA_ISSUER: str = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
EXPECTED_AUDIENCE: str = RESOURCE_API_CLIENT_ID

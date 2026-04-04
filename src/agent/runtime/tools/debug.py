"""Debug tool — verify agent runtime environment (Step A-2/A-3)."""

import base64
import json
import os

from agent_framework import tool


def _decode_jwt_claims(token_str: str) -> dict:
    """Decode JWT payload without verification (inspection only)."""
    parts = token_str.split(".")
    if len(parts) < 2:
        return {"error": "not a valid JWT"}
    payload = parts[1]
    # Add padding
    payload += "=" * (-len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload)
    return json.loads(decoded)


def _run_env_check() -> str:
    """Implementation of the environment check."""
    from azure.identity import DefaultAzureCredential

    # Collect user-defined + notable env vars
    env_vars = {
        "FOUNDRY_PROJECT_ENDPOINT": os.getenv("FOUNDRY_PROJECT_ENDPOINT", "NOT SET"),
        "FOUNDRY_MODEL_DEPLOYMENT_NAME": os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "NOT SET"),
        "ENTRA_TENANT_ID": os.getenv("ENTRA_TENANT_ID", "NOT SET"),
        "ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID": os.getenv(
            "ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID", "NOT SET"
        ),
        "ENTRA_AGENT_IDENTITY_CLIENT_ID": os.getenv("ENTRA_AGENT_IDENTITY_CLIENT_ID", "NOT SET"),
        "RESOURCE_API_URL": os.getenv("RESOURCE_API_URL", "NOT SET"),
        "ENTRA_RESOURCE_API_SCOPE": os.getenv("ENTRA_RESOURCE_API_SCOPE", "NOT SET"),
        "ENTRA_RESOURCE_API_DEFAULT_SCOPE": os.getenv(
            "ENTRA_RESOURCE_API_DEFAULT_SCOPE", "NOT SET"
        ),
    }

    # Dump ALL environment variables (filter out obvious noise)
    all_env = {}
    for k, v in sorted(os.environ.items()):
        # Redact bearer tokens / secrets but keep the key visible
        lower = k.lower()
        if any(s in lower for s in ("secret", "password", "key", "token", "credential")):
            all_env[k] = f"<REDACTED, len={len(v)}>"
        else:
            all_env[k] = v

    credential_status: dict = {}
    identity_claims: dict = {}
    try:
        cred = DefaultAzureCredential()
        token = cred.get_token("https://management.azure.com/.default")
        credential_status = {
            "credential_obtained": True,
            "token_expires_on": token.expires_on,
        }
        # Decode JWT to extract MSI identity info
        claims = _decode_jwt_claims(token.token)
        identity_claims = {
            "appid": claims.get("appid", "N/A"),
            "oid": claims.get("oid", "N/A"),
            "sub": claims.get("sub", "N/A"),
            "tid": claims.get("tid", "N/A"),
            "idtyp": claims.get("idtyp", "N/A"),
            "xms_mirid": claims.get("xms_mirid", "N/A"),
        }
    except Exception as exc:
        credential_status = {
            "credential_obtained": False,
            "error": str(exc),
        }

    return json.dumps(
        {
            "status": "ok",
            **credential_status,
            "identity": identity_claims,
            "env": env_vars,
            "all_env": all_env,
        },
        indent=2,
        ensure_ascii=False,
    )


@tool
def check_agent_environment() -> str:
    """Check the agent runtime environment (for debugging).

    Returns whether Azure credentials can be obtained, MSI identity claims,
    and the status of key environment variables.
    """
    return _run_env_check()

"""Token exchange functions for Entra Agent ID flows.

Provides get_t1() and exchange_app_token() for the Autonomous App flow.
HTTP parameters are based on the verified try_t1_token_acquisition() results.
"""

import base64
import json

import requests
from azure.identity import DefaultAzureCredential
from config import config

# ── Constants ──
_TOKEN_URL = f"https://login.microsoftonline.com/{config.tenant_id}/oauth2/v2.0/token"
_TOKEN_EXCHANGE_SCOPE = "api://AzureADTokenExchange/.default"
_JWT_BEARER = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
_TIMEOUT = 30


def _decode_jwt_claims(token_str: str) -> dict:
    """Decode JWT payload without verification (inspection only)."""
    parts = token_str.split(".")
    if len(parts) < 2:
        return {"error": "not a valid JWT"}
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload)
    return json.loads(decoded)


def get_t1() -> dict:
    """Acquire T1 token (Agent Identity token) using Project MI.

    Step 1: Obtain a token for api://AzureADTokenExchange scope using Project MI
    Step 2: Exchange that MI token as client_assertion to get the T1 token

    Returns a dict with keys:
      - "success": bool
      - "access_token": str (T1 token, only on success)
      - "claims": dict (decoded T1 claims, only on success)
      - "error": str (only on failure)
      - "error_description": str (only on failure)
    """
    # Step 1: Get MI token for api://AzureADTokenExchange
    cred = DefaultAzureCredential()
    mi_token = cred.get_token(_TOKEN_EXCHANGE_SCOPE)

    # Step 2: Exchange MI token → T1 (Blueprint token)
    payload = {
        "client_id": config.blueprint_client_id,
        "scope": _TOKEN_EXCHANGE_SCOPE,
        "grant_type": "client_credentials",
        "client_assertion_type": _JWT_BEARER,
        "client_assertion": mi_token.token,
        "fmi_path": config.agent_identity_oid,
    }

    resp = requests.post(_TOKEN_URL, data=payload, timeout=_TIMEOUT)
    body = resp.json()

    if resp.status_code == 200:
        t1 = body.get("access_token", "")
        return {
            "success": True,
            "access_token": t1,
            "claims": _decode_jwt_claims(t1) if t1 else {},
        }

    return {
        "success": False,
        "error": body.get("error", "unknown"),
        "error_description": body.get("error_description", "N/A"),
        "error_codes": body.get("error_codes", []),
    }


def exchange_app_token(t1: str) -> dict:
    """Exchange T1 for TR (resource token) using client_credentials.

    This is the Autonomous App flow — the resulting TR is an app-only token
    with `roles` (no `scp`), and `sub` = Agent Identity OID.

    Args:
        t1: The T1 access token obtained from get_t1().

    Returns a dict with keys:
      - "success": bool
      - "access_token": str (TR token, only on success)
      - "claims": dict (decoded TR claims, only on success)
      - "error": str (only on failure)
      - "error_description": str (only on failure)
    """
    payload = {
        "client_id": config.agent_identity_oid,
        "scope": config.resource_api_default_scope,
        "grant_type": "client_credentials",
        "client_assertion_type": _JWT_BEARER,
        "client_assertion": t1,
    }

    resp = requests.post(_TOKEN_URL, data=payload, timeout=_TIMEOUT)
    body = resp.json()

    if resp.status_code == 200:
        tr = body.get("access_token", "")
        return {
            "success": True,
            "access_token": tr,
            "claims": _decode_jwt_claims(tr) if tr else {},
        }

    return {
        "success": False,
        "error": body.get("error", "unknown"),
        "error_description": body.get("error_description", "N/A"),
        "error_codes": body.get("error_codes", []),
    }

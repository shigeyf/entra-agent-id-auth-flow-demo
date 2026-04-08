"""Token exchange functions for Entra Agent ID flows.

Provides:
  - get_t1()                    — Project MI → T1 (common to all flows)
  - exchange_app_token()        — T1 → TR (app-only, Autonomous App flow)
  - exchange_user_t2()          — T1 → T2 (Agent Identity exchange token, Autonomous User flow)
  - exchange_user_token()       — T1 + T2 + username → TR (delegated, Autonomous User flow)
  - exchange_interactive_obo()  — T1 + Tc → TR (delegated, Interactive OBO flow)

HTTP parameters are based on the official Microsoft protocol documentation.
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


def exchange_user_t2(t1: str) -> dict:
    """Exchange T1 for T2 (Agent Identity exchange token) using client_credentials.

    This is Step 2 of the Autonomous User flow.
    Entra ID validates that T1.aud == Agent Identity Blueprint.

    Args:
        t1: The T1 access token obtained from get_t1().

    Returns a dict with keys:
      - "success": bool
      - "access_token": str (T2 token, only on success)
      - "claims": dict (decoded T2 claims, only on success)
      - "error": str (only on failure)
      - "error_description": str (only on failure)
    """
    payload = {
        "client_id": config.agent_identity_oid,
        "scope": _TOKEN_EXCHANGE_SCOPE,
        "client_assertion_type": _JWT_BEARER,
        "client_assertion": t1,
        "grant_type": "client_credentials",
    }

    resp = requests.post(_TOKEN_URL, data=payload, timeout=_TIMEOUT)
    body = resp.json()

    if resp.status_code == 200:
        t2 = body.get("access_token", "")
        return {
            "success": True,
            "access_token": t2,
            "claims": _decode_jwt_claims(t2) if t2 else {},
        }

    return {
        "success": False,
        "error": body.get("error", "unknown"),
        "error_description": body.get("error_description", "N/A"),
        "error_codes": body.get("error_codes", []),
    }


def exchange_user_token(t1: str, t2: str, username: str) -> dict:
    """Exchange T1 + T2 for TR (delegated resource token) via user_fic grant.

    This is Step 3 of the Autonomous User flow (Agent User Impersonation).
    Uses the ``user_fic`` grant type with ``user_federated_identity_credential``
    as defined in the official Entra Agent ID protocol:
    https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/agent-user-oauth-flow

    The resulting TR is a **delegated** token with the Agent User as the subject.

    Args:
        t1: The T1 access token (client_assertion).
        t2: The T2 access token (user_federated_identity_credential).
        username: The Agent User UPN (e.g. agentuser@contoso.com).

    Returns a dict with keys:
      - "success": bool
      - "access_token": str (TR token, only on success)
      - "claims": dict (decoded TR claims, only on success)
      - "error": str (only on failure)
      - "error_description": str (only on failure)
    """
    payload = {
        "client_id": config.agent_identity_oid,
        "scope": config.resource_api_scope,
        "grant_type": "user_fic",
        "client_assertion_type": _JWT_BEARER,
        "client_assertion": t1,
        "user_federated_identity_credential": t2,
        "username": username,
        "requested_token_use": "on_behalf_of",
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


def exchange_interactive_obo(t1: str, tc: str) -> dict:
    """Exchange T1 + Tc for TR (delegated resource token) via OBO.

    This is the Interactive OBO flow — the resulting TR is a delegated token
    with the human user as the subject (sub = user OID, upn = user UPN).

    Protocol reference:
    https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/agent-on-behalf-of-oauth-flow

    Args:
        t1: The T1 access token obtained from get_t1().
        tc: The user's access token (aud = Blueprint App ID).

    Returns a dict with keys:
      - "success": bool
      - "access_token": str (TR token, only on success)
      - "claims": dict (decoded TR claims, only on success)
      - "error": str (only on failure)
      - "error_description": str (only on failure)
    """
    payload = {
        "client_id": config.agent_identity_oid,
        "scope": config.resource_api_scope,
        "client_assertion_type": _JWT_BEARER,
        "client_assertion": t1,
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": tc,
        "requested_token_use": "on_behalf_of",
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

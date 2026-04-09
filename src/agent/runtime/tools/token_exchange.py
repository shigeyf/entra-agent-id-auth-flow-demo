"""Token exchange experiment — attempt T1 acquisition with Project MI."""

import base64
import json
import os

import requests
from agent_framework import tool


def _decode_jwt_claims(token_str: str) -> dict:
    """Decode JWT payload without verification (inspection only)."""
    parts = token_str.split(".")
    if len(parts) < 2:
        return {"error": "not a valid JWT"}
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload)
    return json.loads(decoded)


def _run_t1_acquisition() -> str:
    """Implementation of T1 token acquisition."""
    from azure.identity import DefaultAzureCredential

    TENANT_ID = os.getenv("ENTRA_TENANT_ID", "")
    BLUEPRINT_CLIENT_ID = os.getenv("ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID", "")
    AGENT_IDENTITY_CLIENT_ID = os.getenv("ENTRA_AGENT_IDENTITY_CLIENT_ID", "")

    result = {
        "step1_mi_token": {},
        "step2_t1_request": {},
    }

    # ── Step 1: Get MI token for api://AzureADTokenExchange ──
    try:
        cred = DefaultAzureCredential()
        mi_token = cred.get_token("api://AzureADTokenExchange/.default")
        mi_claims = _decode_jwt_claims(mi_token.token)
        result["step1_mi_token"] = {
            "success": True,
            "expires_on": mi_token.expires_on,
            "claims": {
                "aud": mi_claims.get("aud", "N/A"),
                "iss": mi_claims.get("iss", "N/A"),
                "sub": mi_claims.get("sub", "N/A"),
                "oid": mi_claims.get("oid", "N/A"),
                "appid": mi_claims.get("appid", "N/A"),
                "idtyp": mi_claims.get("idtyp", "N/A"),
            },
        }
    except Exception as exc:
        result["step1_mi_token"] = {
            "success": False,
            "error": str(exc),
        }
        return json.dumps(result, indent=2, ensure_ascii=False)

    # ── Step 2: Exchange MI token for T1 (Blueprint token) ──
    token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    _jwt_bearer = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
    payload = {
        "client_id": BLUEPRINT_CLIENT_ID,
        "scope": "api://AzureADTokenExchange/.default",
        "grant_type": "client_credentials",
        "client_assertion_type": _jwt_bearer,
        "client_assertion": mi_token.token,
        "fmi_path": AGENT_IDENTITY_CLIENT_ID,
    }

    try:
        resp = requests.post(token_url, data=payload, timeout=30)
        resp_body = resp.json()

        if resp.status_code == 200:
            t1_token = resp_body.get("access_token", "")
            t1_claims = _decode_jwt_claims(t1_token) if t1_token else {}
            result["step2_t1_request"] = {
                "success": True,
                "status_code": resp.status_code,
                "token_type": resp_body.get("token_type", "N/A"),
                "expires_in": resp_body.get("expires_in", "N/A"),
                "t1_claims": {
                    "aud": t1_claims.get("aud", "N/A"),
                    "iss": t1_claims.get("iss", "N/A"),
                    "sub": t1_claims.get("sub", "N/A"),
                    "oid": t1_claims.get("oid", "N/A"),
                    "appid": t1_claims.get("appid", "N/A"),
                    "idtyp": t1_claims.get("idtyp", "N/A"),
                    "fmi_oid": t1_claims.get("fmi_oid", "N/A"),
                },
            }
        else:
            result["step2_t1_request"] = {
                "success": False,
                "status_code": resp.status_code,
                "error": resp_body.get("error", "unknown"),
                "error_description": resp_body.get("error_description", "N/A"),
                "error_codes": resp_body.get("error_codes", []),
            }
    except Exception as exc:
        result["step2_t1_request"] = {
            "success": False,
            "error": f"request_exception: {exc}",
        }

    return json.dumps(result, indent=2, ensure_ascii=False)


@tool
def try_t1_token_acquisition() -> str:
    """Attempt T1 token acquisition using the Project MI.

    Based on the Entra Agent ID documentation, performs the following 2 steps:
    Step 1: Obtain a token for the api://AzureADTokenExchange scope using Project MI
    Step 2: Exchange that token as a client_assertion to acquire the Blueprint T1 token
    """
    return _run_t1_acquisition()

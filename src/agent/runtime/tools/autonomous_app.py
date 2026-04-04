"""Autonomous App flow tool — T1 → TR (app-only) → Identity Echo API."""

import json

import requests
from agent_framework import tool
from auth.token_exchange import exchange_app_token, get_t1
from config import config


def _run_autonomous_app() -> str:
    """Implementation of the Autonomous App flow."""
    result: dict = {
        "step1_get_t1": {},
        "step2_exchange_app_token": {},
        "step3_call_resource_api": {},
    }

    # Step 1: Get T1
    t1_result = get_t1()
    result["step1_get_t1"] = {
        "success": t1_result["success"],
        "claims": {
            k: t1_result.get("claims", {}).get(k, "N/A")
            for k in ("aud", "sub", "oid", "appid", "idtyp")
        }
        if t1_result["success"]
        else None,
        "error": t1_result.get("error"),
    }

    if not t1_result["success"]:
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Step 2: Exchange T1 → TR (app-only)
    tr_result = exchange_app_token(t1_result["access_token"])
    result["step2_exchange_app_token"] = {
        "success": tr_result["success"],
        "claims": {
            k: tr_result.get("claims", {}).get(k, "N/A")
            for k in ("aud", "sub", "oid", "appid", "idtyp", "roles")
        }
        if tr_result["success"]
        else None,
        "error": tr_result.get("error"),
        "error_description": tr_result.get("error_description"),
    }

    if not tr_result["success"]:
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Step 3: Call Identity Echo API
    api_url = f"{config.resource_api_url}/api/resource"
    try:
        resp = requests.get(
            api_url,
            headers={"Authorization": f"Bearer {tr_result['access_token']}"},
            timeout=30,
        )
        result["step3_call_resource_api"] = {
            "success": resp.status_code == 200,
            "status_code": resp.status_code,
            "body": resp.json()
            if resp.headers.get("content-type", "").startswith("application/json")
            else resp.text,
        }
    except Exception as exc:
        result["step3_call_resource_api"] = {
            "success": False,
            "error": f"request_exception: {exc}",
        }

    return json.dumps(result, indent=2, ensure_ascii=False)


@tool
def call_resource_api_autonomous_app() -> str:
    """Call Identity Echo API using the Autonomous App flow.

    Performs the full token chain:
      1. get_t1()  — Project MI → T1 (Agent Identity token)
      2. exchange_app_token(t1) — T1 → TR (app-only resource token)
      3. Call Identity Echo API with TR as Bearer token

    Returns the Identity Echo API response showing who the caller was identified as.
    """
    return _run_autonomous_app()

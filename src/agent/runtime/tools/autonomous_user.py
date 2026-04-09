"""Autonomous Agent (User) flow tool — T1 → T2 → TR (delegated) → Identity Echo API."""

import json

import requests
from agent_framework import tool
from auth.token_exchange import exchange_user_t2, exchange_user_token, get_t1
from config import config


def _run_autonomous_user() -> str:
    """Implementation of the Autonomous Agent (User) flow."""
    result: dict = {
        "name": "call_resource_api_autonomous_user",
        "description": "Call Identity Echo API with Agent Identity Autonomous Agent (User) flow.",
        "outputs": {},
        "logs": {
            "step1_get_t1": {},
            "step2_exchange_user_t2": {},
            "step3_exchange_user_token": {},
            "step4_call_resource_api": {},
        },
    }

    # Step 1: Get T1 (Blueprint exchange token)
    t1_result = get_t1()
    result["logs"]["step1_get_t1"] = {
        "success": t1_result["success"],
        "claims": t1_result.get("claims") if t1_result["success"] else None,
        "error": t1_result.get("error"),
    }

    if not t1_result["success"]:
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Step 2: Exchange T1 → T2 (Agent Identity exchange token)
    t2_result = exchange_user_t2(t1_result["access_token"])
    result["logs"]["step2_exchange_user_t2"] = {
        "success": t2_result["success"],
        "claims": t2_result.get("claims") if t2_result["success"] else None,
        "error": t2_result.get("error"),
        "error_description": t2_result.get("error_description"),
    }

    if not t2_result["success"]:
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Step 3: Exchange T1 + T2 → TR (delegated resource token, Agent User)
    tr_result = exchange_user_token(
        t1=t1_result["access_token"],
        t2=t2_result["access_token"],
        username=config.agent_user_upn,
    )
    result["logs"]["step3_exchange_user_token"] = {
        "success": tr_result["success"],
        "claims": tr_result.get("claims") if tr_result["success"] else None,
        "error": tr_result.get("error"),
        "error_description": tr_result.get("error_description"),
    }

    if not tr_result["success"]:
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Step 4: Call Identity Echo API with delegated TR
    api_url = f"{config.resource_api_url}/api/resource"
    try:
        resp = requests.get(
            api_url,
            headers={"Authorization": f"Bearer {tr_result['access_token']}"},
            timeout=30,
        )
        result["logs"]["step4_call_resource_api"] = {
            "success": resp.status_code == 200,
            "status_code": resp.status_code,
            "body": resp.json()
            if resp.headers.get("content-type", "").startswith("application/json")
            else resp.text,
        }
        result["outputs"] = (
            resp.json()
            if resp.headers.get("content-type", "").startswith("application/json")
            else {"raw_response": resp.text}
        )
    except Exception as exc:
        result["logs"]["step4_call_resource_api"] = {
            "success": False,
            "error": f"request_exception: {exc}",
        }

    return json.dumps(result, indent=2, ensure_ascii=False)


@tool(
    name="call_resource_api_autonomous_user",
    description="Call Identity Echo API using the Agent Identity Autonomous Agent (User) flow.",
)
def call_resource_api_autonomous_user() -> str:
    """Call Identity Echo API using the Agent Identity Autonomous User flow.

    Performs the full credential chaining (3-step token acquisition):
      1. get_t1()              — Project MI → T1 (Blueprint exchange token)
      2. exchange_user_t2(t1)  — T1 → T2 (Agent Identity exchange token)
      3. exchange_user_token(t1, t2, username) — T1 + T2 → TR (delegated, Agent User)
      4. Call Identity Echo API with TR as Bearer token

    The resulting TR is a **delegated** token with the Agent User as the subject,
    unlike the Autonomous App flow which produces an app-only token.

    Returns:
        A JSON string containing the full logs and outputs of each step
        for transparency and debugging.

    JSON format:
        {
            "name": "call_resource_api_autonomous_user",
            "description":
              "Call Identity Echo API with Agent Identity Autonomous Agent (User) flow.",
            "outputs": { ... }, // The final output from the Identity Echo API call
            "logs": {
                "step1_get_t1": { ... },
                "step2_exchange_user_t2": { ... },
                "step3_exchange_user_token": { ... },
                "step4_call_resource_api": { ... }
            }
        }
    """
    return _run_autonomous_user()

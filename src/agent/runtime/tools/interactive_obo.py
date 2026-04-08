"""Interactive OBO flow tool — T1 + Tc → TR (delegated, human user) → Identity Echo API."""

import json

import requests
from agent_framework import tool
from auth.token_exchange import exchange_interactive_obo, get_t1
from config import config
from request_context import get_user_tc


def _run_interactive_obo() -> str:
    """Implementation of the Interactive OBO flow."""
    result: dict = {
        "name": "call_resource_api_interactive_obo",
        "description": "Call Identity Echo API with Interactive OBO flow (human user delegation).",
        "outputs": {},
        "logs": {
            "step1_get_t1": {},
            "step2_obo_exchange": {},
            "step3_call_resource_api": {},
        },
    }

    # Step 0: Retrieve Tc from request context
    tc = get_user_tc()
    if not tc:
        result["logs"]["step1_get_t1"] = {
            "success": False,
            "error": "no_user_token",
            "error_description": "No user token (Tc) was provided in the request metadata.",
        }
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Step 1: Get T1 (Blueprint exchange token) — same as other flows
    t1_result = get_t1()
    result["logs"]["step1_get_t1"] = {
        "success": t1_result["success"],
        "claims": t1_result.get("claims") if t1_result["success"] else None,
        "error": t1_result.get("error"),
    }

    if not t1_result["success"]:
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Step 2: OBO exchange — T1 + Tc → TR (delegated, sub = human user)
    tr_result = exchange_interactive_obo(
        t1=t1_result["access_token"],
        tc=tc,
    )
    result["logs"]["step2_obo_exchange"] = {
        "success": tr_result["success"],
        "claims": tr_result.get("claims") if tr_result["success"] else None,
        "error": tr_result.get("error"),
        "error_description": tr_result.get("error_description"),
    }

    if not tr_result["success"]:
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Step 3: Call Identity Echo API with delegated TR
    api_url = f"{config.resource_api_url}/api/resource"
    try:
        resp = requests.get(
            api_url,
            headers={"Authorization": f"Bearer {tr_result['access_token']}"},
            timeout=30,
        )
        result["logs"]["step3_call_resource_api"] = {
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
        result["logs"]["step3_call_resource_api"] = {
            "success": False,
            "error": f"request_exception: {exc}",
        }

    return json.dumps(result, indent=2, ensure_ascii=False)


@tool(
    name="call_resource_api_interactive_obo",
    description="Call Identity Echo API using the Interactive OBO flow (human user delegation).",
)
def call_resource_api_interactive_obo() -> str:
    """Call Identity Echo API using the Interactive OBO flow.

    Performs the OBO token chain:
      1. get_t1()  — Project MI → T1 (Agent Identity token)
      2. exchange_interactive_obo(t1, tc) — T1 + Tc → TR (delegated, sub = human user)
      3. Call Identity Echo API with TR as Bearer token

    The user's Tc token is retrieved from request context (set by ToolDispatchAgent
    from the request metadata, NOT from LLM function arguments).

    Returns:
        A JSON string containing the full logs and outputs of each step.

    JSON format:
        {
            "name": "call_resource_api_interactive_obo",
            "description": "...",
            "outputs": { ... },
            "logs": {
                "step1_get_t1": { ... },
                "step2_obo_exchange": { ... },
                "step3_call_resource_api": { ... }
            }
        }
    """
    return _run_interactive_obo()

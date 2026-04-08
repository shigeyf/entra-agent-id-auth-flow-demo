"""Invoke the Hosted Agent with Interactive OBO flow (E2E test).

Acquires a user Tc token via MSAL interactive login, then passes it
to the Hosted Agent via metadata.user_tc alongside force_tool.

This script validates the full Interactive OBO chain WITHOUT the SPA frontend:
  1. MSAL interactive login → Tc (aud = Blueprint, scope = access_agent)
  2. DefaultAzureCredential → Foundry API auth
  3. Responses API call with metadata.user_tc + force_tool
  4. Agent: get_t1() → exchange_interactive_obo(t1, tc) → call Identity Echo API

Prerequisites:
  - src/.env populated (run sync-infra-env.py first)
  - E1 done: Blueprint has identifierUris + access_agent scope
  - E2 done: SPA App Registration has Blueprint access_agent permission + consent
  - Agent deployed with A1-A4 changes

Required env vars:
    ENTRA_TENANT_ID
    ENTRA_SPA_APP_CLIENT_ID          — SPA App Registration Client ID (used for MSAL)
    ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID — Blueprint Client ID (Tc audience)
    FOUNDRY_PROJECT_ENDPOINT

Usage:
    python scripts/invoke-interactive-agent.py                 # default message
    python scripts/invoke-interactive-agent.py "Who am I?"     # custom message
    python scripts/invoke-interactive-agent.py --no-force-tool # let agent choose tool
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import msal
import yaml
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent  # src/agent/
_AGENT_YAML = _PROJECT_ROOT / "agent.yaml"


def _load_env() -> None:
    from dotenv import find_dotenv, load_dotenv

    env_path = find_dotenv(filename=".env", usecwd=False)
    if not env_path:
        print("WARNING: No .env file found", file=sys.stderr)
        return
    print(f"  Loading: {env_path}")
    load_dotenv(env_path, override=True)


def _require_env(key: str) -> str:
    value = os.getenv(key, "")
    if not value:
        print(f"ERROR: {key} is not set in .env", file=sys.stderr)
        sys.exit(1)
    return value


def _to_services_endpoint(endpoint: str) -> str:
    return re.sub(
        r"\.cognitiveservices\.azure\.com/",
        ".services.ai.azure.com/",
        endpoint,
    )


# ---------------------------------------------------------------------------
# Tc acquisition via MSAL
# ---------------------------------------------------------------------------
def _acquire_tc(
    spa_client_id: str,
    tenant_id: str,
    blueprint_client_id: str,
) -> str:
    """Acquire Tc (aud = Blueprint) via MSAL interactive login.

    Uses the SPA App Registration as the public client.
    The scope is api://{BlueprintClientId}/access_agent.
    """
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    # SPA App Registration は「SPA」プラットフォームのため MSAL Python から
    # トークン取得すると AADSTS9002327 になる。テスト用に GRAPH_API_OPS_CLIENT_ID
    # （「モバイルとデスクトップ」プラットフォーム）を使用する。
    # app = msal.PublicClientApplication(client_id=spa_client_id, authority=authority)
    graph_ops_client_id = _require_env("GRAPH_API_OPS_CLIENT_ID")
    app = msal.PublicClientApplication(client_id=graph_ops_client_id, authority=authority)

    scope = f"api://{blueprint_client_id}/access_agent"
    print("\n🔑 Acquiring Tc via MSAL interactive login...")
    # print(f"   Client ID : {spa_client_id}")
    print(f"   Client ID : {graph_ops_client_id}  (GRAPH_API_OPS_CLIENT_ID — test workaround)")
    print(f"   Scope     : {scope}")

    result = app.acquire_token_interactive(scopes=[scope])

    if "access_token" not in result:
        print("\n❌ Tc acquisition failed:", file=sys.stderr)
        print(json.dumps(result, indent=2, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    tc = result["access_token"]

    # Decode and display Tc claims for debugging
    import base64

    parts = tc.split(".")
    if len(parts) >= 2:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        print("\n✅ Tc acquired successfully")
        print(f"   aud : {claims.get('aud')}")
        print(f"   sub : {claims.get('sub')}")
        print(f"   upn : {claims.get('upn', claims.get('preferred_username', 'N/A'))}")
        print(f"   scp : {claims.get('scp', 'N/A')}")

    return tc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Invoke Hosted Agent with Interactive OBO flow (MSAL + metadata.user_tc).",
    )
    parser.add_argument(
        "message",
        nargs="?",
        default="Call Identity Echo API using the Interactive OBO flow.",
        help="User message to send to the agent",
    )
    parser.add_argument(
        "--no-force-tool",
        action="store_true",
        help="Don't set force_tool — let the agent choose which tool to call",
    )
    args = parser.parse_args()

    # Load environment
    print("Loading .env ...")
    _load_env()

    tenant_id = _require_env("ENTRA_TENANT_ID")
    spa_client_id = _require_env("ENTRA_SPA_APP_CLIENT_ID")
    blueprint_client_id = _require_env("ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID")
    project_endpoint = _require_env("FOUNDRY_PROJECT_ENDPOINT")

    # Read agent name from agent.yaml
    if not _AGENT_YAML.is_file():
        print(f"ERROR: {_AGENT_YAML} not found", file=sys.stderr)
        sys.exit(1)
    agent_name = yaml.safe_load(_AGENT_YAML.read_text())["name"]

    # Step 1: Acquire Tc via MSAL interactive login
    tc = _acquire_tc(spa_client_id, tenant_id, blueprint_client_id)

    # Step 2: Connect to Foundry
    services_endpoint = _to_services_endpoint(project_endpoint)
    project = AIProjectClient(
        endpoint=services_endpoint,
        credential=DefaultAzureCredential(),
        allow_preview=True,
    )
    openai_client = project.get_openai_client()

    agent = project.agents.get(agent_name=agent_name)
    print(f"\n🤖 Agent: {agent.name}")

    # Step 3: Build request
    # metadata の各値は 512 文字制限があるため、Tc を 500 文字ごとに分割して格納する。
    # ToolDispatchAgent 側で user_tc_0, user_tc_1, ... を結合して復元する。
    # developer message 方式は adapter が messages=None で run() を呼ぶため不可。
    input_payload = [
        # {"role": "developer", "content": f"__USER_TC__:{tc}"},  # ← adapter が messages に渡さない
        {"role": "user", "content": args.message},
    ]
    metadata = {}
    if not args.no_force_tool:
        metadata["force_tool"] = "call_resource_api_interactive_obo"

    # Split Tc into 500-char chunks
    _CHUNK_SIZE = 500
    for i in range(0, len(tc), _CHUNK_SIZE):
        metadata[f"user_tc_{i // _CHUNK_SIZE}"] = tc[i : i + _CHUNK_SIZE]

    extra = {
        "agent_reference": {
            "name": agent.name,
            "type": "agent_reference",
        },
        "metadata": metadata,
    }

    print("\n📤 Sending request...")
    print(f"   message    : {args.message}")
    print(f"   force_tool : {metadata.get('force_tool', '(auto)')}")
    print(f"   user_tc    : {tc[:20]}...{tc[-10:]}")

    # Step 4: Invoke agent
    response = openai_client.responses.create(
        input=input_payload,
        store=False,
        extra_body=extra,
        timeout=180,
    )

    # Step 5: Display results
    print(f"\n{'=' * 60}")
    print("  Response")
    print(f"{'=' * 60}")

    for item in response.output:
        if item.type == "function_call_output":
            raw = item.output
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    parsed = json.loads(parsed[0])
                elif isinstance(parsed, str):
                    parsed = json.loads(parsed)
                print(json.dumps(parsed, indent=2, ensure_ascii=False))
            except (json.JSONDecodeError, IndexError):
                print(raw)
        elif item.type == "message":
            for c in item.content:
                if hasattr(c, "text"):
                    print(f"\n[agent] {c.text}")


if __name__ == "__main__":
    main()

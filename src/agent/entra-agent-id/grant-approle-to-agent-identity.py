#!/usr/bin/env python3
#
# grant-approle-to-agent-identity.py
#
# Grants the CallerIdentity.Read.All Application Permission (App Role)
# to the Agent Identity's Service Principal, allowing the Autonomous App
# flow to access the Identity Echo API with app-only permissions.
#
# Idempotent: skips if the assignment already exists.
#
# Prerequisites:
#   - src/.env populated (run sync-infra-env.py first)
#   - Required env vars:
#       ENTRA_TENANT_ID
#       ENTRA_RESOURCE_API_CLIENT_ID   (Identity Echo API の Application ID)
#       ENTRA_AGENT_IDENTITY_CLIENT_ID (Agent Identity の Service Principal OID)
#       GRAPH_API_OPS_CLIENT_ID        (Graph API 操作用 Public Client の App ID)
#
# Usage:
#   python src/agent/entra-agent-id/grant-approle-to-agent-identity.py           # grant (default)
#   python src/agent/entra-agent-id/grant-approle-to-agent-identity.py --delete  # revoke

import argparse
import json
import os
import sys
from pathlib import Path

import msal
import requests
from dotenv import load_dotenv

# .env is at src/.env (three levels up: entra-agent-id → agent → src)
dotenv_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
APP_ROLE_VALUE = "CallerIdentity.Read.All"


def get_graph_api_token() -> str:
    """Acquire a Graph API token via MSAL interactive flow."""
    client_id = os.environ["GRAPH_API_OPS_CLIENT_ID"]
    tenant_id = os.environ["ENTRA_TENANT_ID"]
    scopes = [
        "https://graph.microsoft.com/AppRoleAssignment.ReadWrite.All",
        "https://graph.microsoft.com/Application.Read.All",
        "User.Read",
    ]
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.PublicClientApplication(client_id, authority=authority)
    print("Login with browser...")
    result = app.acquire_token_interactive(scopes=scopes)
    if "access_token" not in result:
        print("Failed to acquire token:")
        print(json.dumps(result, indent=2))
        sys.exit(1)
    return result["access_token"]


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"ERROR: {name} is not set in .env", file=sys.stderr)
        sys.exit(1)
    return value


def find_sp_by_app_id(headers: dict, app_id: str) -> dict:
    """Look up a Service Principal by Application (Client) ID."""
    resp = requests.get(
        f"{GRAPH_BASE}/servicePrincipals",
        params={
            "$filter": f"appId eq '{app_id}'",
            "$select": "id,appId,displayName,appRoles",
        },
        headers=headers,
    )
    resp.raise_for_status()
    values = resp.json().get("value", [])
    if not values:
        print(f"ERROR: No Service Principal found for appId '{app_id}'", file=sys.stderr)
        sys.exit(1)
    return values[0]


def find_agent_identity_sp(headers: dict, agent_identity_id: str) -> dict:
    """Look up the Agent Identity's Service Principal.

    The ENTRA_AGENT_IDENTITY_CLIENT_ID from Foundry's agentIdentityId is
    the Service Principal Object ID. If direct lookup fails, fall back to
    searching by appId.
    """
    # Try direct SP Object ID lookup
    resp = requests.get(
        f"{GRAPH_BASE}/servicePrincipals/{agent_identity_id}",
        params={"$select": "id,appId,displayName"},
        headers=headers,
    )
    if resp.status_code == 200:
        return resp.json()

    # Fall back: try as Application (Client) ID
    resp2 = requests.get(
        f"{GRAPH_BASE}/servicePrincipals",
        params={
            "$filter": f"appId eq '{agent_identity_id}'",
            "$select": "id,appId,displayName",
        },
        headers=headers,
    )
    resp2.raise_for_status()
    values = resp2.json().get("value", [])
    if values:
        return values[0]

    print(
        f"ERROR: Agent Identity Service Principal not found for id '{agent_identity_id}'.\n"
        f"  Tried: direct SP lookup and appId filter.",
        file=sys.stderr,
    )
    sys.exit(1)


def find_existing_assignment(
    headers: dict, resource_sp_id: str, agent_sp_id: str, app_role_id: str
) -> dict | None:
    """Check if the app role assignment already exists."""
    resp = requests.get(
        f"{GRAPH_BASE}/servicePrincipals/{resource_sp_id}/appRoleAssignedTo",
        headers=headers,
    )
    resp.raise_for_status()
    for assignment in resp.json().get("value", []):
        if (
            assignment.get("principalId") == agent_sp_id
            and assignment.get("appRoleId") == app_role_id
        ):
            return assignment
    return None


def grant(args: argparse.Namespace) -> None:
    resource_api_client_id = require_env("ENTRA_RESOURCE_API_CLIENT_ID")
    agent_identity_id = require_env("ENTRA_AGENT_IDENTITY_CLIENT_ID")

    token = get_graph_api_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # 1. Find Resource API (Identity Echo API) Service Principal
    print(f"\n--- Looking up Identity Echo API SP (appId: {resource_api_client_id}) ---")
    resource_sp = find_sp_by_app_id(headers, resource_api_client_id)
    resource_sp_id = resource_sp["id"]
    print(f"  Found: {resource_sp.get('displayName', 'N/A')} (id: {resource_sp_id})")

    # Find the CallerIdentity.Read.All App Role
    app_role_id = None
    for role in resource_sp.get("appRoles", []):
        if role["value"] == APP_ROLE_VALUE:
            app_role_id = role["id"]
            break
    if not app_role_id:
        print(
            f"ERROR: App Role '{APP_ROLE_VALUE}' not found on {resource_sp.get('displayName')}",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"  App Role: {APP_ROLE_VALUE} (id: {app_role_id})")

    # 2. Find Agent Identity Service Principal
    print(f"\n--- Looking up Agent Identity SP (id: {agent_identity_id}) ---")
    agent_sp = find_agent_identity_sp(headers, agent_identity_id)
    agent_sp_id = agent_sp["id"]
    print(f"  Found: {agent_sp.get('displayName', 'N/A')} (id: {agent_sp_id})")

    # 3. Check for existing assignment (idempotent)
    print("\n--- Checking existing assignments ---")
    existing = find_existing_assignment(headers, resource_sp_id, agent_sp_id, app_role_id)
    if existing:
        print(f"  Assignment already exists (id: {existing['id']}). Skipping.")
        return

    # 4. Create App Role Assignment
    print("\n--- Creating App Role Assignment ---")
    payload = {
        "principalId": agent_sp_id,
        "resourceId": resource_sp_id,
        "appRoleId": app_role_id,
    }
    resp = requests.post(
        f"{GRAPH_BASE}/servicePrincipals/{resource_sp_id}/appRoleAssignedTo",
        headers=headers,
        json=payload,
    )
    if not resp.ok:
        print(f"ERROR: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)

    created = resp.json()
    print(f"  Created (id: {created['id']})")
    print(f"  Principal: {agent_sp.get('displayName')} ({agent_sp_id})")
    print(f"  Resource:  {resource_sp.get('displayName')} ({resource_sp_id})")
    print(f"  App Role:  {APP_ROLE_VALUE} ({app_role_id})")
    print("\nDone! Agent Identity can now access Identity Echo API with app-only permissions.")


def revoke(args: argparse.Namespace) -> None:
    resource_api_client_id = require_env("ENTRA_RESOURCE_API_CLIENT_ID")
    agent_identity_id = require_env("ENTRA_AGENT_IDENTITY_CLIENT_ID")

    token = get_graph_api_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Look up both SPs
    resource_sp = find_sp_by_app_id(headers, resource_api_client_id)
    resource_sp_id = resource_sp["id"]

    agent_sp = find_agent_identity_sp(headers, agent_identity_id)
    agent_sp_id = agent_sp["id"]

    # Find the App Role ID
    app_role_id = None
    for role in resource_sp.get("appRoles", []):
        if role["value"] == APP_ROLE_VALUE:
            app_role_id = role["id"]
            break
    if not app_role_id:
        print(f"App Role '{APP_ROLE_VALUE}' not found. Nothing to revoke.")
        return

    # Find existing assignment
    existing = find_existing_assignment(headers, resource_sp_id, agent_sp_id, app_role_id)
    if not existing:
        print("No existing assignment found. Nothing to revoke.")
        return

    # Delete the assignment
    assignment_id = existing["id"]
    resp = requests.delete(
        f"{GRAPH_BASE}/servicePrincipals/{resource_sp_id}/appRoleAssignedTo/{assignment_id}",
        headers=headers,
    )
    if not resp.ok:
        print(f"ERROR: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)

    print(f"Revoked App Role Assignment (id: {assignment_id})")
    print(f"  Principal: {agent_sp.get('displayName')} ({agent_sp_id})")
    print(f"  App Role:  {APP_ROLE_VALUE}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Grant/revoke CallerIdentity.Read.All App Role to Agent Identity"
    )
    sub = parser.add_subparsers(dest="command")
    sub.default = "grant"

    sub.add_parser("grant", help="Grant App Role (default, idempotent)")
    sub.add_parser("revoke", help="Revoke App Role")

    args = parser.parse_args()
    cmd = args.command or "grant"

    if cmd == "grant":
        grant(args)
    elif cmd == "revoke":
        revoke(args)


if __name__ == "__main__":
    main()

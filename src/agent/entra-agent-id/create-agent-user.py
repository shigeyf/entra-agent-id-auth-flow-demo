#!/usr/bin/env python3
#
# create-agent-user.py
#
# Creates an Agent User (microsoft.graph.agentUser) for the Autonomous User flow.
# Agent User ≠ regular Entra ID user; it's a special Graph beta type that can
# only be impersonated by a specific Agent Identity.
#
# The creation/deletion of Agent Users requires a token with the
# AgentIdUser.ReadWrite.IdentityParentedBy permission.
#
# Reference:
#   https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/autonomous-agent-request-agent-user-tokens
#
# Idempotent: skips creation if an agent user with the same displayName already exists.
#
# Prerequisites:
#   - src/.env populated (run sync-infra-env.py first)
#   - Required env vars:
#       ENTRA_TENANT_ID
#       ENTRA_AGENT_IDENTITY_CLIENT_ID             (Agent Identity SP OID → identityParentId)
#       ENTRA_AGENT_ID_USER_DISPLAY_NAME           (e.g. "Foundry Agent User")
#       ENTRA_AGENT_ID_USER_UPN                    (full UPN, e.g. "foundry-agent-user@contoso.com")
#       GRAPH_API_OPS_CLIENT_ID                    (Graph API 操作用 Public Client の App ID)
#
# Usage:
#   python src/agent/entra-agent-id/create-agent-user.py            # create (default)
#   python src/agent/entra-agent-id/create-agent-user.py --delete   # delete

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

GRAPH_BASE = "https://graph.microsoft.com/beta"


def get_graph_api_token() -> str:
    """Acquire a Graph API token via MSAL interactive flow."""
    client_id = os.environ["GRAPH_API_OPS_CLIENT_ID"]
    tenant_id = os.environ["ENTRA_TENANT_ID"]
    scopes = [
        "https://graph.microsoft.com/AgentIdentityBlueprint.Create",
        "https://graph.microsoft.com/AgentIdentityBlueprint.AddRemoveCreds.All",
        "https://graph.microsoft.com/AgentIdentityBlueprint.ReadWrite.All",
        "https://graph.microsoft.com/AgentIdentityBlueprintPrincipal.Create",
        "https://graph.microsoft.com/AgentIdentity.ReadWrite.All",
        "https://graph.microsoft.com/DelegatedPermissionGrant.ReadWrite.All",
        "https://graph.microsoft.com/User.ReadWrite.All",
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


def find_agent_user(headers: dict, display_name: str) -> dict | None:
    """Find an existing agent user by displayName. Returns the user dict or None."""
    resp = requests.get(
        f"{GRAPH_BASE}/users",
        params={
            "$filter": f"displayName eq '{display_name}'",
            "$select": "id,displayName,userPrincipalName,accountEnabled",
        },
        headers=headers,
    )
    resp.raise_for_status()
    values = resp.json().get("value", [])
    return values[0] if values else None


def create_user(args: argparse.Namespace) -> None:
    display_name = require_env("ENTRA_AGENT_ID_USER_DISPLAY_NAME")
    upn = require_env("ENTRA_AGENT_ID_USER_UPN")  # e.g. "foundry-agent-user@contoso.com"
    agent_identity_sp_id = require_env("ENTRA_AGENT_IDENTITY_CLIENT_ID")
    mail_nickname = upn.split("@")[0]

    token = get_graph_api_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "OData-Version": "4.0",
    }

    # Check if agent user already exists
    existing = find_agent_user(headers, display_name)
    if existing:
        print(f"Agent User '{display_name}' already exists (id: {existing['id']}). Skipping.")
        print(json.dumps(existing, indent=2))
        return

    body = {
        "@odata.type": "microsoft.graph.agentUser",
        "displayName": display_name,
        "userPrincipalName": upn,
        "identityParentId": agent_identity_sp_id,
        "mailNickname": mail_nickname,
        "accountEnabled": True,
    }

    print(f"Creating Agent User: {upn} ...")
    print(f"  identityParentId: {agent_identity_sp_id}")
    resp = requests.post(f"{GRAPH_BASE}/users", headers=headers, json=body)

    if resp.status_code == 201:
        user = resp.json()
        print("Created Agent User successfully.")
        print(f"  id:                 {user.get('id')}")
        print(f"  displayName:        {user.get('displayName')}")
        print(f"  userPrincipalName:  {user.get('userPrincipalName')}")
    else:
        print(f"ERROR: Failed to create Agent User (HTTP {resp.status_code})")
        print(json.dumps(resp.json(), indent=2))
        sys.exit(1)


def delete_user(args: argparse.Namespace) -> None:
    display_name = require_env("ENTRA_AGENT_ID_USER_DISPLAY_NAME")

    token = get_graph_api_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "OData-Version": "4.0",
    }

    existing = find_agent_user(headers, display_name)
    if not existing:
        print(f"Agent User '{display_name}' does not exist. Nothing to delete.")
        return

    user_id = existing["id"]

    print(f"Deleting Agent User: {display_name} (id: {user_id}) ...")
    resp = requests.delete(f"{GRAPH_BASE}/users/{user_id}", headers=headers)

    if resp.status_code == 204:
        print("Deleted successfully.")
    else:
        print(f"ERROR: Failed to delete Agent User (HTTP {resp.status_code})")
        print(json.dumps(resp.json(), indent=2))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create or delete an Agent User (microsoft.graph.agentUser) "
        "for the Autonomous Agent User flow."
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete the Agent User instead of creating it.",
    )
    args = parser.parse_args()

    if args.delete:
        delete_user(args)
    else:
        create_user(args)

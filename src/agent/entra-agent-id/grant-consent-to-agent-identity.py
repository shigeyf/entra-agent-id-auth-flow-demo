#!/usr/bin/env python3
#
# grant-consent-to-agent-identity.py
#
# Grants an OAuth2 permission (delegated consent) so the Agent Identity can
# act on behalf of the Agent User when accessing a resource API.
#
# This is required BEFORE the Autonomous User flow's Step 3 (user_fic grant)
# can succeed.  Without it, Entra ID returns AADSTS65001 (invalid_grant).
#
# Reference:
#   https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/autonomous-agent-request-agent-user-tokens?tabs=rest#grant-consent-to-agent-identity
#
# Idempotent: skips if a matching grant already exists.
#
# Prerequisites:
#   - src/.env populated (run sync-infra-env.py first)
#   - Required env vars:
#       ENTRA_TENANT_ID
#       ENTRA_AGENT_IDENTITY_CLIENT_ID   (Agent Identity SP OID)
#       ENTRA_AGENT_ID_USER_DISPLAY_NAME (Agent User displayName, used to look up OID)
#       ENTRA_RESOURCE_API_CLIENT_ID     (Resource API Application (Client) ID)
#       ENTRA_RESOURCE_API_SCOPE         (e.g. "api://.../.../CallerIdentity.Read")
#       GRAPH_API_OPS_CLIENT_ID          (Graph API 操作用 Public Client の App ID)
#
# Usage:
#   python src/agent/entra-agent-id/grant-consent-to-agent-identity.py            # grant
#   python src/agent/entra-agent-id/grant-consent-to-agent-identity.py --delete   # revoke

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
GRAPH_BETA = "https://graph.microsoft.com/beta"


def get_graph_api_token() -> str:
    """Acquire a Graph API token via MSAL interactive flow."""
    client_id = os.environ["GRAPH_API_OPS_CLIENT_ID"]
    tenant_id = os.environ["ENTRA_TENANT_ID"]
    scopes = [
        "https://graph.microsoft.com/DelegatedPermissionGrant.ReadWrite.All",
        "https://graph.microsoft.com/Application.Read.All",
        "https://graph.microsoft.com/User.Read.All",
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
            "$select": "id,appId,displayName",
        },
        headers=headers,
    )
    resp.raise_for_status()
    values = resp.json().get("value", [])
    if not values:
        print(f"ERROR: No Service Principal found for appId '{app_id}'", file=sys.stderr)
        sys.exit(1)
    return values[0]


def find_agent_user(headers: dict, display_name: str) -> dict:
    """Find the Agent User by displayName. Returns the user dict or exits."""
    resp = requests.get(
        f"{GRAPH_BETA}/users",
        params={
            "$filter": f"displayName eq '{display_name}'",
            "$select": "id,displayName,userPrincipalName",
        },
        headers={**headers, "OData-Version": "4.0"},
    )
    resp.raise_for_status()
    values = resp.json().get("value", [])
    if not values:
        print(f"ERROR: Agent User '{display_name}' not found", file=sys.stderr)
        sys.exit(1)
    return values[0]


def extract_scope_name(full_scope: str) -> str:
    """Extract the permission name from a full scope URI.

    e.g. "api://52d603ac-.../CallerIdentity.Read" → "CallerIdentity.Read"
    """
    return full_scope.rsplit("/", 1)[-1]


def find_existing_grant(
    headers: dict, client_id: str, principal_id: str, resource_id: str
) -> dict | None:
    """Find an existing oauth2PermissionGrant matching client+principal+resource."""
    resp = requests.get(
        f"{GRAPH_BASE}/oauth2PermissionGrants",
        params={
            "$filter": (
                f"clientId eq '{client_id}' "
                f"and principalId eq '{principal_id}' "
                f"and resourceId eq '{resource_id}'"
            ),
        },
        headers=headers,
    )
    resp.raise_for_status()
    values = resp.json().get("value", [])
    return values[0] if values else None


def grant_consent(args: argparse.Namespace) -> None:
    agent_identity_id = require_env("ENTRA_AGENT_IDENTITY_CLIENT_ID")
    agent_user_display_name = require_env("ENTRA_AGENT_ID_USER_DISPLAY_NAME")
    resource_api_client_id = require_env("ENTRA_RESOURCE_API_CLIENT_ID")
    scope_name = extract_scope_name(args.scope)

    token = get_graph_api_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Look up Agent User OID
    agent_user = find_agent_user(headers, agent_user_display_name)
    agent_user_id = agent_user["id"]
    print(f"Agent User: {agent_user['displayName']} (id: {agent_user_id})")

    # Look up Resource API Service Principal
    resource_sp = find_sp_by_app_id(headers, resource_api_client_id)
    resource_sp_id = resource_sp["id"]
    print(f"Resource API SP: {resource_sp['displayName']} (id: {resource_sp_id})")

    print(f"Agent Identity SP: {agent_identity_id}")
    print(f"Scope: {scope_name}")

    # Check if grant already exists
    existing = find_existing_grant(headers, agent_identity_id, agent_user_id, resource_sp_id)
    if existing:
        existing_scopes = existing.get("scope", "")
        if scope_name in existing_scopes.split():
            print(
                f"Consent grant already exists (id: {existing['id']}, "
                f"scope: '{existing_scopes}'). Skipping."
            )
            return
        # Grant exists but scope needs updating — append
        new_scope = f"{existing_scopes} {scope_name}".strip()
        print(
            f"Updating existing grant (id: {existing['id']}) "
            f"scope: '{existing_scopes}' → '{new_scope}'"
        )
        resp = requests.patch(
            f"{GRAPH_BASE}/oauth2PermissionGrants/{existing['id']}",
            headers=headers,
            json={"scope": new_scope},
        )
        if resp.status_code == 204:
            print("Updated successfully.")
        else:
            print(f"ERROR: Failed to update grant (HTTP {resp.status_code})")
            print(json.dumps(resp.json(), indent=2))
            sys.exit(1)
        return

    # Create new grant
    body = {
        "clientId": agent_identity_id,
        "consentType": "Principal",
        "principalId": agent_user_id,
        "resourceId": resource_sp_id,
        "scope": scope_name,
    }

    print("Creating oauth2PermissionGrant ...")
    resp = requests.post(f"{GRAPH_BASE}/oauth2PermissionGrants", headers=headers, json=body)

    if resp.status_code in (200, 201):
        grant = resp.json()
        print("Consent granted successfully.")
        print(f"  id:          {grant.get('id')}")
        print(f"  clientId:    {grant.get('clientId')}")
        print(f"  principalId: {grant.get('principalId')}")
        print(f"  resourceId:  {grant.get('resourceId')}")
        print(f"  scope:       {grant.get('scope')}")
    else:
        print(f"ERROR: Failed to create consent grant (HTTP {resp.status_code})")
        print(json.dumps(resp.json(), indent=2))
        sys.exit(1)


def revoke_consent(args: argparse.Namespace) -> None:
    agent_identity_id = require_env("ENTRA_AGENT_IDENTITY_CLIENT_ID")
    agent_user_display_name = require_env("ENTRA_AGENT_ID_USER_DISPLAY_NAME")
    resource_api_client_id = require_env("ENTRA_RESOURCE_API_CLIENT_ID")

    token = get_graph_api_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    agent_user = find_agent_user(headers, agent_user_display_name)
    agent_user_id = agent_user["id"]

    resource_sp = find_sp_by_app_id(headers, resource_api_client_id)
    resource_sp_id = resource_sp["id"]

    existing = find_existing_grant(headers, agent_identity_id, agent_user_id, resource_sp_id)
    if not existing:
        print("No consent grant found. Nothing to revoke.")
        return

    grant_id = existing["id"]
    print(f"Revoking consent grant (id: {grant_id}, scope: '{existing.get('scope')}') ...")
    resp = requests.delete(f"{GRAPH_BASE}/oauth2PermissionGrants/{grant_id}", headers=headers)

    if resp.status_code == 204:
        print("Revoked successfully.")
    else:
        print(f"ERROR: Failed to revoke grant (HTTP {resp.status_code})")
        print(json.dumps(resp.json(), indent=2))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Grant or revoke delegated consent (oauth2PermissionGrant) "
        "for the Agent Identity to act on behalf of the Agent User."
    )
    parser.add_argument(
        "--scope",
        type=str,
        default=os.environ.get("ENTRA_RESOURCE_API_SCOPE", ""),
        help="Scope to grant (e.g. 'CallerIdentity.Read' or full URI). "
        "Defaults to ENTRA_RESOURCE_API_SCOPE env var.",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Revoke the consent grant instead of creating it.",
    )
    args = parser.parse_args()

    if not args.delete and not args.scope:
        print(
            "ERROR: --scope is required (or set ENTRA_RESOURCE_API_SCOPE in .env)", file=sys.stderr
        )
        sys.exit(1)

    if args.delete:
        revoke_consent(args)
    else:
        grant_consent(args)

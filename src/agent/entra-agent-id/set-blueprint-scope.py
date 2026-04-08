#!/usr/bin/env python3
#
# set-blueprint-scope.py
#
# Configures the Agent Identity Blueprint for Interactive OBO flow by:
#   1. Setting the App ID URI (identifierUris)
#   2. Exposing the `access_agent` OAuth2 permission scope
#
# This is the E1 step from the Interactive OBO implementation plan.
# The Blueprint must expose a scope so that the SPA client can obtain
# a Tc token (aud = Blueprint) for OBO exchange.
#
# Idempotent: skips if identifierUris and access_agent scope already exist.
#
# Prerequisites:
#   - src/.env populated (run sync-infra-env.py first)
#   - Required env vars:
#       ENTRA_TENANT_ID
#       ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID
#       GRAPH_API_OPS_CLIENT_ID
#
# Reference:
#   https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/create-blueprint?tabs=microsoft-graph-api#configure-identifier-uri-and-scope
#
# Usage:
#   python src/agent/entra-agent-id/set-blueprint-scope.py             # create (default)
#   python src/agent/entra-agent-id/set-blueprint-scope.py --delete    # remove scope + URI

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

import msal
import requests
from dotenv import load_dotenv

# .env is at src/.env (three levels up: entra-agent-id → agent → src)
dotenv_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path)

GRAPH_BETA = "https://graph.microsoft.com/beta"
SCOPE_NAME = "access_agent"


def get_graph_api_token() -> str:
    """Acquire a Graph API token via MSAL interactive flow."""
    client_id = os.environ["GRAPH_API_OPS_CLIENT_ID"]
    tenant_id = os.environ["ENTRA_TENANT_ID"]
    scopes = [
        "https://graph.microsoft.com/AgentIdentityBlueprint.ReadWrite.All",
        "https://graph.microsoft.com/Application.ReadWrite.All",
        "User.Read",
    ]
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.PublicClientApplication(client_id, authority=authority)
    print("🔑 Login with browser...")
    result = app.acquire_token_interactive(scopes=scopes)
    if "access_token" not in result:
        print("Token acquisition failed:")
        print(json.dumps(result, indent=2))
        sys.exit(1)
    return result["access_token"]


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"ERROR: {name} is not set in .env", file=sys.stderr)
        sys.exit(1)
    return value


def get_blueprint_app(headers: dict, blueprint_id: str) -> dict:
    """Fetch the Blueprint application object."""
    url = f"{GRAPH_BETA}/applications/{blueprint_id}"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"❌ Failed to fetch Blueprint application: {resp.status_code}")
        print(resp.text)
        sys.exit(1)
    return resp.json()


def patch_blueprint(headers: dict, object_id: str, body: dict) -> None:
    """PATCH the Blueprint application object."""
    url = f"{GRAPH_BETA}/applications/{object_id}"
    resp = requests.patch(url, headers=headers, json=body)
    if resp.status_code not in (200, 204):
        print(f"❌ PATCH failed: {resp.status_code}")
        print(resp.text)
        sys.exit(1)


def create_scope(args: argparse.Namespace) -> None:
    """Set identifierUris and expose access_agent scope on the Blueprint."""
    blueprint_id = require_env("ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID")
    token = get_graph_api_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "OData-Version": "4.0",
    }

    # Fetch current state
    app = get_blueprint_app(headers, blueprint_id)
    app_id = app["appId"]
    object_id = app["id"]
    current_uris = app.get("identifierUris", [])
    current_scopes = app.get("api", {}).get("oauth2PermissionScopes", [])

    print(f"\n📋 Blueprint: {app.get('displayName')}")
    print(f"   App ID (Client ID) : {app_id}")
    print(f"   Object ID          : {object_id}")
    print(f"   Current URIs       : {current_uris}")
    print(f"   Current Scopes     : {[s.get('value') for s in current_scopes]}")

    expected_uri = f"api://{app_id}"

    # Check identifierUris
    uri_needs_update = expected_uri not in current_uris
    if not uri_needs_update:
        print(f"\n✅ identifierUris already contains '{expected_uri}'. Skipping.")

    # Check access_agent scope
    existing_scope = next((s for s in current_scopes if s.get("value") == SCOPE_NAME), None)
    scope_needs_update = existing_scope is None
    if not scope_needs_update:
        print(f"✅ '{SCOPE_NAME}' scope already exists (id: {existing_scope['id']}). Skipping.")

    if not uri_needs_update and not scope_needs_update:
        print("\n✅ Blueprint is already configured for Interactive OBO. Nothing to do.")
        return

    # Build PATCH body
    # Note: We set both identifierUris and scope in a single PATCH when possible.
    # For oauth2PermissionScopes, we must include ALL existing scopes plus the new one.
    body: dict = {}

    if uri_needs_update:
        new_uris = list(current_uris) + [expected_uri]
        body["identifierUris"] = new_uris
        print(f"\n🔧 Setting identifierUris: {new_uris}")

    if scope_needs_update:
        new_scope = {
            "id": str(uuid.uuid4()),
            "adminConsentDescription": (
                "Allow the application to access the agent on behalf of the signed-in user."
            ),
            "adminConsentDisplayName": "Access agent",
            "isEnabled": True,
            "type": "User",
            "userConsentDescription": ("Allow the application to access the agent on your behalf."),
            "userConsentDisplayName": "Access agent",
            "value": SCOPE_NAME,
        }
        all_scopes = list(current_scopes) + [new_scope]
        body["api"] = {"oauth2PermissionScopes": all_scopes}
        print(f"🔧 Adding '{SCOPE_NAME}' scope (id: {new_scope['id']})")

    # Apply
    patch_blueprint(headers, object_id, body)
    print("\n✅ Blueprint updated successfully.")

    # Verify
    updated_app = get_blueprint_app(headers, blueprint_id)
    print("\n📋 Verification:")
    print(f"   identifierUris : {updated_app.get('identifierUris', [])}")
    print(
        f"   Scopes         : "
        f"{[s.get('value') for s in updated_app.get('api', {}).get('oauth2PermissionScopes', [])]}"
    )


def delete_scope(args: argparse.Namespace) -> None:
    """Remove access_agent scope and identifierUris from the Blueprint.

    Entra ID requires a two-step process:
      1. Disable the scope (isEnabled = false) via PATCH
      2. Remove the scope (empty array) via PATCH
    """
    blueprint_id = require_env("ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID")
    token = get_graph_api_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "OData-Version": "4.0",
    }

    app = get_blueprint_app(headers, blueprint_id)
    app_id = app["appId"]
    object_id = app["id"]
    current_uris = app.get("identifierUris", [])
    current_scopes = app.get("api", {}).get("oauth2PermissionScopes", [])

    print(f"\n📋 Blueprint: {app.get('displayName')}")
    print(f"   Current URIs   : {current_uris}")
    print(f"   Current Scopes : {[s.get('value') for s in current_scopes]}")

    # Find the access_agent scope
    target_scope = next((s for s in current_scopes if s.get("value") == SCOPE_NAME), None)

    if target_scope:
        # Step 1: Disable the scope
        print(f"\n🔧 Step 1: Disabling '{SCOPE_NAME}' scope...")
        disabled_scopes = []
        for s in current_scopes:
            scope_copy = dict(s)
            if scope_copy.get("value") == SCOPE_NAME:
                scope_copy["isEnabled"] = False
            disabled_scopes.append(scope_copy)
        patch_blueprint(headers, object_id, {"api": {"oauth2PermissionScopes": disabled_scopes}})
        print("   Done.")

        # Step 2: Remove the scope
        print(f"🔧 Step 2: Removing '{SCOPE_NAME}' scope...")
        remaining_scopes = [s for s in current_scopes if s.get("value") != SCOPE_NAME]
        patch_blueprint(headers, object_id, {"api": {"oauth2PermissionScopes": remaining_scopes}})
        print("   Done.")
    else:
        print(f"\nℹ️  '{SCOPE_NAME}' scope not found. Skipping scope removal.")

    # Remove identifierUris
    expected_uri = f"api://{app_id}"
    if expected_uri in current_uris:
        print(f"🔧 Removing '{expected_uri}' from identifierUris...")
        new_uris = [u for u in current_uris if u != expected_uri]
        patch_blueprint(headers, object_id, {"identifierUris": new_uris})
        print("   Done.")
    else:
        print(f"ℹ️  '{expected_uri}' not in identifierUris. Skipping.")

    print("\n✅ Cleanup complete.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Configure Blueprint App ID URI and access_agent scope "
            "for Interactive OBO flow (E1 step)."
        ),
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Remove the access_agent scope and App ID URI from the Blueprint.",
    )
    args = parser.parse_args()

    if args.delete:
        delete_scope(args)
    else:
        create_scope(args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
#
# inspect-blueprint.py
#
# Inspects the Foundry-provisioned Agent Identity Blueprint, displaying
# its core properties, identifier URIs, exposed scopes, federated identity
# credentials, and service principal details.
#
# Useful for verifying OBO prerequisites:
#   - identifierUris (App ID URI) is set
#   - oauth2PermissionScopes (e.g. access_agent) is exposed
#   - FIC (Federated Identity Credential) is configured
#   - Service Principal exists
#
# Prerequisites:
#   - src/.env populated (run sync-infra-env.py first)
#   - Required env vars:
#       ENTRA_TENANT_ID
#       ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID
#       GRAPH_API_OPS_CLIENT_ID
#
# Reference:
#   https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/create-blueprint?tabs=microsoft-graph-api
#
# Usage:
#   python src/agent/entra-agent-id/inspect-blueprint.py

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

GRAPH_BETA = "https://graph.microsoft.com/beta"
GRAPH_V1 = "https://graph.microsoft.com/v1.0"


def get_graph_api_token() -> str:
    """Acquire a Graph API token via MSAL interactive flow."""
    client_id = os.environ["GRAPH_API_OPS_CLIENT_ID"]
    tenant_id = os.environ["ENTRA_TENANT_ID"]
    scopes = [
        "https://graph.microsoft.com/Application.Read.All",
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


def pp(label: str, data: object) -> None:
    """Pretty-print a section with a label."""
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    print(json.dumps(data, indent=2, ensure_ascii=False))


def main() -> None:
    blueprint_id = require_env("ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID")
    token = get_graph_api_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "OData-Version": "4.0",
    }

    # ── 1. Application object (Blueprint) ──────────────────────
    print(f"\n🔍 Inspecting Blueprint: {blueprint_id}")
    app_url = f"{GRAPH_BETA}/applications/{blueprint_id}"
    resp = requests.get(app_url, headers=headers)
    if resp.status_code != 200:
        print(f"❌ Failed to fetch Blueprint application: {resp.status_code}")
        print(resp.text)
        sys.exit(1)

    app = resp.json()
    app_object_id = app.get("id")

    pp(
        "1. Blueprint Application (core)",
        {
            "id (object ID)": app.get("id"),
            "appId (client ID)": app.get("appId"),
            "displayName": app.get("displayName"),
            "signInAudience": app.get("signInAudience"),
            "identifierUris": app.get("identifierUris", []),
            "accessTokenAcceptedVersion": app.get("api", {}).get("requestedAccessTokenVersion"),
        },
    )

    # ── 2. Exposed scopes (oauth2PermissionScopes) ─────────────
    scopes = app.get("api", {}).get("oauth2PermissionScopes", [])
    pp("2. Exposed Scopes (oauth2PermissionScopes)", scopes)

    if not scopes:
        print(
            "\n⚠️  WARNING: No scopes exposed. Interactive OBO flow requires 'access_agent' scope."
        )
        print(
            "   Run 'Configure identifier URI and scope' step from create-agent-id-blueprint.http"
        )
    else:
        scope_values = [s.get("value") for s in scopes]
        if "access_agent" in scope_values:
            print("\n✅ 'access_agent' scope is exposed.")
        else:
            print(f"\n⚠️  'access_agent' scope not found. Exposed: {scope_values}")

    if not app.get("identifierUris"):
        print("⚠️  WARNING: identifierUris is empty. App ID URI must be set for OBO.")
    else:
        print(f"✅ identifierUris: {app['identifierUris']}")

    # ── 3. Federated Identity Credentials ──────────────────────
    fic_url = f"{GRAPH_BETA}/applications/{app_object_id}/federatedIdentityCredentials"
    resp = requests.get(fic_url, headers=headers)
    fics = resp.json().get("value", []) if resp.status_code == 200 else []

    fic_summary = [
        {
            "id": f.get("id"),
            "name": f.get("name"),
            "issuer": f.get("issuer"),
            "subject": f.get("subject"),
            "audiences": f.get("audiences"),
        }
        for f in fics
    ]
    pp("3. Federated Identity Credentials", fic_summary)

    if not fics:
        print("\n⚠️  WARNING: No FIC configured. Blueprint needs a credential to exchange tokens.")
    else:
        print(f"\n✅ {len(fics)} FIC(s) configured.")

    # ── 4. Service Principal (Blueprint Principal) ─────────────
    sp_url = f"{GRAPH_V1}/servicePrincipals?$filter=appId eq '{app.get('appId')}'"
    resp = requests.get(sp_url, headers=headers)
    sps = resp.json().get("value", []) if resp.status_code == 200 else []

    if sps:
        sp = sps[0]
        pp(
            "4. Blueprint Service Principal",
            {
                "id (SP object ID)": sp.get("id"),
                "appId": sp.get("appId"),
                "displayName": sp.get("displayName"),
                "servicePrincipalType": sp.get("servicePrincipalType"),
                "appOwnerOrganizationId": sp.get("appOwnerOrganizationId"),
            },
        )
        print("\n✅ Service Principal exists.")
    else:
        pp("4. Blueprint Service Principal", [])
        print("\n⚠️  WARNING: No Service Principal found for Blueprint.")
        print(
            "   Run 'Create an agent blueprint principal' step from create-agent-id-blueprint.http"
        )

    # ── 5. OAuth2 Permission Grants (delegated consents) ───────
    grants = []
    if sps:
        sp_id = sps[0]["id"]
        grants_url = f"{GRAPH_V1}/oauth2PermissionGrants?$filter=resourceId eq '{sp_id}'"
        resp = requests.get(grants_url, headers=headers)
        grants = resp.json().get("value", []) if resp.status_code == 200 else []

        grants_summary = [
            {
                "id": g.get("id"),
                "clientId": g.get("clientId"),
                "consentType": g.get("consentType"),
                "scope": g.get("scope"),
            }
            for g in grants
        ]
        pp("5. OAuth2 Permission Grants (who has consent to this Blueprint)", grants_summary)
        if grants:
            print(f"\n✅ {len(grants)} consent grant(s) found.")
        else:
            print("\nℹ️  No delegated consent grants found yet (expected before E2 step).")

    # ── Summary ────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("  Summary")
    print(f"{'=' * 60}")
    print(f"  Blueprint App ID (Client ID) : {app.get('appId')}")
    print(f"  Blueprint Object ID          : {app.get('id')}")
    print(f"  Display Name                 : {app.get('displayName')}")
    print(f"  Identifier URIs              : {app.get('identifierUris', [])}")
    print(f"  Exposed Scopes               : {[s.get('value') for s in scopes]}")
    print(f"  FIC Count                    : {len(fics)}")
    print(f"  Service Principal            : {'✅ exists' if sps else '❌ missing'}")
    print()

    # ── Full JSON dump ─────────────────────────────────────────
    full_output = {
        "application": app,
        "federatedIdentityCredentials": fics,
        "servicePrincipal": sps[0] if sps else None,
        "oauth2PermissionGrants": grants,
    }

    pp("Full Blueprint Object (all data)", full_output)

    output_path = Path(__file__).resolve().parent / "inspect-blueprint-output.json"
    output_path.write_text(json.dumps(full_output, indent=2, ensure_ascii=False))
    print(f"\n📄 Full JSON output also saved to: {output_path}")
    print()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
#
# set-blueprint-fic.py
#
# Registers a Federated Identity Credential (FIC) on the Agent Identity Blueprint
# so that the Foundry Project's Managed Identity can exchange tokens via
# the client_credentials + client_assertion flow.
#
# Idempotent: skips creation if a FIC with the same name already exists.
#
# Prerequisites:
#   - ACCESS_TOKEN in .env (run get-token.py first)
#   - ENTRA_TENANT_ID, ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID, FOUNDRY_PROJECT_MSI
#     in .env (run sync-infra-env.py first)
#
# Reference:
#   https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/create-blueprint?tabs=microsoft-graph-api#configure-credentials-for-the-agent-identity-blueprint
#
# Usage:
#   python src/agent/entra-agent-id/set-blueprint-fic.py           # create (default)
#   python src/agent/entra-agent-id/set-blueprint-fic.py --delete   # delete

import argparse
import json
import os
import sys
from pathlib import Path

import msal
import requests
from dotenv import load_dotenv

# Always resolve .env relative to the project root (two levels up from this script)
dotenv_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path)

GRAPH_BASE = "https://graph.microsoft.com/beta"
FIC_NAME = "foundry-project-fmi-fic"


def get_graph_api_token() -> str:
    client_id = os.environ["GRAPH_API_OPS_CLIENT_ID"]
    tenant_id = os.environ["ENTRA_TENANT_ID"]
    scopes = [
        "https://graph.microsoft.com/AgentIdentityBlueprint.Create",
        "https://graph.microsoft.com/AgentIdentityBlueprint.AddRemoveCreds.All",
        "https://graph.microsoft.com/AgentIdentityBlueprint.ReadWrite.All",
        "https://graph.microsoft.com/AgentIdentityBlueprintPrincipal.Create",
        "https://graph.microsoft.com/AgentIdentity.ReadWrite.All",
        "https://graph.microsoft.com/AppRoleAssignment.ReadWrite.All",
        "https://graph.microsoft.com/DelegatedPermissionGrant.ReadWrite.All",
        "https://graph.microsoft.com/User.Read.All",
        "User.Read",
    ]
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.PublicClientApplication(client_id, authority=authority)
    print("Login with browser...")
    result = app.acquire_token_interactive(scopes=scopes)
    if "access_token" not in result:
        print("An error occurred when acquiring the token:")
        print(json.dumps(result, indent=2))
        sys.exit(1)
    return result["access_token"]


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"ERROR: {name} is not set in .env", file=sys.stderr)
        sys.exit(1)
    return value


def find_fic(fic_url: str, headers: dict, project_msi: str) -> dict | None:
    """Find an existing FIC by name and subject. Returns the FIC dict or None."""
    resp = requests.get(fic_url, headers=headers)
    resp.raise_for_status()
    for fic in resp.json().get("value", []):
        if fic.get("name") == FIC_NAME and fic.get("subject") == project_msi:
            return fic
    return None


def create_fic(args: argparse.Namespace) -> None:
    tenant_id = require_env("ENTRA_TENANT_ID")
    blueprint_id = require_env("ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID")
    project_msi = require_env("FOUNDRY_PROJECT_MSI")
    token = get_graph_api_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "OData-Version": "4.0",
    }

    fic_url = f"{GRAPH_BASE}/applications/{blueprint_id}/federatedIdentityCredentials"
    existing = find_fic(fic_url, headers, project_msi)
    if existing:
        print(f"FIC '{FIC_NAME}' already exists (id: {existing['id']}). Skipping.")
        return

    payload = {
        "name": FIC_NAME,
        "issuer": f"https://login.microsoftonline.com/{tenant_id}/v2.0",
        "subject": project_msi,
        "audiences": ["api://AzureADTokenExchange"],
    }
    resp = requests.post(fic_url, headers=headers, json=payload)
    resp.raise_for_status()

    created = resp.json()
    print(f"Created FIC '{FIC_NAME}' (id: {created['id']})")
    print(f"  issuer:  {payload['issuer']}")
    print(f"  subject: {project_msi}")


def delete_fic(args: argparse.Namespace) -> None:
    blueprint_id = require_env("ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID")
    project_msi = require_env("FOUNDRY_PROJECT_MSI")
    token = get_graph_api_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "OData-Version": "4.0",
    }

    fic_url = f"{GRAPH_BASE}/applications/{blueprint_id}/federatedIdentityCredentials"
    existing = find_fic(fic_url, headers, project_msi)
    if not existing:
        print(f"FIC '{FIC_NAME}' not found. Nothing to delete.")
        return

    fic_id = existing["id"]
    resp = requests.delete(f"{fic_url}/{fic_id}", headers=headers)
    resp.raise_for_status()
    print(f"Deleted FIC '{FIC_NAME}' (id: {fic_id})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage Federated Identity Credential on Agent Identity Blueprint"
    )
    sub = parser.add_subparsers(dest="command")
    sub.default = "create"

    sub.add_parser("create", help="Register FIC (default, idempotent)")
    sub.add_parser("delete", help="Delete FIC")

    args = parser.parse_args()
    command = args.command or "create"

    if command == "delete":
        delete_fic(args)
    else:
        create_fic(args)


if __name__ == "__main__":
    main()

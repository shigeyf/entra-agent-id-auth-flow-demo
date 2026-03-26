#!/usr/bin/env python3
# setup-app-registration.py
#
# Registers a public client app in Microsoft Entra ID and grants
# the delegated scopes required for Agent ID management.
#
# Prerequisites:
#   - az CLI installed and signed in via `az login`
#   - Signed in with a Global Administrator or Privileged Role Administrator account
#   - Microsoft Entra Agent ID preview enabled on the tenant
#
# Usage:
#   python setup-app-registration.py

import json
import subprocess
import sys
from pathlib import Path

from dotenv import set_key

DISPLAY_NAME = "Entra-Agent-ID-Manager"
GRAPH_APP_ID = "00000003-0000-0000-c000-000000000000"
SCOPES = [
    "AgentIdentity.DeleteRestore.All",
    "AgentIdentity.EnableDisable.All",
    "AgentIdentity.Read.All",
    "AgentIdentity.ReadWrite.All",
    "AgentIdentityBlueprint.AddRemoveCreds.All",
    "AgentIdentityBlueprint.Create",
    "AgentIdentityBlueprint.DeleteRestore.All",
    "AgentIdentityBlueprint.Read.All",
    "AgentIdentityBlueprint.ReadWrite.All",
    "AgentIdentityBlueprint.UpdateAuthProperties.All",
    "AgentIdentityBlueprint.UpdateBranding.All",
    "AgentIdentityBlueprintPrincipal.Create",
    "AgentIdentityBlueprintPrincipal.DeleteRestore.All",
    "AgentIdentityBlueprintPrincipal.EnableDisable.All",
    "AgentIdentityBlueprintPrincipal.Read.All",
    "AgentIdentityBlueprintPrincipal.ReadWrite.All",
    "AgentIdUser.ReadWrite.All",
    "AgentIdUser.ReadWrite.IdentityParentedBy",
    "AgentInstance.Read.All",
    "AgentInstance.ReadWrite.All",
    "User.Read",
]

# Always resolve .env to the project root (two levels up from this script)
DOTENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


def az(*args: str) -> str:
    """Run an az CLI command and return stdout as a stripped string.

    Raises on failure.
    """
    result = subprocess.run(
        ["az", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: az {' '.join(args)}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    return result.stdout.strip()


def az_json(*args: str) -> dict | list:
    """Run an az CLI command and return parsed JSON output."""
    result = subprocess.run(
        ["az", *args, "--output", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: az {' '.join(args)}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    return json.loads(result.stdout)


def main() -> None:
    # --- Create the app registration (single-tenant) ---
    print(f"=== Creating app registration: {DISPLAY_NAME} ===")
    app_obj_id = az(
        "ad",
        "app",
        "create",
        "--display-name",
        DISPLAY_NAME,
        "--sign-in-audience",
        "AzureADMyOrg",
        "--query",
        "id",
        "--output",
        "tsv",
    )
    app_id = az(
        "ad",
        "app",
        "show",
        "--id",
        app_obj_id,
        "--query",
        "appId",
        "--output",
        "tsv",
    )
    print(f"CLIENT_ID: {app_id}")

    # --- Configure public client ---
    print()
    print("=== Configuring public client ===")
    az(
        "ad",
        "app",
        "update",
        "--id",
        app_obj_id,
        "--is-fallback-public-client",
        "true",
        "--public-client-redirect-uris",
        "http://localhost",
    )

    # --- Add Microsoft Graph delegated scopes ---
    print()
    print("=== Adding Microsoft Graph delegated scopes ===")
    sp = az_json("ad", "sp", "show", "--id", GRAPH_APP_ID)
    perm_map: dict[str, str] = {
        p["value"]: p["id"] for p in sp.get("oauth2PermissionScopes", [])
    }

    for scope in SCOPES:
        perm_id = perm_map.get(scope)
        if perm_id:
            az(
                "ad",
                "app",
                "permission",
                "add",
                "--id",
                app_obj_id,
                "--api",
                GRAPH_APP_ID,
                "--api-permissions",
                f"{perm_id}=Scope",
            )
            print(f"  Added: {scope}")
        else:
            print(f"  WARNING: Scope not found in tenant: {scope}")

    # --- Grant tenant-wide admin consent ---
    print()
    print("=== Granting admin consent ===")
    az("ad", "app", "permission", "admin-consent", "--id", app_obj_id)

    # --- Write CLIENT_ID to .env ---
    print()
    set_key(str(DOTENV_PATH), "CLIENT_ID", app_id)
    if DOTENV_PATH.exists():
        print(f"=== Saved CLIENT_ID to {DOTENV_PATH} ===")
    else:
        print(f"=== Created {DOTENV_PATH} and set CLIENT_ID ===")

    print()
    print(f"Done. CLIENT_ID={app_id}")


if __name__ == "__main__":
    main()

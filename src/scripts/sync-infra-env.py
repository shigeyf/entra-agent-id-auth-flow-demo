#!/usr/bin/env python3
# sync-infra-env.py
#
# Syncs Terraform outputs from src/infra into the project .env file.
# Only the variables listed in INFRA_OUTPUT_TO_ENV and PREREQS_OUTPUT_TO_ENV
# are updated; all other .env entries (comments, manual values) are preserved.
#
# Prerequisites:
#   - terraform CLI available on PATH
#   - Terraform state exists in src/infra (i.e. `terraform apply` has been run)
#   - python-dotenv installed (`pip install python-dotenv`)
#
# Usage:
#   python src/scripts/sync-infra-env.py

import json
import subprocess
import sys
from pathlib import Path

from dotenv import set_key

# Resolve paths relative to this script
SCRIPT_DIR = Path(__file__).resolve().parent
SRC_DIR = SCRIPT_DIR.parent
DOTENV_PATH = SRC_DIR / ".env"
INFRA_DIR = SRC_DIR / "infra"
PREREQS_DIR = SRC_DIR / "entra_id" / "prereqs"

# Mapping: terraform output name → .env variable name
INFRA_OUTPUT_TO_ENV: dict[str, str] = {
    "tenant_id": "ENTRA_TENANT_ID",
    "client_app_client_id": "ENTRA_SPA_APP_CLIENT_ID",
    "resource_api_client_id": "ENTRA_RESOURCE_API_CLIENT_ID",
    "resource_api_scope": "ENTRA_RESOURCE_API_SCOPE",
    "resource_api_default_scope": "ENTRA_RESOURCE_API_DEFAULT_SCOPE",
    "foundry_project_endpoint": "FOUNDRY_PROJECT_ENDPOINT",
    "foundry_model_deployment_name": "FOUNDRY_MODEL_DEPLOYMENT_NAME",
    "foundry_agent_identity_id": "ENTRA_AGENT_IDENTITY_CLIENT_ID",
    "foundry_agent_identity_blueprint_id": "ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID",
    "acr_login_server": "FOUNDRY_AGENT_ACR_LOGIN_SERVER",
    "foundry_project_principal_id": "FOUNDRY_PROJECT_MSI",
    "resource_api_url": "RESOURCE_API_URL",
    "backend_api_url": "BACKEND_API_URL",
    "backend_api_foundry_access_client_id": "ENTRA_BACKEND_API_FOUNDRY_ACCESS_CLIENT_ID",
    "frontend_spa_app_url": "FRONTEND_SPA_APP_URL",
}

# Mapping: prereqs terraform output name → .env variable name
PREREQS_OUTPUT_TO_ENV: dict[str, str] = {
    "agent_id_manager_client_id": "GRAPH_API_OPS_CLIENT_ID",
}


def get_terraform_outputs(cwd: Path) -> dict[str, str]:
    """Run `terraform output -json` and return a dict of output name → value."""
    result = subprocess.run(
        ["terraform", "output", "-json"],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode != 0:
        print(f"ERROR: terraform output -json failed in {cwd}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)

    raw = json.loads(result.stdout)
    return {k: v["value"] for k, v in raw.items()}


def sync_outputs(cwd: Path, mapping: dict[str, str], label: str) -> tuple[list[str], list[str]]:
    """Sync terraform outputs from a directory into .env. Returns (updated, skipped)."""
    if not cwd.is_dir():
        print(f"WARNING: Terraform directory not found: {cwd} — skipping {label}")
        return [], []

    outputs = get_terraform_outputs(cwd)
    updated: list[str] = []
    skipped: list[str] = []

    for tf_key, env_key in mapping.items():
        value = outputs.get(tf_key)
        if value is None:
            skipped.append(f"  {tf_key} → {env_key} (not in terraform output)")
            continue
        set_key(DOTENV_PATH, env_key, value, quote_mode="never")
        updated.append(f"  {env_key} = {value}")

    return updated, skipped


def main() -> None:
    if not DOTENV_PATH.exists():
        print(f"ERROR: .env file not found: {DOTENV_PATH}", file=sys.stderr)
        sys.exit(1)

    all_updated: list[str] = []
    all_skipped: list[str] = []

    for cwd, mapping, label in [
        (INFRA_DIR, INFRA_OUTPUT_TO_ENV, "src/infra"),
        (PREREQS_DIR, PREREQS_OUTPUT_TO_ENV, "src/entra_id/prereqs"),
    ]:
        updated, skipped = sync_outputs(cwd, mapping, label)
        if updated:
            print(f"\n[{label}] Updated {len(updated)} variable(s):")
            print("\n".join(updated))
        if skipped:
            print(f"\n[{label}] Skipped {len(skipped)} variable(s):")
            print("\n".join(skipped))
        all_updated.extend(updated)
        all_skipped.extend(skipped)

    if not all_updated and not all_skipped:
        print("No variables to sync.")


if __name__ == "__main__":
    main()

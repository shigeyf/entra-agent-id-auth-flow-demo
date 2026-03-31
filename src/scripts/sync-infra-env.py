#!/usr/bin/env python3
# sync-infra-env.py
#
# Syncs Terraform outputs from src/infra into the project .env file.
# Only the variables listed in TF_OUTPUT_TO_ENV are updated;
# all other .env entries (comments, manual values) are preserved.
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

# Mapping: terraform output name → .env variable name
TF_OUTPUT_TO_ENV: dict[str, str] = {
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
}


def get_terraform_outputs() -> dict[str, str]:
    """Run `terraform output -json` and return a dict of output name → value."""
    result = subprocess.run(
        ["terraform", "output", "-json"],
        capture_output=True,
        text=True,
        cwd=INFRA_DIR,
    )
    if result.returncode != 0:
        print("ERROR: terraform output -json failed", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)

    raw = json.loads(result.stdout)
    return {k: v["value"] for k, v in raw.items()}


def main() -> None:
    if not INFRA_DIR.is_dir():
        print(f"ERROR: Terraform directory not found: {INFRA_DIR}", file=sys.stderr)
        sys.exit(1)

    if not DOTENV_PATH.exists():
        print(f"ERROR: .env file not found: {DOTENV_PATH}", file=sys.stderr)
        sys.exit(1)

    outputs = get_terraform_outputs()
    updated: list[str] = []
    skipped: list[str] = []

    for tf_key, env_key in TF_OUTPUT_TO_ENV.items():
        value = outputs.get(tf_key)
        if value is None:
            skipped.append(f"  {tf_key} → {env_key} (not in terraform output)")
            continue
        set_key(DOTENV_PATH, env_key, value, quote_mode="never")
        updated.append(f"  {env_key} = {value}")

    if updated:
        print(f"Updated {len(updated)} variable(s) in {DOTENV_PATH}:")
        print("\n".join(updated))
    if skipped:
        print(f"\nSkipped {len(skipped)} variable(s):")
        print("\n".join(skipped))
    if not updated and not skipped:
        print("No variables to sync.")


if __name__ == "__main__":
    main()

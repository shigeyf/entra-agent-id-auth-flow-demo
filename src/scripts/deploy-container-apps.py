#!/usr/bin/env python3
# deploy-container-apps.py
#
# Rebuild container images and update Container Apps using ACR build + az CLI.
#
# What this script does:
#   1. Read src/.env (synced by sync-infra-env.py) to obtain ACR and resource info
#   2. For each target app, run `az acr build` to build & push the image
#   3. Update the Container App to pull the new image revision
#
# Prerequisites:
#   - src/.env populated (run `python src/scripts/sync-infra-env.py` first)
#   - az CLI on PATH and logged in
#   - python-dotenv installed (`pip install python-dotenv`)
#
# Usage:
#   python src/scripts/deploy-container-apps.py                  # all apps
#   python src/scripts/deploy-container-apps.py backend-api      # single app
#   python src/scripts/deploy-container-apps.py identity-echo-api backend-api

import argparse
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

SCRIPT_DIR = Path(__file__).resolve().parent
SRC_DIR = SCRIPT_DIR.parent
DOTENV_PATH = SRC_DIR / ".env"

# Container App definitions: key must match var.container_apps key in terraform.tfvars
# build_context is relative to SRC_DIR
APPS: dict[str, dict] = {
    "backend-api": {
        "image_name": "backend-api",
        "build_context": SRC_DIR / "backend_api",
        "dockerfile": "Dockerfile",
    },
    "identity-echo-api": {
        "image_name": "identity-echo-api",
        "build_context": SRC_DIR / "identity_echo_api",
        "dockerfile": "Dockerfile",
    },
}


def load_dotenv_values() -> dict[str, str]:
    """Load src/.env and return as dict."""
    if not DOTENV_PATH.exists():
        print(f"ERROR: {DOTENV_PATH} not found. Run sync-infra-env.py first.", file=sys.stderr)
        sys.exit(1)
    return {k: v for k, v in dotenv_values(DOTENV_PATH).items() if v}


def run_cmd(cmd: list[str], description: str) -> None:
    """Run a command, printing it and exiting on failure."""
    print(f"\n--- {description} ---")
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"ERROR: {description} failed (exit {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)


def build_and_push(acr_name: str, app_key: str) -> None:
    """Build and push an image to ACR."""
    app = APPS[app_key]
    run_cmd(
        [
            "az",
            "acr",
            "build",
            "--registry",
            acr_name,
            "--image",
            f"{app['image_name']}:latest",
            "--file",
            f"{app['build_context']}/{app['dockerfile']}",
            str(app["build_context"]),
        ],
        f"Building {app_key} image",
    )


def update_container_app(resource_group: str, acr_login_server: str, app_key: str) -> None:
    """Update the Container App to use the latest image."""
    app = APPS[app_key]

    # List container apps to find the actual name
    result = subprocess.run(
        [
            "az",
            "containerapp",
            "list",
            "--resource-group",
            resource_group,
            "--query",
            f"[?contains(name, '{app_key}')].name",
            "-o",
            "tsv",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        print(f"ERROR: could not find container app for {app_key}", file=sys.stderr)
        sys.exit(1)

    ca_name = result.stdout.strip().split("\n")[0]
    image = f"{acr_login_server}/{app['image_name']}:latest"

    run_cmd(
        [
            "az",
            "containerapp",
            "update",
            "--name",
            ca_name,
            "--resource-group",
            resource_group,
            "--image",
            image,
        ],
        f"Updating Container App {ca_name}",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build and deploy Container Apps (backend-api, identity-echo-api)"
    )
    parser.add_argument(
        "apps",
        nargs="*",
        choices=list(APPS.keys()) + [[]],
        default=[],
        help="App(s) to deploy. Omit to deploy all.",
    )
    args = parser.parse_args()

    targets = args.apps if args.apps else list(APPS.keys())

    # 1. Load .env values
    print("--- Reading src/.env ---")
    env = load_dotenv_values()

    acr_login_server = env.get("FOUNDRY_AGENT_ACR_LOGIN_SERVER", "")
    if not acr_login_server:
        print("ERROR: FOUNDRY_AGENT_ACR_LOGIN_SERVER not set in .env", file=sys.stderr)
        sys.exit(1)

    # ACR name is the first segment of the login server (e.g. "crfoo.azurecr.io" -> "crfoo")
    acr_name = acr_login_server.split(".")[0]

    # Get resource group from ACR
    result = subprocess.run(
        [
            "az",
            "acr",
            "show",
            "--name",
            acr_name,
            "--query",
            "resourceGroup",
            "-o",
            "tsv",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        print("ERROR: could not determine resource group from ACR", file=sys.stderr)
        sys.exit(1)
    resource_group = result.stdout.strip()

    # 2. Build and deploy each target
    for app_key in targets:
        print(f"\n{'=' * 60}")
        print(f"Deploying: {app_key}")
        print(f"{'=' * 60}")
        build_and_push(acr_name, app_key)
        update_container_app(resource_group, acr_login_server, app_key)

    print(f"\nAll done! Deployed: {', '.join(targets)}")


if __name__ == "__main__":
    main()

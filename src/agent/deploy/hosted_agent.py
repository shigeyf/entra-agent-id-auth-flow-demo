"""Deploy Hosted Agent to Foundry Agent Service.

Usage:
    python -m deploy.hosted_agent [--start]

Reads configuration from src/agent/.env (via dotenv).
Creates (or updates) a hosted agent version using the Foundry SDK,
then optionally starts the deployment via az CLI.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the agent directory (parent of deploy/)
_AGENT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_AGENT_DIR / ".env")


def _require_env(key: str) -> str:
    value = os.getenv(key, "")
    if not value:
        print(
            f"ERROR: Required environment variable {key} is not set in .env",
            file=sys.stderr,
        )
        sys.exit(1)
    return value


def _parse_project_endpoint(endpoint: str) -> tuple[str, str]:
    """Extract account_name and project_name from PROJECT_ENDPOINT.

    Expected format:
      https://<account>.cognitiveservices.azure.com/api/projects/<project>
    """
    m = re.match(
        r"https://([^.]+)\.cognitiveservices\.azure\.com/api/projects/(.+)",
        endpoint,
    )
    if not m:
        print(f"ERROR: Cannot parse PROJECT_ENDPOINT: {endpoint}", file=sys.stderr)
        sys.exit(1)
    return m.group(1), m.group(2)


# ---------- Environment-driven configuration ----------
PROJECT_ENDPOINT = _require_env("PROJECT_ENDPOINT")
ACCOUNT_NAME, PROJECT_NAME = _parse_project_endpoint(PROJECT_ENDPOINT)

ACR_LOGIN_SERVER = _require_env("ACR_LOGIN_SERVER")
AGENT_NAME = _require_env("AGENT_NAME")
CPU = os.getenv("AGENT_CPU", "1")
MEMORY = os.getenv("AGENT_MEMORY", "2Gi")
IMAGE = f"{ACR_LOGIN_SERVER}/{AGENT_NAME}:latest"

# Environment variables to pass into the Hosted Agent container.
# Keys that match .env entries are forwarded; empty values are included
# so they can be set later (e.g. BLUEPRINT_CLIENT_ID for Step B).
_ENV_KEYS = [
    "PROJECT_ENDPOINT",
    "MODEL_DEPLOYMENT_NAME",
    "TENANT_ID",
    "BLUEPRINT_CLIENT_ID",
    "AGENT_IDENTITY_OID",
    "RESOURCE_API_URL",
    "RESOURCE_API_SCOPE",
    "RESOURCE_API_DEFAULT_SCOPE",
]
CONTAINER_ENV_VARS = {k: os.getenv(k, "") for k in _ENV_KEYS}


def create_version() -> int:
    """Create a hosted agent version via Foundry SDK. Returns the version number."""
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import (
        AgentProtocol,
        HostedAgentDefinition,
        ProtocolVersionRecord,
    )
    from azure.core.pipeline.policies import HeadersPolicy
    from azure.identity import DefaultAzureCredential

    headers_policy = HeadersPolicy()
    headers_policy.add_header("Foundry-Features", "HostedAgents=V1Preview")

    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential(),
        allow_preview=True,
        headers_policy=headers_policy,
    )

    print(f"Creating hosted agent version: {AGENT_NAME}")
    print(f"  Image:    {IMAGE}")
    print(f"  CPU: {CPU}, Memory: {MEMORY}")
    print(f"  Account:  {ACCOUNT_NAME}")
    print(f"  Project:  {PROJECT_NAME}")

    agent = client.agents.create_version(
        agent_name=AGENT_NAME,
        definition=HostedAgentDefinition(
            container_protocol_versions=[
                ProtocolVersionRecord(protocol=AgentProtocol.RESPONSES, version="v1")
            ],
            cpu=CPU,
            memory=MEMORY,
            image=IMAGE,
            environment_variables=CONTAINER_ENV_VARS,
        ),
    )

    print(f"\nAgent created: {agent.name} (id: {agent.id}, version: {agent.version})")
    print(
        f"\nTo start manually:\n"
        f"  az cognitiveservices agent start "
        f"--account-name {ACCOUNT_NAME} "
        f"--project-name {PROJECT_NAME} "
        f"--name {AGENT_NAME} "
        f"--agent-version {agent.version}"
    )
    return agent.version


def start_agent(version: int) -> None:
    """Start agent deployment using az CLI."""
    cmd = [
        "az",
        "cognitiveservices",
        "agent",
        "start",
        "--account-name",
        ACCOUNT_NAME,
        "--project-name",
        PROJECT_NAME,
        "--name",
        AGENT_NAME,
        "--agent-version",
        str(version),
        "--show-logs",
    ]
    print(f"Starting deployment: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}", file=sys.stderr)
        sys.exit(result.returncode)
    print("Deployment started successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy Hosted Agent to Foundry")
    parser.add_argument(
        "--start",
        action="store_true",
        help="Also start the deployment after creating the version",
    )
    args = parser.parse_args()

    version = create_version()

    if args.start:
        print()
        start_agent(version=version)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Deploy Hosted Agent: build, push, and deploy to Foundry Agent Service.

Usage:
    python deploy-agent.py                  # Run all phases (build -> push -> deploy)
    python deploy-agent.py build            # Build container image only
    python deploy-agent.py push             # Push container image to ACR only
    python deploy-agent.py deploy           # Create agent version only
    python deploy-agent.py deploy --start   # Create agent version and start deployment
    python deploy-agent.py deploy --wait    # Start and wait for Ready (implies --start)
    python deploy-agent.py deploy --wait --wait-timeout 600  # Custom timeout
    python deploy-agent.py build push       # Build and push only

Reads agent definition from agent.yaml (with ${VAR} expansion from .env).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# .env loader: walk up the directory tree using dotenv's find_dotenv()
# ---------------------------------------------------------------------------
def _load_env() -> None:
    """Find and load the nearest .env by walking up from the cwd."""
    from dotenv import find_dotenv, load_dotenv

    env_path = find_dotenv(filename=".env", usecwd=False)
    if not env_path:
        print("WARNING: No .env file found in any ancestor directory.", file=sys.stderr)
        return
    print(f"  Loading: {env_path}")
    load_dotenv(env_path, override=True)


# ---------------------------------------------------------------------------
# agent.yaml loader with ${VAR} expansion
# ---------------------------------------------------------------------------
def _load_agent_yaml(yaml_path: Path) -> dict:
    """Load agent.yaml and expand ${VAR} references from environment."""
    if not yaml_path.is_file():
        print(f"ERROR: {yaml_path} not found", file=sys.stderr)
        sys.exit(1)

    raw = yaml_path.read_text()

    missing_vars: list[str] = []

    def _expand(m: re.Match) -> str:
        key = m.group(1)
        value = os.environ.get(key, "")
        if not value:
            missing_vars.append(key)
        return value

    expanded = re.sub(r"\$\{(\w+)}", _expand, raw)

    if missing_vars:
        print(
            f"ERROR: Undefined environment variables in {yaml_path.name}: "
            f"{', '.join(missing_vars)}",
            file=sys.stderr,
        )
        sys.exit(1)

    data = yaml.safe_load(expanded)
    return data


def _print_agent_def(data: dict) -> None:
    """Print the resolved agent definition."""
    print(yaml.dump(data, default_flow_style=False, sort_keys=False).rstrip())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a subprocess, echo the command, and optionally check the return code."""
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, text=True)
    if check and result.returncode != 0:
        sys.exit(result.returncode)
    return result


def _parse_project_endpoint(endpoint: str) -> tuple[str, str]:
    """Extract (account_name, project_name) from PROJECT_ENDPOINT.

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


# ---------------------------------------------------------------------------
# Phase: build
# ---------------------------------------------------------------------------
def phase_build(image: str, runtime_dir: Path) -> None:
    """Build the Docker container image."""
    print(f"\n{'=' * 60}")
    print(f"[BUILD] Building {image} ...")
    print(f"{'=' * 60}")
    _run(
        [
            "docker",
            "build",
            "--platform",
            "linux/amd64",
            "-t",
            image,
            "-f",
            str(runtime_dir / "Dockerfile"),
            str(runtime_dir),
        ]
    )
    print(f"[BUILD] Done: {image}")


# ---------------------------------------------------------------------------
# Phase: push
# ---------------------------------------------------------------------------
def phase_push(image: str) -> None:
    """Log in to ACR and push the container image."""
    print(f"\n{'=' * 60}")
    print(f"[PUSH] Pushing {image} ...")
    print(f"{'=' * 60}")

    # Extract ACR login server from image (everything before the first '/').
    acr_login_server = image.split("/")[0]
    acr_name = acr_login_server.split(".")[0]

    print(f"[PUSH] Logging in to {acr_login_server} ...")
    _run(["az", "acr", "login", "--name", acr_name])

    print("[PUSH] Pushing image ...")
    _run(["docker", "push", image])
    print(f"[PUSH] Done: {image}")


# ---------------------------------------------------------------------------
# Phase: deploy (create version + optional start)
# ---------------------------------------------------------------------------
def phase_deploy(*, agent_def: dict, start: bool, wait: bool, wait_timeout: int) -> None:
    """Create a Hosted Agent version and optionally start deployment."""
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import HostedAgentDefinition
    from azure.core.pipeline.policies import HeadersPolicy
    from azure.identity import DefaultAzureCredential

    agent_name = agent_def["name"]
    defn = agent_def["definition"]

    # Resolve project endpoint for the API client
    env_vars = defn.get("environment_variables", {})
    project_endpoint = env_vars.get("FOUNDRY_PROJECT_ENDPOINT", "") or os.getenv(
        "FOUNDRY_PROJECT_ENDPOINT", ""
    )
    if not project_endpoint:
        print("ERROR: FOUNDRY_PROJECT_ENDPOINT is required for deploy", file=sys.stderr)
        sys.exit(1)

    account_name, project_name = _parse_project_endpoint(project_endpoint)

    print(f"\n{'=' * 60}")
    print(f"[DEPLOY] Creating hosted agent version: {agent_name}")
    print(f"{'=' * 60}")
    print(f"  Account:  {account_name}")
    print(f"  Project:  {project_name}")

    headers_policy = HeadersPolicy()
    headers_policy.add_header("Foundry-Features", "HostedAgents=V1Preview")

    client = AIProjectClient(
        endpoint=project_endpoint,
        credential=DefaultAzureCredential(),
        allow_preview=True,
        headers_policy=headers_policy,
    )

    # Check latest version before create to detect new vs existing
    from azure.core.exceptions import ResourceNotFoundError

    try:
        version_before = client.agents.get(agent_name).versions.latest.version
    except ResourceNotFoundError:
        version_before = None

    # create_version is idempotent — returns existing version if definition unchanged
    agent = client.agents.create_version(
        agent_name=agent_name,
        definition=HostedAgentDefinition(defn),
    )

    is_new_version = agent.version != version_before
    if is_new_version:
        print(f"\n[DEPLOY] New version created: {agent.name} (version: {agent.version})")
    else:
        print(
            f"\n[DEPLOY] Definition unchanged — existing version returned: "
            f"{agent.name} (version: {agent.version})"
        )
        print("\n[DEPLOY] Deleting existing deployment to pull fresh container image ...")
        _run(
            [
                "az",
                "cognitiveservices",
                "agent",
                "delete-deployment",
                "--account-name",
                account_name,
                "--project-name",
                project_name,
                "--name",
                agent_name,
                "--agent-version",
                str(agent.version),
            ],
            check=False,
        )
        print("[DEPLOY] Waiting for deployment deletion ...")
        _wait_for_deletion(
            account_name=account_name,
            project_name=project_name,
            agent_name=agent_name,
            agent_version=str(agent.version),
        )

    print(
        f"\n  To start manually:\n"
        f"    az cognitiveservices agent start "
        f"--account-name {account_name} "
        f"--project-name {project_name} "
        f"--name {agent_name} "
        f"--agent-version {agent.version}"
    )

    if start:
        print("\n[DEPLOY] Starting agent ...")
        cmd = [
            "az",
            "cognitiveservices",
            "agent",
            "start",
            "--account-name",
            account_name,
            "--project-name",
            project_name,
            "--name",
            agent_name,
            "--agent-version",
            str(agent.version),
        ]
        result = _run(cmd, check=False)
        if result.returncode != 0:
            print(f"ERROR: Agent start failed (exit code {result.returncode})", file=sys.stderr)
            sys.exit(result.returncode)

        if wait:
            _wait_for_ready(
                account_name=account_name,
                project_name=project_name,
                agent_name=agent_name,
                agent_version=str(agent.version),
                timeout=wait_timeout,
            )
        else:
            print("[DEPLOY] Deployment started (status may still be InProgress).")
            print(
                f"\n  To check status manually:\n"
                f"    az cognitiveservices agent status "
                f"--account-name {account_name} "
                f"--project-name {project_name} "
                f"--name {agent_name} "
                f"--agent-version {agent.version}"
            )


# ---------------------------------------------------------------------------
# Wait helpers
# ---------------------------------------------------------------------------
_POLL_INTERVAL = 10  # seconds between status checks
_DELETION_TIMEOUT = 120  # seconds to wait for deployment deletion

# status field values that indicate a failed/stopped deployment
_FAILED_STATUSES = {"Failed", "Stopped"}


def _wait_for_deletion(
    *,
    account_name: str,
    project_name: str,
    agent_name: str,
    agent_version: str,
) -> None:
    """Poll status until deployment is Deleted or no longer exists."""
    print(f"[WAIT] Waiting up to {_DELETION_TIMEOUT}s for deployment to be deleted ...")
    cmd = [
        "az",
        "cognitiveservices",
        "agent",
        "status",
        "--account-name",
        account_name,
        "--project-name",
        project_name,
        "--name",
        agent_name,
        "--agent-version",
        agent_version,
        "--output",
        "json",
    ]
    start_time = time.monotonic()

    while True:
        elapsed = time.monotonic() - start_time
        if elapsed >= _DELETION_TIMEOUT:
            print(
                f"[WAIT] WARNING: Deletion not confirmed after {_DELETION_TIMEOUT}s, "
                "proceeding anyway.",
                file=sys.stderr,
            )
            return

        result = subprocess.run(cmd, text=True, capture_output=True)
        if result.returncode != 0:
            # Command failure likely means deployment no longer exists
            print("[WAIT] Deployment deleted (status endpoint unavailable).")
            return

        try:
            status_data = json.loads(result.stdout)
        except json.JSONDecodeError:
            time.sleep(_POLL_INTERVAL)
            continue

        status = status_data.get("status", "Unknown")
        print(f"[WAIT] status={status}  elapsed={int(elapsed)}s")

        if status == "Deleted":
            print("[WAIT] Deployment deleted.")
            return

        time.sleep(_POLL_INTERVAL)


def _is_ready(data: dict) -> bool:
    """Return True if all health indicators show a healthy running agent.

    Checks:
      - status == "Running"
      - container.provisioning_state == "Succeeded"
      - container.health_state == "Healthy"
      - container.state starts with "Running"  (e.g. "RunningAtMaxScale")
    """
    container = data.get("container", {})
    return (
        data.get("status") == "Running"
        and container.get("provisioning_state") == "Succeeded"
        and container.get("health_state") == "Healthy"
        and (container.get("state") or "").startswith("Running")
    )


def _is_failed(data: dict) -> bool:
    """Return True if the deployment has reached an unrecoverable state."""
    status = data.get("status", "")
    container = data.get("container", {})
    return (
        status in _FAILED_STATUSES
        or container.get("provisioning_state") == "Failed"
        or container.get("health_state") == "Unhealthy"
    )


def _wait_for_ready(
    *,
    account_name: str,
    project_name: str,
    agent_name: str,
    agent_version: str,
    timeout: int,
) -> None:
    """Poll `az cognitiveservices agent status` until ready, failed, or timeout."""
    print(f"\n[WAIT] Waiting up to {timeout}s for agent to become Ready ...")
    cmd = [
        "az",
        "cognitiveservices",
        "agent",
        "status",
        "--account-name",
        account_name,
        "--project-name",
        project_name,
        "--name",
        agent_name,
        "--agent-version",
        agent_version,
        "--output",
        "json",
    ]
    start_time = time.monotonic()

    while True:
        elapsed = time.monotonic() - start_time
        if elapsed >= timeout:
            print(
                f"\n[WAIT] ERROR: Timed out after {timeout}s. Agent did not reach a ready state.",
                file=sys.stderr,
            )
            sys.exit(1)

        result = subprocess.run(cmd, text=True, capture_output=True)
        if result.returncode != 0:
            print(
                f"[WAIT] WARNING: status check failed (exit {result.returncode}): "
                f"{result.stderr.strip()}",
                file=sys.stderr,
            )
        else:
            try:
                status_data = json.loads(result.stdout)
            except json.JSONDecodeError:
                print("[WAIT] WARNING: Could not parse status response", file=sys.stderr)
                time.sleep(_POLL_INTERVAL)
                continue

            status = status_data.get("status", "Unknown")
            container = status_data.get("container", {})
            prov = container.get("provisioning_state", "—")
            health = container.get("health_state", "—")
            cstate = container.get("state", "—")
            remaining = max(0, int(timeout - elapsed))
            print(
                f"[WAIT] status={status}  provisioning={prov}  "
                f"health={health}  container={cstate}  "
                f"elapsed={int(elapsed)}s  remaining={remaining}s"
            )

            if _is_ready(status_data):
                print("[WAIT] Agent is Ready!")
                return

            if _is_failed(status_data):
                print(
                    "\n[WAIT] ERROR: Agent deployment failed.",
                    file=sys.stderr,
                )
                print(json.dumps(status_data, indent=2), file=sys.stderr)
                sys.exit(1)

        time.sleep(_POLL_INTERVAL)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
PHASES = ["build", "push", "deploy"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build, push, and deploy a Hosted Agent to Foundry Agent Service.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  %(prog)s                  # all phases\n"
            "  %(prog)s build            # build only\n"
            "  %(prog)s push             # push only\n"
            "  %(prog)s deploy --start   # deploy and start\n"
            "  %(prog)s build push       # build + push\n"
        ),
    )
    parser.add_argument(
        "phases",
        nargs="*",
        choices=PHASES,
        default=[],
        metavar="PHASE",
        help=f"Phase(s) to execute: {', '.join(PHASES)}. Omit to run all.",
    )
    parser.add_argument(
        "--start",
        action="store_true",
        help="Start the agent deployment after creating the version (deploy phase).",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for the agent to reach Ready status after starting (implies --start).",
    )
    parser.add_argument(
        "--wait-timeout",
        type=int,
        default=1020,
        metavar="SECONDS",
        help="Maximum seconds to wait for Ready status (default: 1020 = 15min + 2min margin).",
    )
    args = parser.parse_args()

    # --wait implies --start
    if args.wait:
        args.start = True

    selected = args.phases if args.phases else PHASES

    # ---- Load .env ----
    print("Loading .env ...")
    _load_env()

    # ---- Load agent.yaml ----
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    agent_yaml = project_root / "agent.yaml"
    print(f"Loading {agent_yaml.name} ...")
    agent_def = _load_agent_yaml(agent_yaml)
    _print_agent_def(agent_def)

    image = agent_def["definition"]["image"]
    runtime_dir = project_root / "runtime"

    # ---- Execute selected phases ----
    if "build" in selected:
        phase_build(image, runtime_dir)

    if "push" in selected:
        phase_push(image)

    if "deploy" in selected:
        phase_deploy(
            agent_def=agent_def,
            start=args.start,
            wait=args.wait,
            wait_timeout=args.wait_timeout,
        )

    print("\nAll selected phases completed.")


if __name__ == "__main__":
    main()

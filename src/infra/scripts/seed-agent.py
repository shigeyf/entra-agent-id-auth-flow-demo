#!/usr/bin/env python3
"""
Seed Agent: Bootstrap agentIdentity on the Foundry Project.

Creates a minimal Declarative Agent (kind: "prompt") and immediately deletes it.
The agentIdentity persists on the Project after deletion.

Usage:
    python seed-agent.py <endpoint> <project_name> <model_name>

Example:
    python seed-agent.py https://xxx.cognitiveservices.azure.com/ myproject gpt-4o

Cross-platform compatible (Windows/Linux/macOS).
"""

import json
import subprocess
import sys
import urllib.request
import urllib.error


def log(message: str):
    """Print message with immediate flush."""
    print(message, flush=True)


def get_access_token() -> str:
    """Get Azure access token using az CLI."""
    # On Windows, az is az.cmd - use shell=True for cross-platform compatibility
    result = subprocess.run(
        "az account get-access-token --resource https://ai.azure.com/ --query accessToken -o tsv",
        capture_output=True,
        text=True,
        shell=True,
    )
    if result.returncode != 0:
        log(f"[SEED] az command failed with exit code {result.returncode}")
        log(f"[SEED] stdout: {result.stdout}")
        log(f"[SEED] stderr: {result.stderr}")
        raise RuntimeError("Failed to get access token")
    return result.stdout.strip()


def http_request(url: str, method: str, token: str, data: dict | None = None) -> tuple[int, dict | str]:
    """Make HTTP request and return (status_code, response_body)."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    body = json.dumps(data).encode("utf-8") if data else None

    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as response:
            status_code = response.status
            try:
                response_body = json.loads(response.read().decode("utf-8"))
            except json.JSONDecodeError:
                response_body = response.read().decode("utf-8")
            return status_code, response_body
    except urllib.error.HTTPError as e:
        status_code = e.code
        try:
            response_body = json.loads(e.read().decode("utf-8"))
        except json.JSONDecodeError:
            response_body = e.read().decode("utf-8")
        return status_code, response_body


def main():
    if len(sys.argv) != 4:
        log(f"Usage: {sys.argv[0]} <endpoint> <project_name> <model_name>")
        sys.exit(1)

    endpoint = sys.argv[1].rstrip("/")
    project_name = sys.argv[2]
    model_name = sys.argv[3]
    seed_name = "seed-agent"

    base_url = f"{endpoint}/api/projects/{project_name}"

    log(f"[SEED] Getting Azure access token...")
    try:
        token = get_access_token()
    except RuntimeError:
        sys.exit(1)

    log(f"[SEED] Creating declarative agent '{seed_name}' to bootstrap agentIdentity ...")

    create_url = f"{base_url}/agents/{seed_name}/versions?api-version=v1"
    create_data = {
        "definition": {
            "kind": "prompt",
            "model": model_name,
            "instructions": "seed"
        }
    }

    status_code, response = http_request(create_url, "POST", token, create_data)

    if 200 <= status_code < 300:
        log(f"[SEED] Agent created (HTTP {status_code})")
        if isinstance(response, dict):
            log(json.dumps(response, indent=2))
    else:
        log(f"[SEED] ERROR: Failed to create agent (HTTP {status_code})")
        if isinstance(response, dict):
            log(json.dumps(response, indent=2))
        else:
            log(response)
        sys.exit(1)

    log(f"[SEED] Deleting seed agent ...")

    delete_url = f"{base_url}/agents/{seed_name}?api-version=v1"
    status_code, response = http_request(delete_url, "DELETE", token)

    if 200 <= status_code < 300:
        log(f"[SEED] Seed agent deleted (HTTP {status_code}). agentIdentity is now available on the Project.")
    else:
        log(f"[SEED] WARNING: Failed to delete seed agent (HTTP {status_code}). Manual cleanup may be needed.")
        if isinstance(response, dict):
            log(json.dumps(response, indent=2))
        else:
            log(response)


if __name__ == "__main__":
    main()

"""Invoke the deployed Hosted Agent via OpenAI Responses API.

Usage:
    python scripts/invoke-agent.py                        # default (scripts/query.json)
    python scripts/invoke-agent.py "message"              # inline message
    python scripts/invoke-agent.py -f message.txt         # plain-text file
    python scripts/invoke-agent.py -j input.json          # full input array
    echo "hello" | python scripts/invoke-agent.py -       # stdin

Argument priority (highest wins):
    1. -j / --input-json   — JSON file (full input array)
    2. -f / --file         — plain-text file
    3. "-" (stdin)         — pipe / redirect
    4. positional message  — inline string
    5. (none)              — scripts/query.json (default)

Environment variables (loaded from app/.env):
    FOUNDRY_PROJECT_ENDPOINT  — Foundry Project endpoint
    FOUNDRY_AGENT_NAME        — Hosted Agent name

Note:
    - The endpoint must use the services.ai.azure.com domain
      (not cognitiveservices.azure.com)
    - The OpenAI client is obtained via AIProjectClient.get_openai_client(),
      and the Hosted Agent is specified through agent_reference in extra_body
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

# ---------------------------------------------------------------------------
# Paths — resolved relative to this script (scripts/) and agent project root
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent  # src/agent/
_AGENT_YAML = _PROJECT_ROOT / "agent.yaml"  # agent definition
_DEFAULT_QUERY = _SCRIPT_DIR / "query.json"  # default input for invoke


# ---------------------------------------------------------------------------
# .env loader: walk up the directory tree using dotenv's find_dotenv()
# ---------------------------------------------------------------------------
def _load_env(start_dir: Path) -> None:
    """Find and load the nearest .env by walking up from *start_dir*."""
    from dotenv import find_dotenv, load_dotenv

    # find_dotenv walks up from the given filename's directory.
    # We anchor the search by providing a dummy path under start_dir.
    env_path = find_dotenv(filename=".env", usecwd=False)
    if not env_path:
        print("WARNING: No .env file found in any ancestor directory.", file=sys.stderr)
        return
    print(f"  Loading: {env_path}")
    load_dotenv(env_path, override=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _require_env(key: str) -> str:
    """Return the value of an environment variable, or exit with an error."""
    value = os.getenv(key, "")
    if not value:
        print(
            f"ERROR: Required environment variable {key} is not set in .env",
            file=sys.stderr,
        )
        sys.exit(1)
    return value


def _to_services_endpoint(endpoint: str) -> str:
    """Convert cognitiveservices.azure.com to services.ai.azure.com.

    AIProjectClient must connect via the services.ai.azure.com domain.
    The agent_reference is not recognized with the cognitiveservices.azure.com domain.
    """
    return re.sub(
        r"\.cognitiveservices\.azure\.com/",
        ".services.ai.azure.com/",
        endpoint,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def _build_input(args: argparse.Namespace) -> "str | list":
    """Build the ``input`` parameter for openai.responses.create().

    Priority: --input-json > --file > stdin ("-") > positional message > default query.json.
    Returns either a plain string or a list of ResponseInputItem dicts.
    """
    if args.input_json:
        path = Path(args.input_json)
        if not path.is_file():
            print(f"ERROR: JSON file not found: {path}", file=sys.stderr)
            sys.exit(1)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, str | list):
            print("ERROR: --input-json must contain a JSON string or array", file=sys.stderr)
            sys.exit(1)
        return data

    if args.file:
        path = Path(args.file)
        if not path.is_file():
            print(f"ERROR: File not found: {path}", file=sys.stderr)
            sys.exit(1)
        return path.read_text(encoding="utf-8").strip()

    if args.message == "-":
        text = sys.stdin.read().strip()
        if not text:
            print("ERROR: No input received from stdin", file=sys.stderr)
            sys.exit(1)
        return text

    if args.message is not None:
        return args.message

    # Default: load scripts/query.json
    if not _DEFAULT_QUERY.is_file():
        print(f"ERROR: Default query file not found: {_DEFAULT_QUERY}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(_DEFAULT_QUERY.read_text(encoding="utf-8"))
    print(f"  Using default query: {_DEFAULT_QUERY}", file=sys.stderr)
    return data


def invoke(agent_input: "str | list") -> None:
    # ---- Load .env files (recursive) ----
    print("Loading .env ...")
    _load_env(_PROJECT_ROOT)

    project_endpoint = _require_env("FOUNDRY_PROJECT_ENDPOINT")

    # Read agent name from agent.yaml
    if not _AGENT_YAML.is_file():
        print(f"ERROR: {_AGENT_YAML} not found", file=sys.stderr)
        sys.exit(1)
    agent_name = yaml.safe_load(_AGENT_YAML.read_text())["name"]

    # Convert to services.ai.azure.com domain
    services_endpoint = _to_services_endpoint(project_endpoint)

    project = AIProjectClient(
        endpoint=services_endpoint,
        credential=DefaultAzureCredential(),
        allow_preview=True,
    )
    openai_client = project.get_openai_client()

    agent = project.agents.get(agent_name=agent_name)
    print(f"Agent: {agent.name}", file=sys.stderr)

    # If a plain string is given, wrap it as a user message.
    # If a list is given, pass it through as-is (multi-turn / system messages).
    if isinstance(agent_input, str):
        input_payload = [{"role": "user", "content": agent_input}]
    else:
        input_payload = agent_input

    print(f"[input] {json.dumps(input_payload, ensure_ascii=False)}", file=sys.stderr)

    response = openai_client.responses.create(
        input=input_payload,
        store=False,
        extra_body={
            "agent_reference": {
                "name": agent.name,
                "type": "agent_reference",
            }
        },
        timeout=180,
    )

    # Display output by type
    for item in response.output:
        if item.type == "function_call_output":
            raw = item.output
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    parsed = json.loads(parsed[0])
                elif isinstance(parsed, str):
                    parsed = json.loads(parsed)
                print(json.dumps(parsed, indent=2, ensure_ascii=False))
            except (json.JSONDecodeError, IndexError):
                print(raw)
        elif item.type == "message":
            for c in item.content:
                if hasattr(c, "text"):
                    print(f"[agent] {c.text}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Invoke the deployed Hosted Agent via OpenAI Responses API.",
        epilog="Argument priority (highest wins): "
        "-j > -f > stdin ('-') > positional message > scripts/query.json",
    )
    parser.add_argument(
        "message",
        nargs="?",
        default=None,
        help='User message text, or "-" for stdin (default: scripts/query.json)',
    )
    parser.add_argument(
        "-f",
        "--file",
        help="Path to a plain-text file containing the user message",
    )
    parser.add_argument(
        "-j",
        "--input-json",
        help="Path to a JSON file containing the full input array "
        '(e.g. [{"role":"user","content":"..."}])',
    )
    args = parser.parse_args()
    invoke(_build_input(args))

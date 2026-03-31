"""Invoke the deployed Hosted Agent via OpenAI Responses API.

Usage:
    python src/scripts/invoke-hosted-agent.py "message"
    python src/scripts/invoke-hosted-agent.py  # run with default message

Environment variables (loaded from src/agent/.env):
    PROJECT_ENDPOINT  — Foundry Project endpoint
    AGENT_NAME        — Hosted Agent name

Note:
    - The endpoint must use the services.ai.azure.com domain
      (not cognitiveservices.azure.com)
    - The OpenAI client is obtained via AIProjectClient.get_openai_client(),
      and the Hosted Agent is specified through agent_reference in extra_body
"""

import json
import os
import re
import sys
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

# Load config from src/.env (parent of agent/ = src/)
_AGENT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_AGENT_DIR.parent / ".env")


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


def invoke(message: str) -> None:
    project_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    agent_name = os.getenv("FOUNDRY_AGENT_NAME", "demo-entra-agent-id")

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

    response = openai_client.responses.create(
        input=[{"role": "user", "content": message}],
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
    user_message = (
        sys.argv[1] if len(sys.argv) > 1 else "Run try_t1_token_acquisition now."
    )
    invoke(user_message)

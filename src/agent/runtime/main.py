"""Foundry Hosted Agent entry point.

Starts the hosting adapter server on port 8088 (default).
Locally: `python -m agent.main` or `python src/agent/main.py`
Foundry: The container CMD invokes this file directly.
"""

import os
import sys
import traceback

print("[BOOT] main.py starting", flush=True)
print(f"[BOOT] Python {sys.version}", flush=True)
print(f"[BOOT] cwd={os.getcwd()}", flush=True)

try:
    from config import config  # noqa: E402

    print("[BOOT] config loaded", flush=True)
    print(f"[BOOT] FOUNDRY_PROJECT_ENDPOINT={config.project_endpoint}", flush=True)
    print(f"[BOOT] FOUNDRY_MODEL_DEPLOYMENT_NAME={config.model_deployment_name}", flush=True)

    from agent_framework import Agent  # noqa: E402

    print("[BOOT] Agent imported", flush=True)

    from agent_framework_azure_ai import AzureAIAgentClient  # noqa: E402

    print("[BOOT] AzureAIAgentClient imported", flush=True)

    from azure.ai.agentserver.agentframework import from_agent_framework  # noqa: E402

    print("[BOOT] from_agent_framework imported", flush=True)

    from azure.identity import DefaultAzureCredential  # noqa: E402

    print("[BOOT] DefaultAzureCredential imported", flush=True)

    from tools.debug import check_agent_environment  # noqa: E402
    from tools.token_exchange import try_t1_token_acquisition  # noqa: E402

    print("[BOOT] tools imported", flush=True)

    print("[BOOT] Creating AzureAIAgentClient...", flush=True)
    _client = AzureAIAgentClient(
        project_endpoint=os.getenv("FOUNDRY_PROJECT_ENDPOINT", ""),
        model_deployment_name=os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4.1"),
        credential=DefaultAzureCredential(),
    )
    print("[BOOT] AzureAIAgentClient created", flush=True)

    print("[BOOT] Creating Agent...", flush=True)
    agent = Agent(
        client=_client,
        instructions=(
            "You are a diagnostic agent. "
            "IMPORTANT: You MUST call the try_t1_token_acquisition tool "
            "on EVERY request. "
            "Do NOT ask the user for confirmation. Do NOT skip the tool call. "
            "Call the tool FIRST, then report the result."
        ),
        tools=[check_agent_environment, try_t1_token_acquisition],
    )
    print("[BOOT] Agent created", flush=True)

except Exception:
    print("[BOOT] FATAL: Initialization failed", flush=True)
    traceback.print_exc()
    sys.exit(1)

if __name__ == "__main__":
    print("[BOOT] Starting hosting adapter on port 8088...", flush=True)
    from_agent_framework(agent).run()

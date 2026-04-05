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

    from tools.autonomous_app import call_resource_api_autonomous_app  # noqa: E402
    from tools.debug import check_agent_environment  # noqa: E402
    # from tools.token_exchange import try_t1_token_acquisition  # noqa: E402

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
            "You are a caller agent for Identity Echo API (extrernal resource API) "
            "using Entra Agent ID\n"
            "ALWAYS call a tool immediately. Never reply with text only.\n"
            "Call the tool and report results.\n\n"
            "This agent has the following tools to respond to user requests.\n"
            "Please follow the tool usage instructions and examples "
            "to decide which tool to call for each request:\n\n"
            "1. `call_resource_api_autonomous_app`: call this tool by default\n"
            "    - This tools is used for autonomous agent app flow to call the resource API\n"
            "    - Example: `Please call the resource API using autonomous agent app flow`\n"
            "    - NOTE: This is the default selection for no message from users "
            "or messages without specific keywords\n"
            "2. `check_agent_environment`: call this tool only when recieving user requests, "
            "which are including keywords, such as  'debugging`, `environment`, and `status`\n"
            "    - This tools is used for autonomous agent app flow to call the resource API\n"
            "    - Example: `Please help to check the agent environment and status` \n"
            # "You are a diagnostic agent for Entra Agent ID\n"
            # "ALWAYS call a tool immediately. Never reply with text only.\n"
            # "Select the tool based on the user's request:\n"
            # "- call_resource_api_autonomous_app: for autonomous app flow, resource API calls\n"
            # "- check_agent_environment: for environment checks, debugging, credential status\n"
            # "- try_t1_token_acquisition: for T1 token tests, token exchange experiments\n"
            # "Call the tool and report results.\n"
        ),
        tools=[
            call_resource_api_autonomous_app,
            check_agent_environment,
            # try_t1_token_acquisition,  # This is just for testing Agent ID T1 token acquisition
        ],
    )
    print("[BOOT] Agent created", flush=True)

except Exception:
    print("[BOOT] FATAL: Initialization failed", flush=True)
    traceback.print_exc()
    sys.exit(1)

if __name__ == "__main__":
    print("[BOOT] Starting hosting adapter on port 8088...", flush=True)
    from_agent_framework(agent).run()

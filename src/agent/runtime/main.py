"""Foundry Hosted Agent entry point.

Starts the hosting adapter server on port 8088 (default).
Locally: `python -m agent.main` or `python src/agent/main.py`
Foundry: The container CMD invokes this file directly.
"""

import logging
import os
import sys
import traceback

# Use the same logger namespace as the hosting adapter so output
# appears in ``az cognitiveservices agent logs show`` and App Insights.
logger = logging.getLogger("azure.ai.agentserver.agent")

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
    from tools.autonomous_user import call_resource_api_autonomous_user  # noqa: E402
    from tools.debug import check_agent_environment  # noqa: E402

    # from tools.token_exchange import try_t1_token_acquisition  # noqa: E402

    print("[BOOT] tools imported", flush=True)

    # Build lookup tables for tool dispatch
    _TOOL_FUNCS = [
        call_resource_api_autonomous_app,
        call_resource_api_autonomous_user,
        check_agent_environment,
    ]
    _TOOL_NAMES = {fn.name if hasattr(fn, "name") else fn.__name__ for fn in _TOOL_FUNCS}
    _TOOL_BY_NAME = {(fn.name if hasattr(fn, "name") else fn.__name__): fn for fn in _TOOL_FUNCS}

    class ToolDispatchAgent(Agent):
        """Agent subclass that reads ``force_tool`` from the request metadata
        (set by the hosting adapter as ``_request_headers``) and forces
        the model to call exactly that tool.

        The Hosted Agent adapter sets ``self._request_headers`` from the
        request's ``metadata`` field **before** calling ``run()``, so we can
        read it here reliably.

        Approach: when ``force_tool`` is present, pass ``tools=[forced_tool]``
        to ``super().run()`` so the model only sees a single tool.  Combined
        with instructions that mandate tool calling, this effectively forces
        the desired tool without using ``tool_choice`` (which causes the
        Agents Threads/Runs backend to hang — server-side issue).

        Usage — send ``metadata.force_tool`` in the Responses API request::

            {"input": "...", "metadata": {"force_tool": "check_agent_environment"}}
        """

        def run(
            self, messages=None, *, stream=False, session=None, tools=None, options=None, **kwargs
        ):
            # _request_headers is set by the hosting adapter from request metadata
            force_tool = getattr(self, "_request_headers", {}).get("force_tool")
            logger.info("[DISPATCH] _request_headers=%s", getattr(self, "_request_headers", {}))

            if force_tool and force_tool in _TOOL_NAMES:
                # Restrict default_options["tools"] to just the forced tool.
                # _prepare_session_and_messages() deep-copies default_options at
                # the start of execution, so only THIS request's copy is affected.
                # The Hosted Agent adapter is single-threaded, so mutation is safe.
                self.default_options["tools"] = [_TOOL_BY_NAME[force_tool]]
                logger.info(
                    "[DISPATCH] Restricting tools to [%s] only (single-tool dispatch)",
                    force_tool,
                )
            else:
                # Restore full tool list for non-forced requests
                self.default_options["tools"] = list(_TOOL_FUNCS)
                logger.info("[DISPATCH] Using all tools (auto)")

            return super().run(
                messages,
                stream=stream,
                session=session,
                tools=tools,
                options=options,
                **kwargs,
            )

    print("[BOOT] ToolDispatchAgent defined", flush=True)

    print("[BOOT] Creating AzureAIAgentClient...", flush=True)
    _client = AzureAIAgentClient(
        project_endpoint=os.getenv("FOUNDRY_PROJECT_ENDPOINT", ""),
        model_deployment_name=os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4.1"),
        credential=DefaultAzureCredential(),
    )
    print("[BOOT] AzureAIAgentClient created", flush=True)

    print("[BOOT] Creating Agent...", flush=True)
    agent = ToolDispatchAgent(
        client=_client,
        instructions=(
            "You are a tool caller agent. ALWAYS call exactly one tool per request.\n"
            "Never reply with text only — you must call a tool.\n"
            "\n"
            "## Tool dispatch rules\n"
            "\n"
            "If the user message does NOT start with `TOOL:`, select the tool\n"
            "based on keywords:\n"
            "- Keywords: debug, check, environment, status → call `check_agent_environment`\n"
            "- Everything else (default) → call `call_resource_api_autonomous_app`\n"
            "\n"
            "After calling the tool, report the results to the user.\n"
        ),
        tools=_TOOL_FUNCS,
    )
    print("[BOOT] Agent created", flush=True)

except Exception:
    print("[BOOT] FATAL: Initialization failed", flush=True)
    traceback.print_exc()
    sys.exit(1)

if __name__ == "__main__":
    print("[BOOT] Starting hosting adapter on port 8088...", flush=True)
    from_agent_framework(agent).run()

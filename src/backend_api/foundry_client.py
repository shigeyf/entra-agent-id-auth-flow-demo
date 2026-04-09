"""Foundry Hosted Agent client.

Wraps AIProjectClient + OpenAI Responses API to invoke the Hosted Agent
and extract the result.
"""

import json
import logging
from collections.abc import Iterator

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from backend_api.config import FOUNDRY_AGENT_NAME, FOUNDRY_PROJECT_ENDPOINT

logger = logging.getLogger(__name__)

_credential = DefaultAzureCredential()
_project = AIProjectClient(
    endpoint=FOUNDRY_PROJECT_ENDPOINT,
    credential=_credential,
    allow_preview=True,
)
_openai = _project.get_openai_client()


def invoke_agent(message: str, *, force_tool: str | None = None) -> dict:
    """Send *message* to the Hosted Agent and return the parsed result.

    Returns a dict with ``agent_message`` (LLM text) and optionally
    ``tool_output`` (parsed JSON from function_call_output items).

    If *force_tool* is given it is forwarded as ``metadata.force_tool``
    so that the Hosted Agent restricts available tools to just that one.
    """
    agent = _project.agents.get(agent_name=FOUNDRY_AGENT_NAME)

    extra_body: dict = {
        "agent_reference": {
            "name": agent.name,
            "type": "agent_reference",
        }
    }
    if force_tool:
        extra_body["metadata"] = {"force_tool": force_tool}

    response = _openai.responses.create(
        input=[{"role": "user", "content": message}],
        store=False,
        extra_body=extra_body,
        timeout=180,
    )

    agent_message: str | None = None
    tool_output: dict | None = None

    for item in response.output:
        if item.type == "function_call_output":
            tool_output = _parse_tool_output(item.output)
        elif item.type == "message":
            parts = []
            for c in item.content:
                if hasattr(c, "text"):
                    parts.append(c.text)
            if parts:
                agent_message = "\n".join(parts)

    result: dict = {}
    if tool_output is not None:
        result["tool_output"] = tool_output
    if agent_message is not None:
        result["agent_message"] = agent_message
    return result


def invoke_agent_stream(message: str, *, force_tool: str | None = None) -> Iterator[str]:
    """Send *message* to the Hosted Agent and yield SSE-formatted lines.

    Each yielded string is a complete SSE frame::

        event: <event_type>
        data: <json>

    The OpenAI SDK stream events are relayed as-is so that clients
    consuming the standard Responses API streaming format can parse
    them directly.
    """
    agent = _project.agents.get(agent_name=FOUNDRY_AGENT_NAME)

    extra_body: dict = {
        "agent_reference": {
            "name": agent.name,
            "type": "agent_reference",
        }
    }
    if force_tool:
        extra_body["metadata"] = {"force_tool": force_tool}

    stream = _openai.responses.create(
        input=[{"role": "user", "content": message}],
        store=False,
        stream=True,
        extra_body=extra_body,
        timeout=180,
    )

    for event in stream:
        data = json.dumps(event.model_dump(), default=str, ensure_ascii=False)
        yield f"event: {event.type}\ndata: {data}\n\n"


def _parse_tool_output(raw: str) -> dict | list | str:
    """Best-effort JSON parse of function_call_output."""
    try:
        parsed = json.loads(raw)
        # The agent sometimes double-encodes as a JSON string or list
        if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], str):
            parsed = json.loads(parsed[0])
        elif isinstance(parsed, str):
            parsed = json.loads(parsed)
        return parsed
    except (json.JSONDecodeError, IndexError):
        return raw

"""Demo endpoints — invoke the Hosted Agent for each Entra Agent ID flow."""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend_api.foundry_client import invoke_agent, invoke_agent_stream

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/demo", tags=["demo"])


class AgentRequest(BaseModel):
    message: str = "Call the resource API using the autonomous app flow."
    force_tool: str | None = None


@router.post("/autonomous/app")
def autonomous_app(body: AgentRequest):
    """Invoke the Hosted Agent with the user's message (Autonomous App flow)."""
    try:
        result = invoke_agent(body.message, force_tool=body.force_tool)
    except Exception:
        logger.exception("Failed to invoke Hosted Agent")
        raise HTTPException(status_code=502, detail="Hosted Agent invocation failed") from None
    return result


@router.post("/autonomous/app/stream")
def autonomous_app_stream(body: AgentRequest):
    """Invoke the Hosted Agent and stream SSE events back to the client.

    Events are relayed directly from the OpenAI Responses API streaming
    format so that clients can consume them with any SSE / OpenAI-compatible
    parser.
    """
    return StreamingResponse(
        invoke_agent_stream(body.message, force_tool=body.force_tool),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

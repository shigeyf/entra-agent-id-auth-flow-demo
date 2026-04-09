/**
 * Direct Foundry Agent API client for Interactive OBO flow.
 *
 * Unlike the Autonomous flow (which goes through Backend API),
 * Interactive flow calls Foundry Agent API directly from the browser.
 * CORS confirmed: Access-Control-Allow-Origin: * on services.ai.azure.com.
 */

import type { StreamCallbacks } from "./backendApi";

const foundryProjectEndpoint = import.meta.env.FOUNDRY_PROJECT_ENDPOINT ?? "";
const foundryAgentName =
  import.meta.env.FOUNDRY_AGENT_NAME ?? "demo-entraagtid-agent";

/**
 * Convert cognitiveservices.azure.com → services.ai.azure.com.
 * The agent_reference parameter is only recognized on the services domain.
 */
function toServicesEndpoint(endpoint: string): string {
  return endpoint.replace(
    /\.cognitiveservices\.azure\.com\//,
    ".services.ai.azure.com/",
  );
}

/**
 * Split a token string into metadata-safe chunks (max 500 chars each).
 * Foundry metadata values are limited to 512 chars; we use 500 for safety.
 */
function chunkTc(tc: string, size = 500): Record<string, string> {
  const chunks: Record<string, string> = {};
  for (let i = 0; i < tc.length; i += size) {
    chunks[`user_tc_${Math.floor(i / size)}`] = tc.slice(i, i + size);
  }
  return chunks;
}

/**
 * Invoke the Foundry Hosted Agent directly from the browser (Interactive OBO flow).
 *
 * @param message      - User's message to the agent
 * @param foundryToken - Bearer token for Foundry API (scope: cognitiveservices.azure.com/.default)
 * @param tc           - User's Tc token (aud = Blueprint, for OBO exchange)
 * @param callbacks    - SSE stream callbacks (same interface as backendApi.ts)
 */
export function runInteractiveOboStream(
  message: string,
  foundryToken: string,
  tc: string,
  callbacks: StreamCallbacks,
  forceTool?: string,
): AbortController {
  const controller = new AbortController();
  const ctx = { receivedDelta: false };

  const endpoint = toServicesEndpoint(foundryProjectEndpoint);
  // Build project-scoped Responses API URL
  // services.ai.azure.com uses path-based versioning: /openai/v1/responses
  const url =
    endpoint.replace(/\/$/, "") + "/openai/v1/responses";

  const metadata: Record<string, string> = {
    ...chunkTc(tc),
  };
  if (forceTool) {
    metadata.force_tool = forceTool;
  }

  const body = {
    input: [{ role: "user", content: message }],
    stream: true,
    store: false,
    agent_reference: {
      name: foundryAgentName,
      type: "agent_reference",
    },
    metadata,
  };

  fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${foundryToken}`,
    },
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const text = await response.text();
        callbacks.onError(`Foundry API error: ${response.status} — ${text}`);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        callbacks.onError("ReadableStream not supported");
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse SSE frames: "event: ...\ndata: ...\n\n"
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";

        for (const frame of frames) {
          if (!frame.trim()) continue;

          let eventType = "";
          let data = "";

          for (const line of frame.split("\n")) {
            if (line.startsWith("event: ")) {
              eventType = line.slice(7);
            } else if (line.startsWith("data: ")) {
              data = line.slice(6);
            }
          }

          if (!data) continue;

          try {
            const parsed = JSON.parse(data);
            handleSSEEvent(eventType, parsed, callbacks, ctx);
          } catch {
            // Skip malformed JSON
          }
        }
      }

      callbacks.onComplete();
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        callbacks.onError(err.message ?? String(err));
      }
    });

  return controller;
}

// ---------------------------------------------------------------------------
// SSE event handler — same pattern as backendApi.ts
// ---------------------------------------------------------------------------

interface StreamContext {
  receivedDelta: boolean;
}

function handleSSEEvent(
  eventType: string,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any,
  callbacks: StreamCallbacks,
  ctx: StreamContext,
): void {
  switch (eventType) {
    case "response.output_text.delta":
      if (data.delta) {
        ctx.receivedDelta = true;
        callbacks.onDelta(data.delta);
      }
      break;

    case "response.output_item.done":
      if (data.item?.type === "function_call_output") {
        try {
          let output = JSON.parse(data.item.output);
          if (
            Array.isArray(output) &&
            output.length === 1 &&
            typeof output[0] === "string"
          ) {
            output = JSON.parse(output[0]);
          } else if (typeof output === "string") {
            output = JSON.parse(output);
          }
          callbacks.onToolOutput(output);
        } catch {
          // Not JSON — ignore
        }
      } else if (data.item?.type === "message" && !ctx.receivedDelta) {
        const text = extractTextFromMessageItem(data.item);
        if (text) {
          callbacks.onText(text);
        }
      }
      break;

    case "response.completed":
      if (!ctx.receivedDelta) {
        const text = extractTextFromResponse(data.response);
        if (text) {
          callbacks.onText(text);
        }
      }
      break;
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function extractTextFromMessageItem(item: any): string {
  if (!item?.content) return "";
  const parts: string[] = [];
  for (const c of item.content) {
    if (c.type === "output_text" && c.text) {
      parts.push(c.text);
    } else if (c.text) {
      parts.push(c.text);
    }
  }
  return parts.join("\n");
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function extractTextFromResponse(response: any): string {
  if (!response?.output) return "";
  const parts: string[] = [];
  for (const item of response.output) {
    if (item.type === "message") {
      const text = extractTextFromMessageItem(item);
      if (text) parts.push(text);
    }
  }
  return parts.join("\n");
}

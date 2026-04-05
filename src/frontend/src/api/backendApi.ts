const backendApiUrl =
  import.meta.env.BACKEND_API_URL ?? "http://localhost:8000";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  /** Parsed tool_output from function_call_output events (caller info). */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  toolOutput?: any;
}

export interface StreamCallbacks {
  /** Called when a text delta is received (incremental). */
  onDelta: (text: string) => void;
  /** Called when full text is available (fallback if no deltas were received). */
  onText: (text: string) => void;
  /** Called when the full response is complete. */
  onComplete: () => void;
  /** Called when a function_call_output event carries tool output. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onToolOutput: (output: any) => void;
  /** Called on error. */
  onError: (error: string) => void;
}

/**
 * Invoke the Autonomous App flow via SSE streaming.
 * No auth token is required — Backend API uses its own MSI.
 */
export function runAutonomousAppStream(
  message: string,
  callbacks: StreamCallbacks,
): AbortController {
  const controller = new AbortController();
  const ctx = { receivedDelta: false };

  fetch(`${backendApiUrl}/api/demo/autonomous/app/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const text = await response.text();
        callbacks.onError(`API error: ${response.status} — ${text}`);
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
    // --- Incremental text delta ---
    case "response.output_text.delta":
      if (data.delta) {
        ctx.receivedDelta = true;
        callbacks.onDelta(data.delta);
      }
      break;

    case "response.function_call_arguments.done":
      // function call completed — tool output comes next
      break;

    // --- Output item completed ---
    case "response.output_item.done":
      if (data.item?.type === "function_call_output") {
        // Tool output (token chain data)
        try {
          let output = JSON.parse(data.item.output);
          // Handle double-encoded JSON
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
        // Full message text (fallback when no deltas were received)
        const text = extractTextFromMessageItem(data.item);
        if (text) {
          callbacks.onText(text);
        }
      }
      break;

    // --- Full response completed (final fallback) ---
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

/** Extract text from a message output item. */
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

/** Extract text from the full response object in response.completed. */
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

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  runAutonomousAppStream,
  type ChatMessage,
} from "../api/backendApi";

const DEFAULT_MESSAGE =
  "Please call the resource API using autonomous agent app flow.";

/** Available agent tools for the Autonomous Agent App tab. */
const TOOL_OPTIONS = [
  {
    value: "",
    label: "Auto",
    description: "LLM がメッセージ内容からツールを自動選択",
    defaultMessage: "Please call the resource API using autonomous agent app flow.",
  },
  {
    value: "call_resource_api_autonomous_app",
    label: "Autonomous Agent App",
    description: "Call Identity Echo API with Entra Agent Identity (App)",
    defaultMessage: "Call the resource API using autonomous agent app flow.",
  },
  {
    value: "check_agent_environment",
    label: "Check Environment",
    description: "Check the agent runtime environment and Azure credentials",
    defaultMessage: "Check the agent runtime environment and Azure credentials.",
  },
] as const;

type ToolOptionValue = (typeof TOOL_OPTIONS)[number]["value"];

interface AutonomousChatPanelProps {
  /** Called when tool_output is received from the agent. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onToolOutput?: (output: any) => void;
  /** Called when the SSE stream completes. */
  onStreamComplete?: () => void;
}

const AutonomousChatPanel: React.FC<AutonomousChatPanelProps> = ({
  onToolOutput,
  onStreamComplete,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState(DEFAULT_MESSAGE);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedTool, setSelectedTool] = useState<ToolOptionValue>(
    TOOL_OPTIONS[0].value,  // "" = Auto
  );
  const abortRef = useRef<AbortController | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  // --- Streaming text accumulator ---
  // Accumulate delta text in a ref and flush to React state via rAF
  // to avoid React 18 automatic batching from swallowing individual updates.
  const pendingTextRef = useRef("");
  const rafIdRef = useRef<number>(0);

  const flushPendingText = useCallback(() => {
    const text = pendingTextRef.current;
    if (!text) return;
    pendingTextRef.current = "";
    setMessages((prev) => {
      const updated = [...prev];
      const last = updated[updated.length - 1];
      if (last?.role === "assistant") {
        updated[updated.length - 1] = {
          ...last,
          content: last.content + text,
        };
      }
      return updated;
    });
  }, []);

  const scheduleDeltaFlush = useCallback(
    (text: string) => {
      pendingTextRef.current += text;
      if (!rafIdRef.current) {
        rafIdRef.current = requestAnimationFrame(() => {
          rafIdRef.current = 0;
          flushPendingText();
        });
      }
    },
    [flushPendingText],
  );

  // Clean up rAF on unmount
  useEffect(() => {
    return () => {
      if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current);
    };
  }, []);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || streaming) return;

    setError(null);
    pendingTextRef.current = "";

    // Add user message
    const userMsg: ChatMessage = { role: "user", content: trimmed };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setStreaming(true);

    // Placeholder for assistant — will be mutated via streaming
    const assistantMsg: ChatMessage = { role: "assistant", content: "" };
    setMessages((prev) => [...prev, assistantMsg]);

    const controller = runAutonomousAppStream(
      trimmed,
      {
        onDelta: (text) => {
          scheduleDeltaFlush(text);
        },
      onText: (text) => {
        // Full text fallback — flush any pending, then set full text
        flushPendingText();
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === "assistant") {
            updated[updated.length - 1] = { ...last, content: text };
          }
          return updated;
        });
      },
      onToolOutput: (output) => {
        // Flush any pending text first so tool output appears in order
        flushPendingText();
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === "assistant") {
            updated[updated.length - 1] = { ...last, toolOutput: output };
          }
          return updated;
        });
        onToolOutput?.(output);
      },
      onComplete: () => {
        // Flush remaining text before marking complete
        flushPendingText();
        setStreaming(false);
        onStreamComplete?.();
      },
      onError: (err) => {
        flushPendingText();
        setError(err);
        setStreaming(false);
      },
    },
    selectedTool,
  );

    abortRef.current = controller;
  }, [input, streaming, selectedTool, onToolOutput, onStreamComplete, scheduleDeltaFlush, flushPendingText]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleStop = () => {
    abortRef.current?.abort();
    setStreaming(false);
  };

  return (
    <div className="chat-panel">
      <h3>Autonomous Agent Flow</h3>
      <p className="chat-description">
        Backend API (MSI) → Foundry Hosted Agent (Agent Identity) → Identity Echo API
      </p>

      {/* Tool selection buttons */}
      <div className="tool-selector">
        <span className="tool-selector-label">Tool:</span>
        {TOOL_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            className={`tool-btn ${
              selectedTool === opt.value ? "tool-btn-active" : ""
            }`}
            onClick={() => {
              setSelectedTool(opt.value);
              setInput(opt.defaultMessage);
            }}
            disabled={streaming}
            title={opt.description}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Chat messages */}
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            メッセージを送信して Autonomous Agent Flow を実行します。
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`chat-bubble chat-${msg.role}`}>
            <div className="chat-role">
              {msg.role === "user" ? "You" : "Agent"}
            </div>

            {/* Tool output JSON shown as a code block */}
            {msg.toolOutput && (
              <details className="chat-json-details" open>
                <summary>Tool Output (JSON)</summary>
                <pre className="chat-json">
                  {JSON.stringify(msg.toolOutput, null, 2)}
                </pre>
              </details>
            )}

            <div className="chat-content">
              {msg.content ||
                (msg.role === "assistant" &&
                streaming &&
                i === messages.length - 1 ? (
                  <span className="chat-typing">応答中…</span>
                ) : null)}
            </div>
          </div>
        ))}

        <div ref={chatEndRef} />
      </div>

      {error && <div className="chat-error">エラー: {error}</div>}

      {/* Input area */}
      <div className="chat-input-area">
        <textarea
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="メッセージを入力..."
          rows={2}
          disabled={streaming}
        />
        <div className="chat-actions">
          {streaming ? (
            <button className="btn btn-secondary" onClick={handleStop}>
              停止
            </button>
          ) : (
            <button
              className="btn btn-primary"
              onClick={handleSend}
              disabled={!input.trim()}
            >
              送信
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default AutonomousChatPanel;

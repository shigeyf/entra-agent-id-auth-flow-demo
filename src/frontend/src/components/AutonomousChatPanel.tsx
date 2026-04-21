import React, { useState, useRef, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import {
  runAutonomousAppStream,
  type ChatMessage,
} from "../api/backendApi";

const DEFAULT_MESSAGE =
  "Please call the resource API using autonomous agent app flow.";

/** Available agent tools for the Autonomous Agent tab. */
const TOOL_OPTIONS = [
  {
    value: "",
    labelKey: "chat.auto",
    descriptionKey: "chat.autoDescription",
    defaultMessage: "Please call the resource API using autonomous agent app flow.",
  },
  {
    value: "call_resource_api_autonomous_app",
    labelKey: "autonomousPanel.tools.autonomousApp",
    descriptionKey: "autonomousPanel.tools.autonomousAppDesc",
    defaultMessage: "Call the resource API using autonomous agent app flow.",
  },
  {
    value: "call_resource_api_autonomous_user",
    labelKey: "autonomousPanel.tools.autonomousUser",
    descriptionKey: "autonomousPanel.tools.autonomousUserDesc",
    defaultMessage: "Call the resource API using autonomous agent user flow.",
  },
  {
    value: "check_agent_environment",
    labelKey: "autonomousPanel.tools.checkEnv",
    descriptionKey: "autonomousPanel.tools.checkEnvDesc",
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
  /** Called when the user clears the chat. */
  onClear?: () => void;
}

const AutonomousChatPanel: React.FC<AutonomousChatPanelProps> = ({
  onToolOutput,
  onStreamComplete,
  onClear,
}) => {
  const { t } = useTranslation();
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

  const handleClear = () => {
    setMessages([]);
    setError(null);
    setInput(TOOL_OPTIONS.find((o) => o.value === selectedTool)?.defaultMessage ?? DEFAULT_MESSAGE);
    onClear?.();
  };

  return (
    <div className="chat-panel">
      <div className="chat-panel-header">
        <div>
          <h3>{t("autonomousPanel.heading")}</h3>
          <p className="chat-description">
            {t("autonomousPanel.description")}
          </p>
        </div>
        {messages.length > 0 && !streaming && (
          <button className="btn btn-secondary btn-sm" onClick={handleClear}>
            {t("chat.clear")}
          </button>
        )}
      </div>

      {/* Tool selection buttons */}
      <div className="tool-selector">
        <span className="tool-selector-label">{t("chat.toolLabel")}</span>
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
            title={t(opt.descriptionKey)}
          >
            {t(opt.labelKey)}
          </button>
        ))}
      </div>

      {/* Chat messages */}
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            {t("autonomousPanel.emptyState")}
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`chat-bubble chat-${msg.role}`}>
            <div className="chat-role">
              {msg.role === "user" ? t("chat.you") : t("chat.agent")}
            </div>

            {/* Tool output JSON shown as a code block */}
            {msg.toolOutput && (
              <details className="chat-json-details" open>
                <summary>{t("chat.toolOutputJson")}</summary>
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
                  <span className="chat-typing">
                    {t("chat.responding")}
                    <span className="chat-typing-dots">
                      <span className="chat-typing-dot" />
                      <span className="chat-typing-dot" />
                      <span className="chat-typing-dot" />
                    </span>
                  </span>
                ) : null)}
            </div>
          </div>
        ))}

        <div ref={chatEndRef} />
      </div>

      {error && <div className="chat-error">{t("chat.errorPrefix")} {error}</div>}

      {/* Input area */}
      <div className="chat-input-area">
        <textarea
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t("chat.inputPlaceholder")}
          rows={2}
          disabled={streaming}
        />
        <div className="chat-actions">
          {streaming ? (
            <button className="btn btn-secondary" onClick={handleStop}>
              {t("chat.stop")}
            </button>
          ) : (
            <button
              className="btn btn-primary"
              onClick={handleSend}
              disabled={!input.trim()}
            >
              {t("chat.send")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default AutonomousChatPanel;

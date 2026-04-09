import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  useMsal,
  useIsAuthenticated,
} from "@azure/msal-react";
import {
  BrowserAuthError,
  InteractionRequiredAuthError,
} from "@azure/msal-browser";
import { interactiveOboRequest, foundryApiRequest } from "../authConfig";
import {
  runInteractiveOboStream,
} from "../api/foundryAgentApi";
import type { ChatMessage } from "../api/backendApi";

const TOOL_OPTIONS = [
  {
    value: "",
    label: "Auto",
    description: "LLM がメッセージ内容からツールを自動選択",
    defaultMessage: "Call the resource API using the Interactive OBO flow.",
  },
  {
    value: "call_resource_api_interactive_obo",
    label: "Interactive Agent OBO",
    description: "Call Identity Echo API with Interactive OBO flow (delegated human user)",
    defaultMessage: "Call the resource API using the Interactive OBO flow.",
  },
] as const;

type ToolOptionValue = (typeof TOOL_OPTIONS)[number]["value"];

const DEFAULT_MESSAGE = TOOL_OPTIONS[0].defaultMessage;

interface InteractiveOboPanelProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onToolOutput?: (output: any) => void;
  onStreamComplete?: () => void;
  onClear?: () => void;
}

const InteractiveOboPanel: React.FC<InteractiveOboPanelProps> = ({
  onToolOutput,
  onStreamComplete,
  onClear,
}) => {
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState<string>(DEFAULT_MESSAGE);
  const [streaming, setStreaming] = useState(false);
  const [selectedTool, setSelectedTool] = useState<ToolOptionValue>(
    TOOL_OPTIONS[1].value, // default to explicit Interactive Agent OBO
  );
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  // --- Streaming text accumulator (same pattern as AutonomousChatPanel) ---
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

  useEffect(() => {
    return () => {
      if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current);
    };
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  /**
   * Acquire a token via silent first, falling back to popup.
   */
  const acquireToken = useCallback(
    async (request: { scopes: string[] }) => {
      const account = accounts[0];
      if (!account) throw new Error("No active account — please sign in.");

      try {
        return await instance.acquireTokenSilent({ ...request, account });
      } catch (silentError) {
        const isInteractionRequired =
          silentError instanceof InteractionRequiredAuthError;
        const isTimedOut =
          silentError instanceof BrowserAuthError &&
          silentError.errorCode === "timed_out";
        if (isInteractionRequired || isTimedOut) {
          return await instance.acquireTokenPopup(request);
        }
        throw silentError;
      }
    },
    [instance, accounts],
  );

  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || streaming) return;

    setError(null);
    pendingTextRef.current = "";

    const userMsg: ChatMessage = { role: "user", content: trimmed };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setStreaming(true);

    try {
      // 1. Acquire Tc (aud = Blueprint, scope = access_agent) via popup
      const tcResponse = await acquireToken(interactiveOboRequest);

      // 2. Acquire Foundry API token (cognitiveservices.azure.com/.default) via popup
      const foundryResponse = await acquireToken(foundryApiRequest);

      // 3. Placeholder for assistant
      const assistantMsg: ChatMessage = { role: "assistant", content: "" };
      setMessages((prev) => [...prev, assistantMsg]);

      // 4. Call Foundry Agent API directly with Tc in metadata
      const controller = runInteractiveOboStream(
        trimmed,
        foundryResponse.accessToken,
        tcResponse.accessToken,
        {
          onDelta: (text) => {
            scheduleDeltaFlush(text);
          },
          onText: (text) => {
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
        selectedTool || undefined,
      );

      abortRef.current = controller;
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setError(message);
      setStreaming(false);
    }
  }, [
    input,
    streaming,
    selectedTool,
    acquireToken,
    onToolOutput,
    onStreamComplete,
    scheduleDeltaFlush,
    flushPendingText,
  ]);

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

  if (!isAuthenticated) {
    return (
      <div className="chat-panel">
        <div className="chat-panel-header">
          <div>
            <h3>Interactive Agent (OBO) Flow</h3>
            <p className="chat-description">
              SPA (MSAL login) → Foundry Hosted Agent (OBO exchange) → Identity Echo API
            </p>
          </div>
        </div>
        <div className="auth-section">
          <p>Interactive Agent (OBO) フローを実行するにはサインインしてください。</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-panel">
      <div className="chat-panel-header">
        <div>
          <h3>Interactive Agent (OBO) Flow</h3>
          <p className="chat-description">
            SPA (MSAL login) → Foundry Hosted Agent (Agent Identity On-behalf-of) → Identity Echo API
          </p>
        </div>
        {messages.length > 0 && !streaming && (
          <button className="btn btn-secondary btn-sm" onClick={handleClear}>
            クリア
          </button>
        )}
      </div>

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
            メッセージを送信して Interactive Agent (OBO) Flow を実行します。
            ログインユーザーの委任権限で Agent が Identity Echo API を呼び出します。
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`chat-bubble chat-${msg.role}`}>
            <div className="chat-role">
              {msg.role === "user" ? "You" : "Agent"}
            </div>

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
                  <span className="chat-typing">
                    応答中
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

export default InteractiveOboPanel;

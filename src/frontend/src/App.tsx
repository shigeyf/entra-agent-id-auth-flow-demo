import { useState, useCallback } from "react";
import {
  //useIsAuthenticated,
  useMsal,
  AuthenticatedTemplate,
  UnauthenticatedTemplate,
} from "@azure/msal-react";
import {
  BrowserAuthError,
  InteractionRequiredAuthError,
} from "@azure/msal-browser";
import { loginRequest } from "./authConfig";
import { getCallerInfo } from "./api/identityEchoApi";
import CallerInfo from "./components/CallerInfo";
import TokenChainSteps from "./components/TokenChainSteps";
import { extractCallerInfo, extractTokenChainLogs, isTokenChainData, isTokenChainSuccess } from "./utils/extractAgentToolOutput";
import AutonomousChatPanel from "./components/AutonomousChatPanel";
import "./App.css";

type ScenarioTab = "autonomous-agent" | "identity-echo-debug";

function App() {
  const { instance, accounts } = useMsal();
  //const isAuthenticated = useIsAuthenticated();

  const [activeTab, setActiveTab] = useState<ScenarioTab>("autonomous-agent");

  // Autonomous Agent flow — tool output displayed outside chat panel
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [agentToolOutput, setAgentToolOutput] = useState<any | null>(null);
  const [streamCompleted, setStreamCompleted] = useState(false);

  const handleToolOutput = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (output: any) => {
      setAgentToolOutput(output);
      // Reset stream completed when new output arrives (new stream started)
      setStreamCompleted(false);
    },
    [],
  );

  const handleStreamComplete = useCallback(() => {
    setStreamCompleted(true);
  }, []);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [callerData, setCallerData] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = useCallback(async () => {
    try {
      await instance.loginRedirect(loginRequest);
    } catch (e) {
      console.error("Login failed:", e);
    }
  }, [instance]);

  const handleLogout = useCallback(async () => {
    try {
      await instance.logoutRedirect();
      setCallerData(null);
      setError(null);
    } catch (e) {
      console.error("Logout failed:", e);
    }
  }, [instance]);

  const handleCallApi = useCallback(async () => {
    setLoading(true);
    setError(null);
    setCallerData(null);

    try {
      const account = accounts[0];
      if (!account) {
        throw new Error("No active account");
      }

      let tokenResponse;
      try {
        tokenResponse = await instance.acquireTokenSilent({
          ...loginRequest,
          account,
        });
      } catch (silentError) {
        const isInteractionRequired =
          silentError instanceof InteractionRequiredAuthError;
        const isTimedOut =
          silentError instanceof BrowserAuthError &&
          silentError.errorCode === "timed_out";
        if (isInteractionRequired || isTimedOut) {
          tokenResponse = await instance.acquireTokenPopup(loginRequest);
        } else {
          throw silentError;
        }
      }

      const data = await getCallerInfo(tokenResponse.accessToken);
      setCallerData(data);
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [instance, accounts]);

  return (
    <div className="app">
      <header>
        <h1>Entra Agent ID Demo</h1>
        <p className="subtitle">Entra Agent ID の認証フローを可視化</p>
      </header>

      <main>
        {/* Scenario tabs */}
        <nav className="scenario-tabs">
          <button
            className={`tab ${activeTab === "autonomous-agent" ? "active" : ""}`}
            onClick={() => setActiveTab("autonomous-agent")}
          >
            [Entra Agent ID] Autonomous Agent Flow
          </button>
          <button
            className={`tab ${activeTab === "identity-echo-debug" ? "active" : ""}`}
            onClick={() => setActiveTab("identity-echo-debug")}
          >
            [No Entra Agent ID] Identity Echo (Debug)
          </button>
        </nav>

        {/* Autonomous App Flow — no login required */}
        {activeTab === "autonomous-agent" && (
          <>
            <AutonomousChatPanel
              onToolOutput={handleToolOutput}
              onStreamComplete={handleStreamComplete}
            />

            {/* Token chain + CallerInfo — always show frame, accordion closed by default */}
            <div className="agent-result-section">
              <details className="result-accordion">
                <summary>
                  <span className="result-accordion-title">Token Chain Flow</span>
                  {isTokenChainSuccess(agentToolOutput) ? (
                    <span className="result-accordion-badge badge-ready">取得済み</span>
                  ) : isTokenChainData(agentToolOutput) ? (
                    <span className="result-accordion-badge badge-error">一部失敗</span>
                  ) : streamCompleted && !isTokenChainData(agentToolOutput) ? (
                    <span className="result-accordion-badge badge-error">未実行</span>
                  ) : (
                    <span className="result-accordion-badge badge-pending">未取得</span>
                  )}
                </summary>
                <div className="result-accordion-body">
                  {isTokenChainData(agentToolOutput) ? (
                    <TokenChainSteps data={extractTokenChainLogs(agentToolOutput)} />
                  ) : streamCompleted && !isTokenChainData(agentToolOutput) ? (
                    <div className="result-error">
                      エージェントの応答に Token Chain データが含まれていませんでした。クエリ内容を確認してください。
                    </div>
                  ) : (
                    <div className="result-placeholder">
                      エージェントが Autonomous Agent Flow を実行すると、Token Chain の結果がここに表示されます。
                    </div>
                  )}
                </div>
              </details>

              <details className="result-accordion">
                <summary>
                  <span className="result-accordion-title">リソース API レスポンス</span>
                  {extractCallerInfo(agentToolOutput) ? (
                    <span className="result-accordion-badge badge-ready">取得済み</span>
                  ) : isTokenChainData(agentToolOutput) && !extractCallerInfo(agentToolOutput) ? (
                    <span className="result-accordion-badge badge-error">取得失敗</span>
                  ) : streamCompleted && !extractCallerInfo(agentToolOutput) ? (
                    <span className="result-accordion-badge badge-error">未実行</span>
                  ) : (
                    <span className="result-accordion-badge badge-pending">未取得</span>
                  )}
                </summary>
                <div className="result-accordion-body">
                  {extractCallerInfo(agentToolOutput) ? (
                    <CallerInfo
                      data={extractCallerInfo(agentToolOutput)}
                      loading={false}
                      error={null}
                    />
                  ) : isTokenChainData(agentToolOutput) && !extractCallerInfo(agentToolOutput) ? (
                    <div className="result-error">
                      Identity Echo API のレスポンスを取得できませんでした。Token Chain Flow の Step 3 を確認してください。
                    </div>
                  ) : streamCompleted ? (
                    <div className="result-error">
                      エージェントの応答にリソース API のレスポンスが含まれていませんでした。クエリ内容を確認してください。
                    </div>
                  ) : (
                    <div className="result-placeholder">
                      エージェントが Autonomous Agent Flow を実行すると、リソース API のレスポンスがここに表示されます。
                    </div>
                  )}
                </div>
              </details>
            </div>
          </>
        )}

        {/* Identity Echo Debug — requires login */}
        {activeTab === "identity-echo-debug" && (
          <>
            <UnauthenticatedTemplate>
              <div className="auth-section">
                <p>Identity Echo API を呼び出すにはログインしてください。</p>
                <button onClick={handleLogin} className="btn btn-primary">
                  ログイン
                </button>
              </div>
            </UnauthenticatedTemplate>

            <AuthenticatedTemplate>
              <div className="auth-section">
                <p>
                  ログイン中: <strong>{accounts[0]?.username}</strong>
                </p>
                <div className="button-group">
                  <button
                    onClick={handleCallApi}
                    disabled={loading}
                    className="btn btn-primary"
                  >
                    {loading ? "呼び出し中..." : "Identity Echo API を呼び出す"}
                  </button>
                  <button onClick={handleLogout} className="btn btn-secondary">
                    ログアウト
                  </button>
                </div>
              </div>

              <CallerInfo data={callerData} loading={loading} error={error} />
            </AuthenticatedTemplate>
          </>
        )}
      </main>
    </div>
  );
}

export default App;

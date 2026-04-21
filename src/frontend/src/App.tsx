import { useState, useCallback } from "react";
import {
  useMsal,
  useIsAuthenticated,
} from "@azure/msal-react";
import {
  BrowserAuthError,
  InteractionRequiredAuthError,
} from "@azure/msal-browser";
import { useTranslation } from "react-i18next";
import { loginRequest } from "./authConfig";
import { getCallerInfo } from "./api/identityEchoApi";
import CallerInfo from "./components/CallerInfo";
import TokenChainSteps from "./components/TokenChainSteps";
import { extractCallerInfo, extractTokenChainLogs, isTokenChainData, isTokenChainSuccess, getCallerType, callerTypeCssClass } from "./utils/extractAgentToolOutput";
import AutonomousChatPanel from "./components/AutonomousChatPanel";
import InteractiveOboPanel from "./components/InteractiveOboPanel";
import TopBar from "./components/TopBar";
import "./App.css";

type ScenarioTab = "autonomous-agent" | "interactive-obo" | "no-agent";

function App() {
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const { t } = useTranslation();

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

  const handleClear = useCallback(() => {
    setAgentToolOutput(null);
    setStreamCompleted(false);
  }, []);

  // Interactive OBO flow — separate state
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [oboToolOutput, setOboToolOutput] = useState<any | null>(null);
  const [oboStreamCompleted, setOboStreamCompleted] = useState(false);

  const handleOboToolOutput = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (output: any) => {
      setOboToolOutput(output);
      setOboStreamCompleted(false);
    },
    [],
  );

  const handleOboStreamComplete = useCallback(() => {
    setOboStreamCompleted(true);
  }, []);

  const handleOboClear = useCallback(() => {
    setOboToolOutput(null);
    setOboStreamCompleted(false);
  }, []);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [callerData, setCallerData] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      <TopBar />

      <header>
        <h1>{t("app.heading")}</h1>
        <p className="subtitle">
          {t("app.subtitle")}
        </p>
      </header>
      <main>
        {/* Scenario tabs */}
        <nav className="scenario-tabs">
          <button
            className={`tab ${activeTab === "autonomous-agent" ? "active" : ""}`}
            onClick={() => setActiveTab("autonomous-agent")}
          >
            {t("app.tabs.autonomousAgent")}
          </button>
          <button
            className={`tab ${activeTab === "interactive-obo" ? "active" : ""}`}
            onClick={() => setActiveTab("interactive-obo")}
          >
            {t("app.tabs.interactiveObo")}
          </button>
          <button
            className={`tab ${activeTab === "no-agent" ? "active" : ""}`}
            onClick={() => setActiveTab("no-agent")}
          >
            {t("app.tabs.noAgent")}
          </button>
        </nav>

        {/* Autonomous App Flow — no login required */}
        <div style={{ display: activeTab === "autonomous-agent" ? undefined : "none" }}>
            {/* CallerInfo + Token chain — always show frame, accordion closed by default */}
            <div className="agent-result-section">
              <details className="result-accordion">
                <summary>
                  <span className="result-accordion-title">{t("app.resourceApiResponse")}</span>
                  {extractCallerInfo(agentToolOutput) ? (
                    <span className="result-accordion-badge badge-ready">
                      {t("app.badges.ready")}
                      {getCallerType(extractCallerInfo(agentToolOutput), accounts[0]?.username) && (
                        <span className={`badge-caller-type ${callerTypeCssClass(getCallerType(extractCallerInfo(agentToolOutput), accounts[0]?.username))}`}>{getCallerType(extractCallerInfo(agentToolOutput), accounts[0]?.username)}</span>
                      )}
                    </span>
                  ) : isTokenChainData(agentToolOutput) && !extractCallerInfo(agentToolOutput) ? (
                    <span className="result-accordion-badge badge-error">{t("app.badges.error")}</span>
                  ) : streamCompleted && !extractCallerInfo(agentToolOutput) ? (
                    <span className="result-accordion-badge badge-error">{t("app.badges.notExecuted")}</span>
                  ) : (
                    <span className="result-accordion-badge badge-pending">{t("app.badges.pending")}</span>
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
                      {t("app.autonomous.noCallerInfo")}
                    </div>
                  ) : streamCompleted ? (
                    <div className="result-error">
                      {t("app.autonomous.noResourceApi")}
                    </div>
                  ) : (
                    <div className="result-placeholder">
                      {t("app.autonomous.placeholder")}
                    </div>
                  )}
                </div>
              </details>
              <details className="result-accordion">
                <summary>
                  <span className="result-accordion-title">{t("app.tokenChainFlow")}</span>
                  {isTokenChainSuccess(agentToolOutput) ? (
                    <span className="result-accordion-badge badge-ready">{t("app.badges.ready")}</span>
                  ) : isTokenChainData(agentToolOutput) ? (
                    <span className="result-accordion-badge badge-error">{t("app.badges.partialFailure")}</span>
                  ) : streamCompleted && !isTokenChainData(agentToolOutput) ? (
                    <span className="result-accordion-badge badge-error">{t("app.badges.notExecuted")}</span>
                  ) : (
                    <span className="result-accordion-badge badge-pending">{t("app.badges.pending")}</span>
                  )}
                </summary>
                <div className="result-accordion-body">
                  {isTokenChainData(agentToolOutput) ? (
                    <TokenChainSteps data={extractTokenChainLogs(agentToolOutput)} />
                  ) : streamCompleted && !isTokenChainData(agentToolOutput) ? (
                    <div className="result-error">
                      {t("app.autonomous.noTokenChain")}
                    </div>
                  ) : (
                    <div className="result-placeholder">
                      {t("app.autonomous.tokenChainPlaceholder")}
                    </div>
                  )}
                </div>
              </details>
            </div>

            <AutonomousChatPanel
              onToolOutput={handleToolOutput}
              onStreamComplete={handleStreamComplete}
              onClear={handleClear}
            />
        </div>

        {/* Interactive OBO Flow — requires login */}
        <div style={{ display: activeTab === "interactive-obo" ? undefined : "none" }}>
            <div className="agent-result-section">
              <details className="result-accordion">
                <summary>
                  <span className="result-accordion-title">{t("app.resourceApiResponse")}</span>
                  {extractCallerInfo(oboToolOutput) ? (
                    <span className="result-accordion-badge badge-ready">
                      {t("app.badges.ready")}
                      {getCallerType(extractCallerInfo(oboToolOutput), accounts[0]?.username) && (
                        <span className={`badge-caller-type ${callerTypeCssClass(getCallerType(extractCallerInfo(oboToolOutput), accounts[0]?.username))}`}>{getCallerType(extractCallerInfo(oboToolOutput), accounts[0]?.username)}</span>
                      )}
                    </span>
                  ) : isTokenChainData(oboToolOutput) && !extractCallerInfo(oboToolOutput) ? (
                    <span className="result-accordion-badge badge-error">{t("app.badges.error")}</span>
                  ) : oboStreamCompleted && !extractCallerInfo(oboToolOutput) ? (
                    <span className="result-accordion-badge badge-error">{t("app.badges.notExecuted")}</span>
                  ) : (
                    <span className="result-accordion-badge badge-pending">{t("app.badges.pending")}</span>
                  )}
                </summary>
                <div className="result-accordion-body">
                  {extractCallerInfo(oboToolOutput) ? (
                    <CallerInfo
                      data={extractCallerInfo(oboToolOutput)}
                      loading={false}
                      error={null}
                    />
                  ) : isTokenChainData(oboToolOutput) && !extractCallerInfo(oboToolOutput) ? (
                    <div className="result-error">
                      {t("app.obo.noCallerInfo")}
                    </div>
                  ) : oboStreamCompleted ? (
                    <div className="result-error">
                      {t("app.obo.noResourceApi")}
                    </div>
                  ) : (
                    <div className="result-placeholder">
                      {t("app.obo.placeholder")}
                    </div>
                  )}
                </div>
              </details>
              <details className="result-accordion">
                <summary>
                  <span className="result-accordion-title">{t("app.tokenChainFlow")}</span>
                  {isTokenChainSuccess(oboToolOutput) ? (
                    <span className="result-accordion-badge badge-ready">{t("app.badges.ready")}</span>
                  ) : isTokenChainData(oboToolOutput) ? (
                    <span className="result-accordion-badge badge-error">{t("app.badges.partialFailure")}</span>
                  ) : oboStreamCompleted && !isTokenChainData(oboToolOutput) ? (
                    <span className="result-accordion-badge badge-error">{t("app.badges.notExecuted")}</span>
                  ) : (
                    <span className="result-accordion-badge badge-pending">{t("app.badges.pending")}</span>
                  )}
                </summary>
                <div className="result-accordion-body">
                  {isTokenChainData(oboToolOutput) ? (
                    <TokenChainSteps data={extractTokenChainLogs(oboToolOutput)} />
                  ) : oboStreamCompleted && !isTokenChainData(oboToolOutput) ? (
                    <div className="result-error">
                      {t("app.obo.noTokenChain")}
                    </div>
                  ) : (
                    <div className="result-placeholder">
                      {t("app.obo.tokenChainPlaceholder")}
                    </div>
                  )}
                </div>
              </details>
            </div>

            <InteractiveOboPanel
              onToolOutput={handleOboToolOutput}
              onStreamComplete={handleOboStreamComplete}
              onClear={handleOboClear}
            />
        </div>

        {/* Identity Echo Debug — requires login */}
        <div style={{ display: activeTab === "no-agent" ? undefined : "none" }}>
            {!isAuthenticated ? (
              <div className="auth-section">
                <p>{t("app.noAgent.signInRequired")}</p>
              </div>
            ) : (
              <>
                <div className="auth-section">
                  <p>
                    {t("app.noAgent.loggedInAs")} <strong>{accounts[0]?.username}</strong>
                  </p>
                  <div className="button-group">
                    <button
                      onClick={handleCallApi}
                      disabled={loading}
                      className="btn btn-primary"
                    >
                      {loading ? t("app.noAgent.calling") : t("app.noAgent.callApi")}
                    </button>
                  </div>
                </div>

                <details className="result-accordion" open={!!callerData || !!error}>
                  <summary>
                    <span className="result-accordion-title">{t("app.resourceApiResponse")}</span>
                    {callerData ? (
                      <span className="result-accordion-badge badge-ready">
                        {t("app.badges.ready")}
                        {getCallerType(callerData, accounts[0]?.username) && (
                          <span className={`badge-caller-type ${callerTypeCssClass(getCallerType(callerData, accounts[0]?.username))}`}>{getCallerType(callerData, accounts[0]?.username)}</span>
                        )}
                      </span>
                    ) : error ? (
                      <span className="result-accordion-badge badge-error">{t("app.badges.error")}</span>
                    ) : loading ? (
                      <span className="result-accordion-badge badge-pending">{t("app.badges.fetching")}</span>
                    ) : (
                      <span className="result-accordion-badge badge-pending">{t("app.badges.pending")}</span>
                    )}
                  </summary>
                  <div className="result-accordion-body">
                    {loading ? (
                      <div className="result-placeholder">{t("app.noAgent.loading")}</div>
                    ) : error ? (
                      <div className="result-error">{t("app.noAgent.errorPrefix")} {error}</div>
                    ) : callerData ? (
                      <CallerInfo data={callerData} loading={false} error={null} />
                    ) : (
                      <div className="result-placeholder">
                        {t("app.noAgent.placeholder")}
                      </div>
                    )}
                  </div>
                </details>
              </>
            )}
        </div>
      </main>
    </div>
  );
}

export default App;

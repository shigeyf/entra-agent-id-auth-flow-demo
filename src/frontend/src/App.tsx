import { useState, useCallback } from "react";
import {
  //useIsAuthenticated,
  useMsal,
  AuthenticatedTemplate,
  UnauthenticatedTemplate,
} from "@azure/msal-react";
import { InteractionRequiredAuthError } from "@azure/msal-browser";
import { loginRequest } from "./authConfig";
import { getCallerInfo } from "./api/identityEchoApi";
import CallerInfo from "./components/CallerInfo";
import "./App.css";

function App() {
  const { instance, accounts } = useMsal();
  //const isAuthenticated = useIsAuthenticated();

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
        if (silentError instanceof InteractionRequiredAuthError) {
          await instance.acquireTokenRedirect(loginRequest);
          return;
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
        <p className="subtitle">Phase 1: SPA + Identity Echo API</p>
      </header>

      <main>
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
      </main>
    </div>
  );
}

export default App;

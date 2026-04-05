import React from "react";

interface StepResult {
  success: boolean;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  claims?: Record<string, any> | null;
  error?: string;
  error_description?: string;
  status_code?: number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  body?: any;
}

interface TokenChainData {
  step1_get_t1?: StepResult;
  step2_exchange_app_token?: StepResult;
  step3_call_resource_api?: StepResult;
}

interface TokenChainStepsProps {
  data: TokenChainData;
}

const stepLabels: Record<string, { label: string; description: string }> = {
  step1_get_t1: {
    label: "T1 取得",
    description: "Project MSI → Agent Identity Token (T1)",
  },
  step2_exchange_app_token: {
    label: "TR 取得",
    description: "T1 → Resource Token (TR) via client_credentials",
  },
  step3_call_resource_api: {
    label: "API 呼び出し",
    description: "Identity Echo API に Bearer TR でアクセス",
  },
};

const TokenChainSteps: React.FC<TokenChainStepsProps> = ({ data }) => {
  const steps = [
    "step1_get_t1",
    "step2_exchange_app_token",
    "step3_call_resource_api",
  ] as const;

  return (
    <div className="token-chain">
      <h4>Token Chain Flow</h4>
      <div className="token-chain-steps">
        {steps.map((key, i) => {
          const step = data[key];
          if (!step) return null;
          const meta = stepLabels[key];

          return (
            <div key={key} className="token-chain-step">
              <div className="step-header">
                <span className={`step-indicator ${step.success ? "success" : "failure"}`}>
                  {step.success ? "✓" : "✗"}
                </span>
                <span className="step-number">Step {i + 1}</span>
                <span className="step-label">{meta.label}</span>
              </div>
              <div className="step-description">{meta.description}</div>
              {step.claims && (
                <div className="step-claims">
                  <table>
                    <tbody>
                      {Object.entries(step.claims).map(([k, v]) => (
                        <tr key={k}>
                          <th>{k}</th>
                          <td>
                            <code>
                              {typeof v === "object" ? JSON.stringify(v) : String(v ?? "—")}
                            </code>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {step.error && (
                <div className="step-error">
                  {step.error}
                  {step.error_description && (
                    <span>: {step.error_description}</span>
                  )}
                </div>
              )}
              {/* Connector arrow between steps */}
              {i < steps.length - 1 && <div className="step-connector">↓</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default TokenChainSteps;

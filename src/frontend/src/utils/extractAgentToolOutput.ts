/** Extract the Identity Echo API response body from the agent's tool output. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function extractCallerInfo(toolOutput: any): any | null {
  // New format: outputs contains the caller info directly
  if (toolOutput?.outputs?.caller) {
    return toolOutput.outputs;
  }
  // Autonomous User flow (step4)
  const body4 = toolOutput?.step4_call_resource_api?.body;
  if (body4?.caller) {
    return body4;
  }
  // Autonomous App flow (step3)
  const body3 = toolOutput?.step3_call_resource_api?.body;
  if (body3?.caller) {
    return body3;
  }
  return null;
}

/** Extract the token chain logs from the agent's tool output. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function extractTokenChainLogs(toolOutput: any): any | null {
  // New format: logs contains the token chain data
  if (toolOutput?.logs) {
    return toolOutput.logs;
  }
  // Legacy: step keys at top level
  if (hasStepKeys(toolOutput)) {
    return toolOutput;
  }
  return null;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function hasStepKeys(obj: any): boolean {
  if (!obj || typeof obj !== "object") return false;
  return (
    "step1_get_t1" in obj ||
    "step2_exchange_app_token" in obj ||
    "step3_call_resource_api" in obj ||
    // Autonomous User flow keys
    "step2_exchange_user_t2" in obj ||
    "step3_exchange_user_token" in obj ||
    "step4_call_resource_api" in obj
  );
}

export type CallerType = "Human User" | "Agent User" | "Agent Application";

/**
 * Determine the caller type from the Identity Echo API response.
 * - "Human User"        — delegated token whose UPN matches the logged-in user
 * - "Agent User"         — delegated token whose UPN differs from the logged-in user (OBO)
 * - "Agent Application"  — app_only token (client credentials)
 *
 * @param callerData  Identity Echo API response body
 * @param loginUpn    UPN of the currently logged-in user (accounts[0].username)
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function getCallerType(callerData: any, loginUpn?: string): CallerType | null {
  const tokenKind = callerData?.caller?.tokenKind;
  if (!tokenKind) return null;
  if (tokenKind === "app_only") return "Agent Application";
  // delegated — compare UPN
  const callerUpn = (callerData?.caller?.upn ?? "").toLowerCase();
  const currentUpn = (loginUpn ?? "").toLowerCase();
  if (currentUpn && callerUpn === currentUpn) return "Human User";
  if (currentUpn && callerUpn !== currentUpn) return "Agent User";
  // loginUpn not available — fall back to unknown delegated
  return callerUpn ? "Human User" : null;
}

/** Return a CSS modifier class for the caller type badge. */
export function callerTypeCssClass(type: CallerType | null): string {
  switch (type) {
    case "Human User":        return "badge-caller-human";
    case "Agent User":         return "badge-caller-agent";
    case "Agent Application":  return "badge-caller-app";
    default:                   return "";
  }
}

/** Check if the tool output contains token chain data (step1/step2/step3). */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function isTokenChainData(toolOutput: any): boolean {
  return extractTokenChainLogs(toolOutput) !== null;
}

/** Check if all steps in the token chain succeeded. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function isTokenChainSuccess(toolOutput: any): boolean {
  const logs = extractTokenChainLogs(toolOutput);
  if (!logs) return false;

  // Autonomous User flow (4 steps)
  if (logs.step2_exchange_user_t2) {
    return (
      logs.step1_get_t1?.success === true &&
      logs.step2_exchange_user_t2?.success === true &&
      logs.step3_exchange_user_token?.success === true &&
      logs.step4_call_resource_api?.success === true
    );
  }

  // Autonomous App flow (3 steps)
  return (
    logs.step1_get_t1?.success === true &&
    logs.step2_exchange_app_token?.success === true &&
    logs.step3_call_resource_api?.success === true
  );
}

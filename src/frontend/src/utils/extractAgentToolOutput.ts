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

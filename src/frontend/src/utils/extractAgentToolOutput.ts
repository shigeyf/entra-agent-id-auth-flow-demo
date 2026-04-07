/** Extract the Identity Echo API response body from the agent's tool output. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function extractCallerInfo(toolOutput: any): any | null {
  // New format: outputs contains the caller info directly
  if (toolOutput?.outputs?.caller) {
    return toolOutput.outputs;
  }
  // Legacy format
  const body = toolOutput?.step3_call_resource_api?.body;
  if (body?.caller) {
    return body;
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
    "step3_call_resource_api" in obj
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
  return (
    logs.step1_get_t1?.success === true &&
    logs.step2_exchange_app_token?.success === true &&
    logs.step3_call_resource_api?.success === true
  );
}

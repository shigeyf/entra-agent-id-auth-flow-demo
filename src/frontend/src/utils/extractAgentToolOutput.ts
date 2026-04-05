/** Extract the Identity Echo API response body from the agent's tool output. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function extractCallerInfo(toolOutput: any): any | null {
  return toolOutput?.step3_call_resource_api?.body ?? null;
}

/** Check if the tool output contains token chain data (step1/step2/step3). */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function isTokenChainData(toolOutput: any): boolean {
  if (!toolOutput || typeof toolOutput !== "object") return false;
  return (
    "step1_get_t1" in toolOutput ||
    "step2_exchange_app_token" in toolOutput ||
    "step3_call_resource_api" in toolOutput
  );
}

/** Check if all steps in the token chain succeeded. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function isTokenChainSuccess(toolOutput: any): boolean {
  if (!isTokenChainData(toolOutput)) return false;
  return (
    toolOutput.step1_get_t1?.success === true &&
    toolOutput.step2_exchange_app_token?.success === true &&
    toolOutput.step3_call_resource_api?.success === true
  );
}

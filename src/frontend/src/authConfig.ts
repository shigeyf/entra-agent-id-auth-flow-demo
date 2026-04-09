import { type Configuration, LogLevel } from "@azure/msal-browser";

const msalClientId = import.meta.env.ENTRA_SPA_APP_CLIENT_ID ?? "";
const msalTenantId = import.meta.env.ENTRA_TENANT_ID ?? "";

export const msalConfig: Configuration = {
  auth: {
    clientId: msalClientId,
    authority: `https://login.microsoftonline.com/${msalTenantId}`,
    redirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: "sessionStorage",
  },
  system: {
    loggerOptions: {
      logLevel: LogLevel.Warning,
    },
  },
};

export const resourceApiScope =
  import.meta.env.ENTRA_RESOURCE_API_SCOPE ??
  `api://${import.meta.env.ENTRA_RESOURCE_API_CLIENT_ID}/CallerIdentity.Read`;

export const loginRequest = {
  scopes: [resourceApiScope],
};

// --- Interactive Agent OBO flow ---

/** Blueprint scope — used to acquire Tc (user token for OBO exchange). */
const blueprintClientId =
  import.meta.env.ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID ?? "";

export const blueprintScope = blueprintClientId
  ? `api://${blueprintClientId}/access_agent`
  : "";

export const interactiveOboRequest = {
  scopes: [blueprintScope].filter(Boolean),
};

/** Foundry API scope — used to call the Foundry Agent API directly from the SPA.
 * The services.ai.azure.com endpoint expects aud=https://ai.azure.com */
export const foundryApiScope = "https://ai.azure.com/.default";

export const foundryApiRequest = {
  scopes: [foundryApiScope],
};

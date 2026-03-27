import { type Configuration, LogLevel } from "@azure/msal-browser";

const msalClientId = import.meta.env.VITE_MSAL_CLIENT_ID ?? "";
const msalTenantId = import.meta.env.VITE_MSAL_TENANT_ID ?? "";

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
  import.meta.env.VITE_RESOURCE_API_SCOPE ??
  `api://${import.meta.env.VITE_RESOURCE_API_CLIENT_ID}/CallerIdentity.Read`;

export const loginRequest = {
  scopes: [resourceApiScope],
};

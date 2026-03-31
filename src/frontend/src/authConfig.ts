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

/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_MSAL_CLIENT_ID: string;
  readonly VITE_MSAL_TENANT_ID: string;
  readonly VITE_RESOURCE_API_CLIENT_ID: string;
  readonly VITE_RESOURCE_API_URL: string;
  readonly VITE_RESOURCE_API_SCOPE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

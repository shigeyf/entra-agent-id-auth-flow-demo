/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly ENTRA_TENANT_ID: string;
  readonly ENTRA_SPA_APP_CLIENT_ID: string;
  readonly ENTRA_RESOURCE_API_CLIENT_ID: string;
  readonly ENTRA_RESOURCE_API_SCOPE?: string;
  readonly RESOURCE_API_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

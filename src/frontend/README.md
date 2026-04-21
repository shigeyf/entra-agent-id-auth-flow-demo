# Frontend SPA

[English](./README.md) | [日本語](./README.ja.md)

The frontend for the Entra Agent ID demo app. A SPA built with React + TypeScript + Vite,
providing Entra ID authentication via MSAL.js and a UI for the three Agent flows.

## Tech Stack

| Technology   | Version |
| ------------ | ------- |
| React        | 19      |
| TypeScript   | 5.9     |
| Vite         | 8       |
| MSAL Browser | 5.6     |
| MSAL React   | 5.1     |

## Directory Structure

```text
src/frontend/
├── index.html                  # Entry point
├── vite.config.ts              # Vite config (envDir, envPrefix)
├── package.json
├── scripts/
│   └── deploy-swa.py           # Azure Static Web Apps deploy script
├── public/                     # Static assets
└── src/
    ├── main.tsx                # React root (MsalProvider)
    ├── App.tsx                 # Main component (tab routing)
    ├── authConfig.ts           # MSAL configuration & scope definitions
    ├── api/
    │   ├── identityEchoApi.ts  # Identity Echo API client
    │   ├── backendApi.ts       # Backend API client (SSE support)
    │   └── foundryAgentApi.ts  # Foundry Agent API direct call (Interactive OBO)
    ├── components/
    │   ├── TopBar.tsx              # Login/logout UI
    │   ├── AutonomousChatPanel.tsx # Autonomous flow chat UI
    │   ├── InteractiveOboPanel.tsx # Interactive OBO flow chat UI
    │   ├── CallerInfo.tsx          # Identity Echo API response display
    │   └── TokenChainSteps.tsx     # Token exchange flow visualization
    └── utils/
        └── extractAgentToolOutput.ts  # Agent output parser
```

## UI Tabs

| Tab                         | Flow            | Auth required  | API call path                              |
| --------------------------- | --------------- | -------------- | ------------------------------------------ |
| **Autonomous Agent Flow**   | Autonomous      | No             | SPA → Backend API → Foundry → Resource API |
| **Interactive Agent (OBO)** | Interactive OBO | Login required | SPA → Foundry Agent API → Resource API     |
| **No Agent Flow**           | Direct call     | Login required | SPA → Resource API                         |

## Environment Variables

Vite embeds environment variables at build time. `vite.config.ts` specifies `envDir: '../'` (`src/`),
and `envPrefix` exposes only variables with the following prefixes:

```typescript
envPrefix: ["ENTRA_", "RESOURCE_API_", "FOUNDRY_", "BACKEND_"];
```

| Variable                                   | Purpose                          |
| ------------------------------------------ | -------------------------------- |
| `ENTRA_TENANT_ID`                          | MSAL tenant configuration        |
| `ENTRA_SPA_APP_CLIENT_ID`                  | MSAL client ID                   |
| `ENTRA_RESOURCE_API_CLIENT_ID`             | Resource API audience            |
| `ENTRA_RESOURCE_API_SCOPE`                 | Scope for token requests         |
| `ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID` | Blueprint Client ID for OBO flow |
| `RESOURCE_API_URL`                         | Identity Echo API URL            |
| `BACKEND_API_URL`                          | Backend API URL                  |
| `FOUNDRY_PROJECT_ENDPOINT`                 | Foundry API endpoint             |

## MSAL Authentication

- **Cache**: `sessionStorage`
- **Authority**: `https://login.microsoftonline.com/{ENTRA_TENANT_ID}`
- **Token acquisition**: `acquireTokenSilent()` → fallback to `acquireTokenPopup()`

## Local Development

```bash
cd src/frontend
npm install
npm run dev
```

The Vite dev server starts at `http://localhost:5173`.

## npm Scripts

| Command          | Description              |
| ---------------- | ------------------------ |
| `npm run dev`    | Start dev server (HMR)   |
| `npm run build`  | TypeScript check + build |
| `npm run lint`   | Run ESLint               |
| `npm run format` | Run Prettier             |

## Deployment

Deploy to Azure Static Web Apps:

```bash
python src/frontend/scripts/deploy-swa.py
```

See [docs/deployment.md](../../docs/deployment.md) for details.

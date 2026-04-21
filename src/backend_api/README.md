# Backend API

[English](./README.md) | [日本語](./README.ja.md)

A FastAPI server that mediates Autonomous Agent flows from the SPA.
It receives HTTP requests from the SPA, invokes the Foundry Hosted Agent, and returns the results.

## Role

```text
SPA (Frontend) → Backend API → Foundry Hosted Agent → Identity Echo API
```

- Accepts Autonomous flow requests from the SPA
- Invokes the Foundry Hosted Agent via the OpenAI Responses API
- Returns the Agent's response to the SPA as JSON or SSE stream
- Authenticates to Foundry using Azure Managed Identity (`DefaultAzureCredential`)

## API Endpoints

| Method | Path                              | Description                   | Auth |
| ------ | --------------------------------- | ----------------------------- | ---- |
| GET    | `/health`                         | Health check                  | None |
| POST   | `/api/demo/autonomous/app`        | Autonomous Agent invocation   | None |
| POST   | `/api/demo/autonomous/app/stream` | Autonomous Agent (SSE stream) | None |

### Request

```json
{
  "message": "Call the resource API using the autonomous app flow.",
  "force_tool": "call_resource_api_autonomous_app"
}
```

- `message`: Prompt for the Agent
- `force_tool` (optional): Specifies which Tool to use

### Response

- `/autonomous/app`: JSON (`{"tool_output": {...}, "agent_message": "..."}`)
- `/autonomous/app/stream`: Server-Sent Events (OpenAI Responses API format)

## Environment Variables

| Variable                   | Description                   | Required |
| -------------------------- | ----------------------------- | -------- |
| `FOUNDRY_PROJECT_ENDPOINT` | Foundry Project endpoint      | ✅       |
| `ENTRA_TENANT_ID`          | Entra ID tenant ID            | ✅       |
| `FRONTEND_SPA_APP_URL`     | SPA URL (for CORS allow list) | —        |

## CORS

| Origin                    | Purpose         |
| ------------------------- | --------------- |
| `http://localhost:5173`   | Vite dev server |
| `http://localhost:4173`   | Vite preview    |
| `${FRONTEND_SPA_APP_URL}` | Cloud SWA       |

## Directory Structure

```text
src/backend_api/
├── main.py              # FastAPI app initialization & CORS
├── config.py            # Environment variable loading
├── foundry_client.py    # Foundry Agent invocation logic
├── routes/
│   └── call_foundry_agent.py  # Endpoint handlers
├── Dockerfile           # Based on python:3.11-slim
└── requirements.txt     # Dependencies
```

## Local Development

```bash
cd src && uvicorn backend_api.main:app --reload --port 8080
```

> You must be logged in with `az login` to connect to Foundry
> (`DefaultAzureCredential` uses local Azure CLI credentials).

## Deployment

Deploy to Container Apps:

```bash
python src/scripts/deploy-container-apps.py backend-api
```

See [docs/deployment.md](../../docs/deployment.md) for details.

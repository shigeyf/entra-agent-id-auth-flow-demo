# Identity Echo API

[English](./README.md) | [日本語](./README.ja.md)

A Resource API (FastAPI) that returns caller information from Bearer tokens.
This is the core component of the Entra Agent ID demo, visualizing "whose permissions were used to access the resource."

## Role

Each of the three authentication flows uses a different Bearer token.
By comparing the caller information returned by this API, you can experience how Entra Agent ID works.

| Flow                  | Caller recognized by the API               | Token type |
| --------------------- | ------------------------------------------ | ---------- |
| Interactive           | The human user (e.g., `alice@contoso.com`) | delegated  |
| Autonomous Agent App  | Agent Identity (service principal)         | app-only   |
| Autonomous Agent User | Agent User (e.g., `agentuser@contoso.com`) | delegated  |

## API Endpoints

| Method | Path            | Description                                  | Auth         |
| ------ | --------------- | -------------------------------------------- | ------------ |
| GET    | `/api/resource` | Returns caller information from Bearer token | Bearer Token |
| GET    | `/health`       | Health check                                 | None         |

### Response Example (`/api/resource`)

```json
{
  "resource": "Demo Protected Resource",
  "accessedAt": "2026-04-08T12:00:00Z",
  "caller": {
    "tokenKind": "delegated",
    "oid": "...",
    "upn": "alice@contoso.com",
    "displayName": "Alice",
    "appId": "...",
    "scopes": ["CallerIdentity.Read"],
    "roles": []
  },
  "accessToken": { "...JWT claims..." },
  "humanReadable": "Accessed with delegated permissions (CallerIdentity.Read) of alice@contoso.com"
}
```

### Token Type Determination

- `scp` claim present → `"delegated"`
- No `scp` claim → `"app_only"` (application permissions)

## Token Validation

`auth/token_validator.py` validates the following:

1. Presence of the `Authorization: Bearer <token>` header
2. RS256 signature verification (public keys fetched from the Microsoft Entra JWKS endpoint)
3. `aud` (audience) = `ENTRA_RESOURCE_API_CLIENT_ID`
4. `iss` (issuer) = `https://login.microsoftonline.com/{TENANT_ID}/v2.0`
5. `exp` (expiration)

## Environment Variables

| Variable                       | Description                      | Required |
| ------------------------------ | -------------------------------- | -------- |
| `ENTRA_TENANT_ID`              | Entra ID tenant ID               | ✅       |
| `ENTRA_RESOURCE_API_CLIENT_ID` | Client ID (audience) of this API | ✅       |
| `FRONTEND_SPA_APP_URL`         | SPA URL (for CORS allow list)    | —        |

## CORS

| Origin                    | Purpose           |
| ------------------------- | ----------------- |
| `http://localhost:3000`   | Local development |
| `http://localhost:5173`   | Vite dev server   |
| `${FRONTEND_SPA_APP_URL}` | Cloud SWA         |

## Directory Structure

```text
src/identity_echo_api/
├── main.py              # FastAPI app initialization & CORS
├── config.py            # Environment variables & JWT validation settings
├── auth/
│   └── token_validator.py  # Bearer token validation (PyJWT + JWKS)
├── routes/
│   └── resource.py      # /api/resource endpoint
├── Dockerfile           # Based on python:3.11-slim
└── requirements.txt     # Dependencies (PyJWT, httpx, etc.)
```

## Local Development

```bash
cd src && uvicorn identity_echo_api.main:app --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

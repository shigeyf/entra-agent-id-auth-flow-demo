# Entra Agent ID Overview

[English](./entra-agent-id-overview.md) | [日本語](./entra-agent-id-overview.ja.md)

Entra Agent ID is a mechanism that grants AI agents their **own Entra ID identity**.
It clarifies "who" the agent accessed resources as, enabling auditing and governance.

> For protocol details (sequence diagrams and token parameters), see
> [Agent Identity OAuth Flow Comparison](agent-identity-oauth-flow-comparison.md).

---

## Why Agent ID Is Needed

Traditionally, agents accessed resources using **App Registration Client Secrets** or **Managed Identities**.
This makes it difficult to identify "which agent accessed what":

| Traditional Approach       | Problem                                                |
| -------------------------- | ------------------------------------------------------ |
| Shared Client Secret       | Multiple agents access under the same ID — unauditable |
| Managed Identity           | Identity is per infrastructure, not per agent          |
| User delegated tokens only | The agent's own actions cannot be tracked              |

Entra Agent ID issues a **unique service principal** per agent,
making each agent a target of Entra ID audit logs and conditional access policies.

---

## Entity Hierarchy

Entra Agent ID is managed in a three-tier structure:

```text
Agent Identity Blueprint (parent)
├── Agent Identity A (child)
│   └── Agent User X   ← Used in Autonomous Agent User Flow
├── Agent Identity B (child)
└── Agent Identity C (child)
```

### Role of Each Entity

| Entity                       | Description                                                             | Entra ID Representation                  |
| ---------------------------- | ----------------------------------------------------------------------- | ---------------------------------------- |
| **Agent Identity Blueprint** | Governance unit for agents. Holds credentials (FIC)                     | App Registration                         |
| **Agent Identity**           | Identity of an individual agent instance. Impersonated by the Blueprint | Service Principal                        |
| **Agent User**               | User context that the agent impersonates                                | Service Principal (with user attributes) |

- Blueprint : Agent Identity = **1 : N** (one Blueprint manages multiple Agent Identities)
- Agent Identity : Blueprint = **N : 1** (each Agent Identity belongs to exactly one Blueprint)
- Agent Identity : Agent User = **1 : N** (used only in Autonomous Agent User Flow)

### Correspondence in This Demo App

| Entity               | How It's Created                                         |
| -------------------- | -------------------------------------------------------- |
| Blueprint            | Auto-generated when the Foundry Project is created       |
| Agent Identity       | Auto-generated when the Foundry Project is created       |
| Agent User           | Created via scripts in `labs/entra-agent-id/scripts/`    |
| Federated Credential | Configured via scripts in `labs/entra-agent-id/scripts/` |

---

## Three OAuth Flows

Entra Agent ID provides three flows depending on the use case:

### 1. Interactive (User-Delegated)

```text
User → SPA → Backend API → Entra ID (OBO) → Resource API
```

- The user logs in to the SPA and invokes the agent
- The agent accesses resources with the **user's delegated permissions**
- Final token: **delegated** (scopes based on user consent)
- Token acquisition: T1 (exchange) + Tc (user token) → OBO → TR

### 2. Autonomous Agent App (Application Permissions)

```text
Scheduler → Agent → Entra ID → Resource API
```

- No user involvement
- The agent accesses resources with its **own application permissions**
- Final token: **app-only** (permissions pre-granted by an administrator)
- Token acquisition: 2 steps — T1 (exchange) → TR

### 3. Autonomous Agent User (Agent User Impersonation)

```text
Scheduler → Agent → Entra ID (credential chaining) → Resource API
```

- No user involvement, but the agent operates with an **Agent User context**
- The agent accesses resources with the **Agent User's delegated permissions**
- Final token: **delegated** (Agent User's scopes)
- Token acquisition: 3 steps — T1 → T2 → OBO → TR

### Flow Comparison

| Aspect                 | Interactive            | Autonomous Agent App         | Autonomous Agent User     |
| ---------------------- | ---------------------- | ---------------------------- | ------------------------- |
| **User involvement**   | Yes (login + consent)  | None                         | None                      |
| **Final token type**   | delegated              | app-only                     | delegated                 |
| **Permission subject** | Human user             | Agent Identity itself        | Agent User                |
| **Token steps**        | 3 (Tc + T1 → OBO → TR) | 2 (T1 → TR)                  | 3 (T1 → T2 → OBO → TR)    |
| **Primary use case**   | Interactive chatbot    | Batch jobs & scheduled tasks | Automated user delegation |

---

## Credential: Federated Identity Credential (FIC)

A **Federated Identity Credential (FIC)** is required for the Blueprint to acquire tokens from Entra ID.
An FIC is a configuration that says "trust assertions from this Managed Identity":

```text
Blueprint (App Registration)
  └── Federated Credential
        issuer: Managed Identity's OIDC issuer
        subject: Managed Identity's Client ID
```

- **Production**: Configure the Foundry Project's Managed Identity as the issuer
- **Local development**: Use a Client Secret (FIC not required, but not recommended)

> For FIC configuration steps, see section 5 of [Getting Started](getting-started.md).

---

## What This Demo App Lets You Verify

| UI Tab              | Flow                 | What to Check                                     |
| ------------------- | -------------------- | ------------------------------------------------- |
| **Autonomous**      | Autonomous Agent App | API access with Agent Identity's app-only token   |
| **Interactive OBO** | Interactive          | API access with user's delegated token (via OBO)  |
| **No Agent**        | (Reference)          | Comparison with tokens acquired directly via MSAL |

The Identity Echo API returns the `oid`, `azp`, and `scp` from the received token,
allowing you to visualize "whose permissions were used for access" as a REST response.

---

## Related Documentation

- [Agent Identity OAuth Flow Comparison](agent-identity-oauth-flow-comparison.md) — Sequence diagrams & token parameter details for each flow
- [Architecture](architecture.md) — Overall system architecture diagram
- [Getting Started](getting-started.md) — Section 5 covers the Entra Agent ID setup procedure

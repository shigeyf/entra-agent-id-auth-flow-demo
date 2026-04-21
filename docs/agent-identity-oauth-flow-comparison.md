# Agent Identity OAuth Flow Comparison (Interactive Agent / Autonomous Agent App Flow / Autonomous Agent User Flow)

[English](./agent-identity-oauth-flow-comparison.md) | [日本語](./agent-identity-oauth-flow-comparison.ja.md)

## 1. Interactive Agent (User-Delegated)

A pattern where a human user interactively invokes the agent, which then accesses resources with the **user's permissions (delegated permissions)**.

Official documentation:

- [interactive-agent-authenticate-user](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/interactive-agent-authenticate-user) — User authentication
- [interactive-agent-request-user-authorization](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/interactive-agent-request-user-authorization) — User consent
- [interactive-agent-request-user-tokens](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/interactive-agent-request-user-tokens) — OBO token acquisition implementation
- [agent-on-behalf-of-oauth-flow](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/agent-on-behalf-of-oauth-flow) — Detailed OBO protocol flow

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant C as Client App
    participant E as Entra ID
    participant A as Agent Web API
    participant MSI as Managed Identity
    participant G as Downstream API (Graph, etc.)

    Note over U,G: Step A: User Authentication (Authorization Code Flow)
    U->>C: Start using the agent
    C->>U: 1. Redirect to Entra ID login page
    U->>E: 2. Access /authorize<br/>(client_id=ClientAppID,<br/>scope=api://{blueprint}/access_agent,<br/>response_type=code)
    E->>U: 3. Display sign-in screen
    U->>E: 4. Enter credentials
    E->>U: 5. Redirect to redirect_uri with authorization code
    U->>C: 6. Receive code
    C->>E: 7. /token (code → token exchange)
    E->>C: 8. Tc: User access token<br/>(aud=Blueprint, oid=User)

    Note over U,G: Step B: User Consent — Delegated permission to downstream API
    Note right of A: Agent constructs a consent URL<br/>and presents it to the user<br/>(e.g., sends a link in the chat)
    C->>A: 9. API call (Bearer: Tc)
    A->>A: 10. Validate Tc, identify user
    A->>C: 11. Return consent URL
    Note right of A: URL: /authorize?<br/>client_id=AgentIdentityID<br/>&response_type=none<br/>&scope=User.Read<br/>&redirect_uri=...
    C->>U: 12. Redirect or present link to consent URL
    U->>E: 13. Access /authorize<br/>(client_id=AgentIdentityID,<br/>scope=User.Read,<br/>response_type=none)
    E->>U: 14. Consent screen: "Allow this agent User.Read access?"
    U->>E: 15. Grant consent
    E->>U: 16. Redirect to redirect_uri (no code, consent recorded only)

    Note over U,G: Step C: Resource access via OBO (3 tokens required)
    C->>A: 17. API call (Bearer: Tc)

    Note over A,E: Step C-1: Blueprint obtains T1 (exchange token)
    A->>MSI: 18-a Obtain credential (MSI recommended)
    MSI->>A: 18-b UAMI token
    A->>E: 18. /token<br/>(client_id=BlueprintID,<br/>scope=api://AzureADTokenExchange/.default,<br/>grant_type=client_credentials,<br/>fmi_path=AgentID,<br/>client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer,<br/>client_assertion=UAMI token)
    E->>A: 19. T1: exchange token

    Note over A,E: Step C-2: OBO exchange with T1 + Tc
    Note right of E: Entra ID validates:<br/>T1.aud == Blueprint<br/>Tc.aud == Blueprint
    A->>E: 20. /token<br/>(client_id=AgentID,<br/>client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer,<br/>client_assertion=T1,<br/>assertion=Tc,<br/>scope=https://graph.microsoft.com/.default,<br/>grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer,<br/>requested_token_use=on_behalf_of)
    E->>A: 21. TR: Resource access token<br/>(aud=Graph, delegated, user's delegated permissions)

    A->>G: 22. API call (Bearer: TR)
    G->>A: 23. Response
    A->>C: 24. Return result
```

### Step B Notes: Why `response_type=none`

- The /authorize request in Step B specifies **`response_type=none`**
- This is not for obtaining an authorization code — it is **solely for recording consent**
- Entra ID records the user's consent in the tenant and treats it as pre-consented in subsequent OBO flows
- The `client_id` uses the **Agent Identity's ID** (not the Blueprint ID)
- Example from official docs: The agent presents the consent URL as a link within the chat window

### Step C Notes: Why T1 Is Required

- Per the official OBO protocol, the agent must obtain **T1 (exchange token)** before the OBO exchange
- T1 acquisition uses the same mechanism as Autonomous Agent (`client_credentials` + `fmi_path`)
- The OBO exchange presents **two tokens simultaneously**: `client_assertion=T1` and `assertion=Tc`
- Entra ID validates that **T1.aud == Blueprint** and **Tc.aud == Blueprint**
- The agent itself cannot use the `/authorize` endpoint (official: "Agents aren't supported for OBO `/authorize` flows")
- Supported grant types are `client_credentials`, `jwt-bearer`, and `refresh_token` only

### Three Steps in Detail

| Step                       | Summary                                                                                                                                          | Documentation                                                                                                                                 |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- |
| **Step A: User Auth**      | The client redirects to Entra ID via OAuth 2.0 Authorization Code Flow and obtains access token Tc with the Agent Identity Blueprint as audience | [authenticate-user](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/interactive-agent-authenticate-user)                   |
| **Step B: User Consent**   | The user grants delegated permission for the agent to access the downstream API                                                                  | [request-user-authorization](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/interactive-agent-request-user-authorization) |
| **Step C-1: Obtain T1**    | The agent uses the Blueprint's credential to obtain exchange token T1 (same mechanism as Autonomous)                                             | [agent-on-behalf-of-oauth-flow](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/agent-on-behalf-of-oauth-flow)             |
| **Step C-2: OBO Exchange** | Presents T1 + Tc to obtain resource token TR via OBO                                                                                             | [request-user-tokens](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/interactive-agent-request-user-tokens)               |

---

## 2. Autonomous Agent App Flow (Autonomous — Application Permissions)

A pattern where the agent operates without user involvement, using its **own permissions (application permissions)**.

Official documentation:

- [autonomous-agent-request-tokens](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/autonomous-agent-request-tokens) — Token acquisition implementation
- [agent-autonomous-app-oauth-flow](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/agent-autonomous-app-oauth-flow) — Detailed app-only protocol flow

### Parent-Child Relationship Between Blueprint and Agent Identity

```mermaid
flowchart TB
    BP["Agent Identity Blueprint<br/>(Parent App Registration)<br/>client_id = BlueprintID"]
    AI1["Agent Identity A<br/>(Child)<br/>client_id = AgentID-A"]
    AI2["Agent Identity B<br/>(Child)<br/>client_id = AgentID-B"]
    AI3["Agent Identity C<br/>(Child)<br/>client_id = AgentID-C"]
    BP -->|"impersonate (1:N)"| AI1
    BP -->|"impersonate"| AI2
    BP -->|"impersonate"| AI3

    style BP fill:#6c5ce7,color:#fff
    style AI1 fill:#e17055,color:#fff
    style AI2 fill:#e17055,color:#fff
    style AI3 fill:#e17055,color:#fff
```

- A Blueprint can impersonate multiple Agent Identities (1:N)
- Each Agent Identity belongs to exactly one Blueprint
- Agent Identities are always single-tenant

### Token Acquisition Flow

```mermaid
sequenceDiagram
    participant MSI as Managed Identity
    participant T as Trigger / Scheduler
    participant A as Agent
    participant E as Entra ID
    participant G as Downstream API (Graph, etc.)

    Note over T,G: No user auth or consent (2-step token acquisition)
    T->>A: 1. Start processing

    Note over A,E: Step 1: Blueprint obtains T1 (exchange token)
    Note right of A: Uses Managed Identity (recommended),<br/>certificate, or client_secret (dev only) as credential
    A->>MSI: 1-a Obtain Managed Identity token (recommended)
    MSI->>A: 1-b UAMI token
    A->>E: 2. /token<br/>(client_id=BlueprintID,<br/>scope=api://AzureADTokenExchange/.default,<br/>grant_type=client_credentials,<br/>fmi_path=AgentID,<br/>client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer,<br/>client_assertion=UAMI token)
    E->>A: 3. T1: exchange token

    Note over A,E: Step 2: Exchange T1 → Resource access token (TR)
    Note right of E: Entra ID validates T1.aud == Blueprint
    A->>E: 4. /token<br/>(client_id=AgentID,<br/>client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer,<br/>client_assertion=T1,<br/>scope=https://graph.microsoft.com/.default,<br/>grant_type=client_credentials)
    E->>A: 5. TR: app-only resource access token (application permissions)

    A->>G: 6. API call (Bearer: TR)
    G->>A: 7. Response
```

### Step 1 Credential Types

| Credential Type                     | Parameters                                                                                                     | Use Case                                   |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| **Managed Identity (recommended)**  | `client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer` + `client_assertion=UAMI token` | Production (auto-rotation, secure storage) |
| **Certificate**                     | `client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer` + `client_assertion=signed JWT` | Production                                 |
| **Client Secret (not recommended)** | `client_secret=<secret>`                                                                                       | Local development only                     |

---

## 3. Autonomous Agent User Flow (Agent User Impersonation)

A pattern where an Autonomous Agent accesses resources **with a user context (Agent User)**.
Rather than a human user logging in directly, the agent **impersonates an Agent User** and accesses resources with delegated permissions.

Official documentation: [agent-user-oauth-flow](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/agent-user-oauth-flow) — Agent User Impersonation protocol

### Impersonate Chain

```mermaid
flowchart LR
    BP["Agent Identity Blueprint<br/>(actor 1)"]
    AI["Agent Identity<br/>(actor 2)"]
    AU["Agent User<br/>(subject)"]
    BP -->|"impersonate"| AI -->|"impersonate"| AU

    style BP fill:#6c5ce7,color:#fff
    style AI fill:#e17055,color:#fff
    style AU fill:#0984e3,color:#fff
```

- **Credential chaining** from Blueprint → Agent Identity → Agent User
- An Agent User can only be impersonated by **one Agent Identity**
- Access is scoped within the **delegation assigned to the Agent Identity**

### Token Acquisition Flow (3 Steps)

```mermaid
sequenceDiagram
    participant MSI as Managed Identity
    participant A as Agent
    participant E as Entra ID
    participant G as Downstream API (Graph, etc.)

    Note over A,G: 3-step credential chaining

    Note over A,E: Step 1: Blueprint obtains T1 (exchange token)
    A->>MSI: 1-a Obtain UAMI token
    MSI->>A: 1-b UAMI token
    A->>E: 2. /token<br/>(client_id=BlueprintID,<br/>scope=api://AzureADTokenExchange/.default,<br/>grant_type=client_credentials,<br/>fmi_path=AgentID,<br/>client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer,<br/>client_assertion=UAMI token)
    E->>A: 3. T1: exchange token

    Note over A,E: Step 2: Agent Identity obtains T2 (exchange token)
    Note right of E: Entra ID validates T1.aud == Blueprint
    A->>E: 4. /token<br/>(client_id=AgentID,<br/>scope=api://AzureADTokenExchange/.default,<br/>client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer,<br/>client_assertion=T1,<br/>grant_type=client_credentials)
    E->>A: 5. T2: exchange token (for Agent Identity)

    Note over A,E: Step 3: Obtain Agent User's resource token via OBO
    Note right of E: Entra ID validates T2.aud == Agent Identity<br/>Both client_assertion=T1 and assertion=T2 are required
    A->>E: 6. /token<br/>(client_id=AgentID,<br/>client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer,<br/>client_assertion=T1,<br/>assertion=T2,<br/>username=agentuser@contoso.com,<br/>scope=https://resource.example.com/scope1,<br/>grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer,<br/>requested_token_use=on_behalf_of)
    E->>A: 7. TR: Resource access token (delegated, as Agent User)

    A->>G: 8. API call (Bearer: TR)
    G->>A: 9. Response
```

### Three Steps in Detail

| Step             | client_id   | scope                                 | assertion / credential                                            | Returned Token                    |
| ---------------- | ----------- | ------------------------------------- | ----------------------------------------------------------------- | --------------------------------- |
| **Step 1**       | BlueprintID | `api://AzureADTokenExchange/.default` | `client_assertion=UAMI` + `fmi_path=AgentID`                      | **T1** (exchange)                 |
| **Step 2**       | AgentID     | `api://AzureADTokenExchange/.default` | `client_assertion=T1`                                             | **T2** (exchange)                 |
| **Step 3** (OBO) | AgentID     | `https://resource.example.com/scope1` | `client_assertion=T1` + `assertion=T2` + `username=agentuser@...` | **TR** (delegated resource token) |

> **Important**: Steps 2 and 3 must use the **same `client_id=AgentID`**. This constraint prevents privilege escalation attacks.

### Differences from Autonomous Agent App Flow

|                      | Autonomous Agent App Flow              | Autonomous Agent User Flow                          |
| -------------------- | -------------------------------------- | --------------------------------------------------- |
| **Token steps**      | 2 steps (T1 → TR)                      | 3 steps (T1 → T2 → OBO → TR)                        |
| **Final token**      | app-only (application permissions)     | **delegated** (Agent User's permissions)            |
| **User context**     | None                                   | Agent User                                          |
| **Final grant_type** | `client_credentials`                   | `urn:ietf:params:oauth:grant-type:jwt-bearer` (OBO) |
| **Final scope**      | `https://graph.microsoft.com/.default` | Individual scopes (e.g., `User.Read`)               |
| **Subject**          | Agent Identity itself                  | Agent User                                          |

---

## 4. Token Differences

### 4-1. Interactive Agent

```mermaid
flowchart LR
    TC["Tc<br/>aud: Blueprint<br/>scope: access_agent<br/>Human user authenticated"]
    T1I["T1<br/>aud: Blueprint<br/>scope: AzureADTokenExchange<br/>exchange token"]
    TR_I["TR<br/>aud: Graph<br/>scope: User.Read<br/>delegated"]
    TC --- T1I
    T1I -->|"OBO<br/>assertion=Tc<br/>client_assertion=T1"| TR_I

    style TC fill:#4a9eff,color:#fff
    style T1I fill:#fdcb6e,color:#2d3436
    style TR_I fill:#00b894,color:#fff
```

### 4-2. Autonomous Agent App Flow

```mermaid
flowchart LR
    AA1["T1<br/>aud: Blueprint<br/>scope: AzureADTokenExchange<br/>exchange token"]
    AAR["TR<br/>aud: Graph<br/>scope: .default<br/>app-only"]
    AA1 -->|"client_assertion"| AAR

    style AA1 fill:#e17055,color:#fff
    style AAR fill:#d63031,color:#fff
```

### 4-3. Autonomous Agent User Flow

```mermaid
flowchart LR
    AU1["T1<br/>aud: Blueprint<br/>scope: AzureADTokenExchange<br/>exchange token"]
    AU2["T2<br/>aud: Agent Identity<br/>scope: AzureADTokenExchange<br/>exchange token"]
    AUR["TR<br/>aud: Graph<br/>scope: User.Read<br/>delegated(Agent User)"]
    AU1 -->|"client_assertion"| AU2 -->|"OBO<br/>assertion=T2<br/>client_assertion=T1"| AUR

    style AU1 fill:#e17055,color:#fff
    style AU2 fill:#fdcb6e,color:#2d3436
    style AUR fill:#6c5ce7,color:#fff
```

---

## 5. Comparison Table

|                              | Interactive Agent                                                                                                                 | Autonomous Agent App Flow                                                                                                             | Autonomous Agent User Flow                                                                                        |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| **Whose permissions**        | Human user (delegated)                                                                                                            | Agent itself (application)                                                                                                            | Agent User (delegated)                                                                                            |
| **Human user auth**          | Required                                                                                                                          | Not required                                                                                                                          | Not required                                                                                                      |
| **Human user consent**       | Required (OAuth consent)                                                                                                          | Not required                                                                                                                          | Not required                                                                                                      |
| **Subject**                  | Human user                                                                                                                        | Agent Identity                                                                                                                        | Agent User                                                                                                        |
| **Token acquisition method** | Auth Code → OBO                                                                                                                   | Client Credentials (2-step)                                                                                                           | Client Credentials (2-step) + OBO                                                                                 |
| **Number of tokens**         | 3 (Tc + T1 → TR)                                                                                                                  | 2 (T1 → TR)                                                                                                                           | 3 (T1 → T2 → TR)                                                                                                  |
| **Final token type**         | delegated                                                                                                                         | app-only                                                                                                                              | **delegated** (as Agent User)                                                                                     |
| **Final grant_type**         | OBO (jwt-bearer)                                                                                                                  | client_credentials                                                                                                                    | OBO (jwt-bearer)                                                                                                  |
| **Credential**               | Blueprint MSI/cert/secret + client secret                                                                                         | MSI (recommended) / cert / secret                                                                                                     | MSI (recommended) / cert / secret                                                                                 |
| **client_id usage**          | Auth=ClientApp, T1=Blueprint, Consent/OBO=AgentID                                                                                 | Step1=Blueprint, Step2=AgentID                                                                                                        | Step1=Blueprint, Step2-3=AgentID                                                                                  |
| **Official protocol doc**    | [agent-on-behalf-of-oauth-flow](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/agent-on-behalf-of-oauth-flow) | [agent-autonomous-app-oauth-flow](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/agent-autonomous-app-oauth-flow) | [agent-user-oauth-flow](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/agent-user-oauth-flow) |
| **Use case**                 | Chat-based instructions → user-delegated operations                                                                               | Background jobs, etc.                                                                                                                 | Autonomous resource access on behalf of a user                                                                    |

---

## 6. Key Takeaways

All three flows require multi-step token acquisition, but the mechanisms and the final tokens differ:

### Interactive Agent

1. **Tc** (Client → Agent API): audience is Agent Blueprint, scope is `access_agent`. Includes human user authentication
2. **T1** (Agent internal): Obtained via `client_credentials` + `fmi_path` with Blueprint's credential. Same mechanism as Autonomous
3. **TR** (Agent API → Downstream API): Exchanged via **OBO** by presenting T1 + Tc. audience is the downstream API, delegated permission
4. Resource access is limited to the scope of permissions explicitly consented to by the user

### Autonomous Agent App Flow

1. **T1 (exchange token)**: Blueprint obtains via `client_credentials` + `fmi_path` + credential. aud == Blueprint
2. **TR (resource access token)**: Exchanged using T1 as `client_assertion`. **app-only** permissions
3. No user involvement. Operates with application permissions granted by the tenant administrator

### Autonomous Agent User Flow

1. **T1 (exchange token)**: Same as App Flow. Blueprint serves as the starting point for credential chaining
2. **T2 (exchange token)**: Obtained using T1 as `client_assertion` for the Agent Identity's exchange token. aud == Agent Identity
3. **TR (delegated resource token)**: Exchanged via **OBO** using both T1 and T2. Agent User's **delegated** permissions
4. No human user involvement, but accesses resources with the Agent User's user context as delegated

### The Essential Differences Between the Three Flows

```text
Interactive:           Human user auth → Tc + T1      → OBO        → TR (delegated, human user)
Autonomous Agent App:  App auth        → T1           → assertion  → TR (app-only)
Autonomous Agent User: App auth        → T1      → T2 → OBO        → TR (delegated, Agent User)
```

- **T1 (exchange token) acquisition is common across all three flows**: The part that uses Blueprint's `client_credentials` + `fmi_path` is identical
- **Interactive** and **Autonomous Agent User Flow** both ultimately obtain delegated tokens, but differ in whether the subject is a "human user" or an "Agent User"
- **Autonomous Agent App Flow** is the only one that obtains an app-only token
- **Autonomous Agent User Flow** shares Steps 1-2 with Autonomous Agent App Flow, but is distinctive in performing an additional OBO exchange in Step 3

"""Agent configuration loaded from environment variables."""

import os
from dataclasses import dataclass, field


@dataclass
class AgentConfig:
    """Environment variables for the Foundry Hosted Agent."""

    tenant_id: str = field(default_factory=lambda: os.getenv("ENTRA_TENANT_ID", ""))
    project_endpoint: str = field(
        default_factory=lambda: os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")
    )
    model_deployment_name: str = field(
        default_factory=lambda: os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4.1")
    )

    # Entra Agent ID (used in Phase 2 Step B)
    blueprint_client_id: str = field(
        default_factory=lambda: os.getenv(
            "ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID", ""
        )
    )
    agent_identity_oid: str = field(
        default_factory=lambda: os.getenv("ENTRA_AGENT_IDENTITY_OID", "")
    )

    # Autonomous User (used in Phase 4)
    agent_user_oid: str = field(default_factory=lambda: os.getenv("AGENT_USER_OID", ""))
    agent_user_upn: str = field(
        default_factory=lambda: os.getenv("ENTRA_AGENT_ID_USER_UPN", "")
    )

    # Resource API
    resource_api_url: str = field(
        default_factory=lambda: os.getenv("RESOURCE_API_URL", "")
    )
    resource_api_scope: str = field(
        default_factory=lambda: os.getenv("ENTRA_RESOURCE_API_SCOPE", "")
    )
    resource_api_default_scope: str = field(
        default_factory=lambda: os.getenv("ENTRA_RESOURCE_API_DEFAULT_SCOPE", "")
    )


config = AgentConfig()

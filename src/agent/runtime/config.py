"""Agent configuration — single source of truth for environment variables.

dotenv loading and validation are encapsulated here.
Other modules import ``config`` and access typed fields.
"""

import os
import sys
from dataclasses import dataclass, field

from dotenv import find_dotenv, load_dotenv

# Load .env before dataclass fields evaluate default_factory
_env_path = find_dotenv(filename=".env", usecwd=False)
if _env_path:
    load_dotenv(_env_path, override=True)


def _require_env(key: str) -> str:
    value = os.getenv(key, "")
    if not value:
        print(f"ERROR: Required env var {key} is not set", file=sys.stderr)
        sys.exit(1)
    return value


@dataclass(frozen=True)
class AgentConfig:
    """Environment variables for the Foundry Hosted Agent."""

    tenant_id: str = field(default_factory=lambda: _require_env("ENTRA_TENANT_ID"))
    project_endpoint: str = field(default_factory=lambda: _require_env("FOUNDRY_PROJECT_ENDPOINT"))
    model_deployment_name: str = field(
        default_factory=lambda: _require_env("FOUNDRY_MODEL_DEPLOYMENT_NAME")
    )

    # Entra Agent ID
    blueprint_client_id: str = field(
        default_factory=lambda: _require_env("ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID")
    )
    agent_identity_oid: str = field(
        default_factory=lambda: _require_env("ENTRA_AGENT_IDENTITY_CLIENT_ID")
    )
    agent_user_upn: str = field(
        default_factory=lambda: os.getenv("ENTRA_AGENT_ID_USER_UPN", "")
        # default_factory=lambda: _require_env("ENTRA_AGENT_ID_USER_UPN")
    )

    # Resource API
    resource_api_url: str = field(default_factory=lambda: _require_env("RESOURCE_API_URL"))
    resource_api_client_id: str = field(
        default_factory=lambda: os.getenv("ENTRA_RESOURCE_API_CLIENT_ID", "")
    )
    resource_api_scope: str = field(
        default_factory=lambda: _require_env("ENTRA_RESOURCE_API_SCOPE")
    )
    resource_api_default_scope: str = field(
        default_factory=lambda: _require_env("ENTRA_RESOURCE_API_DEFAULT_SCOPE")
    )


config = AgentConfig()

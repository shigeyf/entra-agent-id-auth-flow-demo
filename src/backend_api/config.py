import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _to_services_endpoint(endpoint: str) -> str:
    """Convert cognitiveservices.azure.com to services.ai.azure.com.

    AIProjectClient must connect via the services.ai.azure.com domain.
    The agent_reference is not recognized with the cognitiveservices domain.
    """
    return re.sub(
        r"\.cognitiveservices\.azure\.com/",
        ".services.ai.azure.com/",
        endpoint,
    )


TENANT_ID: str = os.getenv("ENTRA_TENANT_ID", "")
FOUNDRY_PROJECT_ENDPOINT: str = _to_services_endpoint(os.getenv("FOUNDRY_PROJECT_ENDPOINT", ""))
FOUNDRY_AGENT_NAME: str = "demo-entraagtid-agent"

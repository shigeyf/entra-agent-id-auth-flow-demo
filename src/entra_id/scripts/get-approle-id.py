import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv, set_key

# Always resolve .env relative to the project root (two levels up from this script)
dotenv_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path)

token = os.environ.get("ACCESS_TOKEN")
if not token:
    print("ERROR: ACCESS_TOKEN is not set. Run get-token.py first.", file=sys.stderr)
    sys.exit(1)

role_name = "AgentIdUser.ReadWrite.IdentityParentedBy"
ms_graph_app_id = "00000003-0000-0000-c000-000000000000"

# Get Microsoft Graph service principal with appRoles
resp = requests.get(
    "https://graph.microsoft.com/beta/serviceprincipals",
    params={"$filter": f"appId eq '{ms_graph_app_id}'", "$select": "id,appRoles"},
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
)
resp.raise_for_status()
sp = resp.json()["value"][0]

# Save MS Graph service principal object ID (varies per tenant)
print(f"MS Graph SP ID: {sp['id']}")
set_key(dotenv_path, "MS_GRAPH_SP_ID", sp["id"])
print("Saved MS_GRAPH_SP_ID to .env file.")

# Find the target appRole
for role in sp["appRoles"]:
    if role["value"] == role_name:
        print(f"Found: {role_name} = {role['id']}")
        set_key(dotenv_path, "AGENT_ID_USER_APP_ROLE_ID", role["id"])
        print("Saved AGENT_ID_USER_APP_ROLE_ID to .env file.")
        break
else:
    print(
        f"ERROR: appRole '{role_name}' not found in Microsoft Graph service principal."
    )
    sys.exit(1)

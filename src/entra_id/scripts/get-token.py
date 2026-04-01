import json
import os
from pathlib import Path

import msal
from dotenv import load_dotenv, set_key

# Always resolve .env relative to the project root (two levels up from this script)
dotenv_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path)

client_id = os.environ["CLIENT_ID"]
tenant_id = os.environ["TENANT_ID"]
scopes = [
    "https://graph.microsoft.com/AgentIdentityBlueprint.Create",
    "https://graph.microsoft.com/AgentIdentityBlueprint.AddRemoveCreds.All",
    "https://graph.microsoft.com/AgentIdentityBlueprint.ReadWrite.All",
    "https://graph.microsoft.com/AgentIdentityBlueprintPrincipal.Create",
    "https://graph.microsoft.com/AgentIdentity.ReadWrite.All",
    "https://graph.microsoft.com/AppRoleAssignment.ReadWrite.All",
    "https://graph.microsoft.com/DelegatedPermissionGrant.ReadWrite.All",
    "https://graph.microsoft.com/User.Read.All",
    "User.Read",
]
authority = f"https://login.microsoftonline.com/{tenant_id}"

app = msal.PublicClientApplication(client_id, authority=authority)

print("Login with browser...")
result = app.acquire_token_interactive(scopes=scopes)

if "access_token" in result:
    set_key(dotenv_path, "ACCESS_TOKEN", result["access_token"])
    print("Saved ACCESS_TOKEN to .env file.")
    # print("\n--- Successful Acquisition of Access Token ---")
    # print("AccessToken:")
    # print(result["access_token"])
else:
    print("An error occurred when acquiring the token:")
    print(json.dumps(result, indent=2))

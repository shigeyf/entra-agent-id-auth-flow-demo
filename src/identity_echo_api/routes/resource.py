from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from identity_echo_api.auth.token_validator import validate_token
from identity_echo_api.config import AGENT_USER_UPN

router = APIRouter()


def _determine_caller_type(claims: dict, agent_user_upn: str) -> str:
    has_scp = bool(claims.get("scp"))
    if not has_scp:
        return "app_only"
    upn = claims.get("upn") or claims.get("preferred_username", "")
    if agent_user_upn and upn.lower() == agent_user_upn.lower():
        return "delegated_agent_user"
    return "delegated_human_user"


def _build_caller_response(claims: dict) -> dict:
    caller_type = _determine_caller_type(claims, AGENT_USER_UPN)

    scp = claims.get("scp", "")
    scopes = scp.split() if scp else []
    roles = claims.get("roles", [])
    token_kind = "delegated" if scopes else "application"

    upn = claims.get("upn") or claims.get("preferred_username", "")

    caller = {
        "callerType": caller_type,
        "tokenKind": token_kind,
        "oid": claims.get("oid", ""),
        "sub": claims.get("sub", ""),
        "upn": upn,
        "displayName": claims.get("name", ""),
        "appId": claims.get("azp", claims.get("appid", "")),
        "appDisplayName": claims.get("app_displayname", ""),
        "scopes": scopes,
        "roles": roles,
        "issuer": claims.get("iss", ""),
        "issuedAt": claims.get("iat", ""),
        "expiresAt": claims.get("exp", ""),
    }

    # Human-readable summary
    caller_display = caller["upn"] or caller["displayName"] or caller["oid"]
    if caller_type == "delegated_human_user":
        scope_str = ", ".join(scopes) if scopes else "なし"
        human_readable = (
            f"{caller_display} の委任権限 ({scope_str}) でアクセスされました"
        )
    elif caller_type == "delegated_agent_user":
        scope_str = ", ".join(scopes) if scopes else "なし"
        human_readable = (
            f"Agent User {caller_display} の委任権限 ({scope_str}) でアクセスされました"
        )
    else:
        role_str = ", ".join(roles) if roles else "なし"
        human_readable = (
            f"アプリケーション権限 ({role_str}) でアクセスされました"
            f" (OID: {caller['oid']})"
        )

    return {
        "resource": "Demo Protected Resource",
        "accessedAt": datetime.now(UTC).isoformat(),
        "caller": caller,
        "humanReadable": human_readable,
    }


_validate_token = Depends(validate_token)


@router.get("/api/resource")
def get_resource(claims: dict = _validate_token):
    return _build_caller_response(claims)

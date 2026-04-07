from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from identity_echo_api.auth.token_validator import validate_token

router = APIRouter()


def _determine_token_kind(claims: dict) -> str:
    has_scp = bool(claims.get("scp"))
    if not has_scp:
        return "app_only"
    return "delegated"


def _build_caller_response(claims: dict) -> dict:
    caller_type = _determine_token_kind(claims)

    scp = claims.get("scp", "")
    scopes = scp.split() if scp else []
    roles = claims.get("roles", [])

    upn = claims.get("upn") or claims.get("preferred_username", "")

    caller = {
        "tokenKind": caller_type,
        "oid": claims.get("oid", ""),
        "upn": upn,
        "displayName": claims.get("name", ""),
        "appId": claims.get("azp", claims.get("appid", "")),
        "scopes": scopes,
        "roles": roles,
    }

    # Human-readable summary
    caller_display = caller["upn"] or caller["displayName"] or caller["oid"]
    if caller_type == "delegated":
        scope_str = ", ".join(scopes) if scopes else "なし"
        human_readable = f"{caller_display} の委任権限 ({scope_str}) でアクセスされました"
    else:
        role_str = ", ".join(roles) if roles else "なし"
        human_readable = (
            f"アプリケーション権限 ({role_str}) でアクセスされました (OID: {caller['oid']})"
        )

    return {
        "resource": "Demo Protected Resource",
        "accessedAt": datetime.now(UTC).isoformat(),
        "caller": caller,
        "accessToken": claims,
        "humanReadable": human_readable,
    }


_validate_token = Depends(validate_token)


@router.get("/api/resource")
def get_resource(claims: dict = _validate_token):
    return _build_caller_response(claims)

from __future__ import annotations

import jwt
from fastapi import HTTPException, Request

from identity_echo_api.config import ENTRA_ISSUER, ENTRA_JWKS_URL, EXPECTED_AUDIENCE

_jwks_client = jwt.PyJWKClient(ENTRA_JWKS_URL, cache_jwk_set=True, lifespan=3600)


def _extract_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Missing or invalid Authorization header"
        )
    return auth_header[7:]


def validate_token(request: Request) -> dict:
    """Validate the Bearer token from the request and return decoded claims."""
    token = _extract_bearer_token(request)

    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=EXPECTED_AUDIENCE,
            issuer=ENTRA_ISSUER,
            options={"require": ["exp", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired") from None
    except jwt.InvalidAudienceError:
        raise HTTPException(status_code=401, detail="Invalid audience") from None
    except jwt.InvalidIssuerError:
        raise HTTPException(status_code=401, detail="Invalid issuer") from None
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=401, detail=f"Token validation failed: {e}"
        ) from None

    return claims

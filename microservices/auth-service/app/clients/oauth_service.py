from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status

from app.config import settings


MICROSOFT_AUTH_URL = (
    f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}/oauth2/v2.0/authorize"
)
MICROSOFT_TOKEN_URL = (
    f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}/oauth2/v2.0/token"
)
MICROSOFT_GRAPH_ME_URL = "https://graph.microsoft.com/v1.0/me"

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


def _raise_missing_config(provider: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"El proveedor OAuth de {provider} no esta configurado.",
    )


def get_microsoft_authorization_url(state: str, redirect_uri: str | None = None) -> str:
    if not settings.MICROSOFT_CLIENT_ID or not settings.MICROSOFT_CLIENT_SECRET:
        _raise_missing_config("Microsoft")

    params = {
        "client_id": settings.MICROSOFT_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": redirect_uri or settings.MICROSOFT_REDIRECT_URI,
        "scope": "openid email profile User.Read",
        "prompt": "select_account",
        "response_mode": "query",
        "state": state,
    }
    return f"{MICROSOFT_AUTH_URL}?{urlencode(params)}"


def get_google_authorization_url(state: str, redirect_uri: str | None = None) -> str:
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        _raise_missing_config("Google")

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": redirect_uri or settings.GOOGLE_REDIRECT_URI,
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_microsoft_code(code: str, redirect_uri: str | None = None) -> dict[str, str]:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_response = await client.post(
                MICROSOFT_TOKEN_URL,
                data={
                    "client_id": settings.MICROSOFT_CLIENT_ID,
                    "client_secret": settings.MICROSOFT_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": redirect_uri or settings.MICROSOFT_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            token_data = token_response.json()

            user_response = await client.get(
                MICROSOFT_GRAPH_ME_URL,
                headers={"Authorization": f"Bearer {token_data['access_token']}"},
            )
            user_response.raise_for_status()
            user_data = user_response.json()
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No fue posible completar la autenticacion con Microsoft.",
        ) from exc

    return {
        "email": (user_data.get("mail") or user_data.get("userPrincipalName") or "").strip().lower(),
        "full_name": (user_data.get("displayName") or "").strip(),
    }


async def exchange_google_code(code: str, redirect_uri: str | None = None) -> dict[str, str]:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": redirect_uri or settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            token_data = token_response.json()

            user_response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {token_data['access_token']}"},
            )
            user_response.raise_for_status()
            user_data = user_response.json()
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No fue posible completar la autenticacion con Google.",
        ) from exc

    if not isinstance(user_data, dict) or user_data.get("verified_email") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google no confirmo que el correo de la cuenta este verificado.",
        )

    return {
        "email": (user_data.get("email") or "").strip().lower(),
        "full_name": (user_data.get("name") or "").strip(),
    }

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import requests

from nova_scout_app.auth.config import FIREBASE_WEB_CONFIG
from nova_scout_app.auth.models import AuthSession, AuthUser


class AuthError(RuntimeError):
    """Human-friendly authentication error."""


class FirebaseAuthClient:
    def __init__(self) -> None:
        self.api_key = FIREBASE_WEB_CONFIG["apiKey"]
        self.session = requests.Session()
        self.timeout = 20
        self.identity_base = "https://identitytoolkit.googleapis.com/v1"
        self.secure_token_base = "https://securetoken.googleapis.com/v1"

    def sign_in_with_google(self, google_id_token: str) -> AuthSession:
        post_body = urlencode({"id_token": google_id_token, "providerId": "google.com"})
        payload = {
            "postBody": post_body,
            "requestUri": "http://localhost",
            "returnIdpCredential": True,
            "returnSecureToken": True,
        }
        data = self._post_json(f"{self.identity_base}/accounts:signInWithIdp?key={self.api_key}", payload)
        return self._session_from_auth_payload(data, provider="google.com")

    def refresh_session(self, refresh_token: str, cached_user: AuthUser | None = None) -> AuthSession:
        data = self._post_form(
            f"{self.secure_token_base}/token?key={self.api_key}",
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
        user = cached_user or AuthUser(
            email="",
            local_id=str(data.get("user_id", "")),
            provider="google.com",
        )
        return AuthSession(
            user=user,
            id_token=str(data.get("id_token", "")),
            refresh_token=str(data.get("refresh_token", refresh_token)),
            expires_at=self._expires_at(int(data.get("expires_in", "3600"))),
        )

    def lookup_user(self, id_token: str) -> AuthUser | None:
        data = self._post_json(
            f"{self.identity_base}/accounts:lookup?key={self.api_key}",
            {"idToken": id_token},
        )
        users = data.get("users", [])
        if not users:
            return None
        user_payload = users[0]
        provider = "google.com"
        provider_info = user_payload.get("providerUserInfo") or []
        if provider_info:
            provider = str(provider_info[0].get("providerId", provider))
        return AuthUser(
            email=str(user_payload.get("email", "")),
            local_id=str(user_payload.get("localId", "")),
            provider=provider,
            display_name=str(user_payload.get("displayName", "")),
            photo_url=str(user_payload.get("photoUrl", "")),
            email_verified=bool(user_payload.get("emailVerified", False)),
        )

    def _session_from_auth_payload(self, payload: dict[str, Any], provider: str) -> AuthSession:
        user = AuthUser(
            email=str(payload.get("email", "")),
            local_id=str(payload.get("localId", "")),
            provider=str(payload.get("providerId", provider) or provider),
            display_name=str(payload.get("displayName", "")),
            photo_url=str(payload.get("photoUrl", "")),
            email_verified=bool(payload.get("emailVerified", provider == "google.com")),
        )
        return AuthSession(
            user=user,
            id_token=str(payload.get("idToken", "")),
            refresh_token=str(payload.get("refreshToken", "")),
            expires_at=self._expires_at(int(payload.get("expiresIn", "3600"))),
        )

    @staticmethod
    def _expires_at(seconds: int) -> str:
        return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            raise AuthError(f"Network error while talking to Firebase: {exc}") from exc
        return self._parse_response(response)

    def _post_form(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.session.post(url, data=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            raise AuthError(f"Network error while refreshing the session: {exc}") from exc
        return self._parse_response(response)

    @staticmethod
    def _parse_response(response: requests.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except Exception as exc:
            raise AuthError(f"Unexpected response from Firebase: {exc}") from exc

        if response.ok:
            return data

        error_code = str(data.get("error", {}).get("message", "UNKNOWN_ERROR"))
        messages = {
            "USER_DISABLED": "This account has been disabled.",
            "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many attempts. Please try again in a bit.",
            "INVALID_IDP_RESPONSE": "Google sign-in did not complete correctly. Please try again.",
            "INVALID_PENDING_TOKEN": "Google sign-in expired. Please try again.",
            "INVALID_REFRESH_TOKEN": "Your saved session is no longer valid. Please sign in again.",
            "TOKEN_EXPIRED": "Your saved session expired. Please sign in again.",
            "OPERATION_NOT_ALLOWED": "Google sign-in is not enabled in Firebase Authentication.",
        }
        message = messages.get(error_code, error_code.replace("_", " ").title())
        raise AuthError(message)

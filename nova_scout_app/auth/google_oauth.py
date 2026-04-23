from __future__ import annotations

from google_auth_oauthlib.flow import InstalledAppFlow

from nova_scout_app.auth.config import AUTH_SCOPES, GOOGLE_OAUTH_CLIENT_CONFIG
from nova_scout_app.auth.firebase_client import AuthError


class GoogleOAuthService:
    def fetch_google_id_token(self) -> str:
        try:
            flow = InstalledAppFlow.from_client_config(GOOGLE_OAUTH_CLIENT_CONFIG, AUTH_SCOPES)
            credentials = flow.run_local_server(
                host="127.0.0.1",
                port=0,
                open_browser=True,
                authorization_prompt_message="Your browser opened for Nova Image Scout sign-in.",
                success_message="Nova Image Scout sign-in complete. You can close this tab.",
            )
        except Exception as exc:
            raise AuthError(f"Google sign-in was cancelled or failed to start: {exc}") from exc

        id_token = getattr(credentials, "id_token", None)
        if not id_token:
            raise AuthError("Google sign-in succeeded, but no ID token was returned.")
        return id_token

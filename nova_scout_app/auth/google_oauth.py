from __future__ import annotations

from google_auth_oauthlib.flow import InstalledAppFlow

from nova_scout_app.auth.config import AUTH_SCOPES, GOOGLE_OAUTH_CLIENT_CONFIG, google_oauth_config_error
from nova_scout_app.auth.firebase_client import AuthError


class PKCEInstalledAppFlow(InstalledAppFlow):
    def fetch_token(self, **kwargs):
        kwargs.setdefault("code_verifier", self.code_verifier)
        client_secret = str(self.client_config.get("client_secret", "")).strip()
        if client_secret:
            kwargs.setdefault("client_secret", client_secret)
        else:
            kwargs.setdefault("include_client_id", True)
        return self.oauth2session.fetch_token(self.client_config["token_uri"], **kwargs)


class GoogleOAuthService:
    def fetch_google_id_token(self) -> str:
        config_error = google_oauth_config_error()
        if config_error:
            raise AuthError(config_error)
        try:
            flow = PKCEInstalledAppFlow.from_client_config(GOOGLE_OAUTH_CLIENT_CONFIG, AUTH_SCOPES)
            credentials = flow.run_local_server(
                host="127.0.0.1",
                port=0,
                open_browser=True,
                authorization_prompt_message="Your browser opened for Nova Image Scout sign-in.",
                success_message="Nova Image Scout sign-in complete. You can close this tab.",
            )
        except Exception as exc:
            error_text = str(exc)
            if "client_secret" in error_text.lower():
                raise AuthError(
                    "Google OAuth client is misconfigured for desktop sign-in. "
                    "Use a Google Cloud OAuth client of type 'Desktop app' and include its "
                    "'client_id' and 'client_secret' in auth_config.local.json."
                ) from exc
            raise AuthError(f"Google sign-in was cancelled or failed to start: {exc}") from exc

        id_token = getattr(credentials, "id_token", None)
        if not id_token:
            raise AuthError("Google sign-in succeeded, but no ID token was returned.")
        return id_token

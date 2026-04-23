from __future__ import annotations

from nova_scout_app.auth.firebase_client import AuthError, FirebaseAuthClient
from nova_scout_app.auth.google_oauth import GoogleOAuthService
from nova_scout_app.auth.models import AuthSession
from nova_scout_app.auth.session_store import SessionStore


class AuthManager:
    def __init__(self) -> None:
        self.firebase = FirebaseAuthClient()
        self.google = GoogleOAuthService()
        self.store = SessionStore()
        self.session: AuthSession | None = None

    def restore_session(self) -> AuthSession | None:
        cached = self.store.load()
        if cached is None:
            return None

        try:
            refreshed = self.firebase.refresh_session(cached.refresh_token, cached.user)
            looked_up = self.firebase.lookup_user(refreshed.id_token)
            if looked_up is not None:
                refreshed.user = looked_up
            self.store.save(refreshed)
            self.session = refreshed
            return refreshed
        except AuthError:
            self.store.clear()
            self.session = None
            return None

    def sign_in_with_google(self) -> AuthSession:
        google_id_token = self.google.fetch_google_id_token()
        session = self.firebase.sign_in_with_google(google_id_token)
        if not session.user.photo_url or not session.user.display_name:
            looked_up = self.firebase.lookup_user(session.id_token)
            if looked_up is not None:
                session.user = looked_up
        self.store.save(session)
        self.session = session
        return session

    def sign_out(self) -> None:
        self.store.clear()
        self.session = None

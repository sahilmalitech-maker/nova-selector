from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

try:
    import keyring
    from keyring.errors import KeyringError, PasswordDeleteError
except Exception:
    keyring = None
    KeyringError = RuntimeError
    PasswordDeleteError = RuntimeError

from nova_scout_app.auth.config import KEYRING_SERVICE_NAME
from nova_scout_app.auth.models import AuthSession, AuthUser


class SessionStore:
    def __init__(self, metadata_path: Path | None = None) -> None:
        base_dir = Path.home() / ".nova_image_scout"
        base_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_path = metadata_path or (base_dir / "auth_session.json")
        self.refresh_token_key = "current_refresh_token"

    def load(self) -> AuthSession | None:
        if not self.metadata_path.exists():
            return None

        try:
            with self.metadata_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return None

        refresh_token = None
        if keyring is not None:
            try:
                refresh_token = keyring.get_password(KEYRING_SERVICE_NAME, self.refresh_token_key)
            except KeyringError:
                refresh_token = None
        if not refresh_token:
            refresh_token = str(payload.get("refresh_token", ""))
        if not refresh_token:
            return None

        user_payload = payload.get("user", {})
        user = AuthUser(
            email=str(user_payload.get("email", "")),
            local_id=str(user_payload.get("local_id", "")),
            provider=str(user_payload.get("provider", "google.com")),
            display_name=str(user_payload.get("display_name", "")),
            photo_url=str(user_payload.get("photo_url", "")),
            email_verified=bool(user_payload.get("email_verified", False)),
        )
        return AuthSession(
            user=user,
            id_token=str(payload.get("id_token", "")),
            refresh_token=refresh_token,
            expires_at=str(payload.get("expires_at", "")),
        )

    def save(self, session: AuthSession) -> None:
        payload = {
            "user": asdict(session.user),
            "id_token": session.id_token,
            "expires_at": session.expires_at,
        }
        if keyring is None:
            payload["refresh_token"] = session.refresh_token
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with self.metadata_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        if keyring is not None:
            keyring.set_password(KEYRING_SERVICE_NAME, self.refresh_token_key, session.refresh_token)

    def clear(self) -> None:
        if keyring is not None:
            try:
                keyring.delete_password(KEYRING_SERVICE_NAME, self.refresh_token_key)
            except (KeyringError, PasswordDeleteError):
                pass
        try:
            self.metadata_path.unlink()
        except FileNotFoundError:
            pass

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from nova_scout_app.constants import DATACLASS_OPTIONS

@dataclass(**DATACLASS_OPTIONS)
class AuthUser:
    email: str
    local_id: str
    provider: str
    display_name: str = ""
    photo_url: str = ""
    email_verified: bool = False

    @property
    def friendly_name(self) -> str:
        return self.display_name.strip() or self.email


@dataclass(**DATACLASS_OPTIONS)
class AuthSession:
    user: AuthUser
    id_token: str
    refresh_token: str
    expires_at: str

    def is_expired(self) -> bool:
        try:
            expires_at = datetime.fromisoformat(self.expires_at)
        except ValueError:
            return True
        return expires_at <= datetime.now(timezone.utc)

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


AUTH_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

KEYRING_SERVICE_NAME = "NovaImageScoutAuth"

_LOCAL_CONFIG_PATH = Path(__file__).with_name("auth_config.local.json")
_FIREBASE_REQUIRED_KEYS = (
    "apiKey",
    "authDomain",
    "projectId",
    "appId",
    "messagingSenderId",
)
_GOOGLE_REQUIRED_KEYS = ("client_id",)


def _candidate_config_paths() -> list[Path]:
    candidates = [_LOCAL_CONFIG_PATH]

    if getattr(sys, "frozen", False):
        executable_dir = Path(sys.executable).resolve().parent
        candidates.extend(
            [
                executable_dir / "nova_scout_app" / "auth" / "auth_config.local.json",
                executable_dir / "_internal" / "nova_scout_app" / "auth" / "auth_config.local.json",
            ]
        )

        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "nova_scout_app" / "auth" / "auth_config.local.json")

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _load_local_config() -> dict[str, Any]:
    for path in _candidate_config_paths():
        if not path.exists():
            continue
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(loaded, dict):
            return loaded
    return {}


def _local_mapping(key: str) -> dict[str, Any]:
    local_config = _load_local_config()
    mapping = local_config.get(key, {})
    return mapping if isinstance(mapping, dict) else {}


def _setting(mapping: dict[str, Any], key: str, env_name: str, default: str = "") -> str:
    env_value = os.environ.get(env_name, "").strip()
    if env_value:
        return env_value

    local_value = mapping.get(key, default)
    return str(local_value).strip() if local_value is not None else default


_firebase_config = _local_mapping("firebase")
FIREBASE_WEB_CONFIG = {
    "apiKey": _setting(_firebase_config, "apiKey", "NOVA_FIREBASE_API_KEY"),
    "authDomain": _setting(_firebase_config, "authDomain", "NOVA_FIREBASE_AUTH_DOMAIN"),
    "projectId": _setting(_firebase_config, "projectId", "NOVA_FIREBASE_PROJECT_ID"),
    "storageBucket": _setting(_firebase_config, "storageBucket", "NOVA_FIREBASE_STORAGE_BUCKET"),
    "messagingSenderId": _setting(_firebase_config, "messagingSenderId", "NOVA_FIREBASE_MESSAGING_SENDER_ID"),
    "appId": _setting(_firebase_config, "appId", "NOVA_FIREBASE_APP_ID"),
    "measurementId": _setting(_firebase_config, "measurementId", "NOVA_FIREBASE_MEASUREMENT_ID"),
}

_google_oauth = _local_mapping("google_oauth")
GOOGLE_OAUTH_CLIENT_CONFIG = {
    "installed": {
        "client_id": _setting(_google_oauth, "client_id", "NOVA_GOOGLE_CLIENT_ID"),
        "client_secret": _setting(_google_oauth, "client_secret", "NOVA_GOOGLE_CLIENT_SECRET"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "redirect_uris": ["http://localhost"],
    }
}


def missing_firebase_fields() -> list[str]:
    return [key for key in _FIREBASE_REQUIRED_KEYS if not str(FIREBASE_WEB_CONFIG.get(key, "")).strip()]


def missing_google_oauth_fields() -> list[str]:
    installed = GOOGLE_OAUTH_CLIENT_CONFIG.get("installed", {})
    return [key for key in _GOOGLE_REQUIRED_KEYS if not str(installed.get(key, "")).strip()]


def firebase_config_error() -> str | None:
    missing = missing_firebase_fields()
    if not missing:
        return None
    return (
        "Google sign-in is not configured in this build. "
        "Missing Firebase settings: "
        + ", ".join(missing)
        + "."
    )


def google_oauth_config_error() -> str | None:
    missing = missing_google_oauth_fields()
    if not missing:
        return None
    return (
        "Google sign-in is not configured in this build. "
        "Missing Google OAuth settings: "
        + ", ".join(missing)
        + "."
    )

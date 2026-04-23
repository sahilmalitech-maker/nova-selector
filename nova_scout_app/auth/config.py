from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


AUTH_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

KEYRING_SERVICE_NAME = "NovaImageScoutAuth"

_LOCAL_CONFIG_PATH = Path(__file__).with_name("auth_config.local.json")


def _load_local_config() -> dict[str, Any]:
    if not _LOCAL_CONFIG_PATH.exists():
        return {}

    try:
        loaded = json.loads(_LOCAL_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

    return loaded if isinstance(loaded, dict) else {}


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

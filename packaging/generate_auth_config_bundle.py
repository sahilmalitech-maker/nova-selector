#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    source_path = project_dir / "nova_scout_app" / "auth" / "auth_config.local.json"
    generated_dir = project_dir / "packaging" / "generated"
    output_path = generated_dir / "auth_config.local.json"

    if not source_path.exists():
        print("No local auth config found. Skipping bundled auth config generation.")
        return

    loaded = json.loads(source_path.read_text(encoding="utf-8"))
    firebase = loaded.get("firebase", {}) if isinstance(loaded, dict) else {}
    google_oauth = loaded.get("google_oauth", {}) if isinstance(loaded, dict) else {}

    bundled_config = {
        "firebase": {
            "apiKey": firebase.get("apiKey", ""),
            "authDomain": firebase.get("authDomain", ""),
            "projectId": firebase.get("projectId", ""),
            "storageBucket": firebase.get("storageBucket", ""),
            "messagingSenderId": firebase.get("messagingSenderId", ""),
            "appId": firebase.get("appId", ""),
            "measurementId": firebase.get("measurementId", ""),
        },
        "google_oauth": {
            "client_id": google_oauth.get("client_id", ""),
            "client_secret": google_oauth.get("client_secret", ""),
        },
    }

    generated_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(bundled_config, indent=2), encoding="utf-8")
    print(f"Bundled sanitized auth config into {output_path}")


if __name__ == "__main__":
    main()

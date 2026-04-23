#!/usr/bin/env python3
"""
Nova Image Scout

launcher
"""

from __future__ import annotations

import os
import sys
import traceback


def main() -> int:
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

    try:
        from nova_scout_app.app import run_application
    except ImportError as exc:
        dependency_name = getattr(exc, "name", str(exc))
        if str(dependency_name).startswith("nova_scout_app"):
            print("Application import failed:")
            traceback.print_exc()
            return 1
        print(
            "Missing dependency: "
            f"{dependency_name}\n"
            "Install the runtime dependencies and run again:\n"
            "pip install PyQt6 numpy opencv-python pillow pytesseract tensorflow requests keyring google-auth google-auth-oauthlib"
        )
        return 1

    return run_application()


if __name__ == "__main__":
    sys.exit(main())

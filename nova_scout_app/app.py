from __future__ import annotations

import os
import sys

from PyQt6.QtWidgets import QApplication

from nova_scout_app.constants import APP_TITLE
from nova_scout_app.coordinator import AppCoordinator
from nova_scout_app.ui.theme import apply_app_theme, build_stylesheet


def run_application() -> int:
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setStyle("Fusion")
    apply_app_theme()
    app.setStyleSheet(build_stylesheet())

    coordinator = AppCoordinator()
    app._coordinator = coordinator  # Keep coordinator alive for the full app session.
    coordinator.start()
    return app.exec()

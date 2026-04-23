from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from nova_scout_app.auth import AuthManager


class AuthWorker(QThread):
    finished_with_session = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(self, manager: AuthManager, operation: str) -> None:
        super().__init__()
        self.manager = manager
        self.operation = operation

    def run(self) -> None:
        try:
            if self.operation == "restore":
                result = self.manager.restore_session()
            elif self.operation == "google":
                result = self.manager.sign_in_with_google()
            else:
                raise RuntimeError(f"Unsupported auth operation: {self.operation}")
            self.finished_with_session.emit(result)
        except Exception as exc:
            self.error_occurred.emit(str(exc))

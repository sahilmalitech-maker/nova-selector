from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer

from nova_scout_app.auth import AuthManager
from nova_scout_app.ui.auth_window import AuthWindow
from nova_scout_app.ui.main_window import MainWindow
from nova_scout_app.ui.splash_screen import SplashScreen
from nova_scout_app.workers.auth_worker import AuthWorker


class AppCoordinator(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.auth_manager = AuthManager()
        self.splash = SplashScreen()
        self.auth_window: AuthWindow | None = None
        self.main_window: MainWindow | None = None
        self.auth_worker: AuthWorker | None = None
        self._startup_complete = False
        self._minimum_splash_elapsed = False
        self._restored_session = None

    def start(self) -> None:
        self.splash.set_status("Checking saved Google session", 24)
        self.splash.show()

        QTimer.singleShot(1050, self._mark_minimum_splash)
        self._run_auth_worker("restore")

    def _mark_minimum_splash(self) -> None:
        self._minimum_splash_elapsed = True
        self._try_finish_startup()

    def _run_auth_worker(self, operation: str) -> None:
        if self.auth_worker is not None:
            return
        self.auth_worker = AuthWorker(self.auth_manager, operation)
        self.auth_worker.finished_with_session.connect(lambda session: self._on_auth_success(operation, session))
        self.auth_worker.error_occurred.connect(lambda message: self._on_auth_error(operation, message))
        self.auth_worker.finished.connect(self._clear_auth_worker)
        self.auth_worker.start()

    def _on_auth_success(self, operation: str, session) -> None:
        if operation == "restore":
            self._restored_session = session
            self.splash.set_status("Preparing Nova Scout workspace", 100 if session else 74)
            self._startup_complete = True
            self._try_finish_startup()
            return

        if self.auth_window is None or session is None:
            return

        self.auth_window.set_busy(False, "Google account connected")
        self.auth_window.set_success("Workspace ready. Opening Nova Scout...")
        QTimer.singleShot(420, lambda: self._complete_auth_flow(session))

    def _on_auth_error(self, operation: str, message: str) -> None:
        if operation == "restore":
            self._restored_session = None
            self._startup_complete = True
            self._try_finish_startup()
            return

        if self.auth_window is None:
            return

        friendly = message if message else "Google sign-in could not be completed."
        self.auth_window.set_busy(False, "Ready")
        self.auth_window.set_error(friendly)

    def _clear_auth_worker(self) -> None:
        self.auth_worker = None

    def _try_finish_startup(self) -> None:
        if not self._minimum_splash_elapsed or not self._startup_complete:
            return

        if self._restored_session is not None:
            self._open_main_window(self._restored_session)
        else:
            self._show_auth_window()
        self.splash.finish_and_close()

    def _show_auth_window(self) -> None:
        self.auth_window = AuthWindow()
        self.auth_window.google_requested.connect(self._handle_google_requested)
        self.auth_window.show()
        self.auth_window.reset_status("Continue with Google to start selecting faster.")

    def _complete_auth_flow(self, session) -> None:
        if self.auth_window is not None:
            self.auth_window.close()
            self.auth_window = None
        self._open_main_window(session)

    def _open_main_window(self, session) -> None:
        if self.main_window is None:
            self.main_window = MainWindow()
            self.main_window.logout_requested.connect(self._logout)
        self.main_window.set_authenticated_user(session.user)
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def _logout(self) -> None:
        self.auth_manager.sign_out()
        if self.main_window is not None:
            self.main_window.close()
            self.main_window = None
        self._show_auth_window()

    def _handle_google_requested(self) -> None:
        if self.auth_window is not None:
            self.auth_window.set_busy(True, "Opening Google sign-in...")
        self._run_auth_worker("google")

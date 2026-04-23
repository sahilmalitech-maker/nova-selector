"""Modular package for the legacy Nova Image Scout application."""

__all__ = ["run_application"]

def run_application() -> int:
    from .app import run_application as _run_application

    return _run_application()

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytesseract


def runtime_search_roots() -> list[Path]:
    roots: list[Path] = []

    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            roots.append(Path(meipass))

        executable = Path(sys.executable).resolve()
        roots.extend(
            [
                executable.parent,
                executable.parent / "_internal",
                executable.parent.parent / "Resources",
                executable.parent.parent / "Frameworks",
            ]
        )

    module_path = Path(__file__).resolve()
    package_root = module_path.parents[1]
    project_root = module_path.parents[2]
    roots.extend([package_root, project_root, project_root / "packaging" / "generated"])

    unique_roots: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key not in seen:
            seen.add(key)
            unique_roots.append(root)
    return unique_roots


def bundled_tesseract_binary(runtime_root: Path) -> Path | None:
    bin_dir = runtime_root / "bin"
    candidates = [bin_dir / "tesseract"]
    if os.name == "nt":
        candidates.insert(0, bin_dir / "tesseract.exe")

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def bundled_tesseract_root() -> Path | None:
    for root in runtime_search_roots():
        candidate = root / "tesseract-runtime"
        if bundled_tesseract_binary(candidate) is not None:
            return candidate
    return None


def configure_tesseract_path() -> None:
    bundled_root = bundled_tesseract_root()
    if bundled_root is not None:
        bundled_binary = bundled_tesseract_binary(bundled_root)
        if bundled_binary is not None:
            os.environ["TESSDATA_PREFIX"] = str(bundled_root / "tessdata")
            pytesseract.pytesseract.tesseract_cmd = str(bundled_binary)
        return

    if shutil.which("tesseract"):
        return

    common_locations = [
        "/opt/homebrew/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/opt/local/bin/tesseract",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for candidate in common_locations:
        if os.path.exists(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
            return

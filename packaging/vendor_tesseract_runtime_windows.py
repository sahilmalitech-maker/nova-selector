#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path


def _candidate_runtime_dirs() -> list[Path]:
    candidates: list[Path] = []
    env_path = os.environ.get("TESSERACT_DIR", "").strip()
    if env_path:
        candidates.append(Path(env_path))

    for raw_path in (
        r"C:\Program Files\Tesseract-OCR",
        r"C:\Program Files (x86)\Tesseract-OCR",
    ):
        candidates.append(Path(raw_path))
    return candidates


def main() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    generated_dir = project_dir / "packaging" / "generated"
    runtime_dir = generated_dir / "windows-tesseract-runtime"
    bin_dir = runtime_dir / "bin"
    tessdata_dir = runtime_dir / "tessdata"

    source_dir = next((path for path in _candidate_runtime_dirs() if (path / "tesseract.exe").exists()), None)
    if source_dir is None:
        raise SystemExit(
            "Could not find a Windows Tesseract runtime. "
            "Install Tesseract on the Windows build machine or set TESSERACT_DIR before building."
        )

    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    bin_dir.mkdir(parents=True, exist_ok=True)

    copied_files: list[str] = []
    for pattern in ("*.exe", "*.dll"):
        for path in sorted(source_dir.glob(pattern)):
            shutil.copy2(path, bin_dir / path.name)
            copied_files.append(path.name)

    source_tessdata = source_dir / "tessdata"
    if source_tessdata.exists():
        shutil.copytree(source_tessdata, tessdata_dir)

    manifest = {
        "source_dir": str(source_dir),
        "files": copied_files,
        "tessdata_files": sorted(path.name for path in tessdata_dir.iterdir()) if tessdata_dir.exists() else [],
    }
    (runtime_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Bundled Windows Tesseract runtime into {runtime_dir}")


if __name__ == "__main__":
    main()

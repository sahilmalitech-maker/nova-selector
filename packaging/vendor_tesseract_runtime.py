#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path


def run(command: list[str]) -> str:
    return subprocess.check_output(command, text=True).strip()


def list_linked_homebrew_paths(path: Path) -> list[str]:
    output = run(["otool", "-L", str(path)])
    entries = []
    for raw_line in output.splitlines()[1:]:
        line = raw_line.strip()
        if not line:
            continue
        linked_path = line.split(" (compatibility", 1)[0].strip()
        entries.append(linked_path)

    if path.suffix == ".dylib" and entries:
        entries = entries[1:]

    return [entry for entry in entries if entry.startswith("/opt/homebrew/")]


def patch_binary(binary_path: Path, is_dylib: bool) -> None:
    linked_paths = list_linked_homebrew_paths(binary_path)
    for linked_path in linked_paths:
        resolved_name = Path(linked_path).resolve().name if Path(linked_path).exists() else Path(linked_path).name
        replacement = f"@loader_path/{resolved_name}" if is_dylib else f"@executable_path/../lib/{resolved_name}"
        subprocess.run(
            ["install_name_tool", "-change", linked_path, replacement, str(binary_path)],
            check=True,
        )

    if is_dylib:
        subprocess.run(
            ["install_name_tool", "-id", f"@loader_path/{binary_path.name}", str(binary_path)],
            check=True,
        )


def main() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    generated_dir = project_dir / "packaging" / "generated"
    runtime_dir = generated_dir / "tesseract-runtime"
    bin_dir = runtime_dir / "bin"
    lib_dir = runtime_dir / "lib"
    tessdata_dir = runtime_dir / "tessdata"

    tesseract_path = shutil.which("tesseract")
    if not tesseract_path:
        raise SystemExit("Tesseract is not installed. Install it on the build machine before bundling.")

    tesseract_binary = Path(tesseract_path).resolve()
    brew_prefix = Path(run(["brew", "--prefix", "tesseract"])).resolve()
    source_tessdata = brew_prefix / "share" / "tessdata"
    if not source_tessdata.exists():
        raise SystemExit(f"Could not find tessdata at {source_tessdata}")

    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    bin_dir.mkdir(parents=True, exist_ok=True)
    lib_dir.mkdir(parents=True, exist_ok=True)

    queue = [tesseract_binary]
    seen: set[str] = set()
    dylibs: list[Path] = []

    while queue:
        current = Path(queue.pop(0)).resolve()
        key = str(current)
        if key in seen:
            continue
        seen.add(key)

        for dependency in list_linked_homebrew_paths(current):
            queue.append(Path(dependency).resolve())

        if current != tesseract_binary:
            dylibs.append(current)

    bundled_binary = bin_dir / "tesseract"
    shutil.copy2(tesseract_binary, bundled_binary)
    bundled_binary.chmod(bundled_binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    copied_dylibs: list[str] = []
    for dylib in sorted(dylibs, key=lambda path: path.name):
        destination = lib_dir / dylib.name
        shutil.copy2(dylib, destination)
        destination.chmod(destination.stat().st_mode | stat.S_IWUSR)
        copied_dylibs.append(dylib.name)

    if tessdata_dir.exists():
        shutil.rmtree(tessdata_dir)
    shutil.copytree(source_tessdata, tessdata_dir)

    patch_binary(bundled_binary, is_dylib=False)
    for dylib_name in copied_dylibs:
        patch_binary(lib_dir / dylib_name, is_dylib=True)

    manifest = {
        "tesseract_binary": bundled_binary.name,
        "lib_count": len(copied_dylibs),
        "libs": copied_dylibs,
        "tessdata_files": sorted(path.name for path in tessdata_dir.iterdir()),
    }
    (runtime_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Bundled Tesseract runtime into {runtime_dir}")


if __name__ == "__main__":
    main()

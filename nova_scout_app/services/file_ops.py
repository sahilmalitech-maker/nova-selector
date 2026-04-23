from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from nova_scout_app.models import ImageRecord
from nova_scout_app.services.text_processing import is_image_file, normalize_name


def safe_copy_file(source_path: str, destination_dir: str) -> str:
    destination_root = Path(destination_dir)
    destination_root.mkdir(parents=True, exist_ok=True)

    source = Path(source_path)
    destination = destination_root / source.name
    stem = source.stem
    suffix = source.suffix
    counter = 1

    while destination.exists():
        destination = destination_root / f"{stem}_{counter}{suffix}"
        counter += 1

    shutil.copy2(source_path, destination)
    return str(destination)


def validate_folder_pair(source_dir: str, destination_dir: str) -> tuple[bool, str]:
    source_path = Path(source_dir).expanduser().resolve()
    destination_path = Path(destination_dir).expanduser().resolve()

    if not source_path.exists() or not source_path.is_dir():
        return False, "The source folder is missing or invalid."
    if source_path == destination_path:
        return False, "Source and destination folders must be different."

    try:
        common = Path(os.path.commonpath([str(source_path), str(destination_path)]))
    except ValueError:
        return True, ""

    if common == source_path:
        return False, "Place the destination outside the source folder to avoid recursive copies."
    if common == destination_path:
        return False, "Place the destination outside the source folder hierarchy for clean indexing."

    return True, ""


def collect_image_records(
    source_dir: str,
    progress_callback: Callable[[int], None] | None = None,
) -> list[ImageRecord]:
    records: list[ImageRecord] = []
    discovered = 0

    for root, _, files in os.walk(source_dir):
        for file_name in files:
            if not is_image_file(file_name):
                continue

            full_path = os.path.join(root, file_name)
            try:
                stat_result = os.stat(full_path)
            except OSError:
                continue

            stem = Path(file_name).stem
            records.append(
                ImageRecord(
                    path=full_path,
                    name=file_name,
                    stem=stem,
                    normalized=normalize_name(stem),
                    extension=Path(file_name).suffix.lower(),
                    size=stat_result.st_size,
                    modified=stat_result.st_mtime,
                )
            )
            discovered += 1
            if progress_callback and discovered % 25 == 0:
                progress_callback(discovered)

    records.sort(key=lambda item: item.name.casefold())
    if progress_callback:
        progress_callback(discovered)
    return records


def read_cv_image(path: str) -> np.ndarray | None:
    try:
        raw = np.fromfile(path, dtype=np.uint8)
        if raw.size == 0:
            return None
        return cv2.imdecode(raw, cv2.IMREAD_COLOR)
    except Exception:
        return None

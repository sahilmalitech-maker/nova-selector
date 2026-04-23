from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable

from nova_scout_app.constants import NORMALIZE_PATTERN, OCR_CLEAN_PATTERN, QUERY_SPLIT_PATTERN, SUPPORTED_EXTENSIONS


def is_image_file(path: str) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def normalize_name(value: str) -> str:
    value = os.path.splitext(os.path.basename(value.strip()))[0]
    return NORMALIZE_PATTERN.sub("", value.lower())


def clean_ocr_text(text: str) -> list[str]:
    candidates: list[str] = []
    for raw_line in text.splitlines():
        cleaned = OCR_CLEAN_PATTERN.sub(" ", raw_line)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ._-|")
        if not cleaned:
            continue
        for chunk in re.split(r"[,\t]+", cleaned):
            chunk = chunk.strip(" ._-|")
            if len(chunk) >= 2 and re.search(r"[A-Za-z0-9]", chunk):
                candidates.append(chunk)

    unique: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        key = item.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def parse_queries(text: str) -> list[str]:
    chunks = QUERY_SPLIT_PATTERN.split(text)
    cleaned: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        item = OCR_CLEAN_PATTERN.sub(" ", chunk)
        item = re.sub(r"\s+", " ", item).strip(" ._-")
        if len(item) < 2:
            continue
        key = item.casefold()
        if key not in seen:
            seen.add(key)
            cleaned.append(item)
    return cleaned


def unique_paths(paths: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            result.append(path)
    return result


def format_similarity(score: float) -> str:
    return f"{score:.3f}"

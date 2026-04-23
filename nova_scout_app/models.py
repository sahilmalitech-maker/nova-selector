from __future__ import annotations

from dataclasses import dataclass

from .constants import DATACLASS_OPTIONS


@dataclass(**DATACLASS_OPTIONS)
class ImageRecord:
    path: str
    name: str
    stem: str
    normalized: str
    extension: str
    size: int
    modified: float


@dataclass(**DATACLASS_OPTIONS)
class ProcessingOptions:
    fuzzy_threshold: int = 82
    visual_threshold: float = 0.78
    visual_candidate_depth: int = 8


@dataclass
class MatchResult:
    total_source_images: int
    copied_files: list[str]
    missing_queries: list[str]
    unmatched_references: list[str]
    matched_by_name: dict[str, list[str]]
    matched_by_visual: dict[str, list[tuple[str, float]]]
    warnings: list[str]
    vision_engine: str
    report_text: str


@dataclass
class PhotoSelectionItem:
    path: str
    score: float
    selected: bool
    category: str
    reasons: list[str]
    metrics: dict[str, float | int | str]


@dataclass
class PhotoSelectionResult:
    source_dir: str
    total_source_images: int
    selected_items: list[PhotoSelectionItem]
    rejected_items: list[PhotoSelectionItem]
    vision_engine: str
    warnings: list[str]
    elapsed_seconds: float
    profile_id: str
    shoot_type: str
    learning_summary: str

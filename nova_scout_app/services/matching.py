from __future__ import annotations

import difflib
from collections import defaultdict
from pathlib import Path
from typing import Callable, Sequence

from nova_scout_app.models import ImageRecord
from nova_scout_app.services.text_processing import normalize_name


def match_queries_by_name(
    records: Sequence[ImageRecord],
    queries: Sequence[str],
    threshold: int,
    progress_callback: Callable[[int, int], None] | None = None,
) -> tuple[dict[str, list[str]], list[str], set[str]]:
    index: dict[str, list[ImageRecord]] = defaultdict(list)
    for record in records:
        index[record.normalized].append(record)

    matched: dict[str, list[str]] = {}
    missing: list[str] = []
    matched_paths: set[str] = set()
    total_queries = len(queries)

    for position, query in enumerate(queries, start=1):
        normalized_query = normalize_name(query)
        if not normalized_query:
            continue

        direct_hits = index.get(normalized_query, [])
        if direct_hits:
            hits = [item.path for item in direct_hits]
            matched[query] = hits
            matched_paths.update(hits)
            if progress_callback:
                progress_callback(position, total_queries)
            continue

        substring_hits: list[ImageRecord] = []
        if len(normalized_query) >= 4:
            for record in records:
                if normalized_query in record.normalized or record.normalized in normalized_query:
                    substring_hits.append(record)

        if substring_hits:
            substring_hits.sort(key=lambda item: (abs(len(item.normalized) - len(normalized_query)), item.name.casefold()))
            selected = [item.path for item in substring_hits[: min(5, len(substring_hits))]]
            matched[query] = selected
            matched_paths.update(selected)
            if progress_callback:
                progress_callback(position, total_queries)
            continue

        ranked: list[tuple[int, ImageRecord]] = []
        for record in records:
            score = int(difflib.SequenceMatcher(None, normalized_query, record.normalized).ratio() * 100)
            if score >= threshold:
                ranked.append((score, record))

        if ranked:
            ranked.sort(key=lambda item: (-item[0], abs(len(item[1].normalized) - len(normalized_query)), item[1].name.casefold()))
            best_score = ranked[0][0]
            selected_records = [record for score, record in ranked if score >= max(threshold, best_score - 3)][:5]
            selected = [record.path for record in selected_records]
            matched[query] = selected
            matched_paths.update(selected)
        else:
            missing.append(query)

        if progress_callback:
            progress_callback(position, total_queries)

    return matched, missing, matched_paths


def assign_unique_visual_matches(
    visual_candidates: dict[str, list[tuple[str, float]]],
) -> tuple[dict[str, list[tuple[str, float]]], list[str]]:
    ranked_candidates: list[tuple[float, int, str, str]] = []
    for reference_path, candidates in visual_candidates.items():
        for rank, (candidate_path, score) in enumerate(candidates):
            ranked_candidates.append((score, rank, reference_path, candidate_path))

    ranked_candidates.sort(
        key=lambda item: (
            -item[0],
            item[1],
            Path(item[2]).name.casefold(),
            Path(item[3]).name.casefold(),
        )
    )

    assigned_matches: dict[str, tuple[str, float]] = {}
    used_source_paths: set[str] = set()
    for score, _rank, reference_path, candidate_path in ranked_candidates:
        if reference_path in assigned_matches or candidate_path in used_source_paths:
            continue
        assigned_matches[reference_path] = (candidate_path, score)
        used_source_paths.add(candidate_path)

    matched_by_visual = {
        Path(reference_path).name: [assigned_matches[reference_path]]
        for reference_path in visual_candidates
        if reference_path in assigned_matches
    }
    unresolved_references = [
        Path(reference_path).name
        for reference_path in visual_candidates
        if reference_path not in assigned_matches
    ]
    return matched_by_visual, unresolved_references

from __future__ import annotations

import os
import traceback
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from nova_scout_app.models import MatchResult, ProcessingOptions
from nova_scout_app.services.file_ops import collect_image_records, safe_copy_file, validate_folder_pair
from nova_scout_app.services.matching import assign_unique_visual_matches, match_queries_by_name
from nova_scout_app.services.reporting import build_match_report
from nova_scout_app.services.vision import FeatureCache, VisionEngine


class ProcessingThread(QThread):
    progress_changed = pyqtSignal(int)
    status_changed = pyqtSignal(str)
    stats_changed = pyqtSignal(int, int, int)
    warning_emitted = pyqtSignal(str)
    engine_changed = pyqtSignal(str)
    result_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        source_dir: str,
        destination_dir: str,
        queries: list[str],
        reference_images: list[str],
        options: ProcessingOptions,
    ) -> None:
        super().__init__()
        self.source_dir = source_dir
        self.destination_dir = destination_dir
        self.queries = queries
        self.reference_images = reference_images
        self.options = options
        self.cache = FeatureCache()
        self.warnings: list[str] = []
        self.total_source_images = 0
        self.copied_count = 0

    def _set_status(self, text: str) -> None:
        self.status_changed.emit(text)

    def _set_progress(self, value: int) -> None:
        self.progress_changed.emit(max(0, min(100, value)))

    def _update_stats(self) -> None:
        remaining = max(self.total_source_images - self.copied_count, 0)
        self.stats_changed.emit(self.total_source_images, self.copied_count, remaining)

    def _progress_from_stage(self, start: int, end: int, index: int, total: int) -> None:
        if total <= 0:
            self._set_progress(end)
            return
        ratio = min(max(index / total, 0.0), 1.0)
        self._set_progress(int(start + ((end - start) * ratio)))

    def run(self) -> None:
        try:
            is_valid, validation_message = validate_folder_pair(self.source_dir, self.destination_dir)
            if not is_valid:
                raise ValueError(validation_message)

            os.makedirs(self.destination_dir, exist_ok=True)

            self._set_status("Scanning source library...")
            self._set_progress(3)

            records = collect_image_records(
                self.source_dir,
                progress_callback=lambda discovered: (
                    self._set_status(f"Scanning source library... {discovered} image(s) indexed"),
                    self._set_progress(min(15, 3 + (discovered // 40))),
                ),
            )
            self.total_source_images = len(records)
            self._update_stats()
            if not records:
                raise ValueError("No supported images were found in the source folder.")

            source_paths = [record.path for record in records]
            matched_by_name: dict[str, list[str]] = {}
            missing_queries: list[str] = []
            selected_paths: set[str] = set()

            if self.queries:
                self._set_status("Matching text queries against filenames...")
                matched_by_name, missing_queries, name_matched_paths = match_queries_by_name(
                    records,
                    self.queries,
                    self.options.fuzzy_threshold,
                    progress_callback=lambda position, total: (
                        self._set_status(f"Matching text queries... {position}/{total}"),
                        self._progress_from_stage(16, 32, position, total),
                    ),
                )
                selected_paths.update(name_matched_paths)
            else:
                self._set_progress(32)

            matched_by_visual: dict[str, list[tuple[str, float]]] = {}
            unmatched_references: list[str] = []
            vision_engine = "Not used"

            if self.reference_images:
                self._set_status("Loading vision model...")
                vision_engine_instance = VisionEngine()
                vision_engine = vision_engine_instance.ensure_ready()
                self.engine_changed.emit(vision_engine)
                if vision_engine_instance.warning:
                    self.warnings.append(vision_engine_instance.warning)
                    self.warning_emitted.emit(vision_engine_instance.warning)

                ref_embeddings = vision_engine_instance.compute_embeddings(
                    self.reference_images,
                    cache=self.cache,
                    progress_callback=lambda done, total, message: (
                        self._set_status(message),
                        self._progress_from_stage(33, 48, done, total),
                    ),
                )

                source_embeddings = vision_engine_instance.compute_embeddings(
                    source_paths,
                    cache=self.cache,
                    progress_callback=lambda done, total, message: (
                        self._set_status(message),
                        self._progress_from_stage(49, 76, done, total),
                    ),
                )

                ordered_source_paths = [path for path in source_paths if path in source_embeddings]
                if ordered_source_paths and ref_embeddings:
                    source_matrix = np.vstack([source_embeddings[path] for path in ordered_source_paths]).astype(np.float32)
                    visual_candidates: dict[str, list[tuple[str, float]]] = {}
                    candidate_depth = min(len(ordered_source_paths), max(2, self.options.visual_candidate_depth))

                    for index, reference_path in enumerate(self.reference_images, start=1):
                        if reference_path not in ref_embeddings:
                            unmatched_references.append(Path(reference_path).name)
                            self._progress_from_stage(77, 85, index, len(self.reference_images))
                            continue

                        similarity = source_matrix @ ref_embeddings[reference_path]
                        similarity = np.nan_to_num(similarity, nan=0.0, posinf=0.0, neginf=0.0)
                        if candidate_depth < len(ordered_source_paths):
                            top_indices = np.argpartition(similarity, -candidate_depth)[-candidate_depth:]
                            ranked_indices = top_indices[np.argsort(similarity[top_indices])[::-1]]
                        else:
                            ranked_indices = np.argsort(similarity)[::-1]

                        confident_matches: list[tuple[str, float]] = []
                        for ranked_index in ranked_indices:
                            score = float(similarity[ranked_index])
                            if score < self.options.visual_threshold:
                                break
                            candidate_path = ordered_source_paths[int(ranked_index)]
                            confident_matches.append((candidate_path, score))
                            if len(confident_matches) >= candidate_depth:
                                break

                        if confident_matches:
                            visual_candidates[reference_path] = confident_matches
                        else:
                            unmatched_references.append(Path(reference_path).name)

                        self._set_status(
                            f"Comparing visual embeddings... {index}/{len(self.reference_images)} reference image(s)"
                        )
                        self._progress_from_stage(77, 85, index, len(self.reference_images))

                    if visual_candidates:
                        self._set_status("Resolving best unique visual matches...")
                        matched_by_visual, unresolved_references = assign_unique_visual_matches(visual_candidates)
                        selected_paths.update(
                            matched_path
                            for matches in matched_by_visual.values()
                            for matched_path, _score in matches
                        )
                        unmatched_references.extend(unresolved_references)
                else:
                    unmatched_references.extend(Path(path).name for path in self.reference_images)
            else:
                self._set_progress(85)

            unique_selected_paths = sorted(selected_paths)
            copied_files: list[str] = []

            if unique_selected_paths:
                self._set_status("Copying matched images...")
                copy_total = len(unique_selected_paths)
                for index, image_path in enumerate(unique_selected_paths, start=1):
                    destination_path = safe_copy_file(image_path, self.destination_dir)
                    copied_files.append(destination_path)
                    self.copied_count = len(copied_files)
                    self._update_stats()
                    self._set_status(f"Copying matched images... {index}/{copy_total}")
                    self._progress_from_stage(86, 100, index, copy_total)
            else:
                self._set_progress(100)

            report_text = build_match_report(
                source_dir=self.source_dir,
                destination_dir=self.destination_dir,
                total_source_images=self.total_source_images,
                queries=self.queries,
                reference_images=self.reference_images,
                copied_files=copied_files,
                missing_queries=missing_queries,
                unmatched_references=unmatched_references,
                matched_by_name=matched_by_name,
                matched_by_visual=matched_by_visual,
                vision_engine=vision_engine,
                warnings=self.warnings,
            )
            result = MatchResult(
                total_source_images=self.total_source_images,
                copied_files=copied_files,
                missing_queries=missing_queries,
                unmatched_references=unmatched_references,
                matched_by_name=matched_by_name,
                matched_by_visual=matched_by_visual,
                warnings=self.warnings,
                vision_engine=vision_engine,
                report_text=report_text,
            )
            self.cache.save()
            self._set_status("Completed successfully.")
            self.result_ready.emit(result)
        except Exception:
            self.cache.save()
            self.error_occurred.emit(traceback.format_exc())

from __future__ import annotations

import traceback

from PyQt6.QtCore import QThread, pyqtSignal

from nova_scout_app.services.file_ops import collect_image_records
from nova_scout_app.services.photo_selection import select_best_photos
from nova_scout_app.services.vision import FeatureCache


class PhotoSelectionThread(QThread):
    progress_changed = pyqtSignal(int)
    status_changed = pyqtSignal(str)
    stats_changed = pyqtSignal(int, int, int)
    warning_emitted = pyqtSignal(str)
    engine_changed = pyqtSignal(str)
    result_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(self, source_dir: str, profile_id: str) -> None:
        super().__init__()
        self.source_dir = source_dir
        self.profile_id = profile_id
        self.cache = FeatureCache()

    def _set_progress(self, value: int) -> None:
        self.progress_changed.emit(max(0, min(100, value)))

    def run(self) -> None:
        try:
            self.status_changed.emit("Scanning source folder for photos...")
            self._set_progress(3)
            records = collect_image_records(
                self.source_dir,
                progress_callback=lambda discovered: (
                    self.status_changed.emit(f"Scanning source folder... {discovered} photo(s) found"),
                    self._set_progress(min(8, 3 + (discovered // 60))),
                ),
            )
            if not records:
                raise ValueError("No supported photos were found in the source folder.")

            self.stats_changed.emit(len(records), 0, 0)
            result = select_best_photos(
                source_dir=self.source_dir,
                records=records,
                cache=self.cache,
                profile_id=self.profile_id,
                progress_callback=self._set_progress,
                status_callback=self.status_changed.emit,
                engine_callback=self.engine_changed.emit,
                warning_callback=self.warning_emitted.emit,
            )
            self.cache.save()
            self.stats_changed.emit(
                result.total_source_images,
                len(result.selected_items),
                len(result.rejected_items),
            )
            self.result_ready.emit(result)
        except Exception:
            self.cache.save()
            self.error_occurred.emit(traceback.format_exc())

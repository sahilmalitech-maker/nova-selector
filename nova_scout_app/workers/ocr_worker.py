from __future__ import annotations

import pytesseract
from PyQt6.QtCore import QThread, pyqtSignal

from nova_scout_app.services.ocr import extract_queries_from_screenshot


class OCRThread(QThread):
    finished_with_queries = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(self, image_path: str) -> None:
        super().__init__()
        self.image_path = image_path

    def run(self) -> None:
        try:
            queries = extract_queries_from_screenshot(self.image_path)
            self.finished_with_queries.emit(queries)
        except pytesseract.TesseractNotFoundError:
            self.error_occurred.emit(
                "Tesseract OCR was not found. Install Tesseract locally and ensure it is available in your PATH."
            )
        except Exception as exc:
            self.error_occurred.emit(f"OCR failed: {exc}")

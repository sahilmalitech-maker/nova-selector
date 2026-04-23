from __future__ import annotations

import re
import sys
from pathlib import Path


APP_TITLE = "Nova Image Scout"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
QUERY_SPLIT_PATTERN = re.compile(r"[,;\n\r\t]+")
OCR_CLEAN_PATTERN = re.compile(r"[^A-Za-z0-9._\-\s]+")
NORMALIZE_PATTERN = re.compile(r"[^a-z0-9]+")
CACHE_PATH = Path.home() / ".nova_image_scout" / "feature_cache.pkl"
MAX_CACHE_ITEMS = 12000
DEFAULT_BATCH_SIZE = 24
MAX_REPORT_COPY_LINES = 150
DATACLASS_OPTIONS = {"slots": True} if sys.version_info >= (3, 10) else {}

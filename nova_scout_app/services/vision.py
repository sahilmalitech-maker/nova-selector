from __future__ import annotations

import os
import pickle
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Sequence

import cv2
import numpy as np
from PIL import Image

from nova_scout_app.constants import CACHE_PATH, DEFAULT_BATCH_SIZE, MAX_CACHE_ITEMS
from nova_scout_app.services.file_ops import read_cv_image
from nova_scout_app.services.text_processing import unique_paths


class FeatureCache:
    def __init__(self, path: Path = CACHE_PATH, max_items: int = MAX_CACHE_ITEMS) -> None:
        self.path = path
        self.max_items = max_items
        self.entries: dict[str, dict[str, object]] = {}
        self.dirty = False
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("rb") as handle:
                loaded = pickle.load(handle)
            if isinstance(loaded, dict):
                self.entries = loaded
        except Exception:
            self.entries = {}

    def _signature(self, image_path: str) -> tuple[int, int]:
        stat_result = os.stat(image_path)
        return stat_result.st_mtime_ns, stat_result.st_size

    def get(self, image_path: str, engine_name: str) -> np.ndarray | None:
        entry = self.entries.get(image_path)
        if not entry or entry.get("engine") != engine_name:
            return None
        try:
            if tuple(entry.get("signature", ())) != self._signature(image_path):
                return None
        except OSError:
            return None

        feature = entry.get("feature")
        if feature is None:
            return None
        return np.asarray(feature, dtype=np.float32)

    def set(self, image_path: str, engine_name: str, feature: np.ndarray) -> None:
        try:
            signature = self._signature(image_path)
        except OSError:
            return

        self.entries[image_path] = {
            "engine": engine_name,
            "signature": signature,
            "feature": np.asarray(feature, dtype=np.float32),
        }
        self.dirty = True

        if len(self.entries) > self.max_items:
            overflow = len(self.entries) - self.max_items
            for stale_key in list(self.entries.keys())[:overflow]:
                self.entries.pop(stale_key, None)

    def save(self) -> None:
        if not self.dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.path.open("wb") as handle:
                pickle.dump(self.entries, handle, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            pass


class VisionEngine:
    def __init__(self) -> None:
        self.model = None
        self.preprocess_input = None
        self.model_kind = "opencv"
        self.torch_preprocess = None
        self.torch_device = None
        self.engine_name = "Hybrid OpenCV Descriptor"
        self.warning: str | None = None
        self._initialized = False

    def ensure_ready(self) -> str:
        if self._initialized:
            return self.engine_name
        self._initialized = True

        try:
            import torch
            import open_clip

            if torch.backends.mps.is_available():
                device = "mps"
            elif torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
            model, _, preprocess = open_clip.create_model_and_transforms(
                "ViT-B-32",
                pretrained="laion2b_s34b_b79k",
            )
            model.eval().to(device)
            self.model = model
            self.torch_preprocess = preprocess
            self.torch_device = device
            self.model_kind = "clip"
            self.engine_name = f"CLIP ViT-B/32 ({device})"
            return self.engine_name
        except Exception:
            self.model = None
            self.torch_preprocess = None
            self.torch_device = None
            self.model_kind = "opencv"

        try:
            from tensorflow.keras.applications.mobilenet_v2 import MobileNetV2, preprocess_input

            self.model = MobileNetV2(weights="imagenet", include_top=False, pooling="avg", input_shape=(224, 224, 3))
            self.preprocess_input = preprocess_input
            self.model_kind = "mobilenet"
            self.engine_name = "MobileNetV2 (ImageNet)"
        except Exception as exc:
            self.model = None
            self.preprocess_input = None
            self.model_kind = "opencv"
            self.engine_name = "Hybrid OpenCV Descriptor"
            self.warning = (
                "CLIP and TensorFlow MobileNetV2 could not be loaded. "
                "Visual search switched to the OpenCV fallback descriptor.\n"
                f"Reason: {exc}"
            )
        return self.engine_name

    @staticmethod
    def _normalize_feature(feature: np.ndarray) -> np.ndarray:
        norm = float(np.linalg.norm(feature))
        if norm <= 1e-9:
            return feature.astype(np.float32)
        return (feature / norm).astype(np.float32)

    def _prepare_mobilenet_image(self, image_path: str) -> tuple[str, np.ndarray] | None:
        image = read_cv_image(image_path)
        if image is None:
            return None
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (224, 224), interpolation=cv2.INTER_AREA)
        return image_path, resized.astype(np.float32)

    def _compute_mobilenet_embeddings(
        self,
        image_paths: Sequence[str],
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> dict[str, np.ndarray]:
        if self.model is None or self.preprocess_input is None:
            return {}

        results: dict[str, np.ndarray] = {}
        total = len(image_paths)
        workers = max(2, min(8, os.cpu_count() or 4))

        with ThreadPoolExecutor(max_workers=workers) as executor:
            for start in range(0, total, DEFAULT_BATCH_SIZE):
                batch_paths = list(image_paths[start : start + DEFAULT_BATCH_SIZE])
                prepared = list(executor.map(self._prepare_mobilenet_image, batch_paths))
                valid_items = [item for item in prepared if item is not None]
                if not valid_items:
                    if progress_callback:
                        progress_callback(min(start + len(batch_paths), total), total, "Skipping unreadable images")
                    continue

                valid_paths = [item[0] for item in valid_items]
                batch_array = np.stack([item[1] for item in valid_items], axis=0)
                batch_array = self.preprocess_input(batch_array)
                embeddings = self.model.predict(batch_array, verbose=0)

                for index, image_path in enumerate(valid_paths):
                    results[image_path] = self._normalize_feature(embeddings[index])

                if progress_callback:
                    progress_callback(
                        min(start + len(batch_paths), total),
                        total,
                        "Extracting MobileNetV2 visual embeddings",
                    )

        return results

    def _prepare_clip_image(self, image_path: str):
        if self.torch_preprocess is None:
            return None
        try:
            with Image.open(image_path) as image:
                rgb = image.convert("RGB")
                return image_path, self.torch_preprocess(rgb)
        except Exception:
            return None

    def _compute_clip_embeddings(
        self,
        image_paths: Sequence[str],
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> dict[str, np.ndarray]:
        if self.model is None or self.torch_preprocess is None or self.torch_device is None:
            return {}

        import torch

        results: dict[str, np.ndarray] = {}
        total = len(image_paths)
        workers = max(2, min(8, os.cpu_count() or 4))

        with ThreadPoolExecutor(max_workers=workers) as executor:
            for start in range(0, total, DEFAULT_BATCH_SIZE):
                batch_paths = list(image_paths[start : start + DEFAULT_BATCH_SIZE])
                prepared = list(executor.map(self._prepare_clip_image, batch_paths))
                valid_items = [item for item in prepared if item is not None]
                if not valid_items:
                    if progress_callback:
                        progress_callback(min(start + len(batch_paths), total), total, "Skipping unreadable images")
                    continue

                valid_paths = [item[0] for item in valid_items]
                batch_tensor = torch.stack([item[1] for item in valid_items], dim=0).to(self.torch_device)
                with torch.no_grad():
                    embeddings = self.model.encode_image(batch_tensor)
                    embeddings = embeddings / embeddings.norm(dim=-1, keepdim=True).clamp_min(1e-9)
                embeddings_np = embeddings.detach().cpu().numpy().astype(np.float32)

                for index, image_path in enumerate(valid_paths):
                    results[image_path] = self._normalize_feature(embeddings_np[index])

                if progress_callback:
                    progress_callback(
                        min(start + len(batch_paths), total),
                        total,
                        "Extracting CLIP visual embeddings",
                    )

        return results

    def _compute_fallback_feature(self, image_path: str) -> tuple[str, np.ndarray] | None:
        image = read_cv_image(image_path)
        if image is None:
            return None

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray_small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
        edges = cv2.Canny(gray, 50, 150)

        hist = cv2.calcHist([hsv], [0, 1, 2], None, [12, 4, 4], [0, 180, 0, 256, 0, 256]).flatten()
        edge_hist = cv2.calcHist([edges], [0], None, [16], [0, 256]).flatten()
        dct = cv2.dct(np.float32(gray_small) / 255.0)[:8, :8].flatten()
        hu_moments = cv2.HuMoments(cv2.moments(gray)).flatten()
        hu_moments = np.sign(hu_moments) * np.log1p(np.abs(hu_moments))

        feature = np.concatenate([hist, edge_hist, dct, hu_moments]).astype(np.float32)
        return image_path, self._normalize_feature(feature)

    def _compute_fallback_embeddings(
        self,
        image_paths: Sequence[str],
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> dict[str, np.ndarray]:
        total = len(image_paths)
        if total == 0:
            return {}

        workers = max(2, min(8, os.cpu_count() or 4))
        results: dict[str, np.ndarray] = {}

        with ThreadPoolExecutor(max_workers=workers) as executor:
            for index, item in enumerate(executor.map(self._compute_fallback_feature, image_paths), start=1):
                if item is not None:
                    path, feature = item
                    results[path] = feature
                if progress_callback and (index % 10 == 0 or index == total):
                    progress_callback(index, total, "Extracting OpenCV fallback visual descriptors")

        return results

    def compute_embeddings(
        self,
        image_paths: Sequence[str],
        cache: FeatureCache | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> dict[str, np.ndarray]:
        self.ensure_ready()

        image_paths = unique_paths(image_paths)
        if not image_paths:
            return {}

        cached_results: dict[str, np.ndarray] = {}
        uncached_paths: list[str] = []
        for image_path in image_paths:
            if cache is None:
                uncached_paths.append(image_path)
                continue

            cached = cache.get(image_path, self.engine_name)
            if cached is not None:
                cached_results[image_path] = cached
            else:
                uncached_paths.append(image_path)

        if progress_callback and cached_results:
            progress_callback(len(cached_results), len(image_paths), "Loaded cached visual embeddings")

        if not uncached_paths:
            return cached_results

        cached_count = len(cached_results)
        wrapped_progress = None
        if progress_callback is not None:
            wrapped_progress = lambda done, _total, message: progress_callback(
                cached_count + done,
                len(image_paths),
                message,
            )

        if self.model_kind == "clip":
            fresh = self._compute_clip_embeddings(uncached_paths, wrapped_progress)
        elif self.model is not None and self.preprocess_input is not None:
            fresh = self._compute_mobilenet_embeddings(uncached_paths, wrapped_progress)
        else:
            fresh = self._compute_fallback_embeddings(uncached_paths, wrapped_progress)

        for image_path, feature in fresh.items():
            cached_results[image_path] = feature
            if cache is not None:
                cache.set(image_path, self.engine_name, feature)

        return cached_results

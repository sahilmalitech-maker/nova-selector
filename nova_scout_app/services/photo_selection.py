from __future__ import annotations

import json
import os
import re
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Sequence

import cv2
import numpy as np

from nova_scout_app.models import ImageRecord, PhotoSelectionItem, PhotoSelectionResult
from nova_scout_app.services.file_ops import read_cv_image
from nova_scout_app.services.vision import FeatureCache, VisionEngine


ProgressCallback = Callable[[int], None]
StatusCallback = Callable[[str], None]
EngineCallback = Callable[[str], None]
WarningCallback = Callable[[str], None]

SELECT_CATEGORY = "SELECT"
REJECT_CATEGORY = "REJECT"
DEFAULT_PROFILE_ID = "local-photographer"
PREFERENCE_PROFILE_PATH = Path.home() / ".nova_image_scout" / "preference_profiles.json"
SEVERE_DISTRACTION_SCORE = 0.92
_SEQUENCE_PATTERN = re.compile(r"^(.*?)(\d+)$")

_THREAD_LOCAL = threading.local()


def _cascade_path(file_name: str) -> str:
    base_dir = getattr(cv2.data, "haarcascades", "")
    return os.path.join(base_dir, file_name)


def _get_cascades() -> tuple[cv2.CascadeClassifier | None, cv2.CascadeClassifier | None]:
    face_cascade = getattr(_THREAD_LOCAL, "face_cascade", None)
    eye_cascade = getattr(_THREAD_LOCAL, "eye_cascade", None)
    initialized = getattr(_THREAD_LOCAL, "cascades_initialized", False)

    if initialized:
        return face_cascade, eye_cascade

    face_cascade = cv2.CascadeClassifier(_cascade_path("haarcascade_frontalface_default.xml"))
    eye_cascade = cv2.CascadeClassifier(_cascade_path("haarcascade_eye_tree_eyeglasses.xml"))

    if face_cascade.empty():
        face_cascade = None
    if eye_cascade.empty():
        eye_cascade = None

    _THREAD_LOCAL.face_cascade = face_cascade
    _THREAD_LOCAL.eye_cascade = eye_cascade
    _THREAD_LOCAL.cascades_initialized = True
    return face_cascade, eye_cascade


def _get_body_detector() -> tuple[cv2.CascadeClassifier | None, cv2.CascadeClassifier | None]:
    detector = getattr(_THREAD_LOCAL, "body_detector", None)
    initialized = getattr(_THREAD_LOCAL, "body_detector_initialized", False)
    if initialized:
        return detector

    upper_body = cv2.CascadeClassifier(_cascade_path("haarcascade_upperbody.xml"))
    full_body = cv2.CascadeClassifier(_cascade_path("haarcascade_fullbody.xml"))
    if upper_body.empty():
        upper_body = None
    if full_body.empty():
        full_body = None
    detector = (upper_body, full_body)

    _THREAD_LOCAL.body_detector = detector
    _THREAD_LOCAL.body_detector_initialized = True
    return detector


def _resize_for_analysis(image: np.ndarray, max_side: int = 720) -> np.ndarray:
    height, width = image.shape[:2]
    largest_side = max(height, width)
    if largest_side <= max_side:
        return image
    scale = max_side / float(largest_side)
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)


def _safe_crop(gray: np.ndarray, x0: float, y0: float, x1: float, y1: float) -> np.ndarray:
    height, width = gray.shape[:2]
    left = max(0, min(width - 1, int(width * x0)))
    top = max(0, min(height - 1, int(height * y0)))
    right = max(left + 1, min(width, int(width * x1)))
    bottom = max(top + 1, min(height, int(height * y1)))
    return gray[top:bottom, left:right]


def _laplacian_variance(gray: np.ndarray) -> float:
    if gray.size == 0:
        return 0.0
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _edge_density(gray: np.ndarray) -> float:
    if gray.size == 0:
        return 0.0
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, 70, 170)
    return float(np.mean(edges > 0))


def _tenengrad_focus(gray: np.ndarray) -> float:
    if gray.size == 0:
        return 0.0
    resized = _resize_gray(gray, 640)
    gradient_x = cv2.Sobel(resized, cv2.CV_32F, 1, 0, ksize=3)
    gradient_y = cv2.Sobel(resized, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = cv2.magnitude(gradient_x, gradient_y)
    return float(np.mean(magnitude))


def _resize_gray(gray: np.ndarray, max_side: int) -> np.ndarray:
    height, width = gray.shape[:2]
    largest_side = max(height, width)
    if largest_side <= max_side:
        return gray
    scale = max_side / float(largest_side)
    return cv2.resize(
        gray,
        (max(1, int(width * scale)), max(1, int(height * scale))),
        interpolation=cv2.INTER_AREA,
    )


def _detail_distribution(gray: np.ndarray) -> tuple[float, float, float]:
    if gray.size == 0:
        return 0.0, 0.0, 0.0

    small = _resize_gray(gray, 420)
    gradient_x = cv2.Sobel(small, cv2.CV_32F, 1, 0, ksize=3)
    gradient_y = cv2.Sobel(small, cv2.CV_32F, 0, 1, ksize=3)
    detail = cv2.magnitude(gradient_x, gradient_y)
    total_detail = float(np.sum(detail)) + 1e-6

    height, width = small.shape[:2]
    y_indices, x_indices = np.indices((height, width), dtype=np.float32)
    center_x = (width - 1) / 2.0
    center_y = (height - 1) / 2.0
    normalized_distance = np.sqrt(((x_indices - center_x) / max(width, 1)) ** 2 + ((y_indices - center_y) / max(height, 1)) ** 2)
    center_weight = np.clip(1.0 - normalized_distance * 2.8, 0.0, 1.0)

    top = int(height * 0.22)
    bottom = int(height * 0.78)
    left = int(width * 0.22)
    right = int(width * 0.78)
    center_detail = float(np.sum(detail[top:bottom, left:right])) / total_detail
    weighted_center_detail = float(np.sum(detail * center_weight)) / total_detail

    outer_mask = np.ones_like(small, dtype=bool)
    outer_mask[top:bottom, left:right] = False
    outer_detail = float(np.sum(detail[outer_mask])) / total_detail
    return center_detail, weighted_center_detail, outer_detail


def _color_quality(image: np.ndarray) -> tuple[float, float]:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1].astype(np.float32)
    saturation_mean = float(np.mean(saturation))
    saturation_std = float(np.std(saturation))
    saturation_score = _score_range(saturation_mean, 18.0, 86.0)
    oversaturation_penalty = _score_range(saturation_mean, 164.0, 224.0) * 0.35
    color_score = float(np.clip((saturation_score * 0.75) + (_score_range(saturation_std, 8.0, 42.0) * 0.25) - oversaturation_penalty, 0.0, 1.0))
    return color_score, saturation_mean


def _perceptual_hash(gray: np.ndarray) -> int:
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    diff = small[:, 1:] > small[:, :-1]
    value = 0
    for bit in diff.flatten():
        value = (value << 1) | int(bool(bit))
    return value


def _hamming_distance(left: int, right: int) -> int:
    value = max(0, int(left)) ^ max(0, int(right))
    distance = 0
    while value:
        value &= value - 1
        distance += 1
    return distance


def _score_range(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return float(np.clip((value - low) / (high - low), 0.0, 1.0))


def _clamp(value: float, low: float, high: float) -> float:
    return float(np.clip(value, low, high))


def _as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _default_context_profile() -> dict[str, object]:
    return {
        "utility_model_version": 2,
        "feedback_count": 0,
        "positive_feedback_count": 0,
        "negative_feedback_count": 0,
        "positive_preference_vector": [],
        "negative_preference_vector": [],
        "last_pairwise_loss": 0.0,
    }


def _profile_key(profile_id: str | None) -> str:
    cleaned = (profile_id or DEFAULT_PROFILE_ID).strip().casefold()
    return cleaned or DEFAULT_PROFILE_ID


def _load_profile_store() -> dict[str, object]:
    if not PREFERENCE_PROFILE_PATH.exists():
        return {"profiles": {}}
    try:
        with PREFERENCE_PROFILE_PATH.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict) and isinstance(loaded.get("profiles"), dict):
            return loaded
    except Exception:
        pass
    return {"profiles": {}}


def _save_profile_store(store: dict[str, object]) -> None:
    PREFERENCE_PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PREFERENCE_PROFILE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(store, handle, indent=2, sort_keys=True)


def load_preference_profile(profile_id: str | None) -> dict[str, object]:
    store = _load_profile_store()
    profiles = store.setdefault("profiles", {})
    key = _profile_key(profile_id)
    profile = profiles.get(key)
    if not isinstance(profile, dict):
        profile = {
            "profile_id": key,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "contexts": {},
        }
    profile.setdefault("profile_id", key)
    profile.setdefault("contexts", {})
    return profile


def _context_profile(profile: dict[str, object], shoot_type: str) -> dict[str, object]:
    contexts = profile.setdefault("contexts", {})
    if not isinstance(contexts, dict):
        contexts = {}
        profile["contexts"] = contexts

    context = contexts.get(shoot_type)
    if not isinstance(context, dict):
        context = _default_context_profile()
        global_context = contexts.get("General")
        if isinstance(global_context, dict):
            context = _merge_context_profiles(context, global_context)
        contexts[shoot_type] = context
    return context


def _merge_context_profiles(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key in (
        "utility_model",
        "preference_vector",
        "positive_preference_vector",
        "negative_preference_vector",
        "feedback_count",
        "positive_feedback_count",
        "negative_feedback_count",
        "last_feedback_at",
        "last_feedback_engine",
        "last_pairwise_loss",
    ):
        if key in override:
            merged[key] = override[key]
    return merged


def _dominant_shoot_type(source_dir: str, items: Sequence[PhotoSelectionItem]) -> str:
    text = f"{Path(source_dir).name} " + " ".join(Path(item.path).stem for item in items[:60])
    lowered = text.casefold()
    keyword_map = {
        "Wedding": ("wedding", "bride", "groom", "haldi", "sangeet", "reception", "ceremony"),
        "Maternity": ("maternity", "pregnancy", "baby bump", "mom", "motherhood"),
        "Fashion": ("fashion", "model", "lookbook", "editorial", "catalog", "portfolio"),
        "Portrait": ("portrait", "headshot", "profile", "studio"),
        "Event": ("event", "party", "birthday", "conference", "concert"),
        "Artistic": ("art", "creative", "abstract", "fineart", "fine-art", "detail"),
    }
    for shoot_type, keywords in keyword_map.items():
        if any(keyword in lowered for keyword in keywords):
            return shoot_type

    total = max(len(items), 1)
    face_ratio = sum(1 for item in items if _as_int(item.metrics.get("face_count")) > 0) / total
    multi_face_ratio = sum(1 for item in items if _as_int(item.metrics.get("face_count")) >= 3) / total
    no_human_ratio = sum(
        1
        for item in items
        if _as_int(item.metrics.get("face_count")) == 0 and _as_int(item.metrics.get("body_count")) == 0
    ) / total

    if multi_face_ratio > 0.22:
        return "Event"
    if face_ratio > 0.48:
        return "Portrait"
    if no_human_ratio > 0.72:
        return "Artistic"
    return "General"


def _component_score(metrics: dict[str, float | int | str], key: str) -> float:
    return _clamp(_as_float(metrics.get(key), 50.0), 0.0, 100.0)


def _set_category(item: PhotoSelectionItem, category: str, reason: str | None = None) -> None:
    item.category = category
    item.selected = category == SELECT_CATEGORY
    if reason is not None:
        item.reasons = [reason]
    item.metrics["category"] = category
    item.metrics["decision_reason"] = item.reasons[0] if item.reasons else ""


def _numeric_feature_vector(item: PhotoSelectionItem) -> np.ndarray:
    metrics = item.metrics
    values = [
        _component_score(metrics, "technical_quality") / 100.0,
        _component_score(metrics, "face_quality") / 100.0,
        _component_score(metrics, "aesthetic_value") / 100.0,
        _component_score(metrics, "composition_quality") / 100.0,
        _as_float(metrics.get("sharpness_score")),
        _as_float(metrics.get("exposure_score")),
        _as_float(metrics.get("dynamic_range_score")),
        _as_float(metrics.get("noise_score")),
        _as_float(metrics.get("subject_score")),
        _as_float(metrics.get("color_score")),
        1.0 - _as_float(metrics.get("distraction_score")),
        1.0 - _as_float(metrics.get("closed_eye_confidence")),
        _as_float(metrics.get("creative_preserve_score")),
        _as_float(metrics.get("weighted_center_detail")),
        _as_float(metrics.get("rule_of_thirds_score")),
        _as_float(metrics.get("framing_score")),
    ]
    return np.nan_to_num(np.asarray(values, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)


def _feature_vector(item: PhotoSelectionItem, embedding: np.ndarray) -> np.ndarray:
    embedding = np.nan_to_num(np.asarray(embedding, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    embedding_norm = float(np.linalg.norm(embedding))
    if embedding_norm > 1e-9:
        embedding = embedding / embedding_norm
    return np.nan_to_num(
        np.concatenate([embedding, _numeric_feature_vector(item)]).astype(np.float32),
        nan=0.0,
        posinf=0.0,
        neginf=0.0,
    )


def _stable_seed(*parts: object) -> int:
    text = "|".join(str(part) for part in parts)
    value = 2166136261
    for char in text:
        value ^= ord(char)
        value = (value * 16777619) & 0xFFFFFFFF
    return int(value or 1)


def _init_utility_model(input_dim: int, profile_id: str, shoot_type: str) -> dict[str, object]:
    seed = _stable_seed(profile_id, shoot_type, input_dim)
    rng = np.random.default_rng(seed)
    hidden_1 = max(24, min(96, int(np.sqrt(max(input_dim, 1)) * 4)))
    hidden_2 = max(12, hidden_1 // 2)
    return {
        "input_dim": input_dim,
        "hidden_1": hidden_1,
        "hidden_2": hidden_2,
        "w1": (rng.normal(0.0, 1.0 / np.sqrt(max(input_dim, 1)), size=(input_dim, hidden_1))).astype(np.float32).tolist(),
        "b1": np.zeros(hidden_1, dtype=np.float32).tolist(),
        "w2": (rng.normal(0.0, 1.0 / np.sqrt(max(hidden_1, 1)), size=(hidden_1, hidden_2))).astype(np.float32).tolist(),
        "b2": np.zeros(hidden_2, dtype=np.float32).tolist(),
        "w3": (rng.normal(0.0, 1.0 / np.sqrt(max(hidden_2, 1)), size=(hidden_2,))).astype(np.float32).tolist(),
        "b3": 0.0,
        "trained_pairs": 0,
    }


def _load_utility_model(context: dict[str, object], input_dim: int, profile_id: str, shoot_type: str) -> dict[str, object]:
    model = context.get("utility_model")
    if not isinstance(model, dict) or _as_int(model.get("input_dim")) != input_dim:
        return _init_utility_model(input_dim, profile_id, shoot_type)
    required_keys = {"w1", "b1", "w2", "b2", "w3", "b3"}
    if not required_keys.issubset(model.keys()):
        return _init_utility_model(input_dim, profile_id, shoot_type)
    return json.loads(json.dumps(model))


def _model_arrays(model: dict[str, object]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    return (
        np.clip(np.nan_to_num(np.asarray(model["w1"], dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0), -3.0, 3.0),
        np.clip(np.nan_to_num(np.asarray(model["b1"], dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0), -3.0, 3.0),
        np.clip(np.nan_to_num(np.asarray(model["w2"], dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0), -3.0, 3.0),
        np.clip(np.nan_to_num(np.asarray(model["b2"], dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0), -3.0, 3.0),
        np.clip(np.nan_to_num(np.asarray(model["w3"], dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0), -3.0, 3.0),
        float(np.clip(np.nan_to_num(float(model["b3"]), nan=0.0, posinf=0.0, neginf=0.0), -3.0, 3.0)),
    )


def _store_model_arrays(
    model: dict[str, object],
    w1: np.ndarray,
    b1: np.ndarray,
    w2: np.ndarray,
    b2: np.ndarray,
    w3: np.ndarray,
    b3: float,
) -> dict[str, object]:
    model["w1"] = np.clip(np.nan_to_num(np.asarray(w1, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0), -3.0, 3.0).tolist()
    model["b1"] = np.clip(np.nan_to_num(np.asarray(b1, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0), -3.0, 3.0).tolist()
    model["w2"] = np.clip(np.nan_to_num(np.asarray(w2, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0), -3.0, 3.0).tolist()
    model["b2"] = np.clip(np.nan_to_num(np.asarray(b2, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0), -3.0, 3.0).tolist()
    model["w3"] = np.clip(np.nan_to_num(np.asarray(w3, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0), -3.0, 3.0).tolist()
    model["b3"] = float(np.clip(np.nan_to_num(b3, nan=0.0, posinf=0.0, neginf=0.0), -3.0, 3.0))
    return model


def _mlp_forward(model: dict[str, object], vectors: np.ndarray) -> np.ndarray:
    w1, b1, w2, b2, w3, b3 = _model_arrays(model)
    safe_vectors = np.clip(np.nan_to_num(np.asarray(vectors, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0), -8.0, 8.0)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        hidden_1 = np.tanh(np.clip((safe_vectors @ w1) + b1, -20.0, 20.0))
        hidden_2 = np.tanh(np.clip((np.nan_to_num(hidden_1, nan=0.0, posinf=0.0, neginf=0.0) @ w2) + b2, -20.0, 20.0))
        output = (np.nan_to_num(hidden_2, nan=0.0, posinf=0.0, neginf=0.0) @ w3) + b3
    return np.nan_to_num(output.astype(np.float32))


def _train_pairwise_model(
    model: dict[str, object],
    vectors: np.ndarray,
    preferred_pairs: Sequence[tuple[int, int]],
) -> dict[str, object]:
    if vectors.size == 0 or not preferred_pairs:
        return model

    w1, b1, w2, b2, w3, b3 = _model_arrays(model)
    pair_count = max(len(preferred_pairs), 1)
    learning_rate = 0.5 / np.sqrt(float(max(1, w3.shape[0]) + pair_count))
    epochs = max(1, min(8, int(np.sqrt(pair_count))))

    safe_vectors = np.clip(np.nan_to_num(np.asarray(vectors, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0), -8.0, 8.0)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        hidden_1 = np.tanh(np.clip((safe_vectors @ w1) + b1, -20.0, 20.0))
        hidden_2 = np.tanh(np.clip((np.nan_to_num(hidden_1, nan=0.0, posinf=0.0, neginf=0.0) @ w2) + b2, -20.0, 20.0))
    hidden_2 = np.nan_to_num(hidden_2, nan=0.0, posinf=0.0, neginf=0.0)

    ordered_pairs = list(dict.fromkeys(preferred_pairs))
    for _ in range(epochs):
        for preferred_index, weaker_index in ordered_pairs:
            if preferred_index == weaker_index:
                continue
            feature_delta = hidden_2[preferred_index] - hidden_2[weaker_index]
            delta = float(np.clip(feature_delta @ w3, -30.0, 30.0))
            probability = 1.0 / (1.0 + np.exp(-delta))
            grad_delta = probability - 1.0
            w3 -= learning_rate * np.clip(feature_delta * grad_delta, -1.0, 1.0)
            w3 = np.clip(np.nan_to_num(w3, nan=0.0, posinf=0.0, neginf=0.0), -3.0, 3.0)

    model = _store_model_arrays(model, w1, b1, w2, b2, w3, b3)
    model["trained_pairs"] = _as_int(model.get("trained_pairs")) + (len(ordered_pairs) * epochs)
    return model


def _kmeans_1d_levels(values: Sequence[float]) -> list[int]:
    array = np.asarray(values, dtype=np.float32)
    count = len(array)
    if count == 0:
        return []
    if count == 1 or float(np.max(array) - np.min(array)) <= 1e-9:
        return [1 for _ in range(count)]

    cluster_count = min(3, count)
    centers = np.percentile(array, np.linspace(0, 100, cluster_count + 2)[1:-1]).astype(np.float32)
    labels = np.zeros(count, dtype=np.int32)
    for _ in range(max(4, int(np.sqrt(count)))):
        distances = np.abs(array[:, None] - centers[None, :])
        labels = np.argmin(distances, axis=1)
        next_centers = centers.copy()
        for cluster_index in range(cluster_count):
            members = array[labels == cluster_index]
            if members.size:
                next_centers[cluster_index] = float(np.mean(members))
        if np.allclose(next_centers, centers):
            break
        centers = next_centers

    order = np.argsort(centers)
    ordered_labels = np.zeros(count, dtype=np.int32)
    if cluster_count == 2:
        mapping = {int(order[0]): 0, int(order[1]): 2}
    else:
        mapping = {int(order[0]): 0, int(order[1]): 1, int(order[2]): 2}
    for raw_label, ordered_label in mapping.items():
        ordered_labels[labels == raw_label] = ordered_label
    return ordered_labels.tolist()


class _DisjointSet:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _natural_neighbor_count(similarities: np.ndarray) -> int:
    if similarities.size <= 1:
        return int(similarities.size)
    sorted_values = np.sort(similarities.astype(np.float32))[::-1]
    gaps = sorted_values[:-1] - sorted_values[1:]
    if gaps.size == 0:
        return 1
    return int(np.argmax(gaps) + 1)


def _build_similarity_clusters(embedding_matrix: np.ndarray) -> list[list[int]]:
    count = int(embedding_matrix.shape[0])
    if count == 0:
        return []
    if count == 1:
        return [[0]]

    neighbor_count = max(2, min(count - 1, int(np.ceil(np.sqrt(count)))))
    neighbor_indices: list[np.ndarray] = []
    neighbor_scores: list[np.ndarray] = []

    try:
        import faiss

        index = faiss.IndexFlatIP(int(embedding_matrix.shape[1]))
        index.add(np.asarray(embedding_matrix, dtype=np.float32))
        scores, indices = index.search(np.asarray(embedding_matrix, dtype=np.float32), neighbor_count + 1)
        for current_index, (row_scores, row_indices) in enumerate(zip(scores, indices)):
            mask = row_indices >= 0
            row_indices = row_indices[mask]
            row_scores = row_scores[mask]
            non_self = row_indices != current_index
            neighbor_indices.append(row_indices[non_self][:neighbor_count])
            neighbor_scores.append(row_scores[non_self][:neighbor_count])
    except Exception:
        similarity = np.nan_to_num(embedding_matrix @ embedding_matrix.T, nan=0.0, posinf=0.0, neginf=0.0)
        np.fill_diagonal(similarity, -np.inf)
        for row in similarity:
            if neighbor_count < count - 1:
                candidate_indices = np.argpartition(row, -neighbor_count)[-neighbor_count:]
                ordered = candidate_indices[np.argsort(row[candidate_indices])[::-1]]
            else:
                ordered = np.argsort(row)[::-1][:neighbor_count]
            neighbor_indices.append(ordered.astype(np.int32))
            neighbor_scores.append(row[ordered].astype(np.float32))

    disjoint = _DisjointSet(count)
    edge_candidates: list[tuple[int, int, float]] = []
    for index, (indices, scores) in enumerate(zip(neighbor_indices, neighbor_scores)):
        usable_count = _natural_neighbor_count(scores)
        for neighbor_index, score in zip(indices[:usable_count], scores[:usable_count]):
            neighbor_index = int(neighbor_index)
            if neighbor_index == index:
                continue
            left = min(index, neighbor_index)
            right = max(index, neighbor_index)
            edge_candidates.append((left, right, float(score)))

    if edge_candidates:
        edge_levels = _kmeans_1d_levels([score for _, _, score in edge_candidates])
        strongest_level = max(edge_levels) if edge_levels else 1
        for (left, right, _score), level in zip(edge_candidates, edge_levels):
            if level == strongest_level:
                disjoint.union(left, right)

    clusters_by_root: dict[int, list[int]] = defaultdict(list)
    for index in range(count):
        clusters_by_root[disjoint.find(index)].append(index)
    return sorted(clusters_by_root.values(), key=lambda cluster: (min(cluster), len(cluster)))


def _standardize_signal(values: np.ndarray) -> np.ndarray:
    array = np.nan_to_num(np.asarray(values, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    if array.size == 0:
        return array
    spread = float(np.std(array))
    if spread <= 1e-9:
        return np.zeros_like(array, dtype=np.float32)
    return ((array - float(np.mean(array))) / spread).astype(np.float32)


def _batch_relative_prior(items: Sequence[PhotoSelectionItem], embeddings: np.ndarray) -> np.ndarray:
    if not items:
        return np.empty(0, dtype=np.float32)

    metric_matrix = np.vstack([_numeric_feature_vector(item) for item in items]).astype(np.float32)
    metric_matrix = np.nan_to_num(metric_matrix, nan=0.0, posinf=0.0, neginf=0.0)
    centered_metrics = metric_matrix - np.mean(metric_matrix, axis=0, keepdims=True)
    metric_spread = np.std(metric_matrix, axis=0)
    metric_weights = metric_spread / max(float(np.sum(metric_spread)), 1e-9)
    metric_signal = centered_metrics @ metric_weights

    centroid = np.mean(embeddings, axis=0)
    centroid_norm = float(np.linalg.norm(centroid))
    if centroid_norm > 1e-9:
        centroid = centroid / centroid_norm
    centrality_signal = embeddings @ centroid

    signals = np.vstack([
        _standardize_signal(metric_signal),
        _standardize_signal(centrality_signal),
    ]).T
    signal_spread = np.std(signals, axis=0)
    signal_weights = signal_spread / max(float(np.sum(signal_spread)), 1e-9)
    return np.nan_to_num(signals @ signal_weights, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def _bootstrap_pairs(
    items: Sequence[PhotoSelectionItem],
    clusters: Sequence[Sequence[int]],
    embeddings: np.ndarray,
) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    batch_prior = _batch_relative_prior(items, embeddings)
    prior_order = np.argsort(batch_prior)[::-1]
    for left, right in zip(prior_order, prior_order[1:]):
        if float(batch_prior[left]) == float(batch_prior[right]):
            continue
        pairs.append((int(left), int(right)))

    for cluster in clusters:
        if len(cluster) < 2:
            continue
        cluster_embeddings = embeddings[list(cluster)]
        centroid = np.mean(cluster_embeddings, axis=0)
        centroid_norm = float(np.linalg.norm(centroid))
        if centroid_norm > 1e-9:
            centroid = centroid / centroid_norm
        centrality = cluster_embeddings @ centroid
        ordered = [cluster[index] for index in np.argsort(centrality)[::-1]]
        for left, right in zip(ordered, ordered[1:]):
            pairs.append((left, right))
    return pairs


def _feedback_pairs(items: Sequence[PhotoSelectionItem]) -> list[tuple[int, int]]:
    rank = {REJECT_CATEGORY: 0, SELECT_CATEGORY: 1}
    ordered = sorted(range(len(items)), key=lambda index: rank.get(items[index].category, 0), reverse=True)
    pairs: list[tuple[int, int]] = []
    for left, right in zip(ordered, ordered[1:]):
        if rank.get(items[left].category, 0) > rank.get(items[right].category, 0):
            pairs.append((left, right))
    for preferred_index, preferred_item in enumerate(items):
        preferred_rank = rank.get(preferred_item.category, 0)
        weaker_candidates = [
            index
            for index, item in enumerate(items)
            if rank.get(item.category, 0) < preferred_rank
        ]
        if not weaker_candidates:
            continue
        pairs.append((preferred_index, weaker_candidates[-1]))
    return pairs


def _preference_vector_from_context(
    context: dict[str, object],
    embedding_dim: int,
    vector_key: str = "positive_preference_vector",
) -> np.ndarray | None:
    raw_vector = context.get(vector_key)
    if vector_key == "positive_preference_vector" and not isinstance(raw_vector, list):
        raw_vector = context.get("preference_vector")
    if not isinstance(raw_vector, list) or len(raw_vector) != embedding_dim:
        return None
    vector = np.asarray(raw_vector, dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-9:
        return None
    return vector / norm


def _adaptive_keep_count(scores_desc: Sequence[float]) -> int:
    count = len(scores_desc)
    if count <= 1:
        return count
    if count <= 3:
        return count

    score_array = np.asarray(scores_desc, dtype=np.float32)
    gaps = score_array[:-1] - score_array[1:]
    if gaps.size == 0 or float(np.max(gaps)) <= 1e-9:
        return min(3, count)
    return max(1, min(3, int(np.argmax(gaps) + 1)))


def _apply_embedding_rank_decisions(
    *,
    items: Sequence[PhotoSelectionItem],
    embeddings_by_path: dict[str, np.ndarray],
    profile: dict[str, object],
    shoot_type: str,
) -> None:
    valid_indices = [index for index, item in enumerate(items) if item.path in embeddings_by_path]
    if not valid_indices:
        analysis_scores = [_as_float(item.metrics.get("analysis_prior"), item.score) for item in items]
        analysis_levels = _kmeans_1d_levels(analysis_scores)
        ordered = np.argsort(np.asarray(analysis_scores, dtype=np.float32))[::-1].tolist()
        rank_by_index = {int(index): rank for rank, index in enumerate(ordered, start=1)}
        for index, item in enumerate(items):
            rank = rank_by_index.get(index, len(items))
            item.score = round(100.0 * (len(items) - rank + 1) / max(len(items), 1), 2)
            item.metrics["relative_rank"] = rank
            item.metrics["cluster_id"] = 0
            item.metrics["cluster_size"] = 1
            item.metrics["cluster_position"] = "solo"
            item.metrics["image_id"] = item.path
            if str(item.metrics.get("hard_failure")) == "true" or analysis_levels[index] == 0:
                category = REJECT_CATEGORY
                explanation = str(item.metrics.get("hard_failure_reason", "")).strip() or "lower quality than selected images"
            else:
                category = SELECT_CATEGORY
                explanation = "strong usable frame chosen from technical and aesthetic analysis"
            item.metrics["decision"] = category
            item.metrics["explanation"] = explanation
            item.metrics["ai_category"] = category
            _set_category(item, category, explanation)
        return

    profile_id = str(profile.get("profile_id", DEFAULT_PROFILE_ID))
    context = _context_profile(profile, shoot_type)
    embedding_matrix = np.vstack([embeddings_by_path[items[index].path] for index in valid_indices]).astype(np.float32)
    norms = np.linalg.norm(embedding_matrix, axis=1, keepdims=True)
    embedding_matrix = embedding_matrix / np.clip(norms, 1e-9, None)
    clusters = _build_similarity_clusters(embedding_matrix)

    vectors = np.vstack(
        [
            _feature_vector(items[global_index], embeddings_by_path[items[global_index].path])
            for global_index in valid_indices
        ]
    ).astype(np.float32)
    model = _load_utility_model(context, vectors.shape[1], profile_id, shoot_type)
    transient_model = _train_pairwise_model(model, vectors, _bootstrap_pairs([items[index] for index in valid_indices], clusters, embedding_matrix))
    utilities = _mlp_forward(transient_model, vectors)

    positive_preference = _preference_vector_from_context(context, embedding_matrix.shape[1], "positive_preference_vector")
    negative_preference = _preference_vector_from_context(context, embedding_matrix.shape[1], "negative_preference_vector")
    if positive_preference is not None or negative_preference is not None:
        preference_signal = np.zeros(len(valid_indices), dtype=np.float32)
        if positive_preference is not None:
            preference_signal += embedding_matrix @ positive_preference
        if negative_preference is not None:
            preference_signal -= embedding_matrix @ negative_preference
        preference_signal = preference_signal - float(np.mean(preference_signal))
        strength = np.std(utilities) if float(np.std(utilities)) > 1e-9 else 1.0
        history_count = _as_float(context.get("feedback_count"), 0.0)
        utilities = utilities + (preference_signal * strength * (history_count / max(history_count + len(valid_indices), 1.0)))

    utility_order = np.argsort(utilities)[::-1]
    rank_by_local_index = {int(local_index): rank for rank, local_index in enumerate(utility_order, start=1)}
    global_levels = _kmeans_1d_levels(utilities.tolist())
    cluster_id_by_local: dict[int, int] = {}
    cluster_leader_by_local: dict[int, int] = {}
    cluster_rank_by_local: dict[int, int] = {}
    cluster_keep_count_by_local: dict[int, int] = {}
    rejected_by_cluster_pressure: set[int] = set()
    selected_by_cluster_pressure: set[int] = set()

    for cluster_id, cluster in enumerate(clusters):
        ordered_cluster = sorted(cluster, key=lambda local_index: float(utilities[local_index]), reverse=True)
        keep_count = _adaptive_keep_count([float(utilities[index]) for index in ordered_cluster])
        leader_local = ordered_cluster[0]
        for position, local_index in enumerate(ordered_cluster, start=1):
            cluster_id_by_local[int(local_index)] = cluster_id
            cluster_leader_by_local[int(local_index)] = int(leader_local)
            cluster_rank_by_local[int(local_index)] = position
            cluster_keep_count_by_local[int(local_index)] = keep_count
            if position <= keep_count:
                selected_by_cluster_pressure.add(int(local_index))
            else:
                rejected_by_cluster_pressure.add(int(local_index))

    for local_index, global_index in enumerate(valid_indices):
        item = items[global_index]
        rank = rank_by_local_index.get(local_index, len(valid_indices))
        relative_score = 100.0 * (len(valid_indices) - rank + 1) / max(len(valid_indices), 1)
        global_level = global_levels[local_index] if local_index < len(global_levels) else 0
        cluster_id = cluster_id_by_local.get(local_index, 0)
        cluster = clusters[cluster_id] if cluster_id < len(clusters) else [local_index]
        leader_local = cluster_leader_by_local.get(local_index, local_index)
        leader_name = Path(items[valid_indices[leader_local]].path).name
        cluster_rank = cluster_rank_by_local.get(local_index, 1)
        keep_count = cluster_keep_count_by_local.get(local_index, 1)
        is_hard_failure = str(item.metrics.get("hard_failure")) == "true"

        if is_hard_failure:
            category = REJECT_CATEGORY
            explanation = str(item.metrics.get("hard_failure_reason", "")).strip() or "critical failure compared with selected images"
        elif local_index in rejected_by_cluster_pressure:
            category = REJECT_CATEGORY
            explanation = f"weaker duplicate than {leader_name}" if len(cluster) > 1 else "lower quality than selected images"
        elif len(cluster) > 1:
            category = SELECT_CATEGORY
            if cluster_rank == 1:
                explanation = "best in cluster"
            elif keep_count > 1:
                explanation = f"strong usable variation from cluster around {leader_name}"
            else:
                explanation = f"strongest usable frame in cluster around {leader_name}"
        elif global_level == 0:
            category = REJECT_CATEGORY
            explanation = "lower quality than selected images"
        else:
            category = SELECT_CATEGORY
            explanation = "strong usable frame"

        item.score = round(relative_score, 2)
        item.metrics["utility_score"] = round(float(utilities[local_index]), 6)
        item.metrics["relative_rank"] = rank
        item.metrics["cluster_id"] = cluster_id
        item.metrics["cluster_size"] = len(cluster)
        item.metrics["cluster_position"] = "best" if cluster_rank == 1 else "kept" if category == SELECT_CATEGORY else "rejected"
        item.metrics["cluster_rank"] = cluster_rank
        item.metrics["cluster_keep_count"] = keep_count
        item.metrics["image_id"] = item.path
        item.metrics["decision"] = category
        item.metrics["explanation"] = explanation
        item.metrics["ai_category"] = category
        _set_category(item, category, explanation)

    missing_embedding_items = [item for item in items if item.path not in embeddings_by_path]
    for item in missing_embedding_items:
        item.score = round(_as_float(item.metrics.get("analysis_prior"), item.score), 2)
        item.metrics["relative_rank"] = len(valid_indices) + 1
        item.metrics["cluster_id"] = -1
        item.metrics["cluster_size"] = 1
        item.metrics["cluster_position"] = "solo"
        item.metrics["image_id"] = item.path
        if str(item.metrics.get("hard_failure")) == "true":
            category = REJECT_CATEGORY
            explanation = str(item.metrics.get("hard_failure_reason", "")).strip() or "critical failure without embedding support"
        else:
            category = SELECT_CATEGORY
            explanation = "selected from analysis because embedding extraction was unavailable"
        item.metrics["decision"] = category
        item.metrics["explanation"] = explanation
        item.metrics["ai_category"] = category
        _set_category(item, category, explanation)


def record_culling_feedback(
    *,
    profile_id: str | None,
    shoot_type: str,
    items: Sequence[PhotoSelectionItem],
) -> str:
    store = _load_profile_store()
    profiles = store.setdefault("profiles", {})
    key = _profile_key(profile_id)
    profile = profiles.get(key)
    if not isinstance(profile, dict):
        profile = {
            "profile_id": key,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "contexts": {},
        }
        profiles[key] = profile

    context = _context_profile(profile, shoot_type)
    feedback_items = list(items)
    selected = [
        item
        for item in feedback_items
        if item.category == SELECT_CATEGORY or str(item.metrics.get("implicit_positive", "")).casefold() in {"exported", "favorite", "edited"}
    ]
    rejected = [item for item in feedback_items if item.category == REJECT_CATEGORY or str(item.metrics.get("implicit_negative", "")).casefold() in {"deleted", "ignored"}]

    embeddings: dict[str, np.ndarray] = {}
    engine_name = "feedback embeddings unavailable"
    try:
        cache = FeatureCache()
        vision_engine = VisionEngine()
        engine_name = vision_engine.ensure_ready()
        embeddings = vision_engine.compute_embeddings([item.path for item in feedback_items], cache=cache)
        cache.save()
    except Exception:
        embeddings = {}

    vector_items = [item for item in feedback_items if item.path in embeddings]
    if vector_items:
        vectors = np.vstack([_feature_vector(item, embeddings[item.path]) for item in vector_items]).astype(np.float32)
        model = _load_utility_model(context, vectors.shape[1], key, shoot_type)
        index_by_path = {item.path: index for index, item in enumerate(vector_items)}
        local_pairs: list[tuple[int, int]] = []
        for preferred, weaker in _feedback_pairs(vector_items):
            local_pairs.append((preferred, weaker))
        for preferred_item in selected:
            preferred_index = index_by_path.get(preferred_item.path)
            if preferred_index is None:
                continue
            weaker_candidates = [
                index_by_path[item.path]
                for item in rejected
                if item.path in index_by_path and item.path != preferred_item.path
            ]
            if weaker_candidates:
                utilities = _mlp_forward(model, vectors[weaker_candidates])
                local_pairs.append((preferred_index, weaker_candidates[int(np.argmin(utilities))]))

        if local_pairs:
            context["utility_model"] = _train_pairwise_model(model, vectors, local_pairs)

        selected_embeddings = [embeddings[item.path] for item in selected if item.path in embeddings]
        rejected_embeddings = [embeddings[item.path] for item in rejected if item.path in embeddings]
        if selected_embeddings:
            batch_preference = np.mean(np.vstack(selected_embeddings).astype(np.float32), axis=0)
            preference_norm = float(np.linalg.norm(batch_preference))
            if preference_norm > 1e-9:
                batch_preference = batch_preference / preference_norm
                previous = _preference_vector_from_context(context, batch_preference.shape[0], "positive_preference_vector")
                previous_count = _as_float(context.get("positive_feedback_count"), 0.0)
                batch_count = float(len(selected_embeddings))
                blend = batch_count / max(previous_count + batch_count, 1.0)
                if previous is None:
                    updated = batch_preference
                else:
                    updated = ((1.0 - blend) * previous) + (blend * batch_preference)
                    updated_norm = float(np.linalg.norm(updated))
                    if updated_norm > 1e-9:
                        updated = updated / updated_norm
                context["positive_preference_vector"] = np.asarray(updated, dtype=np.float32).tolist()
                context["preference_vector"] = np.asarray(updated, dtype=np.float32).tolist()
                context["positive_feedback_count"] = previous_count + batch_count
        if rejected_embeddings:
            batch_negative = np.mean(np.vstack(rejected_embeddings).astype(np.float32), axis=0)
            negative_norm = float(np.linalg.norm(batch_negative))
            if negative_norm > 1e-9:
                batch_negative = batch_negative / negative_norm
                previous_negative = _preference_vector_from_context(context, batch_negative.shape[0], "negative_preference_vector")
                previous_negative_count = _as_float(context.get("negative_feedback_count"), 0.0)
                negative_batch_count = float(len(rejected_embeddings))
                blend = negative_batch_count / max(previous_negative_count + negative_batch_count, 1.0)
                if previous_negative is None:
                    updated_negative = batch_negative
                else:
                    updated_negative = ((1.0 - blend) * previous_negative) + (blend * batch_negative)
                    updated_negative_norm = float(np.linalg.norm(updated_negative))
                    if updated_negative_norm > 1e-9:
                        updated_negative = updated_negative / updated_negative_norm
                context["negative_preference_vector"] = np.asarray(updated_negative, dtype=np.float32).tolist()
                context["negative_feedback_count"] = previous_negative_count + negative_batch_count

    feedback_count = len(feedback_items)
    context["feedback_count"] = _as_int(context.get("feedback_count")) + feedback_count
    context["last_feedback_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    context["last_feedback_engine"] = engine_name
    context["last_positive_count"] = len(selected)
    context["last_negative_count"] = len(rejected)
    profile["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    profiles[key] = profile
    _save_profile_store(store)

    return (
        f"Learned pairwise preferences from {feedback_count} decision(s): "
        f"{len(selected)} positive, {len(rejected)} negative signal(s)."
    )


def _detect_body(gray: np.ndarray) -> tuple[int, float]:
    upper_body, full_body = _get_body_detector()
    if (upper_body is None and full_body is None) or gray.size == 0:
        return 0, 0.0

    small = _resize_gray(gray, 520)
    height, width = small.shape[:2]
    if min(height, width) < 128:
        return 0, 0.0

    equalized = cv2.equalizeHist(small)
    min_body = max(42, int(min(height, width) * 0.12))
    all_boxes = []
    for cascade in (upper_body, full_body):
        if cascade is None:
            continue
        try:
            boxes = cascade.detectMultiScale(
                equalized,
                scaleFactor=1.06,
                minNeighbors=3,
                minSize=(min_body, min_body),
            )
        except Exception:
            continue
        all_boxes.extend(boxes)

    if not all_boxes:
        return 0, 0.0

    largest_box = max(all_boxes, key=lambda box: int(box[2]) * int(box[3]))
    _x, _y, body_w, body_h = [int(value) for value in largest_box]
    body_area = float((body_w * body_h) / max(1, width * height))
    return len(all_boxes), body_area


def _eye_region_metrics(gray: np.ndarray, face_rect: tuple[int, int, int, int]) -> tuple[float, float, float]:
    x, y, face_w, face_h = face_rect
    region = gray[y : y + int(face_h * 0.52), x : x + face_w]
    if region.size == 0:
        return 0.0, 0.0, 0.0

    focus = _tenengrad_focus(region)
    edges = _edge_density(region)
    darkness = float(np.mean(region < 70))
    return focus, edges, darkness


def _closed_eye_confidence(
    *,
    visible_eye_count: int,
    dominant_face_area: float,
    dominant_face_focus: float,
    eye_region_focus: float,
    eye_region_edges: float,
    eye_region_darkness: float,
    contrast: float,
    exposure_score: float,
) -> float:
    if visible_eye_count > 0 or dominant_face_area < 0.055 or dominant_face_focus < 72.0:
        return 0.0
    if contrast < 34.0 or exposure_score < 0.34:
        return 0.0

    confidence = 0.36
    confidence += _score_range(dominant_face_area, 0.055, 0.18) * 0.18
    confidence += _score_range(dominant_face_focus, 72.0, 260.0) * 0.14
    confidence += (1.0 - _score_range(eye_region_focus, 8.0, 26.0)) * 0.16
    confidence += (1.0 - _score_range(eye_region_edges, 0.018, 0.055)) * 0.10
    confidence += _score_range(eye_region_darkness, 0.38, 0.72) * 0.06
    return float(np.clip(confidence, 0.0, 1.0))


def _detect_subjects(gray: np.ndarray) -> tuple[int, int, float, float, int, float, float, float, float]:
    face_cascade, eye_cascade = _get_cascades()
    if face_cascade is None:
        body_count, body_area = _detect_body(gray)
        return 0, 0, 0.0, 0.0, body_count, body_area, 0.0, 0.0, 0.0

    equalized = cv2.equalizeHist(gray)
    min_face = max(32, int(min(gray.shape[:2]) * 0.075))
    faces = face_cascade.detectMultiScale(
        equalized,
        scaleFactor=1.08,
        minNeighbors=5,
        minSize=(min_face, min_face),
    )

    if len(faces) == 0:
        body_count, body_area = _detect_body(gray)
        return 0, 0, 0.0, 0.0, body_count, body_area, 0.0, 0.0, 0.0

    height, width = gray.shape[:2]
    largest_face = max(faces, key=lambda rect: int(rect[2]) * int(rect[3]))
    x, y, face_w, face_h = [int(value) for value in largest_face]
    dominant_face_area = float((face_w * face_h) / max(1, width * height))
    dominant_face_focus = _laplacian_variance(gray[y : y + face_h, x : x + face_w])
    eye_region_focus, eye_region_edges, eye_region_darkness = _eye_region_metrics(gray, (x, y, face_w, face_h))

    if eye_cascade is None:
        return (
            int(len(faces)),
            0,
            dominant_face_area,
            dominant_face_focus,
            0,
            0.0,
            eye_region_focus,
            eye_region_edges,
            eye_region_darkness,
        )

    eye_region = equalized[y : y + int(face_h * 0.62), x : x + face_w]
    min_eye = max(8, int(face_w * 0.12))
    eyes = eye_cascade.detectMultiScale(
        eye_region,
        scaleFactor=1.07,
        minNeighbors=4,
        minSize=(min_eye, min_eye),
    )
    return (
        int(len(faces)),
        int(min(len(eyes), 2)),
        dominant_face_area,
        dominant_face_focus,
        0,
        0.0,
        eye_region_focus,
        eye_region_edges,
        eye_region_darkness,
    )


def _analyze_record(record: ImageRecord) -> PhotoSelectionItem:
    image = read_cv_image(record.path)
    if image is None:
        return PhotoSelectionItem(
            path=record.path,
            score=0.0,
            selected=False,
            category=REJECT_CATEGORY,
            reasons=["Unreadable or corrupted image"],
            metrics={
                "file_size": record.size,
                "hard_failure": "true",
                "absolute_reject_allowed": "true",
                "hard_failure_reason": "Unreadable or corrupted image",
                "technical_quality": 0.0,
                "face_quality": 50.0,
                "aesthetic_value": 0.0,
                "composition_quality": 0.0,
            },
        )

    image = _resize_for_analysis(image)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape[:2]

    brightness = float(np.mean(gray))
    contrast = float(np.std(gray))
    p1, p99 = np.percentile(gray, [1, 99])
    overexposed_ratio = float(np.mean(gray >= 245))
    underexposed_ratio = float(np.mean(gray <= 12))

    sharpness = _laplacian_variance(gray)
    tenengrad = _tenengrad_focus(gray)
    center_gray = _safe_crop(gray, 0.22, 0.22, 0.78, 0.78)
    center_sharpness = _laplacian_variance(center_gray)
    center_tenengrad = _tenengrad_focus(center_gray)
    center_edge_density = _edge_density(center_gray)
    whole_edge_density = _edge_density(gray)
    center_detail_ratio, weighted_center_detail, outer_detail_ratio = _detail_distribution(gray)
    color_score, saturation_mean = _color_quality(image)

    mask = np.ones_like(gray, dtype=np.uint8)
    top = int(height * 0.22)
    bottom = int(height * 0.78)
    left = int(width * 0.22)
    right = int(width * 0.78)
    mask[top:bottom, left:right] = 0
    edges = cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 70, 170)
    outer_pixels = max(1, int(np.sum(mask > 0)))
    outer_edge_density = float(np.sum((edges > 0) & (mask > 0)) / outer_pixels)

    denoised = cv2.GaussianBlur(gray, (5, 5), 0)
    noise_estimate = float(np.mean(np.abs(gray.astype(np.float32) - denoised.astype(np.float32))))
    noise_score = 1.0 - _score_range(noise_estimate, 4.0, 26.0)
    dynamic_range_score = _score_range(float(p99 - p1), 48.0, 184.0)

    small_edges = cv2.resize((edges > 0).astype(np.float32), (96, 96), interpolation=cv2.INTER_AREA)
    total_edges = float(np.sum(small_edges)) + 1e-6
    grid_y, grid_x = np.indices(small_edges.shape, dtype=np.float32)
    centroid_x = float(np.sum(grid_x * small_edges) / total_edges) / 95.0
    centroid_y = float(np.sum(grid_y * small_edges) / total_edges) / 95.0
    thirds_points = ((1 / 3, 1 / 3), (2 / 3, 1 / 3), (1 / 3, 2 / 3), (2 / 3, 2 / 3), (0.5, 0.5))
    nearest_thirds_distance = min(((centroid_x - x) ** 2 + (centroid_y - y) ** 2) ** 0.5 for x, y in thirds_points)
    rule_of_thirds_score = 1.0 - _score_range(nearest_thirds_distance, 0.04, 0.34)

    (
        face_count,
        visible_eye_count,
        dominant_face_area,
        dominant_face_focus,
        body_count,
        body_area,
        eye_region_focus,
        eye_region_edges,
        eye_region_darkness,
    ) = _detect_subjects(gray)

    exposure_score = 1.0 - min(abs(brightness - 126.0) / 126.0, 1.0)
    exposure_score -= min(overexposed_ratio * 1.08, 0.34)
    exposure_score -= min(underexposed_ratio * 1.02, 0.34)
    if p99 < 172.0:
        exposure_score -= _score_range(172.0 - float(p99), 0.0, 82.0) * 0.12
    if p1 > 70.0:
        exposure_score -= _score_range(float(p1) - 70.0, 0.0, 90.0) * 0.08
    exposure_score = float(np.clip(exposure_score, 0.0, 1.0))

    contrast_score = _score_range(contrast, 24.0, 82.0)
    laplacian_score = _score_range(np.log1p(max(sharpness, center_sharpness)), np.log1p(34.0), np.log1p(760.0))
    tenengrad_score = _score_range(max(tenengrad, center_tenengrad), 10.0, 42.0)
    sharpness_score = float(np.clip((laplacian_score * 0.62) + (tenengrad_score * 0.38), 0.0, 1.0))

    if face_count > 0:
        subject_score = _score_range(dominant_face_area, 0.014, 0.12)
        subject_score += 0.17 if visible_eye_count >= 2 else 0.07 if visible_eye_count == 1 else -0.10
        subject_score += _score_range(dominant_face_focus, 36.0, 380.0) * 0.18
        subject_score += _score_range(weighted_center_detail, 0.15, 0.38) * 0.08
    elif body_count > 0:
        subject_score = 0.46
        subject_score += _score_range(body_area, 0.05, 0.34) * 0.28
        subject_score += _score_range(center_detail_ratio, 0.18, 0.46) * 0.16
        subject_score += sharpness_score * 0.10
    else:
        center_focus_ratio = max(center_sharpness, center_tenengrad * 11.0) / max(max(sharpness, tenengrad * 11.0), 1.0)
        subject_score = 0.40
        subject_score += _score_range(center_focus_ratio, 0.62, 1.18) * 0.22
        subject_score += _score_range(center_detail_ratio, 0.22, 0.46) * 0.20
        subject_score += _score_range(weighted_center_detail, 0.13, 0.34) * 0.18
        subject_score += sharpness_score * 0.10
        subject_score -= max(outer_edge_density - center_edge_density, 0.0) * 0.95
    subject_score = float(np.clip(subject_score, 0.0, 1.0))

    outer_dominance = max(0.0, outer_detail_ratio - max(center_detail_ratio, weighted_center_detail) * 1.04)
    distraction_score = max(0.0, outer_edge_density - (center_edge_density * 0.78))
    distraction_score = max(_score_range(distraction_score, 0.032, 0.17), _score_range(outer_dominance, 0.13, 0.42))
    if face_count >= 4:
        distraction_score += min(0.26, (face_count - 3) * 0.09)
    if whole_edge_density > 0.26 and outer_edge_density > center_edge_density * 1.55 and center_detail_ratio < 0.30:
        distraction_score += 0.12
    distraction_score = float(np.clip(distraction_score, 0.0, 1.0))

    closed_eye_confidence = _closed_eye_confidence(
        visible_eye_count=visible_eye_count,
        dominant_face_area=dominant_face_area,
        dominant_face_focus=dominant_face_focus,
        eye_region_focus=eye_region_focus,
        eye_region_edges=eye_region_edges,
        eye_region_darkness=eye_region_darkness,
        contrast=contrast,
        exposure_score=exposure_score,
    )

    focus_peak = max(tenengrad, center_tenengrad)
    soft_blur_penalty = _score_range(0.20 - sharpness_score, 0.0, 0.20) * 16.0
    if focus_peak >= 16.0:
        soft_blur_penalty *= 0.45

    severe_overexposed = brightness > 247.0 or overexposed_ratio > 0.82 or (p99 >= 254.0 and overexposed_ratio > 0.52 and contrast < 24.0)
    severe_underexposed = brightness < 9.0 or underexposed_ratio > 0.84 or (p1 <= 1.0 and underexposed_ratio > 0.58 and contrast < 22.0)
    extreme_blur = (
        (sharpness_score < 0.025 and focus_peak < 7.0 and whole_edge_density < 0.016)
        or (face_count > 0 and dominant_face_focus < 8.0 and sharpness_score < 0.055 and focus_peak < 9.0)
        or (face_count == 0 and body_count == 0 and sharpness_score < 0.018 and focus_peak < 6.0 and contrast < 18.0)
    )
    clearly_closed_eyes = closed_eye_confidence >= 0.92 and face_count > 0 and dominant_face_area >= 0.07
    major_distractions = face_count >= 9 or distraction_score >= SEVERE_DISTRACTION_SCORE

    technical_quality = (
        sharpness_score * 40.0
        + exposure_score * 26.0
        + contrast_score * 13.0
        + dynamic_range_score * 12.0
        + noise_score * 9.0
    )
    technical_quality = _clamp(technical_quality, 0.0, 100.0)

    if face_count > 0:
        face_quality = (
            subject_score * 43.0
            + _score_range(dominant_face_focus, 32.0, 420.0) * 27.0
            + (1.0 - closed_eye_confidence) * 20.0
            + (10.0 if visible_eye_count >= 2 else 5.0 if visible_eye_count == 1 else 0.0)
        )
    elif body_count > 0:
        face_quality = 70.0 + (_score_range(body_area, 0.04, 0.28) * 12.0) + (subject_score * 8.0)
    else:
        # No-human/detail images should not be punished for lacking a face.
        face_quality = 82.0
    face_quality = _clamp(face_quality, 0.0, 100.0)

    clean_background_score = 1.0 - distraction_score
    lighting_score = _clamp((exposure_score * 0.55) + (dynamic_range_score * 0.23) + (contrast_score * 0.22), 0.0, 1.0)
    storytelling_score = _clamp(
        (weighted_center_detail * 1.25)
        + (color_score * 0.22)
        + (0.14 if face_count > 0 or body_count > 0 else 0.22 if center_detail_ratio > 0.28 else 0.08),
        0.0,
        1.0,
    )
    creative_preserve_score = _clamp(
        (color_score * 0.30)
        + (rule_of_thirds_score * 0.28)
        + (dynamic_range_score * 0.18)
        + (center_detail_ratio * 0.24),
        0.0,
        1.0,
    )
    aesthetic_value = _clamp(
        (lighting_score * 34.0)
        + (clean_background_score * 22.0)
        + (color_score * 17.0)
        + (storytelling_score * 18.0)
        + (creative_preserve_score * 9.0),
        0.0,
        100.0,
    )

    balance_score = 1.0 - _score_range(abs(center_detail_ratio - 0.36), 0.02, 0.34)
    framing_score = _clamp((rule_of_thirds_score * 0.42) + (weighted_center_detail * 1.15) + (balance_score * 0.26), 0.0, 1.0)
    composition_quality = _clamp(
        (framing_score * 48.0)
        + (clean_background_score * 22.0)
        + (_score_range(center_edge_density, 0.018, 0.12) * 16.0)
        + (storytelling_score * 14.0),
        0.0,
        100.0,
    )

    hard_failure_reason = ""
    if severe_overexposed:
        hard_failure_reason = "Exposure failure: image is almost fully blown out"
    elif severe_underexposed:
        hard_failure_reason = "Exposure failure: image is almost fully black"
    elif extreme_blur:
        hard_failure_reason = "Extreme blur: usable content is not recognizable"

    hard_failure = bool(hard_failure_reason)
    absolute_reject_allowed = hard_failure or (
        clearly_closed_eyes
        and face_quality < 34.0
        and technical_quality < 44.0
        and aesthetic_value < 44.0
    )

    if face_count > 0:
        context_tag = "human subject"
    elif body_count > 0:
        context_tag = "body/pose frame"
    elif creative_preserve_score >= 0.58 or aesthetic_value >= 58.0:
        context_tag = "creative/detail frame"
    else:
        context_tag = "environment frame"

    analysis_prior = float(np.mean([technical_quality, face_quality, aesthetic_value, composition_quality]))

    metrics: dict[str, float | int | str] = {
        "width": width,
        "height": height,
        "brightness": round(brightness, 2),
        "p1_brightness": round(float(p1), 2),
        "p99_brightness": round(float(p99), 2),
        "contrast": round(contrast, 2),
        "sharpness": round(sharpness, 2),
        "tenengrad": round(tenengrad, 2),
        "center_sharpness": round(center_sharpness, 2),
        "center_tenengrad": round(center_tenengrad, 2),
        "focus_peak": round(focus_peak, 2),
        "soft_blur_penalty": round(soft_blur_penalty, 2),
        "sharpness_score": round(sharpness_score, 4),
        "exposure_score": round(exposure_score, 4),
        "contrast_score": round(contrast_score, 4),
        "dynamic_range_score": round(dynamic_range_score, 4),
        "noise_estimate": round(noise_estimate, 4),
        "noise_score": round(noise_score, 4),
        "subject_score": round(subject_score, 4),
        "color_score": round(color_score, 4),
        "saturation_mean": round(saturation_mean, 2),
        "closed_eye_confidence": round(closed_eye_confidence, 4),
        "clearly_closed_eyes": "true" if clearly_closed_eyes else "false",
        "overexposed_ratio": round(overexposed_ratio, 4),
        "underexposed_ratio": round(underexposed_ratio, 4),
        "distraction_score": round(distraction_score, 4),
        "clean_background_score": round(clean_background_score, 4),
        "lighting_score": round(lighting_score, 4),
        "storytelling_score": round(storytelling_score, 4),
        "rule_of_thirds_score": round(rule_of_thirds_score, 4),
        "framing_score": round(framing_score, 4),
        "creative_preserve_score": round(creative_preserve_score, 4),
        "technical_quality": round(technical_quality, 2),
        "face_quality": round(face_quality, 2),
        "aesthetic_value": round(aesthetic_value, 2),
        "composition_quality": round(composition_quality, 2),
        "analysis_prior": round(analysis_prior, 2),
        "hard_failure": "true" if hard_failure else "false",
        "absolute_reject_allowed": "true" if absolute_reject_allowed else "false",
        "hard_failure_reason": hard_failure_reason,
        "context_tag": context_tag,
        "center_detail_ratio": round(center_detail_ratio, 4),
        "weighted_center_detail": round(weighted_center_detail, 4),
        "outer_detail_ratio": round(outer_detail_ratio, 4),
        "face_count": face_count,
        "visible_eye_count": visible_eye_count,
        "dominant_face_area": round(dominant_face_area, 4),
        "dominant_face_focus": round(dominant_face_focus, 2),
        "body_count": body_count,
        "body_area": round(body_area, 4),
        "eye_region_focus": round(eye_region_focus, 2),
        "eye_region_edges": round(eye_region_edges, 4),
        "perceptual_hash": _perceptual_hash(gray),
    }

    initial_reason = (
        f"{hard_failure_reason}; final decision waits for embedding comparison"
        if hard_failure_reason
        else "Analysis complete; final decision waits for embedding comparison"
    )
    return PhotoSelectionItem(
        path=record.path,
        score=round(float(analysis_prior), 2),
        selected=False,
        category=REJECT_CATEGORY if hard_failure else SELECT_CATEGORY,
        reasons=[initial_reason],
        metrics=metrics,
    )


def select_best_photos(
    *,
    source_dir: str,
    records: Sequence[ImageRecord],
    cache: FeatureCache | None = None,
    profile_id: str | None = None,
    progress_callback: ProgressCallback | None = None,
    status_callback: StatusCallback | None = None,
    engine_callback: EngineCallback | None = None,
    warning_callback: WarningCallback | None = None,
) -> PhotoSelectionResult:
    started_at = time.perf_counter()
    warnings: list[str] = []
    engine_name = "Photographer-Grade Culling AI (multi-stage, conservative rejection, adaptive learning)"

    if engine_callback:
        engine_callback(engine_name)
    if status_callback:
        status_callback("Analyzing focus, exposure, eyes, and subject clarity...")

    analyzed: list[PhotoSelectionItem] = []
    total = len(records)
    workers = max(2, min(8, os.cpu_count() or 4))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for index, item in enumerate(executor.map(_analyze_record, records), start=1):
            analyzed.append(item)
            if progress_callback and (index % 8 == 0 or index == total):
                progress_callback(8 + int(62 * (index / max(total, 1))))
            if status_callback and (index % 25 == 0 or index == total):
                status_callback(f"Analyzing photo quality... {index}/{total}")

    profile = load_preference_profile(profile_id)
    shoot_type = _dominant_shoot_type(source_dir, analyzed)
    if status_callback:
        status_callback("Extracting dense embeddings for relative culling...")

    embeddings: dict[str, np.ndarray] = {}
    try:
        vision_engine = VisionEngine()
        deep_engine_name = vision_engine.ensure_ready()
        engine_name = f"Embedding Pairwise Culling AI + {deep_engine_name}"
        if engine_callback:
            engine_callback(engine_name)

        if vision_engine.warning:
            warnings.append(vision_engine.warning)
            if warning_callback:
                warning_callback(vision_engine.warning)

        embeddings = vision_engine.compute_embeddings(
            [item.path for item in analyzed],
            cache=cache,
            progress_callback=lambda done, total_count, message: (
                status_callback(f"{message}... {done}/{total_count}") if status_callback else None,
                progress_callback(70 + int(22 * (done / max(total_count, 1)))) if progress_callback else None,
            ),
        )
    except Exception as exc:
        warning = f"Embedding extraction was limited. Relative culling will fall back to analysis-driven SELECT/REJECT decisions. Reason: {exc}"
        warnings.append(warning)
        if warning_callback:
            warning_callback(warning)

    if status_callback:
        status_callback("Learning pairwise utility, suppressing duplicates, and assigning final decisions...")
    _apply_embedding_rank_decisions(
        items=analyzed,
        embeddings_by_path=embeddings,
        profile=profile,
        shoot_type=shoot_type,
    )
    if progress_callback:
        progress_callback(96)

    for item in analyzed:
        item.selected = item.category == SELECT_CATEGORY
        item.metrics["final_category"] = item.category

    selected_items = sorted(
        [item for item in analyzed if item.category == SELECT_CATEGORY],
        key=lambda item: (-item.score, Path(item.path).name.casefold()),
    )
    rejected_items = sorted(
        [item for item in analyzed if item.category == REJECT_CATEGORY],
        key=lambda item: (-item.score, item.reasons[0] if item.reasons else "", Path(item.path).name.casefold()),
    )

    if progress_callback:
        progress_callback(100)
    if status_callback:
        status_callback("Best photo selection complete.")

    return PhotoSelectionResult(
        source_dir=source_dir,
        total_source_images=total,
        selected_items=selected_items,
        rejected_items=rejected_items,
        vision_engine=engine_name,
        warnings=warnings,
        elapsed_seconds=round(time.perf_counter() - started_at, 2),
        profile_id=_profile_key(profile_id),
        shoot_type=shoot_type,
        learning_summary="Embedding utility model applied; export or save final SELECT/REJECT changes to train pairwise preferences.",
    )

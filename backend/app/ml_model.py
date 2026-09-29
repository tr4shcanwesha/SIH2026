from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "varroa_detector.pt"
CONFIDENCE_THRESHOLDS = {
    "queen": 0.15,
    "worker": 0.25,
    "drone": 0.55,
    "varroa": 0.30,
}
MIN_CONFIDENCE = 0.10


def _canonical_class(label: str) -> str:
    normalized = " ".join(label.casefold().replace("_", " ").replace("-", " ").split())
    for class_name in ("varroa", "queen", "worker", "drone"):
        if class_name in normalized:
            return class_name
    return normalized


class ModelUnavailableError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _load_detector() -> Any:
    if not MODEL_PATH.is_file():
        raise ModelUnavailableError(f"Detector weights not found at {MODEL_PATH}")

    try:
        from ultralytics import YOLO
    except ImportError as error:
        raise ModelUnavailableError("Ultralytics is not installed. Install backend requirements first.") from error

    try:
        return YOLO(str(MODEL_PATH))
    except Exception as error:
        raise ModelUnavailableError("The Varroa detector weights could not be loaded.") from error


def predict(image: Image.Image) -> dict[str, Any]:
    detector = _load_detector()
    results = detector.predict(
        source=image,
        conf=MIN_CONFIDENCE,
        imgsz=640,
        device="cpu",
        verbose=False,
    )

    names = detector.names
    detections: list[dict[str, Any]] = []
    counts: dict[str, int] = {}

    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue
        for box in boxes:
            class_id = int(box.cls[0].item())
            label = str(names[class_id] if not isinstance(names, dict) else names[class_id])
            confidence = float(box.conf[0].item())
            class_key = _canonical_class(label)
            threshold = CONFIDENCE_THRESHOLDS.get(class_key, MIN_CONFIDENCE)
            if confidence < threshold:
                continue

            coordinates = [round(float(value), 2) for value in box.xyxy[0].tolist()]
            detections.append({
                "label": label,
                "confidence": round(confidence, 4),
                "box": coordinates,
            })
            counts[label] = counts.get(label, 0) + 1

    varroa_detected = any(_canonical_class(detection["label"]) == "varroa" for detection in detections)
    bee_status = "Infected" if varroa_detected else "Healthy"
    return {
        "prediction": bee_status,
        "bee_status": bee_status,
        "varroa_detected": varroa_detected,
        "detections": detections,
        "counts": counts,
        "thresholds": CONFIDENCE_THRESHOLDS,
    }
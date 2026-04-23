from __future__ import annotations

import cv2
import numpy as np
import pytesseract
from PIL import Image

from nova_scout_app.services.file_ops import read_cv_image
from nova_scout_app.services.runtime import configure_tesseract_path
from nova_scout_app.services.text_processing import clean_ocr_text


def extract_queries_from_screenshot(image_path: str) -> list[str]:
    configure_tesseract_path()
    image = read_cv_image(image_path)
    if image is None:
        with Image.open(image_path) as pil_image:
            image = cv2.cvtColor(np.array(pil_image.convert("RGB")), cv2.COLOR_RGB2BGR)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    thresholded = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )

    text = pytesseract.image_to_string(thresholded, config="--oem 3 --psm 6")
    return clean_ocr_text(text)

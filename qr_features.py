"""Feature extraction for the QR fraud model.

IMPORTANT: this must be the single source of truth. Your training script
should import extract_features_from_array (or extract_features) from HERE
instead of keeping its own copy — any drift between training and inference
feature logic will silently produce garbage predictions.
"""
import cv2
import numpy as np


def extract_features_from_array(image: np.ndarray) -> np.ndarray:
    """image: a grayscale OpenCV image (2D array), already loaded/decoded."""
    image = cv2.resize(image, (64, 64))
    normalized = image.astype(np.float32) / 255.0

    features = []
    features.extend(normalized.flatten())  # A. pixel features

    # B. image statistics
    black_pixel_ratio = np.mean(image < 128)
    mean_intensity = np.mean(image)
    std_intensity = np.std(image)
    features.extend([black_pixel_ratio, mean_intensity, std_intensity])

    # C. edge features
    edges = cv2.Canny(image, 100, 200)
    edge_density = np.mean(edges > 0)
    features.append(edge_density)

    # D. QR decoder features
    detector = cv2.QRCodeDetector()
    try:
        decoded_data, _, _ = detector.detectAndDecode(image)
        if decoded_data:
            decoded_successfully = 1
            payload_length = len(decoded_data)
            is_url = int(decoded_data.lower().startswith(("http://", "https://")))
            is_https = int(decoded_data.lower().startswith("https://"))
            special_character_count = sum(c in "@?=&%_-" for c in decoded_data)
        else:
            decoded_successfully = payload_length = is_url = is_https = special_character_count = 0
    except Exception:
        decoded_successfully = payload_length = is_url = is_https = special_character_count = 0

    features.extend([decoded_successfully, payload_length, is_url, is_https, special_character_count])
    return np.array(features, dtype=np.float32)


def extract_features(image_path: str):
    """Matches your training script's signature — loads from a file path."""
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None
    return extract_features_from_array(image)


def extract_features_from_bytes(image_bytes: bytes):
    """Used at inference time — the app has bytes (an upload), not a file path."""
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None
    return extract_features_from_array(image)

import os
import cv2
import numpy as np
import joblib

from sklearn.model_selection import train_test_split  # type: ignore[reportMissingModuleSource]
from sklearn.metrics import (  # type: ignore[reportMissingModuleSource]
    classification_report,
    confusion_matrix,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score
)
from xgboost import XGBClassifier


# ============================================================
# 1. DATASET PATH
# ============================================================

DATASET_PATH = r"C:\Users\Vaishali Sen\Downloads\paytm-sentinel-mvp final\sentinel\QR_codes"

BENIGN_FOLDER = "benign_qr_images_500"
MALICIOUS_FOLDER = "malicious_qr_images_500"


# ============================================================
# 2. IMAGE FEATURE EXTRACTION
# ============================================================

def extract_features(image_path):

    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

    if image is None:
        return None

    # Resize QR image
    image = cv2.resize(image, (64, 64))

    # Normalize pixel values
    normalized = image.astype(np.float32) / 255.0

    features = []

    # --------------------------------------------------------
    # A. Image pixel features
    # --------------------------------------------------------

    # Flatten resized QR image
    pixel_features = normalized.flatten()

    features.extend(pixel_features)

    # --------------------------------------------------------
    # B. Image statistics
    # --------------------------------------------------------

    black_pixel_ratio = np.mean(image < 128)

    mean_intensity = np.mean(image)

    std_intensity = np.std(image)

    features.extend([
        black_pixel_ratio,
        mean_intensity,
        std_intensity
    ])

    # --------------------------------------------------------
    # C. Edge features
    # --------------------------------------------------------

    edges = cv2.Canny(image, 100, 200)

    edge_density = np.mean(edges > 0)

    features.append(edge_density)

    # --------------------------------------------------------
    # D. QR decoder features
    # --------------------------------------------------------

    detector = cv2.QRCodeDetector()

    try:
        decoded_data, points, _ = detector.detectAndDecode(image)

        if decoded_data:

            decoded_successfully = 1
            payload_length = len(decoded_data)

            is_url = int(
                decoded_data.lower().startswith(
                    ("http://", "https://")
                )
            )

            is_https = int(
                decoded_data.lower().startswith("https://")
            )

            special_character_count = sum(
                c in "@?=&%_-"
                for c in decoded_data
            )

        else:

            decoded_successfully = 0
            payload_length = 0
            is_url = 0
            is_https = 0
            special_character_count = 0

    except Exception:

        decoded_successfully = 0
        payload_length = 0
        is_url = 0
        is_https = 0
        special_character_count = 0

    features.extend([
        decoded_successfully,
        payload_length,
        is_url,
        is_https,
        special_character_count
    ])

    return np.array(features, dtype=np.float32)


# ============================================================
# 3. LOAD DATASET
# ============================================================

X = []
y = []

print("\nLoading dataset...\n")


def load_folder(folder_path, label):

    count = 0

    for filename in os.listdir(folder_path):

        image_path = os.path.join(
            folder_path,
            filename
        )

        if not filename.lower().endswith(
            (".png", ".jpg", ".jpeg", ".bmp", ".webp")
        ):
            continue

        features = extract_features(image_path)

        if features is not None:

            X.append(features)
            y.append(label)

            count += 1

    return count


benign_path = os.path.join(
    DATASET_PATH,
    BENIGN_FOLDER
)

malicious_path = os.path.join(
    DATASET_PATH,
    MALICIOUS_FOLDER
)


benign_count = load_folder(
    benign_path,
    0
)

malicious_count = load_folder(
    malicious_path,
    1
)


print("Benign images:", benign_count)
print("Malicious images:", malicious_count)
print("Total images:", len(X))


# ============================================================
# 4. CONVERT TO NUMPY
# ============================================================

X = np.array(X)
y = np.array(y)

print("\nFeature shape:", X.shape)


# ============================================================
# 5. TRAIN / TEST SPLIT
# ============================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)


print("\nTraining samples:", len(X_train))
print("Testing samples:", len(X_test))


# ============================================================
# 6. XGBOOST MODEL
# ============================================================

model = XGBClassifier(

    n_estimators=300,

    max_depth=6,

    learning_rate=0.05,

    subsample=0.8,

    colsample_bytree=0.8,

    objective="binary:logistic",

    eval_metric="logloss",

    random_state=42,

    n_jobs=-1
)


# ============================================================
# 7. TRAIN
# ============================================================

print("\nTraining XGBoost...\n")

model.fit(
    X_train,
    y_train
)


print("Training completed.")


# ============================================================
# 8. PREDICTIONS
# ============================================================

y_pred = model.predict(X_test)

y_probability = model.predict_proba(X_test)[:, 1]


# ============================================================
# 9. EVALUATION
# ============================================================

accuracy = accuracy_score(
    y_test,
    y_pred
)

precision = precision_score(
    y_test,
    y_pred,
    zero_division=0
)

recall = recall_score(
    y_test,
    y_pred,
    zero_division=0
)

f1 = f1_score(
    y_test,
    y_pred,
    zero_division=0
)

try:

    roc_auc = roc_auc_score(
        y_test,
        y_probability
    )

except ValueError:

    roc_auc = 0


print("\n===================================")
print("       SENTINEL QR MODEL")
print("===================================")

print(f"Accuracy  : {accuracy:.4f}")
print(f"Precision : {precision:.4f}")
print(f"Recall    : {recall:.4f}")
print(f"F1 Score  : {f1:.4f}")
print(f"ROC-AUC   : {roc_auc:.4f}")


print("\nClassification Report:\n")

print(
    classification_report(
        y_test,
        y_pred,
        target_names=[
            "Benign",
            "Malicious"
        ],
        zero_division=0
    )
)


print("\nConfusion Matrix:\n")

print(
    confusion_matrix(
        y_test,
        y_pred
    )
)


# ============================================================
# 10. SAVE MODEL
# ============================================================

MODEL_PATH = "sentinel_xgboost_qr_model.pkl"

joblib.dump(
    model,
    MODEL_PATH
)

print(
    f"\nModel saved as: {MODEL_PATH}"
)
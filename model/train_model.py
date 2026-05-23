"""
model/train_model.py
====================
GestureSense — ML Gesture Classifier Training
Member 5 Responsibility: Model Training & Evaluation

This script:
  1. Loads data/labels.csv (collected by Member 4 using data/capture.py)
  2. Normalises landmarks relative to the wrist (landmark 0)
  3. Splits: 70% train / 15% validation / 15% test
  4. Trains a Random Forest classifier
  5. Validates on the val split (prints accuracy)
  6. Saves the trained model to model/gesture_model.pkl
  7. Saves the test split to model/test_data.npz for evaluate_model.py

RUN
---
    python model/train_model.py
"""

import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, classification_report

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).parent.parent
DATA_CSV   = ROOT / "data" / "labels.csv"
MODEL_DIR  = ROOT / "model"
MODEL_FILE = MODEL_DIR / "gesture_model.pkl"
TEST_FILE  = MODEL_DIR / "test_data.npz"
MODEL_DIR.mkdir(exist_ok=True)


def normalize_landmarks(X: np.ndarray) -> np.ndarray:
    """
    Normalize each sample so that:
      - Wrist (landmark 0) becomes the origin  →  translation-invariant
      - Scale by the max distance from wrist    →  scale-invariant
    Input shape:  (N, 63)  — 21 landmarks × (x, y, z)
    Output shape: (N, 63)
    """
    X_norm = np.zeros_like(X, dtype=np.float32)
    for i, row in enumerate(X):
        pts = row.reshape(21, 3)
        origin = pts[0].copy()        # wrist
        pts -= origin                 # translate
        scale = np.max(np.linalg.norm(pts, axis=1)) + 1e-9
        pts /= scale                  # scale
        X_norm[i] = pts.flatten()
    return X_norm


def main():
    # ── 1. Load data ──────────────────────────────────────────────────────────
    if not DATA_CSV.exists():
        print(f"❌ Dataset not found at {DATA_CSV}")
        print("   Run data/capture.py first to collect training data.")
        sys.exit(1)

    print(f"📂 Loading dataset from {DATA_CSV} …")
    df = pd.read_csv(DATA_CSV)

    if "label" not in df.columns:
        print("❌ CSV missing 'label' column.")
        sys.exit(1)

    feature_cols = [c for c in df.columns if c != "label"]
    X = df[feature_cols].values.astype(np.float32)
    y_raw = df["label"].values

    print(f"   Total samples : {len(X)}")
    print(f"   Gesture classes: {sorted(set(y_raw))}")
    print(f"   Features per sample: {X.shape[1]}")

    # ── 2. Encode labels ──────────────────────────────────────────────────────
    le = LabelEncoder()
    y  = le.fit_transform(y_raw)
    print(f"\n   Classes (encoded): {list(le.classes_)}")

    # ── 3. Normalize ──────────────────────────────────────────────────────────
    print("\n🔢 Normalizing landmarks (origin=wrist, scale-invariant) …")
    X = normalize_landmarks(X)

    # ── 4. Split 70 / 15 / 15 ────────────────────────────────────────────────
    X_temp, X_test, y_temp, y_test = train_test_split(
        X, y, test_size=0.15, random_state=42, stratify=y
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp, test_size=0.15 / 0.85,
        random_state=42, stratify=y_temp
    )

    print(f"\n📊 Data split:")
    print(f"   Train      : {len(X_train)} samples")
    print(f"   Validation : {len(X_val)} samples")
    print(f"   Test       : {len(X_test)} samples")

    # ── 5. Train ──────────────────────────────────────────────────────────────
    print("\n🌲 Training Random Forest classifier …")
    clf = RandomForestClassifier(
        n_estimators=200,
        max_depth=None,
        min_samples_split=2,
        min_samples_leaf=1,
        n_jobs=-1,
        random_state=42,
        class_weight="balanced",
    )
    clf.fit(X_train, y_train)
    print("   ✅ Training complete")

    # ── 6. Validate ───────────────────────────────────────────────────────────
    val_preds = clf.predict(X_val)
    val_acc   = accuracy_score(y_val, val_preds)
    print(f"\n📈 Validation accuracy: {val_acc * 100:.2f}%")
    print("\nValidation classification report:")
    print(classification_report(y_val, val_preds, target_names=le.classes_))

    # ── 7. Save model + encoder ───────────────────────────────────────────────
    payload = {"model": clf, "label_encoder": le}
    joblib.dump(payload, MODEL_FILE)
    print(f"\n💾 Model saved to {MODEL_FILE}")

    # ── 8. Save test split for evaluate_model.py ──────────────────────────────
    np.savez(TEST_FILE, X_test=X_test, y_test=y_test)
    print(f"💾 Test data saved to {TEST_FILE}")

    print("\n✅ Training complete! Run model/evaluate_model.py to see full metrics.")


if __name__ == "__main__":
    main()

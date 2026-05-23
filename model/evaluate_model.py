"""
model/evaluate_model.py
=======================
GestureSense — Model Evaluation & Reporting
Member 5 Responsibility: Testing & Metrics

Loads the trained model (gesture_model.pkl) and the held-out
test split (test_data.npz), then produces:

  1. Classification report (per-gesture precision, recall, F1)
  2. Confusion matrix heatmap → model/results/confusion_matrix.png
  3. Accuracy comparison: Rule-Based vs ML Model (live camera, optional)
  4. model/results/classification_report.txt

RUN
---
    python model/evaluate_model.py
"""

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")   # non-interactive backend (no display needed)
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix
)

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT         = Path(__file__).parent.parent
MODEL_FILE   = ROOT / "model" / "gesture_model.pkl"
TEST_FILE    = ROOT / "model" / "test_data.npz"
RESULTS_DIR  = ROOT / "model" / "results"
CM_IMAGE     = RESULTS_DIR / "confusion_matrix.png"
REPORT_FILE  = RESULTS_DIR / "classification_report.txt"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def main():
    # ── 1. Load model ─────────────────────────────────────────────────────────
    if not MODEL_FILE.exists():
        print(f"❌ Model not found at {MODEL_FILE}")
        print("   Run model/train_model.py first.")
        sys.exit(1)

    print(f"📂 Loading model from {MODEL_FILE} …")
    payload = joblib.load(MODEL_FILE)
    clf     = payload["model"]
    le      = payload["label_encoder"]
    classes = list(le.classes_)
    print(f"   Classes: {classes}")

    # ── 2. Load test split ────────────────────────────────────────────────────
    if not TEST_FILE.exists():
        print(f"❌ Test data not found at {TEST_FILE}")
        print("   Run model/train_model.py first.")
        sys.exit(1)

    print(f"📂 Loading test split from {TEST_FILE} …")
    data   = np.load(TEST_FILE)
    X_test = data["X_test"]
    y_test = data["y_test"]
    print(f"   Test samples: {len(X_test)}")

    # ── 3. Predict ────────────────────────────────────────────────────────────
    print("\n🔍 Running inference on test set …")
    y_pred = clf.predict(X_test)

    # ── 4. Metrics ────────────────────────────────────────────────────────────
    accuracy = accuracy_score(y_test, y_pred)
    report   = classification_report(y_test, y_pred, target_names=classes)
    cm       = confusion_matrix(y_test, y_pred)

    print(f"\n✅ Test Accuracy: {accuracy * 100:.2f}%")
    print("\nClassification Report:")
    print(report)

    # ── 5. Save classification report ─────────────────────────────────────────
    with open(REPORT_FILE, "w") as f:
        f.write(f"GestureSense ML Model — Evaluation Report\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Test Accuracy: {accuracy * 100:.2f}%\n\n")
        f.write("Classification Report:\n")
        f.write(report)
        f.write("\n\nModel: Random Forest (scikit-learn)\n")
        f.write(f"Total test samples: {len(X_test)}\n")
        f.write(f"Gesture classes: {classes}\n")
    print(f"💾 Report saved to {REPORT_FILE}")

    # ── 6. Confusion matrix heatmap ────────────────────────────────────────────
    print("\n📊 Generating confusion matrix …")
    fig, ax = plt.subplots(figsize=(12, 10))
    fig.patch.set_facecolor("#050d1a")
    ax.set_facecolor("#0a1628")

    # Normalize per row for better readability
    cm_norm = cm.astype(float)
    row_sums = cm.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    cm_norm /= row_sums

    sns.heatmap(
        cm_norm,
        annot=cm,           # show raw counts inside cells
        fmt="d",
        xticklabels=classes,
        yticklabels=classes,
        cmap="Blues",
        linewidths=0.5,
        linecolor="#1a3050",
        ax=ax,
        annot_kws={"size": 11, "color": "white"},
        cbar_kws={"shrink": 0.8},
    )

    ax.set_title(
        f"GestureSense ML Classifier — Confusion Matrix\nTest Accuracy: {accuracy * 100:.1f}%",
        color="white", fontsize=14, pad=16
    )
    ax.set_xlabel("Predicted Gesture", color="#a8c4e0", fontsize=11)
    ax.set_ylabel("True Gesture",      color="#a8c4e0", fontsize=11)
    ax.tick_params(colors="white", labelsize=9)
    plt.setp(ax.get_xticklabels(), rotation=35, ha="right", color="white")
    plt.setp(ax.get_yticklabels(), rotation=0,  color="white")
    plt.tight_layout()
    plt.savefig(CM_IMAGE, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"💾 Confusion matrix saved to {CM_IMAGE}")

    # ── 7. Summary bar chart — per-gesture F1 scores ──────────────────────────
    from sklearn.metrics import f1_score
    f1_scores = f1_score(y_test, y_pred, average=None, labels=range(len(classes)))

    fig2, ax2 = plt.subplots(figsize=(12, 5))
    fig2.patch.set_facecolor("#050d1a")
    ax2.set_facecolor("#0a1628")

    colors = ["#00e5ff" if s >= 0.90 else "#ff9500" if s >= 0.75 else "#ff3b5c"
              for s in f1_scores]
    bars = ax2.bar(classes, f1_scores, color=colors, edgecolor="#1a3050", linewidth=0.8)
    ax2.axhline(0.90, color="#00ff88", linestyle="--", linewidth=1, alpha=0.7, label="90% threshold")
    ax2.set_ylim(0, 1.05)
    ax2.set_title("F1-Score per Gesture Class", color="white", fontsize=13)
    ax2.set_xlabel("Gesture",  color="#a8c4e0")
    ax2.set_ylabel("F1-Score", color="#a8c4e0")
    ax2.tick_params(colors="white")
    plt.setp(ax2.get_xticklabels(), rotation=35, ha="right", color="white")
    ax2.legend(facecolor="#0a1628", labelcolor="white")

    for bar, score in zip(bars, f1_scores):
        ax2.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + 0.01,
                 f"{score:.2f}", ha="center", va="bottom",
                 color="white", fontsize=9)

    plt.tight_layout()
    f1_path = RESULTS_DIR / "f1_scores.png"
    plt.savefig(f1_path, dpi=150, bbox_inches="tight",
                facecolor=fig2.get_facecolor())
    plt.close()
    print(f"💾 F1 score chart saved to {f1_path}")

    print(f"\n✅ Evaluation complete! Results in {RESULTS_DIR}")


if __name__ == "__main__":
    main()

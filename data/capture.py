"""
data/capture.py
===============
GestureSense — Landmark Data Capture Tool
Member 4 Responsibility: Data Collection

HOW TO USE
----------
1. Run this script:
       python data/capture.py

2. You will see your webcam feed with hand landmarks drawn.

3. Press a NUMBER KEY to start capturing samples for that gesture:
       1 → fist          2 → open_palm     3 → index
       4 → peace         5 → three_fingers 6 → thumb_up
       7 → thumb_down    8 → pinch         9 → ok_sign
       0 → shaka         Q → index_pinky

4. While a key is held, samples are saved every 5 frames.
   The UI shows how many samples have been collected.

5. Press ESC to quit and see the summary.

OUTPUT
------
    data/landmarks/<gesture_name>.csv   — one file per gesture
    data/labels.csv                     — consolidated master CSV

Each CSV row has 63 columns (x0,y0,z0, x1,y1,z1, ..., x20,y20,z20) + label.
"""

import csv
import os
import time
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent
LANDMARKS_DIR = BASE_DIR / "landmarks"
LABELS_FILE   = BASE_DIR / "labels.csv"
LANDMARKS_DIR.mkdir(parents=True, exist_ok=True)

# ── Gesture label map ──────────────────────────────────────────────────────────
KEY_MAP = {
    ord("1"): "fist",
    ord("2"): "open_palm",
    ord("3"): "index",
    ord("4"): "peace",
    ord("5"): "three_fingers",
    ord("6"): "thumb_up",
    ord("7"): "thumb_down",
    ord("8"): "pinch",
    ord("9"): "ok_sign",
    ord("0"): "shaka",
    ord("q"): "index_pinky",
    ord("Q"): "index_pinky",
}

GESTURE_DISPLAY = {
    "fist":          "1 - ✊ Fist",
    "open_palm":     "2 - 🖐 Open Palm",
    "index":         "3 - ☝ Index",
    "peace":         "4 - ✌ Peace",
    "three_fingers": "5 - 🤟 Three Fingers",
    "thumb_up":      "6 - 👍 Thumb Up",
    "thumb_down":    "7 - 👎 Thumb Down",
    "pinch":         "8 - 🤏 Pinch",
    "ok_sign":       "9 - 👌 OK Sign",
    "shaka":         "0 - 🤙 Shaka",
    "index_pinky":   "Q - 🤘 Rock On",
}

# ── Column headers ─────────────────────────────────────────────────────────────
HEADER = [f"{a}{i}" for i in range(21) for a in ("x", "y", "z")] + ["label"]


def _lm_to_row(lm_list, label: str) -> list:
    """Flatten 21 MediaPipe landmarks into 63 floats + label."""
    row = []
    for lm in lm_list:
        row += [round(lm.x, 6), round(lm.y, 6), round(lm.z, 6)]
    row.append(label)
    return row


def _append_to_csv(filepath: Path, row: list, write_header: bool):
    """Append one row to a CSV; write header if file is new."""
    with open(filepath, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(HEADER)
        writer.writerow(row)


def _counts() -> dict:
    """Count existing samples per gesture from individual CSV files."""
    counts = {}
    for g in GESTURE_DISPLAY:
        p = LANDMARKS_DIR / f"{g}.csv"
        if p.exists():
            with open(p) as f:
                # subtract 1 for header row
                counts[g] = max(0, sum(1 for _ in f) - 1)
        else:
            counts[g] = 0
    return counts


def _rebuild_labels():
    """Rebuild the master labels.csv from all individual gesture CSVs."""
    with open(LABELS_FILE, "w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(HEADER)
        for g in GESTURE_DISPLAY:
            p = LANDMARKS_DIR / f"{g}.csv"
            if not p.exists():
                continue
            with open(p) as f:
                reader = csv.reader(f)
                next(reader, None)  # skip header
                for row in reader:
                    writer.writerow(row)


def main():
    mp_hands   = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils
    hands      = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7,
    )

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    current_label  = None
    frame_count    = 0
    sample_counter = 0
    counts         = _counts()
    SAMPLE_EVERY   = 5  # capture 1 sample every N frames

    print("\n🎥 GestureSense Data Capture Tool")
    print("=" * 40)
    for name, disp in GESTURE_DISPLAY.items():
        print(f"  {disp:30s}  [{counts.get(name, 0):4d} samples]")
    print("\nPress a key to start capturing. ESC to quit.")
    print("=" * 40)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame  = cv2.flip(frame, 1)
        rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        lm_list = None
        if result.multi_hand_landmarks:
            for hand_lm in result.multi_hand_landmarks:
                mp_drawing.draw_landmarks(frame, hand_lm, mp_hands.HAND_CONNECTIONS)
                lm_list = hand_lm.landmark

        # ── Key capture ──────────────────────────────────────────────────────
        key = cv2.waitKey(1) & 0xFF
        if key == 27:   # ESC
            break
        if key in KEY_MAP:
            new_label = KEY_MAP[key]
            if new_label != current_label:
                current_label  = new_label
                sample_counter = 0
                print(f"\n▶ Capturing: {current_label}")

        # ── Sample every N frames when hand is visible ────────────────────
        if current_label and lm_list:
            frame_count += 1
            if frame_count % SAMPLE_EVERY == 0:
                row = _lm_to_row(lm_list, current_label)
                gesture_csv = LANDMARKS_DIR / f"{current_label}.csv"
                is_new = not gesture_csv.exists()
                _append_to_csv(gesture_csv, row, write_header=is_new)
                counts[current_label] = counts.get(current_label, 0) + 1
                sample_counter += 1
                if sample_counter % 20 == 0:
                    print(f"  {current_label}: {counts[current_label]} samples total")

        # ── Overlay HUD ───────────────────────────────────────────────────
        overlay_color = (0, 255, 136) if current_label else (100, 100, 100)
        status_text   = f"CAPTURING: {current_label}" if current_label else "Press 1-9, 0, Q to start"
        cv2.rectangle(frame, (0, 0), (640, 40), (10, 22, 40), -1)
        cv2.putText(frame, status_text, (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, overlay_color, 2)

        total = sum(counts.values())
        cv2.putText(frame, f"Total samples: {total}", (420, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 200, 220), 1)

        # Show per-gesture counts on the right
        y = 70
        for g, c in counts.items():
            color = (0, 255, 136) if g == current_label else (100, 140, 180)
            cv2.putText(frame, f"{g}: {c}", (470, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1)
            y += 18

        cv2.imshow("GestureSense — Data Capture (ESC to quit)", frame)

    cap.release()
    cv2.destroyAllWindows()
    hands.close()

    # ── Rebuild master CSV ─────────────────────────────────────────────────
    print("\n📊 Rebuilding master labels.csv …")
    _rebuild_labels()
    print("✅ Done! Saved to:")
    print(f"   {LANDMARKS_DIR}/<gesture>.csv")
    print(f"   {LABELS_FILE}")
    print("\nFinal sample counts:")
    for g, c in _counts().items():
        print(f"  {g:20s}: {c:4d} samples")


if __name__ == "__main__":
    main()

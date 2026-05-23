"""
web/server.py
=============
GestureSense FastAPI WebSocket backend.

RUN standalone:
    uvicorn web.server:app --port 8000

Or launch through main.py.
"""

import asyncio
import base64
import json
import math
import threading
import time

import cv2
import mediapipe as mp
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import config.manager as cfg_mgr
from core.detector import get_finger_states, detect_gesture
from core.executor import execute_action
from core.mouse_control import MouseController

# ── MediaPipe setup ───────────────────────────────────────────────────────────
_mp_hands   = mp.solutions.hands
_mp_drawing = mp.solutions.drawing_utils
_hands      = _mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.75,
    min_tracking_confidence=0.75,
)

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="GestureSense API", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Session state ─────────────────────────────────────────────────────────────
last_trigger:  dict[str, float] = {}
gesture_stats: dict[str, int]   = {}
session_start: float            = time.time()


# ── REST endpoints ────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "GestureSense v3 Running", "status": "ok"}


@app.get("/api/gestures")
def get_gestures():
    cfg = cfg_mgr.load()
    return {"gestures": {**cfg["mappings"], **cfg["custom"]}}


@app.get("/api/stats")
def get_stats():
    total = sum(gesture_stats.values())
    return {
        "uptime_seconds": int(time.time() - session_start),
        "total_gestures": total,
        "gesture_counts": gesture_stats,
        "top_gesture": max(gesture_stats, key=gesture_stats.get) if total > 0 else "none",
    }


@app.post("/api/cooldown")
async def set_cooldown(data: dict):
    g = data.get("gesture")
    c = float(data.get("cooldown", 1.0))
    cfg = cfg_mgr.load()
    if g in cfg["mappings"]:
        cfg["mappings"][g]["cooldown"] = c
    elif g in cfg["custom"]:
        cfg["custom"][g]["cooldown"] = c
    cfg_mgr.save(cfg)
    return {"success": True, "gesture": g, "cooldown": c}


@app.post("/api/custom_gesture")
async def add_custom_gesture(data: dict):
    pattern = data.get("pattern", "")
    if len(pattern) != 5 or not all(c in "01" for c in pattern):
        return {"success": False, "error": "Pattern must be 5 binary digits e.g. 10001"}

    cfg = cfg_mgr.load()
    mapping = {
        "label":    data.get("label", "Custom Gesture"),
        "icon":     data.get("icon", "🤌"),
        "key":      data.get("key", ""),
        "key_type": data.get("key_type", "char"),
        "cooldown": float(data.get("cooldown", 1.0)),
    }
    cfg["custom"][pattern] = mapping
    cfg_mgr.save(cfg)
    gesture_stats[pattern] = 0
    return {"success": True, "pattern": pattern, "mapping": mapping}


@app.delete("/api/custom_gesture/{pattern}")
async def delete_custom_gesture(pattern: str):
    cfg = cfg_mgr.load()
    if pattern in cfg["custom"]:
        del cfg["custom"][pattern]
        cfg_mgr.save(cfg)
        gesture_stats.pop(pattern, None)
        return {"success": True}
    return {"success": False, "error": "Not found"}


@app.get("/api/custom_gestures")
def list_custom():
    return {"custom_gestures": cfg_mgr.load()["custom"]}


# ── WebSocket stream ──────────────────────────────────────────────────────────

@app.websocket("/ws/gesture")
async def gesture_websocket(ws: WebSocket, cam_index: int = 0, mouse_control: bool = False):
    await ws.accept()

    mouse_controller = MouseController()
    cap = cv2.VideoCapture(cam_index)
    if not cap or not cap.isOpened():
        await ws.send_text(json.dumps({
            "type":    "error",
            "message": f"Could not open camera at index {cam_index}. Please verify connection.",
        }))
        await ws.close()
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)

    frame_count      = 0
    fps_time         = time.time()
    fps              = 0
    cooldown_remaining = 0.0
    on_cooldown      = False

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame  = cv2.flip(frame, 1)
            rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = _hands.process(rgb)

            gesture_name = "none"
            confidence   = 0.0
            fingers      = [0, 0, 0, 0, 0]
            cooldown_remaining = 0.0
            on_cooldown  = False

            if result.multi_hand_landmarks:
                for hand_lm, hand_info in zip(
                    result.multi_hand_landmarks, result.multi_handedness
                ):
                    _mp_drawing.draw_landmarks(frame, hand_lm, _mp_hands.HAND_CONNECTIONS)
                    lm         = hand_lm.landmark
                    handedness = hand_info.classification[0].label
                    cfg        = cfg_mgr.load()

                    fingers      = get_finger_states(lm, handedness)
                    gesture_name, confidence = detect_gesture(lm, fingers, cfg["custom"])

                    if mouse_control:
                        mouse_controller.update(gesture_name, lm)

                    if gesture_name != "none":
                        is_mouse_gesture = gesture_name in ("index", "pinch", "peace", "three_fingers", "ok_sign")
                        if mouse_control and is_mouse_gesture:
                            # Handled by mouse_controller
                            pass
                        else:
                            mapping  = cfg_mgr.get_mapping(gesture_name)
                            cooldown = mapping.get("cooldown", 1.0)
                            now      = time.time()
                            elapsed  = now - last_trigger.get(gesture_name, 0)
                            cooldown_remaining = round(max(0.0, cooldown - elapsed), 2)
                            on_cooldown = elapsed < cooldown

                            if not on_cooldown:
                                key      = mapping.get("key", "")
                                key_type = mapping.get("key_type", "none")
                                if key_type != "none" and key:
                                    threading.Thread(
                                        target=execute_action,
                                        args=(key, key_type),
                                        daemon=True,
                                    ).start()
                                last_trigger[gesture_name] = now
                                gesture_stats[gesture_name] = gesture_stats.get(gesture_name, 0) + 1
            else:
                if mouse_control:
                    mouse_controller.update("none", None)

            # FPS counter
            frame_count += 1
            if frame_count % 15 == 0:
                fps = round(15 / (time.time() - fps_time), 1)
                fps_time = time.time()

            # Encode frame
            _, buf   = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame64  = base64.b64encode(buf).decode("utf-8")
            mapping  = cfg_mgr.get_mapping(gesture_name)

            await ws.send_text(json.dumps({
                "type":               "gesture_frame",
                "gesture":            gesture_name,
                "confidence":         round(confidence * 100),
                "label":              mapping.get("label", ""),
                "icon":               mapping.get("icon", ""),
                "key":                mapping.get("key", ""),
                "cooldown":           mapping.get("cooldown", 1.0),
                "cooldown_remaining": cooldown_remaining,
                "on_cooldown":        on_cooldown,
                "fingers":            fingers,
                "fps":                fps,
                "frame":              frame64,
            }))
            await asyncio.sleep(0.033)

    except WebSocketDisconnect:
        print("[web/server] Client disconnected")
    except Exception as e:
        print(f"[web/server] WS error: {e}")
    finally:
        cap.release()

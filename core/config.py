"""
core/config.py
==============
Single source of truth for GestureSense configuration.
Loads from assets/gestures_config.json and persists changes to
gestures_config.json in the project root.
"""

import json
import os
import shutil

_BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_CFG = os.path.join(_BASE_DIR, "assets", "gestures_config.json")
_USER_CFG    = os.path.join(_BASE_DIR, "gestures_config.json")


def load() -> dict:
    """Load user config; fall back to bundled defaults on first run."""
    if os.path.exists(_USER_CFG):
        try:
            with open(_USER_CFG, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass  # corrupted → regenerate

    shutil.copy(_DEFAULT_CFG, _USER_CFG)
    with open(_USER_CFG, "r", encoding="utf-8") as f:
        return json.load(f)


def save(cfg: dict) -> None:
    """Persist config to disk."""
    with open(_USER_CFG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def all_mappings(cfg: dict) -> dict:
    """Return built-in + custom mappings merged."""
    return {**cfg.get("mappings", {}), **cfg.get("custom", {})}


def get_settings(cfg: dict) -> dict:
    return cfg.get("settings", {
        "camera_index": 0,
        "ema_alpha": 0.7,
        "width": 640,
        "height": 480,
    })

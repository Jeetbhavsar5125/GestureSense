"""
config/manager.py
=================
Centralised configuration loader / saver.
Handles gestures_config.json in the config/ directory.
Provides an in-memory cache to avoid repeated disk reads.
"""
import os
import json

# Config file lives in the same directory as this module
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "gestures_config.json")

DEFAULT_MAPPINGS = {
    "fist":          {"label": "Play / Pause",  "icon": "✊", "key": "space",  "key_type": "special", "cooldown": 1.0},
    "peace":         {"label": "Skip +10s",     "icon": "✌️", "key": "l",      "key_type": "char",    "cooldown": 1.0},
    "three_fingers": {"label": "Skip -10s",     "icon": "🤟", "key": "j",      "key_type": "char",    "cooldown": 1.0},
    "open_palm":     {"label": "Skip +5s",      "icon": "🖐️", "key": "right",  "key_type": "special", "cooldown": 0.8},
    "thumb_up":      {"label": "Volume Up",     "icon": "👍", "key": "up",     "key_type": "special", "cooldown": 0.5},
    "thumb_down":    {"label": "Volume Down",   "icon": "👎", "key": "down",   "key_type": "special", "cooldown": 0.5},
    "pinch":         {"label": "Mute Toggle",   "icon": "🤏", "key": "m",      "key_type": "char",    "cooldown": 1.2},
    "ok_sign":       {"label": "Fullscreen",    "icon": "👌", "key": "f",      "key_type": "char",    "cooldown": 1.5},
    "shaka":         {"label": "Theater Mode",  "icon": "🤙", "key": "t",      "key_type": "char",    "cooldown": 1.5},
    "index":         {"label": "Move Cursor",   "icon": "☝️", "key": "",       "key_type": "none",    "cooldown": 0.0},
}

DEFAULT_CUSTOM = {
    "01001": {
        "label":    "Open YouTube",
        "icon":     "📺",
        "key":      "https://youtube.com",
        "key_type": "url",
        "cooldown": 2.0,
    }
}

# ── In-memory cache ──────────────────────────────────────────────────────────
_cache: dict | None = None


def load() -> dict:
    """Load config from disk (or cache). Returns dict with 'mappings' and 'custom' keys."""
    global _cache
    if _cache is not None:
        return _cache

    if not os.path.exists(CONFIG_FILE):
        _cache = {"mappings": DEFAULT_MAPPINGS, "custom": DEFAULT_CUSTOM}
        save(_cache)
        return _cache

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "mappings" not in data:
            data["mappings"] = DEFAULT_MAPPINGS
        if "custom" not in data:
            data["custom"] = {}
        if not data["custom"]:
            data["custom"] = DEFAULT_CUSTOM
        _cache = data
        return _cache
    except Exception as e:
        print(f"[config] Load error: {e}")
        _cache = {"mappings": DEFAULT_MAPPINGS, "custom": DEFAULT_CUSTOM}
        return _cache


def save(config: dict) -> None:
    """Write config to disk and refresh cache."""
    global _cache
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        _cache = config
    except Exception as e:
        print(f"[config] Save error: {e}")


def invalidate() -> None:
    """Force a reload from disk on the next load() call."""
    global _cache
    _cache = None


def get_mapping(name: str) -> dict:
    """Return the mapping dict for a gesture name (checks both mappings and custom)."""
    cfg = load()
    return cfg["mappings"].get(name) or cfg["custom"].get(name) or {}

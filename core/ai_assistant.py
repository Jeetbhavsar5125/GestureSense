"""
core/ai_assistant.py
====================
Local rule-based AI assistant for GestureSense.
No API key or internet connection required.

Gemini Upgrade (Feature 4)
--------------------------
If the GEMINI_API_KEY environment variable is set, the assistant
automatically upgrades to use Google Gemini for open-ended Q&A.
Falls back silently to rule-based mode if the key is missing or the
google-generativeai package is not installed.

Usage:
    from core.ai_assistant import get_assistant
    ai = get_assistant()   # returns GeminiAssistant or AIAssistant
"""

import os
import re
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
#  Gesture Knowledge Base
# ─────────────────────────────────────────────────────────────────────────────

GESTURE_KB = {
    "fist": {
        "name": "Fist",
        "icon": "✊",
        "description": "Close all fingers into a fist.",
        "default_action": "Play / Pause (Spacebar)",
        "tip": "Great for play/pause — very distinct from other gestures.",
    },
    "open_palm": {
        "name": "Open Palm",
        "icon": "🖐",
        "description": "Extend all four fingers (thumb can be tucked).",
        "default_action": "Skip forward / right arrow",
        "tip": "Works well for 'stop' or 'next slide'.",
    },
    "index": {
        "name": "Index Finger",
        "icon": "☝",
        "description": "Point with just the index finger.",
        "default_action": "Move mouse cursor (in Air Mouse mode)",
        "tip": "In Air Mouse mode this moves the cursor smoothly.",
    },
    "peace": {
        "name": "Peace / Victory Sign",
        "icon": "✌",
        "description": "Index + middle finger extended (V shape).",
        "default_action": "Right-click (in Air Mouse mode)",
        "tip": "In gesture mode you can map it to skip +10s, next track, etc.",
    },
    "three_fingers": {
        "name": "Three Fingers",
        "icon": "🤟",
        "description": "Index + middle + ring finger extended.",
        "default_action": "Scroll (velocity-based, in Air Mouse mode)",
        "tip": "Move your hand up/down while holding three fingers to scroll.",
    },
    "thumb_up": {
        "name": "Thumb Up",
        "icon": "👍",
        "description": "Only thumb extended, pointing up.",
        "default_action": "Volume Up / Scroll Up (in Air Mouse mode)",
        "tip": "In Air Mouse mode it scrolls up. In gesture mode: volume up.",
    },
    "thumb_down": {
        "name": "Thumb Down",
        "icon": "👎",
        "description": "Only thumb extended, pointing down.",
        "default_action": "Volume Down / Scroll Down (in Air Mouse mode)",
        "tip": "In Air Mouse mode it scrolls down. In gesture mode: volume down.",
    },
    "pinch": {
        "name": "Pinch",
        "icon": "🤏",
        "description": "Touch thumb tip to index fingertip.",
        "default_action": "Left-click (in Air Mouse mode)",
        "tip": "Tap a pinch quickly to left-click. Perfect for selecting items.",
    },
    "ok_sign": {
        "name": "OK Sign",
        "icon": "👌",
        "description": "Pinch (thumb+index) while middle, ring, pinky are extended.",
        "default_action": "Double-click (in Air Mouse mode)",
        "tip": "Use for opening files or links with a double-click.",
    },
    "shaka": {
        "name": "Shaka / Hang Loose",
        "icon": "🤙",
        "description": "Thumb + pinky extended, other fingers curled.",
        "default_action": "Mute toggle (M key)",
        "tip": "Looks like a phone gesture — easy to remember for mute.",
    },
    "index_pinky": {
        "name": "Rock On / Horns",
        "icon": "🤘",
        "description": "Index + pinky extended, middle and ring curled.",
        "default_action": "Next (Right Arrow key)",
        "tip": "Visually unique — very rarely done by accident. Great for Next Slide.",
    },
}

MOUSE_MODE_INFO = """
**Air Mouse Mode** lets you control your mouse with hand gestures:

• ☝ **Index** → moves the cursor
• 🤏 **Pinch** → left single-click
• ✌ **Peace** → right-click
• 👌 **OK Sign** → double-click
• 🤟 **Three Fingers** → scroll (move hand up/down)
• 👍 **Thumb Up** → scroll up
• 👎 **Thumb Down** → scroll down

Enable it by clicking **🖱 AIR MOUSE** on the Dashboard.
"""

DWELL_INFO = """
**Dwell-Time Gating** prevents accidental triggers.

A gesture only fires its action after you hold it steadily for **~0.35 seconds**.
Brief flicks or transitions between gestures are ignored.

You can see a small progress bar fill up as you hold a gesture — it turns green when it fires.
"""

HOW_TO_MAP = """
**To map a gesture to a new action:**

1. Go to the **✋ Gestures** page (click the sidebar).
2. Find the gesture card you want to change.
3. Click the action dropdown and choose a key/action.
4. Adjust the cooldown slider if needed (how long to wait before it can fire again).

For custom hotkeys (e.g. Ctrl+Z), choose **⌘ Custom Key / Hotkey** and type `ctrl+z`.
"""

TROUBLESHOOT_TRIGGERS = """
**Gestures firing too easily or accidentally?**

✅ The app uses dwell-time gating (hold for 0.35 s) — brief flicks are ignored.
✅ Increase the **cooldown** on that gesture card so it can't repeat quickly.
✅ Remap rarely-used gestures to **No Action** on the Gestures page.
✅ Try better lighting — MediaPipe works best with clear hand contrast.
"""

TROUBLESHOOT_CAMERA = """
**Camera not working?**

✅ Make sure no other app (Teams, Zoom, OBS) has the camera open.
✅ Try a different camera index in **⚙ Settings** (0, 1, 2…).
✅ Check your webcam is plugged in and recognized by Windows.
✅ Restart the app after changing camera index.
"""


# ─────────────────────────────────────────────────────────────────────────────
#  Intent Patterns
# ─────────────────────────────────────────────────────────────────────────────

def _contains(text: str, *keywords) -> bool:
    return any(k in text for k in keywords)


INTENTS = [
    # List gestures
    {
        "check": lambda t: _contains(t, "list", "show all", "all gesture", "what gesture", "available gesture", "gestures available"),
        "handler": "_list_gestures",
    },
    # Mouse mode info
    {
        "check": lambda t: _contains(t, "mouse", "cursor", "click", "right click", "left click", "scroll", "air mouse"),
        "handler": "_mouse_info",
    },
    # Dwell / accidental
    {
        "check": lambda t: _contains(t, "accident", "too sensitive", "wrong gesture", "dwell", "misfire", "false", "unintentional", "not want"),
        "handler": "_dwell_info",
    },
    # How to map
    {
        "check": lambda t: _contains(t, "map", "assign", "change action", "change gesture", "how do i set", "configure", "bind"),
        "handler": "_map_info",
    },
    # Camera trouble
    {
        "check": lambda t: _contains(t, "camera", "webcam", "not working", "black screen", "no feed", "camera error"),
        "handler": "_camera_info",
    },
    # Specific gesture lookup
    {
        "check": lambda t: any(g in t for g in GESTURE_KB),
        "handler": "_gesture_lookup",
    },
    # Task-based suggestion (next, play, pause, skip, volume, mute, fullscreen, open)
    {
        "check": lambda t: _contains(t, "next", "previous", "play", "pause", "stop", "skip", "volume", "mute", "fullscreen", "open site", "open youtube", "open google", "type text", "hotkey", "keyboard shortcut"),
        "handler": "_task_suggest",
    },
    # Greeting
    {
        "check": lambda t: _contains(t, "hello", "hi ", "hey", "help", "what can you do", "what do you do"),
        "handler": "_greet",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
#  AI Assistant Class
# ─────────────────────────────────────────────────────────────────────────────

class AIAssistant:
    """
    Local rule-based AI assistant.
    Call `chat(user_message)` to get a response string.
    Maintains the last 3 turns of context.
    """

    MAX_HISTORY = 6   # 3 pairs of (user, bot)

    def __init__(self):
        self._history: list[tuple[str, str]] = []   # [(user, bot), ...]
        self._live_cfg: Optional[dict] = None        # injected from app if needed

    def set_config(self, cfg: dict) -> None:
        """Optionally inject the live gesture config for context-aware answers."""
        self._live_cfg = cfg

    # ── Public ────────────────────────────────────────────────────────────────

    def chat(self, user_message: str) -> str:
        text = user_message.strip().lower()
        response = self._route(text, user_message)
        # Trim history
        self._history.append((user_message, response))
        if len(self._history) > self.MAX_HISTORY:
            self._history = self._history[-self.MAX_HISTORY:]
        return response

    def clear_history(self) -> None:
        self._history.clear()

    # ── Router ────────────────────────────────────────────────────────────────

    def _route(self, text: str, original: str) -> str:
        for intent in INTENTS:
            if intent["check"](text):
                method = getattr(self, intent["handler"])
                return method(text, original)
        return self._fallback(text)

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _greet(self, text: str, original: str) -> str:
        return (
            "👋 Hi! I'm the **GestureSense AI Assistant**.\n\n"
            "I can help you with:\n"
            "• 🤚 **Gesture reference** — ask 'list gestures' or 'what does pinch do?'\n"
            "• 🖱 **Air Mouse** — ask 'how does air mouse work?'\n"
            "• ⌨ **Mapping** — ask 'how do I map a gesture to a hotkey?'\n"
            "• 🔧 **Troubleshooting** — ask 'gestures fire accidentally' or 'camera not working'\n"
            "• 💡 **Task help** — ask 'what gesture should I use to go to the next slide?'\n\n"
            "What would you like to know?"
        )

    def _list_gestures(self, text: str, original: str) -> str:
        lines = ["Here are all available gestures:\n"]
        for gid, g in GESTURE_KB.items():
            lines.append(f"{g['icon']} **{g['name']}** — {g['description']}")
            lines.append(f"   _Default: {g['default_action']}_\n")
        lines.append("\nYou can remap any of these on the **✋ Gestures** page.")
        return "\n".join(lines)

    def _mouse_info(self, text: str, original: str) -> str:
        return MOUSE_MODE_INFO

    def _dwell_info(self, text: str, original: str) -> str:
        return DWELL_INFO + "\n\n" + TROUBLESHOOT_TRIGGERS

    def _map_info(self, text: str, original: str) -> str:
        return HOW_TO_MAP

    def _camera_info(self, text: str, original: str) -> str:
        return TROUBLESHOOT_CAMERA

    def _gesture_lookup(self, text: str, original: str) -> str:
        # Find which gesture was mentioned
        found = []
        for gid, g in GESTURE_KB.items():
            if gid in text or g["name"].lower() in text:
                found.append((gid, g))
        if not found:
            return self._fallback(text)

        parts = []
        for gid, g in found:
            parts.append(
                f"{g['icon']} **{g['name']}** (`{gid}`)\n"
                f"**How to do it:** {g['description']}\n"
                f"**Default action:** {g['default_action']}\n"
                f"**Tip:** {g['tip']}"
            )
        return "\n\n---\n\n".join(parts)

    def _task_suggest(self, text: str, original: str) -> str:
        suggestions = []

        if _contains(text, "next slide", "next page", "next track", "forward", "skip next"):
            suggestions.append(
                "🤘 **Rock On (index_pinky)** — index + pinky extended.\n"
                "   Mapped to **Right Arrow** by default. Very distinct, rarely accidental."
            )
            suggestions.append(
                "🖐 **Open Palm** — all fingers extended.\n"
                "   Also works great for 'next'."
            )

        if _contains(text, "previous", "back", "prev slide", "go back"):
            suggestions.append(
                "👎 **Thumb Down** — remap to Left Arrow for 'previous'.\n"
                "   Or use ✊ **Fist** if you prefer something more dramatic."
            )

        if _contains(text, "play", "pause", "play pause"):
            suggestions.append(
                "✊ **Fist** — default: Spacebar (Play/Pause).\n"
                "   Very intuitive — clench your fist to pause."
            )

        if _contains(text, "volume up"):
            suggestions.append("👍 **Thumb Up** — default: Volume Up (↑ arrow).")

        if _contains(text, "volume down"):
            suggestions.append("👎 **Thumb Down** — default: Volume Down (↓ arrow).")

        if _contains(text, "mute"):
            suggestions.append("🤙 **Shaka** — default: Mute (M key). Thumb + pinky extended.")

        if _contains(text, "fullscreen"):
            suggestions.append(
                "👌 **OK Sign** — in non-mouse mode you can map it to F (fullscreen).\n"
                "   Or use ✊ **Fist** → Spacebar → then remap OK sign to F."
            )

        if _contains(text, "scroll"):
            suggestions.append(
                "In **Air Mouse mode**:\n"
                "• 🤟 **Three Fingers** — move hand up/down to scroll\n"
                "• 👍 **Thumb Up** — scroll up\n"
                "• 👎 **Thumb Down** — scroll down"
            )

        if _contains(text, "open youtube", "open google", "open site", "open website", "open url"):
            suggestions.append(
                "You can map any gesture to open a website!\n"
                "Go to **✋ Gestures** → pick a gesture → choose **🔗 Custom URL…** "
                "and type your URL."
            )

        if _contains(text, "type text", "auto type", "type message"):
            suggestions.append(
                "Use the **⌨ Auto-Type Text…** action on any gesture.\n"
                "Go to **✋ Gestures** → pick a gesture → choose **⌨ Auto-Type Text…** "
                "and enter the text you want typed."
            )

        if _contains(text, "hotkey", "keyboard shortcut", "ctrl", "alt", "shift"):
            suggestions.append(
                "For hotkeys like Ctrl+Z or Alt+Tab:\n"
                "Go to **✋ Gestures** → pick a gesture → choose **⌘ Custom Key / Hotkey…** "
                "and type e.g. `ctrl+z` or `alt+tab`."
            )

        if not suggestions:
            return self._fallback(text)

        return "💡 **Suggestions for your task:**\n\n" + "\n\n".join(suggestions) + "\n\n" + HOW_TO_MAP

    def _fallback(self, text: str) -> str:
        return (
            "🤔 I'm not sure about that one. Here's what I can help with:\n\n"
            "• Type **'list gestures'** for a full gesture reference\n"
            "• Type **'air mouse'** to learn about mouse mode\n"
            "• Type **'how to map'** to configure gesture actions\n"
            "• Type **'gestures firing accidentally'** for troubleshooting\n"
            "• Ask something like **'what gesture for next slide?'**"
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Gemini LLM Assistant (Feature 4)
# ─────────────────────────────────────────────────────────────────────────────

# Try to import Gemini SDK
try:
    import google.generativeai as genai
    _GEMINI_SDK_AVAILABLE = True
except ImportError:
    _GEMINI_SDK_AVAILABLE = False

_GEMINI_SYSTEM_PROMPT = """
You are the GestureSense AI Assistant — a friendly, concise expert on the
GestureSense hand gesture control system.

GestureSense lets users control their computer with webcam hand gestures.
You know every gesture it supports:
  • Fist (✊) — Play/Pause (space)
  • Open Palm (🞖) — Skip forward
  • Index (☝) — Move cursor (Air Mouse)
  • Peace (✌) — Right-click (Air Mouse)
  • Three Fingers (🤟) — Scroll (Air Mouse)
  • Thumb Up (👍) — Volume Up
  • Thumb Down (👎) — Volume Down
  • Pinch (🤏) — Left-click (Air Mouse)
  • OK Sign (👌) — Double-click (Air Mouse)
  • Shaka (🤙) — Mute toggle
  • Rock On (🤘) — Next (Right Arrow)

Always respond in a concise, helpful, friendly tone.
Use markdown-style **bold** for key terms.
Keep responses under 200 words unless a detailed explanation is requested.
If asked about something unrelated to GestureSense, gently redirect.
""".strip()


class GeminiAssistant(AIAssistant):
    """
    Gemini-powered AI assistant.
    Uses the rule-based logic as a system-context fallback.
    """

    def __init__(self, api_key: str):
        super().__init__()
        self._api_key  = api_key
        self._model    = None
        self._chat     = None
        self._gemini_ok = False
        self._init_gemini()

    def _init_gemini(self) -> None:
        try:
            genai.configure(api_key=self._api_key)
            self._model    = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=_GEMINI_SYSTEM_PROMPT,
            )
            self._chat     = self._model.start_chat(history=[])
            self._gemini_ok = True
            print("[AIAssistant] ✅ Gemini 1.5 Flash connected")
        except Exception as e:
            print(f"[AIAssistant] Gemini init failed: {e} — using rule-based")
            self._gemini_ok = False

    def chat(self, user_message: str) -> str:
        if not self._gemini_ok:
            return super().chat(user_message)   # fall back to rule-based

        try:
            response = self._chat.send_message(user_message)
            text = response.text.strip()
            # Store in base history too
            self._history.append((user_message, text))
            if len(self._history) > self.MAX_HISTORY:
                self._history = self._history[-self.MAX_HISTORY:]
            return text
        except Exception as e:
            print(f"[AIAssistant] Gemini error: {e} — falling back")
            self._gemini_ok = False
            return super().chat(user_message)

    def clear_history(self) -> None:
        super().clear_history()
        # Reset Gemini chat session
        if self._model and self._gemini_ok:
            self._chat = self._model.start_chat(history=[])

    @property
    def mode(self) -> str:
        return "gemini" if self._gemini_ok else "local"


# ─────────────────────────────────────────────────────────────────────────────
#  Factory
# ─────────────────────────────────────────────────────────────────────────────

def get_assistant() -> AIAssistant:
    """
    Returns a GeminiAssistant if GEMINI_API_KEY is set and SDK is installed,
    otherwise returns the local rule-based AIAssistant.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key and _GEMINI_SDK_AVAILABLE:
        return GeminiAssistant(api_key)
    return AIAssistant()


def get_assistant_with_key(api_key: str) -> AIAssistant:
    """Create an assistant with an explicit API key (e.g., from Settings UI)."""
    if api_key and _GEMINI_SDK_AVAILABLE:
        return GeminiAssistant(api_key)
    return AIAssistant()

"""
core/executor.py
================
Action executor: keyboard key presses, hotkeys, text typing, URL opening.
Single clean implementation — no more duplication.
"""

import time
import webbrowser
from pynput.keyboard import Key, Controller

keyboard = Controller()

SPECIAL_KEYS: dict = {
    "space":     Key.space,
    "right":     Key.right,
    "left":      Key.left,
    "up":        Key.up,
    "down":      Key.down,
    "enter":     Key.enter,
    "esc":       Key.esc,
    "tab":       Key.tab,
    "backspace": Key.backspace,
    "f1":        Key.f1,
    "f2":        Key.f2,
    "f3":        Key.f3,
    "f4":        Key.f4,
    "f5":        Key.f5,
    "f6":        Key.f6,
    "f7":        Key.f7,
    "f8":        Key.f8,
    "f9":        Key.f9,
    "f10":       Key.f10,
    "f11":       Key.f11,
    "f12":       Key.f12,
}


def execute(key_str: str, key_type: str) -> None:
    """
    Execute the action mapped to a gesture.

    key_type values
    ---------------
    "special"  – named key (space, right, f5 …)
    "char"     – single printable character
    "hotkey"   – modifier combo e.g. "ctrl+s"
    "type"     – auto-type a string verbatim
    "url"      – open URL in default browser
    "none"     – do nothing
    """
    if not key_str or key_type == "none":
        return

    try:
        time.sleep(0.05)  # small delay to avoid missed presses

        if key_type == "special":
            k = SPECIAL_KEYS.get(key_str.lower())
            if k:
                keyboard.press(k)
                keyboard.release(k)

        elif key_type == "char":
            keyboard.press(key_str[0])
            keyboard.release(key_str[0])

        elif key_type == "type":
            keyboard.type(key_str)

        elif key_type == "url":
            url = key_str.strip()
            if not url.startswith(("http://", "https://", "file://")):
                url = "https://" + url
            webbrowser.open(url)

        elif key_type == "hotkey":
            parts = key_str.lower().split("+")
            mods  = [SPECIAL_KEYS.get(p, p) for p in parts[:-1]]
            char  = parts[-1]
            for mod in mods:
                keyboard.press(mod)
            keyboard.press(char)
            keyboard.release(char)
            for mod in reversed(mods):
                keyboard.release(mod)

    except Exception as exc:
        print(f"[executor] Error executing '{key_str}' ({key_type}): {exc}")

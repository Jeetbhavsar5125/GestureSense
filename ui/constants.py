"""
ui/constants.py
===============
Shared constants for key/action options used across gesture cards and
the add-gesture panel. Define once, import everywhere.

KEY_OPTIONS entry format:
    (display_label, key_value, key_type, needs_custom_input)

  needs_custom_input = True  →  show a QLineEdit for the user's value
  needs_custom_input = False →  use key_value directly
"""

# ── Quick-launch site definitions ─────────────────────────────────────────────
QUICK_SITES = [
    ("🎬", "YouTube",      "https://youtube.com"),
    ("🔍", "Google",       "https://google.com"),
    ("🎥", "Netflix",      "https://netflix.com"),
    ("🎵", "Spotify",      "https://open.spotify.com"),
    ("💻", "GitHub",       "https://github.com"),
    ("💬", "WhatsApp",     "https://web.whatsapp.com"),
    ("📧", "Gmail",        "https://mail.google.com"),
    ("📹", "Google Meet",  "https://meet.google.com"),
    ("🐦", "X / Twitter",  "https://x.com"),
    ("📘", "Facebook",     "https://facebook.com"),
    ("📸", "Instagram",    "https://instagram.com"),
    ("🎮", "Steam",        "https://store.steampowered.com"),
]

# ── All key action options ─────────────────────────────────────────────────────
KEY_OPTIONS = [
    # (label, key_value, key_type, needs_input)
    ("—  No Action",                  "",                              "none",    False),

    # Media Controls
    ("▶  Play / Pause",               "space",                         "special", False),
    ("⏩  Skip Forward  (+5 s)",       "right",                         "special", False),
    ("⏪  Skip Backward  (−5 s)",      "left",                          "special", False),
    ("🔊  Volume Up",                  "up",                            "special", False),
    ("🔉  Volume Down",                "down",                          "special", False),
    ("🔇  Mute / Unmute  (M)",         "m",                             "char",    False),
    ("📺  Fullscreen  (F)",            "f",                             "char",    False),
    ("🎭  Theater Mode  (T)",          "t",                             "char",    False),
    ("⏯  Alt Play/Pause  (K)",        "k",                             "char",    False),
    ("⏭  Next Track  (N)",            "n",                             "char",    False),
    ("➡  Next Slide / Right Arrow",   "right",                         "special", False),
    ("⬅  Prev Slide / Left Arrow",    "left",                          "special", False),


    # Quick-Launch Sites
    ("🎬  Open YouTube",               "https://youtube.com",           "url",     False),
    ("🔍  Open Google",                "https://google.com",            "url",     False),
    ("🎥  Open Netflix",               "https://netflix.com",           "url",     False),
    ("🎵  Open Spotify",               "https://open.spotify.com",      "url",     False),
    ("💻  Open GitHub",                "https://github.com",            "url",     False),
    ("💬  Open WhatsApp Web",          "https://web.whatsapp.com",      "url",     False),
    ("📧  Open Gmail",                 "https://mail.google.com",       "url",     False),
    ("📹  Open Google Meet",           "https://meet.google.com",       "url",     False),
    ("🐦  Open X / Twitter",           "https://x.com",                 "url",     False),
    ("📘  Open Facebook",              "https://facebook.com",          "url",     False),
    ("📸  Open Instagram",             "https://instagram.com",         "url",     False),
    ("🎮  Open Steam",                 "https://store.steampowered.com","url",     False),

    # System Keys
    ("↩  Enter",                       "enter",                         "special", False),
    ("✖  Escape",                      "esc",                           "special", False),
    ("⇥  Tab",                         "tab",                           "special", False),
    ("⌫  Backspace",                   "backspace",                     "special", False),
    ("🔄  Refresh  (F5)",              "f5",                            "special", False),
    ("⛶  Toggle Fullscreen  (F11)",   "f11",                           "special", False),

    # Custom inputs
    ("🔗  Custom URL…",                "__url__",                       "url",     True ),
    ("⌨  Auto-Type Text…",            "__type__",                      "type",    True ),
    ("⌘  Custom Key / Hotkey…",        "__key__",                       "char",    True ),
]


def find_option_index(key: str, key_type: str):
    """
    Return (combo_index, custom_value) for a given key+key_type.
    Falls back to the appropriate "Custom …" entry if not found.
    """
    if not key or key_type == "none":
        return 0, ""

    for idx, (_, kv, kt, _) in enumerate(KEY_OPTIONS):
        if kv == key and kt == key_type:
            return idx, ""

    # Not in predefined list → route to custom entry
    if key_type == "url":
        sentinel = "__url__"
    elif key_type == "type":
        sentinel = "__type__"
    else:
        sentinel = "__key__"

    for idx, (_, kv, _, _) in enumerate(KEY_OPTIONS):
        if kv == sentinel:
            return idx, key

    return 0, ""

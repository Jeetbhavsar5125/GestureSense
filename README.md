# GestureSense v3

Control your computer with hand gestures using your webcam.

## Project Structure

```
GestureSense/
├── core/                   ← Shared gesture detection + action engine
│   ├── detector.py         ← Finger state detection & gesture classification
│   └── executor.py         ← Keyboard, hotkey & URL action executor
├── config/                 ← Configuration management
│   ├── manager.py          ← Load/save/cache gestures_config.json
│   └── gestures_config.json
├── desktop/                ← PyQt6 Desktop Application
│   └── app.py
├── web/                    ← FastAPI Backend + HTML Dashboard
│   ├── server.py
│   └── frontend.html
├── assets/
│   └── logo.ico
├── main.py                 ← Unified entry point
├── START_GESTURESENSE.bat  ← Launch desktop app
├── START_WEB_DASHBOARD.bat ← Launch web server only
└── requirements.txt
```

## Installation

```bash
pip install -r requirements.txt
```

## Running

**Desktop App (+ background web server):**
```bash
python main.py
# or double-click START_GESTURESENSE.bat
```

**Web Dashboard only:**
```bash
python main.py --web
# or double-click START_WEB_DASHBOARD.bat
# then open http://127.0.0.1:8000 in your browser
```

## Gestures

| Gesture | Action |
|---------|--------|
| ✊ Fist | Play / Pause |
| ✌️ Peace | Skip +10s |
| 🤟 Three Fingers | Skip -10s |
| 🖐️ Open Palm | Skip +5s |
| 👍 Thumb Up | Volume Up |
| 👎 Thumb Down | Volume Down |
| 🤏 Pinch | Mute Toggle |
| 👌 OK Sign | Fullscreen |
| 🤙 Shaka | Theater Mode |
| ☝️ Index Only | Move Cursor |

Custom gestures (including URL launchers) can be added via the desktop app's **"+ Add New"** tab.

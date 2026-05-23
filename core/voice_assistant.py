"""
core/voice_assistant.py
=======================
GestureSense — Voice Command Thread (Feature 5)
Member 2 Responsibility: Voice + Gesture Combo

Runs a background QThread that listens for voice commands via the
microphone and maps spoken phrases to the same actions that gesture
mappings trigger (using core/executor.py).

Requirements:
    pip install SpeechRecognition pyaudio

Usage:
    from core.voice_assistant import VoiceThread
    vt = VoiceThread(get_mapping_fn=..., on_command_fn=...)
    vt.start()
    vt.stop()

Recognized commands (extensible):
    "pause" / "play"        → space
    "next"                  → right arrow
    "previous" / "back"     → left arrow
    "volume up"             → up arrow
    "volume down"           → down arrow
    "mute"                  → m
    "fullscreen"            → f
    "open youtube"          → opens youtube.com
    "open google"           → opens google.com
    "air mouse on/off"      → toggle air mouse (callback)
    "stop listening"        → pauses voice thread
"""

import threading
import time

from PyQt6.QtCore import QThread, pyqtSignal

# Optional SpeechRecognition import
try:
    import speech_recognition as sr
    _SR_AVAILABLE = True
except ImportError:
    _SR_AVAILABLE = False


# ── Command → Action mapping ──────────────────────────────────────────────────

VOICE_COMMANDS = {
    # Playback
    "pause":         ("space",       "special"),
    "play":          ("space",       "special"),
    "play pause":    ("space",       "special"),
    "stop":          ("space",       "special"),
    # Navigation
    "next":          ("right",       "special"),
    "forward":       ("right",       "special"),
    "previous":      ("left",        "special"),
    "back":          ("left",        "special"),
    "go back":       ("left",        "special"),
    # Volume
    "volume up":     ("up",          "special"),
    "louder":        ("up",          "special"),
    "volume down":   ("down",        "special"),
    "quieter":       ("down",        "special"),
    # Controls
    "mute":          ("m",           "char"),
    "fullscreen":    ("f",           "char"),
    "escape":        ("esc",         "special"),
    # URLs
    "open youtube":  ("youtube.com", "url"),
    "open google":   ("google.com",  "url"),
    "open github":   ("github.com",  "url"),
}


def _match_command(transcript: str) -> tuple:
    """
    Match a transcript to a known voice command.
    Returns (key, key_type) or (None, None) if no match.
    """
    t = transcript.lower().strip()
    # Exact and substring matching
    for phrase, action in sorted(VOICE_COMMANDS.items(), key=lambda x: -len(x[0])):
        if phrase in t:
            return action
    return None, None


# ── Voice Thread ──────────────────────────────────────────────────────────────

class VoiceThread(QThread):
    """
    Signals
    -------
    command_detected(str phrase, str key, str key_type)
        Emitted when a voice command is recognized and executed.
    status_changed(str status)
        Emitted with status updates: 'listening', 'processing', 'idle', 'error'.
    error_occurred(str message)
        Emitted on unrecoverable error (e.g., no microphone).
    """

    command_detected = pyqtSignal(str, str, str)   # phrase, key, key_type
    status_changed   = pyqtSignal(str)              # listening / processing / idle
    error_occurred   = pyqtSignal(str)

    def __init__(self, on_toggle_mouse=None, parent=None):
        super().__init__(parent)
        self._running          = False
        self._paused           = False
        self._on_toggle_mouse  = on_toggle_mouse  # callable(bool) for air mouse toggle
        self._recognizer       = None
        self._microphone       = None
        self._mic_device_index = None

    # ── Configuration ─────────────────────────────────────────────────────────

    def set_mic_device(self, index: int) -> None:
        """Set microphone device index (None = system default)."""
        self._mic_device_index = index if index >= 0 else None

    def pause(self) -> None:
        self._paused = True
        self.status_changed.emit("idle")

    def resume(self) -> None:
        self._paused = False

    def stop(self) -> None:
        self._running = False
        self.wait(3000)

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        if not _SR_AVAILABLE:
            self.error_occurred.emit(
                "SpeechRecognition not installed.\n"
                "Run: pip install SpeechRecognition pyaudio"
            )
            return

        try:
            self._recognizer = sr.Recognizer()
            self._recognizer.pause_threshold  = 0.6   # shorter silence = faster response
            self._recognizer.energy_threshold = 300

            mic_kwargs = {}
            if self._mic_device_index is not None:
                mic_kwargs["device_index"] = self._mic_device_index

            self._microphone = sr.Microphone(**mic_kwargs)
        except Exception as e:
            self.error_occurred.emit(f"Microphone error: {e}")
            return

        self._running = True
        print("[VoiceThread] Started — listening for voice commands")

        with self._microphone as source:
            # Calibrate for ambient noise
            self.status_changed.emit("idle")
            self._recognizer.adjust_for_ambient_noise(source, duration=1.5)
            print("[VoiceThread] Ambient noise calibrated")

            while self._running:
                if self._paused:
                    time.sleep(0.5)
                    continue

                try:
                    self.status_changed.emit("listening")
                    audio = self._recognizer.listen(source, timeout=5, phrase_time_limit=5)
                    self.status_changed.emit("processing")

                    transcript = self._recognizer.recognize_google(audio).lower()
                    print(f"[VoiceThread] Heard: '{transcript}'")

                    # Special: air mouse toggle
                    if "air mouse" in transcript:
                        if self._on_toggle_mouse:
                            enable = "on" in transcript
                            self._on_toggle_mouse(enable)
                            self.command_detected.emit(transcript, "air_mouse", "toggle")
                        self.status_changed.emit("listening")
                        continue

                    # Special: stop listening
                    if "stop listening" in transcript or "voice off" in transcript:
                        self.pause()
                        self.command_detected.emit(transcript, "", "none")
                        continue

                    key, key_type = _match_command(transcript)
                    if key:
                        from core.executor import execute
                        threading.Thread(
                            target=execute,
                            args=(key, key_type),
                            daemon=True,
                        ).start()
                        self.command_detected.emit(transcript, key, key_type)
                    else:
                        print(f"[VoiceThread] No command matched for: '{transcript}'")

                except sr.WaitTimeoutError:
                    self.status_changed.emit("listening")   # normal — just no speech
                except sr.UnknownValueError:
                    self.status_changed.emit("listening")   # couldn't understand
                except sr.RequestError as e:
                    print(f"[VoiceThread] API error: {e}")
                    self.status_changed.emit("error")
                    time.sleep(2)
                except Exception as e:
                    print(f"[VoiceThread] Unexpected error: {e}")
                    time.sleep(1)

        print("[VoiceThread] Stopped")


# ── Microphone utilities ──────────────────────────────────────────────────────

def list_microphones() -> list[tuple[int, str]]:
    """Return list of (index, name) for all available microphones."""
    if not _SR_AVAILABLE:
        return []
    try:
        return [(i, name) for i, name in enumerate(sr.Microphone.list_microphone_names())]
    except Exception:
        return []

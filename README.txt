============================
  GESTURE SENSE v2.0
  Hand Gesture Controller
============================

REQUIREMENTS:
  - Windows 10 / 11
  - Python 3.11
  - Webcam

------------------------------
STEP 1 - Install libraries (run once):

  pip install -r requirements.txt

------------------------------
OPTION A - Desktop App (Recommended):

  python gesture_sense_app.py

  Then click the START button inside the app.
  Show your hand to the webcam and gesture!

------------------------------
OPTION B - Web Dashboard:

  1. Open terminal and run:
       uvicorn backend:app --port 8000

  2. Open frontend.html in Chrome

  3. Click CONNECT button

------------------------------
GESTURE CONTROLS:

  Fist          -> Play / Pause
  2 Fingers     -> Skip +10 seconds
  3 Fingers     -> Skip -10 seconds
  Open Palm     -> Skip +5 seconds
  Thumb Up      -> Volume Up
  Thumb Down    -> Volume Down
  Pinch         -> Mute Toggle
  OK Sign       -> Fullscreen
  Shaka         -> Theater Mode
  Index Finger  -> Move Cursor

------------------------------
PROJECT FILES:

  gesture_sense_app.py  <- Desktop App (main)
  backend.py            <- Web Backend Server
  frontend.html         <- Web Dashboard
  requirements.txt      <- Python libraries

============================
  Made with MediaPipe + PyQt6
============================

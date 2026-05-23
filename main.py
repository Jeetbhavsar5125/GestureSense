"""
main.py
=======
GestureSense entry point.
Run: python main.py
"""

import sys
import os

# Ensure project root is on sys.path so sub-packages resolve correctly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore    import Qt
from ui.app import GestureSenseApp


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("GestureSense")
    app.setApplicationVersion("2.0")
    app.setQuitOnLastWindowClosed(False)   # Keep alive in system tray

    window = GestureSenseApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

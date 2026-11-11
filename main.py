#!/usr/bin/env python3
"""ROV Telemetry Ground Station - entry point."""
import sys

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow
from gui.style import QSS


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("ROV Telemetry Ground Station")
    app.setStyleSheet(QSS)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

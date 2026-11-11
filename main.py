#!/usr/bin/env python3
"""ROV Telemetry Ground Station - entry point."""
import argparse
import os
import sys

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow
from gui.style import QSS
from gui.location import parse_origin_arg


def main() -> int:
    ap = argparse.ArgumentParser(description="ROV Telemetry Ground Station")
    ap.add_argument("--origin", metavar="LAT,LON", default=os.environ.get("ROV_ORIGIN"),
                    help="launch origin override (skips GPS/IP lookup), e.g. 28.6654,77.4391")
    args, qt_args = ap.parse_known_args()
    origin = parse_origin_arg(args.origin)
    if args.origin and origin is None:
        ap.error(f"--origin must be LAT,LON within range, got {args.origin!r}")

    app = QApplication([sys.argv[0]] + qt_args)
    app.setApplicationName("ROV Telemetry Ground Station")
    app.setStyleSheet(QSS)
    win = MainWindow(origin=origin)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

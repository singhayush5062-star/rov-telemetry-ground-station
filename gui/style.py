"""Dark dashboard stylesheet."""
QSS = """
QMainWindow, QWidget { background: #1b1f27; color: #e6e9ef; font-size: 13px; }
QGroupBox { border: 1px solid #343a46; border-radius: 6px; margin-top: 14px; padding: 8px 6px 6px 6px;
            font-weight: bold; color: #9fb3c8; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QLabel#telemName  { color: #9fb3c8; font-size: 14px; }
QLabel#telemValue { font-family: "DejaVu Sans Mono", monospace; font-size: 22px; font-weight: bold; }
QLabel#mode       { font-size: 18px; font-weight: bold; color: #7fc8ff; }
QLabel#armed      { font-size: 20px; font-weight: bold; color: #ff5c5c; }
QLabel#armed[armed="true"] { color: #39d353; }
QLabel#telemValue[low="true"] { color: #ffb347; }
QLabel#helpText   { color: #7d8797; font-size: 11px; }
QLabel#placeholder{ border: 1px dashed #343a46; border-radius: 6px; color: #5c6675; }
QPushButton { background: #2a3140; border: 1px solid #3e4756; border-radius: 5px; padding: 6px 12px; }
QPushButton:hover { background: #343d4f; }
QPushButton:disabled { color: #5c6675; background: #222835; }
QPushButton#armBtn    { background: #1f6f3a; font-weight: bold; font-size: 15px; }
QPushButton#armBtn:disabled { background: #1a2b22; color: #4f6b58; }
QPushButton#disarmBtn { background: #8a2b2b; font-weight: bold; font-size: 15px; }
QPushButton#disarmBtn:disabled { background: #2b1f1f; color: #6b4f4f; }
QComboBox, QDoubleSpinBox { background: #121620; border: 1px solid #3e4756; border-radius: 4px; padding: 4px; }
QComboBox QAbstractItemView { background: #121620; selection-background-color: #2a3140; }
QStatusBar { background: #121620; color: #9fb3c8; font-family: monospace; }
"""

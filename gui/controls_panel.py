"""Operator controls: Arm/Disarm, mode selection, target depth / heading."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton,
                               QComboBox, QDoubleSpinBox, QLabel, QFormLayout, QCheckBox)

from rov_sim.safety import Mode


class ControlsPanel(QGroupBox):
    arm_requested = Signal()
    disarm_requested = Signal()
    reset_requested = Signal()
    mode_changed = Signal(object)          # Mode
    target_depth_set = Signal(float)
    target_heading_set = Signal(float)
    log_toggled = Signal(bool)
    current_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__("Controls", parent)
        lay = QVBoxLayout(self)

        # Arm / Disarm
        row = QHBoxLayout()
        self.arm_btn = QPushButton("ARM")
        self.arm_btn.setObjectName("armBtn")
        self.disarm_btn = QPushButton("DISARM")
        self.disarm_btn.setObjectName("disarmBtn")
        self.disarm_btn.setEnabled(False)
        for b in (self.arm_btn, self.disarm_btn):
            b.setMinimumHeight(40)
            b.setFocusPolicy(Qt.NoFocus)
            row.addWidget(b)
        lay.addLayout(row)

        self.reset_btn = QPushButton("RESET SIMULATION")
        self.reset_btn.setObjectName("resetBtn")
        self.reset_btn.setFocusPolicy(Qt.NoFocus)
        self.reset_btn.setToolTip("Disarm, return the vehicle to the launch point, full battery, clear plot and trail")
        lay.addWidget(self.reset_btn)

        # Mode
        form = QFormLayout()
        self.mode_combo = QComboBox()
        for m in Mode:
            self.mode_combo.addItem(m.value, m)
        self.mode_combo.setFocusPolicy(Qt.NoFocus)
        form.addRow("Mode", self.mode_combo)

        # Targets
        self.depth_spin = QDoubleSpinBox()
        self.depth_spin.setRange(0.0, 100.0); self.depth_spin.setDecimals(1)
        self.depth_spin.setSingleStep(0.5); self.depth_spin.setSuffix(" m")
        self.depth_apply = QPushButton("Set")
        self.depth_apply.setFocusPolicy(Qt.NoFocus)
        form.addRow("Target depth", self._with_button(self.depth_spin, self.depth_apply))

        self.heading_spin = QDoubleSpinBox()
        self.heading_spin.setRange(0.0, 359.9); self.heading_spin.setDecimals(1)
        self.heading_spin.setSingleStep(5.0); self.heading_spin.setSuffix(" °")
        self.heading_spin.setWrapping(True)
        self.heading_apply = QPushButton("Set")
        self.heading_apply.setFocusPolicy(Qt.NoFocus)
        form.addRow("Target heading", self._with_button(self.heading_spin, self.heading_apply))
        lay.addLayout(form)

        # Extras: CSV logging, simulated current, joystick status
        extras = QFormLayout()
        self.log_btn = QPushButton("Start CSV log")
        self.log_btn.setCheckable(True); self.log_btn.setFocusPolicy(Qt.NoFocus)
        extras.addRow("Logging", self.log_btn)
        self.current_chk = QCheckBox("Simulated water current")
        self.current_chk.setFocusPolicy(Qt.NoFocus)
        extras.addRow("Environment", self.current_chk)
        self.joy_lbl = QLabel("none detected (keyboard active)")
        self.joy_lbl.setObjectName("helpText")
        extras.addRow("Joystick", self.joy_lbl)
        lay.addLayout(extras)

        help_lbl = QLabel(
            "Keyboard (Manual):  \u2191 rise / \u2193 dive (or R / F)   \u2190 \u2192 turn (or Q / E)   "
            "W / S forward / back (or PgUp / PgDn)   A / D sway left / right.  Space = emergency disarm.\n"
            "Gamepad: left stick forward/sway, right stick turn/dive, A = arm, B = disarm."
        )
        help_lbl.setObjectName("helpText")
        help_lbl.setWordWrap(True)
        lay.addWidget(help_lbl)
        lay.addStretch(1)

        # Wiring
        self.arm_btn.clicked.connect(self.arm_requested)
        self.disarm_btn.clicked.connect(self.disarm_requested)
        self.reset_btn.clicked.connect(self.reset_requested)
        self.mode_combo.currentIndexChanged.connect(
            lambda i: self.mode_changed.emit(self.mode_combo.itemData(i)))
        self.depth_apply.clicked.connect(self._apply_depth)
        self.heading_apply.clicked.connect(self._apply_heading)
        self.depth_spin.editingFinished.connect(self._apply_depth)
        self.heading_spin.editingFinished.connect(self._apply_heading)
        self.log_btn.toggled.connect(self._on_log_toggled)
        self.current_chk.toggled.connect(self.current_toggled)
        self._sync_target_enabled(Mode.MANUAL)
        self.mode_changed.connect(self._sync_target_enabled)

    def _on_log_toggled(self, on: bool) -> None:
        self.log_btn.setText("Stop CSV log" if on else "Start CSV log")
        self.log_toggled.emit(on)

    def set_joystick_name(self, name: str) -> None:
        self.joy_lbl.setText(name if name else "none detected (keyboard active)")

    @staticmethod
    def _with_button(spin, btn):
        from PySide6.QtWidgets import QWidget
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(spin, 1); h.addWidget(btn)
        return w

    def _apply_depth(self) -> None:
        self.target_depth_set.emit(self.depth_spin.value())
        self.depth_spin.clearFocus()        # hand keyboard control back to the dashboard

    def _apply_heading(self) -> None:
        self.target_heading_set.emit(self.heading_spin.value())
        self.heading_spin.clearFocus()

    def _sync_target_enabled(self, mode: Mode) -> None:
        self.depth_spin.setEnabled(mode is Mode.DEPTH_HOLD)
        self.depth_apply.setEnabled(mode is Mode.DEPTH_HOLD)
        self.heading_spin.setEnabled(mode is Mode.HEADING_HOLD)
        self.heading_apply.setEnabled(mode is Mode.HEADING_HOLD)

    def set_armed(self, armed: bool) -> None:
        self.arm_btn.setEnabled(not armed)
        self.disarm_btn.setEnabled(armed)

    def current_mode(self) -> Mode:
        return self.mode_combo.currentData()

    def set_mode(self, mode: Mode) -> None:
        self.mode_combo.setCurrentIndex(self.mode_combo.findData(mode))

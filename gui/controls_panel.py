"""Operator controls: Arm/Disarm, mode selection, target depth / heading."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton,
                               QComboBox, QDoubleSpinBox, QLabel, QFormLayout)

from rov_sim.safety import Mode


class ControlsPanel(QGroupBox):
    arm_requested = Signal()
    disarm_requested = Signal()
    mode_changed = Signal(object)          # Mode
    target_depth_set = Signal(float)
    target_heading_set = Signal(float)

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

        help_lbl = QLabel(
            "Keyboard (Manual):  W/S surge   A/D sway   Q/E yaw   R/F heave\n"
            "Space = emergency disarm.  Click the dashboard to give it key focus."
        )
        help_lbl.setObjectName("helpText")
        help_lbl.setWordWrap(True)
        lay.addWidget(help_lbl)
        lay.addStretch(1)

        # Wiring
        self.arm_btn.clicked.connect(self.arm_requested)
        self.disarm_btn.clicked.connect(self.disarm_requested)
        self.mode_combo.currentIndexChanged.connect(
            lambda i: self.mode_changed.emit(self.mode_combo.itemData(i)))
        self.depth_apply.clicked.connect(lambda: self.target_depth_set.emit(self.depth_spin.value()))
        self.heading_apply.clicked.connect(lambda: self.target_heading_set.emit(self.heading_spin.value()))
        self.depth_spin.editingFinished.connect(lambda: self.target_depth_set.emit(self.depth_spin.value()))
        self.heading_spin.editingFinished.connect(lambda: self.target_heading_set.emit(self.heading_spin.value()))
        self._sync_target_enabled(Mode.MANUAL)
        self.mode_changed.connect(self._sync_target_enabled)

    @staticmethod
    def _with_button(spin, btn):
        from PySide6.QtWidgets import QWidget
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(spin, 1); h.addWidget(btn)
        return w

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

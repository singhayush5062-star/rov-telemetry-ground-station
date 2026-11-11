"""Live telemetry read-outs: armed state, mode, roll, pitch, yaw, depth, battery."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QGridLayout, QLabel

from rov_sim.safety import ArmState, Mode
from rov_sim.simulator import ROVState


class TelemetryPanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Telemetry", parent)
        grid = QGridLayout(self)
        grid.setVerticalSpacing(6)

        self.armed_lbl = self._value("DISARMED", "armed")
        self.mode_lbl = self._value("Manual", "mode")
        self.roll_lbl = self._value("0.0°")
        self.pitch_lbl = self._value("0.0°")
        self.yaw_lbl = self._value("0.0°")
        self.depth_lbl = self._value("0.00 m")
        self.batt_lbl = self._value("16.80 V")

        rows = [
            ("Armed", self.armed_lbl), ("Mode", self.mode_lbl),
            ("Roll", self.roll_lbl), ("Pitch", self.pitch_lbl), ("Yaw", self.yaw_lbl),
            ("Depth", self.depth_lbl), ("Battery", self.batt_lbl),
        ]
        for r, (name, lbl) in enumerate(rows):
            n = QLabel(name)
            n.setObjectName("telemName")
            grid.addWidget(n, r, 0, Qt.AlignLeft | Qt.AlignVCenter)
            grid.addWidget(lbl, r, 1, Qt.AlignRight | Qt.AlignVCenter)
        grid.setColumnStretch(1, 1)

    @staticmethod
    def _value(text: str, obj_name: str = "telemValue") -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName(obj_name)
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return lbl

    def update_values(self, s: ROVState, armed: ArmState, mode: Mode) -> None:
        self.armed_lbl.setText(armed.value)
        self.armed_lbl.setProperty("armed", armed is ArmState.ARMED)
        self.armed_lbl.style().unpolish(self.armed_lbl)
        self.armed_lbl.style().polish(self.armed_lbl)
        self.mode_lbl.setText(mode.value)
        self.roll_lbl.setText(f"{s.roll:+.1f}°")
        self.pitch_lbl.setText(f"{s.pitch:+.1f}°")
        self.yaw_lbl.setText(f"{s.yaw:.1f}°")
        self.depth_lbl.setText(f"{s.depth:.2f} m")
        self.batt_lbl.setText(f"{s.battery_v:.2f} V")
        low = s.battery_v < 14.0
        if self.batt_lbl.property("low") != low:
            self.batt_lbl.setProperty("low", low)
            self.batt_lbl.style().unpolish(self.batt_lbl)
            self.batt_lbl.style().polish(self.batt_lbl)

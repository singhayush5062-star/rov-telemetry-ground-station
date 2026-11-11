"""
Main dashboard window.

Owns the simulation loop:
    operator input (keys/joystick) -> hold controller -> safety gate -> simulator
Runs at SIM_HZ on the GUI thread via QTimer (one step costs microseconds).
Widgets refresh on a slower UI_HZ timer so rendering never starves the sim.
"""
from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer, QEvent, Signal
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                               QLabel, QApplication, QLineEdit, QAbstractSpinBox,
                               QStatusBar)

from rov_sim.simulator import ROVSimulator, Command, ROVState
from rov_sim.safety import ArmState, Mode, InputWatchdog, apply_safety
from rov_sim.controllers import DepthHold, HeadingHold, build_command
from .telemetry_panel import TelemetryPanel
from .controls_panel import ControlsPanel

SIM_HZ = 50
UI_HZ = 20

KEY_MAP = {
    Qt.Key_W: ("surge", +1), Qt.Key_S: ("surge", -1),
    Qt.Key_D: ("sway", +1), Qt.Key_A: ("sway", -1),
    Qt.Key_E: ("yaw", +1), Qt.Key_Q: ("yaw", -1),
    Qt.Key_F: ("heave", +1), Qt.Key_R: ("heave", -1),
}


class MainWindow(QMainWindow):
    state_updated = Signal(object)   # ROVState, emitted at UI_HZ for plot/map/logger

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ROV Telemetry Ground Station")
        self.resize(1200, 720)

        # --- model
        self.sim = ROVSimulator()
        self.armed = ArmState.DISARMED
        self.mode = Mode.MANUAL
        self.watchdog = InputWatchdog()
        self.depth_hold = DepthHold()
        self.heading_hold = HeadingHold()
        self._keys: set[int] = set()
        self._joystick_cmd: Command | None = None   # set by joystick module later
        self._last_tick = time.monotonic()
        self._safe_cmd = Command.zero()

        # --- widgets
        central = QWidget(); self.setCentralWidget(central)
        root = QHBoxLayout(central)

        left = QVBoxLayout()
        self.telemetry = TelemetryPanel()
        self.controls = ControlsPanel()
        left.addWidget(self.telemetry)
        left.addWidget(self.controls, 1)
        left_w = QWidget(); left_w.setLayout(left); left_w.setFixedWidth(360)
        root.addWidget(left_w)

        self.right = QVBoxLayout()
        self.plot_placeholder = QLabel("Depth vs time plot (Phase 3)")
        self.map_placeholder = QLabel("OpenStreetMap view (Phase 3)")
        for ph in (self.plot_placeholder, self.map_placeholder):
            ph.setAlignment(Qt.AlignCenter); ph.setObjectName("placeholder")
            self.right.addWidget(ph, 1)
        root.addLayout(self.right, 1)

        self.status = QStatusBar(); self.setStatusBar(self.status)
        self.thrust_lbl = QLabel(); self.status.addPermanentWidget(self.thrust_lbl)

        # --- wiring
        self.controls.arm_requested.connect(self.arm)
        self.controls.disarm_requested.connect(self.disarm)
        self.controls.mode_changed.connect(self.set_mode)
        self.controls.target_depth_set.connect(self.depth_hold.set_target)
        self.controls.target_heading_set.connect(self.heading_hold.set_target)

        central.setFocusPolicy(Qt.StrongFocus)
        central.setFocus()
        QApplication.instance().installEventFilter(self)

        # --- timers
        self.sim_timer = QTimer(self); self.sim_timer.setTimerType(Qt.PreciseTimer)
        self.sim_timer.timeout.connect(self._tick); self.sim_timer.start(1000 // SIM_HZ)
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self._refresh_ui); self.ui_timer.start(1000 // UI_HZ)
        self._refresh_ui()

    # ------------------------------------------------------------ arm / mode
    def arm(self) -> None:
        self.armed = ArmState.ARMED
        self.controls.set_armed(True)
        self._reset_controllers()
        self.status.showMessage("ARMED", 2000)

    def disarm(self) -> None:
        self.armed = ArmState.DISARMED
        self.controls.set_armed(False)
        self._reset_controllers()
        self._safe_cmd = Command.zero()           # takes effect immediately, not next tick
        self.status.showMessage("DISARMED - thrust forced to zero", 2000)

    def set_mode(self, mode: Mode) -> None:
        if mode is self.mode:
            return
        self.mode = mode
        self._reset_controllers()
        s = self.sim.s
        if mode is Mode.DEPTH_HOLD:        # default target = current depth
            self.depth_hold.set_target(s.depth)
            self.controls.depth_spin.setValue(round(s.depth, 1))
        elif mode is Mode.HEADING_HOLD:    # default target = current heading
            self.heading_hold.set_target(s.yaw)
            self.controls.heading_spin.setValue(round(s.yaw, 1))
        self.status.showMessage(f"Mode: {mode.value}", 2000)

    def _reset_controllers(self) -> None:
        self.depth_hold.reset()
        self.heading_hold.reset()

    # ------------------------------------------------------------ input
    def eventFilter(self, obj, ev):
        et = ev.type()
        if et in (QEvent.KeyPress, QEvent.KeyRelease):
            fw = QApplication.focusWidget()
            if isinstance(fw, (QLineEdit, QAbstractSpinBox)):
                return False                      # let the user type numbers
            key = ev.key()
            if ev.isAutoRepeat():
                return key in KEY_MAP
            if et == QEvent.KeyPress:
                if key == Qt.Key_Space:
                    self.disarm(); return True
                if key in KEY_MAP:
                    self._keys.add(key); return True
            else:
                self._keys.discard(key)
                if key in KEY_MAP:
                    return True
        return super().eventFilter(obj, ev)

    def set_joystick_command(self, cmd: Command | None) -> None:
        """Called by the joystick poller; None means no device / no input."""
        self._joystick_cmd = cmd

    def _operator_command(self, now: float) -> Command:
        cmd = Command()
        for key in self._keys:
            axis, sign = KEY_MAP[key]
            setattr(cmd, axis, sign)
        if self._joystick_cmd is not None and not self._joystick_cmd.is_zero():
            cmd = self._joystick_cmd
        if not cmd.is_zero():
            self.watchdog.feed(now)
        return cmd

    # ------------------------------------------------------------ loop
    def _tick(self) -> None:
        now = time.monotonic()
        dt = min(now - self._last_tick, 0.1)      # guard against stalls
        self._last_tick = now

        op = self._operator_command(now)
        merged = build_command(op, self.mode, self.depth_hold, self.heading_hold, self.sim.s, dt)
        self._safe_cmd = apply_safety(merged, self.armed, self.mode, self.watchdog, now)
        self.sim.step(self._safe_cmd, dt)

    def _refresh_ui(self) -> None:
        s = self.sim.s
        self.telemetry.update_values(s, self.armed, self.mode)
        c = self._safe_cmd
        self.thrust_lbl.setText(
            f"thrust  surge {c.surge:+.2f}  sway {c.sway:+.2f}  heave {c.heave:+.2f}  yaw {c.yaw:+.2f}"
            f"   |   t = {s.t:6.1f} s")
        self.state_updated.emit(s)

    def closeEvent(self, ev):
        self.sim_timer.stop(); self.ui_timer.stop()
        QApplication.instance().removeEventFilter(self)
        super().closeEvent(ev)

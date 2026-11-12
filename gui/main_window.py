"""
Main dashboard window.

Owns the simulation loop:
    operator input (keys/joystick) -> hold controller -> safety gate -> simulator
Runs at SIM_HZ on the GUI thread via QTimer (one step costs microseconds).
Widgets refresh on a slower UI_HZ timer so rendering never starves the sim.
"""
from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer, Signal, QEvent
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                               QLabel, QStatusBar, QAbstractSpinBox, QLineEdit)

from rov_sim.simulator import ROVSimulator, Command, ROVState
from rov_sim.safety import ArmState, Mode, InputWatchdog, apply_safety
from rov_sim.controllers import DepthHold, HeadingHold, build_command
from .map_view import MapView
from .depth_plot import DepthPlot
from .telemetry_panel import TelemetryPanel
from .controls_panel import ControlsPanel
from .joystick import JoystickReader
from .location import LocationProvider
from logging_util.csv_logger import CsvLogger

SIM_HZ = 50
UI_HZ = 20

KEY_MAP = {
    # letters
    Qt.Key_W: ("surge", +1), Qt.Key_S: ("surge", -1),
    Qt.Key_D: ("sway", +1), Qt.Key_A: ("sway", -1),
    Qt.Key_E: ("yaw", +1), Qt.Key_Q: ("yaw", -1),
    Qt.Key_F: ("heave", +1), Qt.Key_R: ("heave", -1),
    # arrows: Up/Down surge, Left/Right turn, PageUp/PageDown rise/dive
    Qt.Key_Up: ("surge", +1), Qt.Key_Down: ("surge", -1),
    Qt.Key_Right: ("yaw", +1), Qt.Key_Left: ("yaw", -1),
    Qt.Key_PageDown: ("heave", +1), Qt.Key_PageUp: ("heave", -1),
}


class MainWindow(QMainWindow):
    state_updated = Signal(object)   # ROVState, emitted at UI_HZ for plot/map/logger

    def __init__(self, origin: tuple[float, float] | None = None):
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
        self._joystick_cmd: Command | None = None   # latest gamepad command, None = no device
        self.logger = CsvLogger("logs")
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

        right = QVBoxLayout()
        self.depth_plot = DepthPlot()
        self.map_view = MapView()
        # Neither view takes keyboard focus (and driving keys are additionally
        # captured at the window level, see _handle_key).
        self.depth_plot.setFocusPolicy(Qt.NoFocus)
        self.map_view.setFocusPolicy(Qt.NoFocus)
        right.addWidget(self.depth_plot, 1)
        right.addWidget(self.map_view, 1)
        root.addLayout(right, 1)
        self._ui_frame = 0

        self.status = QStatusBar(); self.setStatusBar(self.status)
        self.thrust_lbl = QLabel(); self.status.addPermanentWidget(self.thrust_lbl)

        # --- wiring
        self.controls.arm_requested.connect(self.arm)
        self.controls.disarm_requested.connect(self.disarm)
        self.controls.reset_requested.connect(self.reset_simulation)
        self.controls.mode_changed.connect(self.set_mode)
        self.controls.target_depth_set.connect(self._set_target_depth)
        self.controls.target_heading_set.connect(self.heading_hold.set_target)
        self.controls.log_toggled.connect(self._toggle_log)
        self.controls.current_toggled.connect(self._toggle_current)

        self.joystick = JoystickReader(parent=self)
        self.joystick.command.connect(self.set_joystick_command)
        self.joystick.arm_pressed.connect(self.arm)
        self.joystick.disarm_pressed.connect(self.disarm)
        self.joystick.device_changed.connect(self.controls.set_joystick_name)
        self.controls.set_joystick_name(self.joystick.device_name)

        # Launch origin = operator's location (GPS/OS -> IP -> default); async.
        self.origin_source = "locating..."
        self.location = LocationProvider(manual=origin, parent=self)
        self.location.located.connect(self._on_located)
        self.location.start()

        central.setFocusPolicy(Qt.StrongFocus)
        central.setFocus()

        # --- key capture at the top-level QWindow (see _handle_key)
        self._window_filter_installed = False

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

    def reset_simulation(self) -> None:
        """Back to a fresh start: disarmed, Manual, vehicle at the launch point,
        full battery, empty plot and trail. The launch origin is kept."""
        self.disarm()
        self._keys.clear()
        self.watchdog.reset()
        self.sim.reset()
        self.controls.log_btn.setChecked(False)        # stops the CSV logger if running
        self.controls.set_mode(Mode.MANUAL)            # -> set_mode() resets controllers/target line
        self.mode = Mode.MANUAL
        self.depth_hold.set_target(0.0); self.heading_hold.set_target(0.0)
        self.controls.depth_spin.setValue(0.0); self.controls.heading_spin.setValue(0.0)
        self.depth_plot.clear_history(); self.depth_plot.set_target(None)
        self.map_view.clear_trail()
        lat, lon = self.sim.lat_lon()
        self.map_view.update_rov(lat, lon, self.sim.s.yaw)
        self._refresh_ui()
        self.status.showMessage("Simulation reset - disarmed, Manual, vehicle at launch point", 4000)

    def set_mode(self, mode: Mode) -> None:
        if mode is self.mode:
            return
        self.mode = mode
        self._reset_controllers()
        s = self.sim.s
        if mode is Mode.DEPTH_HOLD:        # default target = current depth
            self._set_target_depth(s.depth)
            self.controls.depth_spin.setValue(round(s.depth, 1))
        else:
            self.depth_plot.set_target(None)
        if mode is Mode.HEADING_HOLD:      # default target = current heading
            self.heading_hold.set_target(s.yaw)
            self.controls.heading_spin.setValue(round(s.yaw, 1))
        self.status.showMessage(f"Mode: {mode.value}", 2000)

    def _set_target_depth(self, depth_m: float) -> None:
        self.depth_hold.set_target(depth_m)
        self.depth_plot.set_target(self.depth_hold.target if self.mode is Mode.DEPTH_HOLD else None)

    def _on_located(self, lat: float, lon: float, source: str) -> None:
        self.sim.set_origin(lat, lon)
        self.origin_source = source
        self.map_view.set_origin(lat, lon, source)
        self.status.showMessage(f"Launch origin {lat:.5f}, {lon:.5f} from {source}", 8000)

    def _toggle_log(self, on: bool) -> None:
        if on:
            path = self.logger.start()
            self.status.showMessage(f"Logging to {path}")
        else:
            path = self.logger.stop()
            self.status.showMessage(f"Log saved: {path} ({self.logger.rows} rows)", 5000)

    def _toggle_current(self, on: bool) -> None:
        # ~0.2 m/s current flowing north-east; enough to see the vehicle drift on the map
        self.sim.p.current_north = 0.12 if on else 0.0
        self.sim.p.current_east = 0.16 if on else 0.0

    def _reset_controllers(self) -> None:
        self.depth_hold.reset()
        self.heading_hold.reset()

    # ------------------------------------------------------------ input
    # ------------------------------------------------------------ keys
    # Driving keys are intercepted on the top-level QWindow, i.e. before Qt
    # routes the event to whichever child widget has focus. This keeps the
    # arrows working even if the map (Chromium) or another child has taken
    # focus after a mouse click. Only the window's own events are filtered,
    # never the whole application (an app-wide filter crashes with QtWebEngine).
    def showEvent(self, ev):
        super().showEvent(ev)
        if not self._window_filter_installed and self.windowHandle() is not None:
            self.windowHandle().installEventFilter(self)
            self._window_filter_installed = True

    def eventFilter(self, obj, ev):
        if obj is self.windowHandle() and ev.type() in (QEvent.KeyPress, QEvent.KeyRelease):
            if self._handle_key(ev, ev.type() == QEvent.KeyPress):
                return True
        return super().eventFilter(obj, ev)

    def _handle_key(self, ev, pressed: bool) -> bool:
        """Return True if the event was a driving key and has been consumed."""
        key = ev.key()
        if key == Qt.Key_Space:          # emergency disarm: always, whatever has focus
            if pressed and not ev.isAutoRepeat():
                self.disarm()
            return True
        if key not in KEY_MAP:
            return False
        fw = self.focusWidget()          # focused child of this window (independent of activation)
        if isinstance(fw, (QAbstractSpinBox, QLineEdit)):
            return False                 # let the operator type / step a target value
        if ev.isAutoRepeat():
            return True                  # held key: state already recorded
        if pressed:
            self._keys.add(key)
        else:
            self._keys.discard(key)
        return True

    def keyPressEvent(self, ev):
        # Fallback path (e.g. events synthesised directly on the widget tree).
        if not self._handle_key(ev, True):
            super().keyPressEvent(ev)

    def keyReleaseEvent(self, ev):
        if not self._handle_key(ev, False):
            super().keyReleaseEvent(ev)

    def focusOutEvent(self, ev):
        self._keys.clear()                         # never leave a key "stuck" when the window loses focus
        super().focusOutEvent(ev)

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
        self.depth_plot.append(s)
        self._ui_frame += 1
        lat, lon = self.sim.lat_lon()
        if self._ui_frame % (UI_HZ // 2) == 0:       # map marker at 2 Hz
            self.map_view.update_rov(lat, lon, s.yaw)
        if self._ui_frame % 2 == 0:                  # CSV at 10 Hz
            self.logger.log(s, self.armed.value, self.mode.value, lat, lon)
        self.state_updated.emit(s)

    def closeEvent(self, ev):
        self.sim_timer.stop(); self.ui_timer.stop()
        self.logger.stop()
        super().closeEvent(ev)

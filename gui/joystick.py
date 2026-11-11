"""
Joystick / gamepad input via pygame, polled from a QTimer.

Mapping (Xbox-style layout, SDL axis numbering):
    axis 0  left stick X   -> sway   (+right)
    axis 1  left stick Y   -> surge  (stick up = forward, so inverted)
    axis 3  right stick X  -> yaw    (+clockwise)
    axis 4  right stick Y  -> heave  (stick down = dive, +down)
    button 0 (A)           -> arm
    button 1 (B)           -> disarm

A dead zone removes stick drift. If no device is present the reader is idle
and keyboard control is unaffected; devices are re-scanned every 2 s so a pad
plugged in after start-up is picked up.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer, Signal

from rov_sim.simulator import Command, clamp

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")   # no SDL window needed
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

try:
    import pygame
except ImportError:          # joystick support is optional
    pygame = None

DEAD_ZONE = 0.12


@dataclass
class AxisMap:
    sway: int = 0
    surge: int = 1
    yaw: int = 3
    heave: int = 4
    invert_surge: bool = True
    arm_button: int = 0
    disarm_button: int = 1


def apply_dead_zone(v: float, dz: float = DEAD_ZONE) -> float:
    """Zero inside the dead zone, then rescale so the output still reaches +/-1."""
    if abs(v) < dz:
        return 0.0
    sign = 1.0 if v > 0 else -1.0
    return clamp(sign * (abs(v) - dz) / (1.0 - dz), -1.0, 1.0)


def axes_to_command(get_axis, n_axes: int, m: AxisMap = AxisMap()) -> Command:
    """Pure mapping helper (unit-testable): get_axis(i) -> float in [-1, 1]."""
    def ax(i: int) -> float:
        return apply_dead_zone(get_axis(i)) if i < n_axes else 0.0
    surge = -ax(m.surge) if m.invert_surge else ax(m.surge)
    return Command(surge=surge, sway=ax(m.sway), heave=ax(m.heave), yaw=ax(m.yaw))


class JoystickReader(QObject):
    command = Signal(object)        # Command or None (no device)
    arm_pressed = Signal()
    disarm_pressed = Signal()
    device_changed = Signal(str)    # human-readable device name or ""

    def __init__(self, poll_hz: int = 50, parent=None):
        super().__init__(parent)
        self.map = AxisMap()
        self._js = None
        self._prev_buttons: tuple[bool, ...] = ()
        self.available = pygame is not None
        if self.available:
            try:
                pygame.display.init()      # event pump needs the video subsystem (dummy driver)
                pygame.joystick.init()     # only these two; no mixer/font/audio
            except pygame.error:
                self.available = False
        self._poll = QTimer(self); self._poll.timeout.connect(self._tick)
        self._scan = QTimer(self); self._scan.timeout.connect(self._rescan)
        if self.available:
            self._rescan()
            self._poll.start(1000 // poll_hz)
            self._scan.start(2000)

    # ------------------------------------------------------------------
    def _rescan(self) -> None:
        count = pygame.joystick.get_count()
        if self._js is None and count > 0:
            self._js = pygame.joystick.Joystick(0); self._js.init()
            self._prev_buttons = ()
            self.device_changed.emit(self._js.get_name())
        elif self._js is not None and count == 0:
            self._js = None
            self.device_changed.emit("")
            self.command.emit(None)

    def _tick(self) -> None:
        pygame.event.pump()
        if self._js is None:
            return
        try:
            cmd = axes_to_command(self._js.get_axis, self._js.get_numaxes(), self.map)
            buttons = tuple(self._js.get_button(i) for i in range(self._js.get_numbuttons()))
        except pygame.error:
            self._js = None
            self.device_changed.emit("")
            self.command.emit(None)
            return
        # rising-edge button handling
        for i, b in enumerate(buttons):
            was = self._prev_buttons[i] if i < len(self._prev_buttons) else False
            if b and not was:
                if i == self.map.arm_button:
                    self.arm_pressed.emit()
                elif i == self.map.disarm_button:
                    self.disarm_pressed.emit()
        self._prev_buttons = buttons
        self.command.emit(cmd)

    @property
    def device_name(self) -> str:
        return self._js.get_name() if self._js is not None else ""

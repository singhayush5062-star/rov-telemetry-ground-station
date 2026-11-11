"""
Safety gate between operator/controller input and the simulator.

Rules (from the assessment):
  1. Thrust must be zero whenever disarmed.
  2. In Manual mode, thrust returns to zero after 1 s without operator input.

The gate is a pure function of (command, arm state, mode, time since last
operator input), so it is trivially unit-testable and impossible to bypass as
long as every command goes through `apply_safety` before `simulator.step`.
"""
from __future__ import annotations

from enum import Enum

from .simulator import Command


class ArmState(Enum):
    DISARMED = "DISARMED"
    ARMED = "ARMED"


class Mode(Enum):
    MANUAL = "Manual"
    DEPTH_HOLD = "Depth Hold"
    HEADING_HOLD = "Heading Hold"


MANUAL_INPUT_TIMEOUT_S = 1.0


class InputWatchdog:
    """Tracks the last time the operator provided any input."""

    def __init__(self, timeout_s: float = MANUAL_INPUT_TIMEOUT_S):
        self.timeout_s = timeout_s
        self._last_input_t: float | None = None

    def feed(self, now: float) -> None:
        self._last_input_t = now

    def expired(self, now: float) -> bool:
        if self._last_input_t is None:
            return True
        return (now - self._last_input_t) > self.timeout_s

    def reset(self) -> None:
        self._last_input_t = None


def apply_safety(cmd: Command, armed: ArmState, mode: Mode,
                 watchdog: InputWatchdog, now: float) -> Command:
    """Return the command that is actually allowed to reach the thrusters."""
    if armed is not ArmState.ARMED:
        return Command.zero()
    if mode is Mode.MANUAL and watchdog.expired(now):
        return Command.zero()
    return cmd.clamped()

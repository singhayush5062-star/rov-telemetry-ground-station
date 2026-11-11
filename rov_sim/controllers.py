"""
Hold-mode controllers.

Both holds are discrete PID loops with output clamping and integrator
anti-windup (integrator only accumulates while output is not saturated).

  Depth Hold   : error = target_depth - depth  -> heave command [-1, 1]
  Heading Hold : error = shortest signed angle(target - yaw) -> yaw command
"""
from __future__ import annotations

from .simulator import Command, clamp


class PID:
    def __init__(self, kp: float, ki: float, kd: float,
                 out_limit: float = 1.0, i_limit: float | None = None):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.out_limit = out_limit
        self.i_limit = i_limit if i_limit is not None else out_limit
        self.reset()

    def reset(self) -> None:
        self._i = 0.0
        self._prev_err: float | None = None

    def update(self, err: float, dt: float) -> float:
        if dt <= 0:
            return 0.0
        d = 0.0 if self._prev_err is None else (err - self._prev_err) / dt
        self._prev_err = err

        unsat = self.kp * err + self._i + self.kd * d
        out = clamp(unsat, -self.out_limit, self.out_limit)

        # Anti-windup: only integrate when not pushing further into saturation
        if out == unsat or (err * unsat) < 0:
            self._i = clamp(self._i + self.ki * err * dt, -self.i_limit, self.i_limit)
        return out


def shortest_angle_deg(target: float, current: float) -> float:
    """Signed shortest rotation from current to target, in [-180, 180)."""
    return (target - current + 180.0) % 360.0 - 180.0


class DepthHold:
    def __init__(self):
        # Tuned for ~11 kg ROV, 40 N heave; settles ~10-15 s without overshoot
        self.pid = PID(kp=0.8, ki=0.05, kd=0.9, out_limit=1.0, i_limit=0.3)
        self.target = 0.0

    def set_target(self, depth_m: float) -> None:
        self.target = max(0.0, depth_m)

    def reset(self) -> None:
        self.pid.reset()

    def heave(self, depth: float, dt: float) -> float:
        return self.pid.update(self.target - depth, dt)


class HeadingHold:
    def __init__(self):
        self.pid = PID(kp=0.03, ki=0.002, kd=0.012, out_limit=1.0, i_limit=0.2)
        self.target = 0.0

    def set_target(self, heading_deg: float) -> None:
        self.target = heading_deg % 360.0

    def reset(self) -> None:
        self.pid.reset()

    def yaw(self, heading: float, dt: float) -> float:
        return self.pid.update(shortest_angle_deg(self.target, heading), dt)


def build_command(mode_cmd: Command, mode, depth_hold: DepthHold,
                  heading_hold: HeadingHold, state, dt: float) -> Command:
    """Merge operator input with the active hold controller.

    In Depth Hold the controller owns `heave`; operator keeps surge/sway/yaw.
    In Heading Hold the controller owns `yaw`; operator keeps surge/sway/heave.
    """
    from .safety import Mode  # local import to avoid a cycle

    out = Command(mode_cmd.surge, mode_cmd.sway, mode_cmd.heave, mode_cmd.yaw)
    if mode is Mode.DEPTH_HOLD:
        out.heave = depth_hold.heave(state.depth, dt)
    elif mode is Mode.HEADING_HOLD:
        out.yaw = heading_hold.yaw(state.yaw, dt)
    return out

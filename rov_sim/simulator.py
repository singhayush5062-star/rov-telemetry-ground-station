"""
Pure-Python ROV simulator (no Qt dependency).

Model summary (4 controlled DOF + derived roll/pitch):
  - Operator/controller command: surge, sway, heave, yaw_rate in [-1, 1].
  - Thruster lag:    T += (T_cmd - T) * dt / tau            (first-order response)
  - Drag:            a = (T*F_max - c_lin*v - c_quad*v*|v|) / m
  - Depth is positive downward and clamped at 0 (surface).
  - Heading (yaw) is wrapped to [0, 360).
  - Roll/pitch are small damped responses to lateral/longitudinal
    acceleration plus a little noise so the display is alive.
  - Battery: slow linear discharge plus sag proportional to total thrust.
  - Position is integrated in a local tangent plane and converted to
    lat/lon with a flat-earth offset from the launch origin for the map view.
    The origin defaults to DEFAULT_ORIGIN and is normally replaced at start-up
    by the operator's real location (see gui/location.py).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def wrap_deg(a: float) -> float:
    """Wrap an angle to [0, 360)."""
    return a % 360.0


@dataclass
class Command:
    """Normalised thrust demand in body frame. Each field in [-1, 1]."""
    surge: float = 0.0   # +forward
    sway: float = 0.0    # +right
    heave: float = 0.0   # +down
    yaw: float = 0.0     # +clockwise (heading increases)

    def clamped(self) -> "Command":
        return Command(
            clamp(self.surge, -1, 1), clamp(self.sway, -1, 1),
            clamp(self.heave, -1, 1), clamp(self.yaw, -1, 1),
        )

    @staticmethod
    def zero() -> "Command":
        return Command()

    def is_zero(self) -> bool:
        return self.surge == 0 and self.sway == 0 and self.heave == 0 and self.yaw == 0


@dataclass
class ROVState:
    t: float = 0.0            # s
    x: float = 0.0            # m north of origin
    y: float = 0.0            # m east of origin
    depth: float = 0.0        # m, positive down
    yaw: float = 0.0          # deg, 0 = north, clockwise
    roll: float = 0.0         # deg
    pitch: float = 0.0        # deg
    u: float = 0.0            # body surge velocity m/s
    v: float = 0.0            # body sway velocity m/s
    w: float = 0.0            # heave velocity m/s (+down)
    r: float = 0.0            # yaw rate deg/s
    battery_v: float = 16.8   # V (4S Li-ion full)
    thrust: Command = field(default_factory=Command)  # actual (lagged) thrust


@dataclass
class ROVParams:
    mass: float = 11.0            # kg (BlueROV2-class)
    inertia_z: float = 0.25       # kg m^2 (yaw)
    f_max: float = 40.0           # N per axis at full command
    torque_max: float = 4.0       # N m at full yaw command
    c_lin: float = 6.0            # linear drag N/(m/s)
    c_quad: float = 20.0          # quadratic drag N/(m/s)^2
    c_rot_lin: float = 0.08       # N m /(deg/s)
    c_rot_quad: float = 0.002     # N m /(deg/s)^2
    tau_thruster: float = 0.25    # s, first-order thruster response
    battery_full: float = 16.8    # V
    battery_drain_per_s: float = 0.0015  # V/s at idle
    battery_sag: float = 0.6      # V at full combined thrust
    current_north: float = 0.0    # m/s simulated water current
    current_east: float = 0.0
    noise: float = 0.15           # deg roll/pitch noise amplitude


# Fallback launch origin used only when no real location is available.
DEFAULT_ORIGIN = (18.5204, 73.8567)      # Pune, India
_M_PER_DEG_LAT = 111_320.0


class ROVSimulator:
    def __init__(self, params: ROVParams | None = None, seed: int | None = 0,
                 origin: tuple[float, float] = DEFAULT_ORIGIN):
        self.p = params or ROVParams()
        self.s = ROVState(battery_v=self.p.battery_full)
        self._rng = random.Random(seed)
        self.origin_lat, self.origin_lon = origin

    def set_origin(self, lat: float, lon: float) -> None:
        """Move the launch point; the vehicle's x/y offsets are kept."""
        self.origin_lat, self.origin_lon = float(lat), float(lon)

    def reset(self) -> None:
        self.s = ROVState(battery_v=self.p.battery_full)

    # ------------------------------------------------------------------ step
    def step(self, cmd: Command, dt: float) -> ROVState:
        """Advance the simulation by dt seconds under the given command.

        The caller is responsible for applying the safety gate first; the
        simulator itself does not know about arming.
        """
        p, s = self.p, self.s
        cmd = cmd.clamped()

        # 1. Thruster first-order lag
        k = clamp(dt / p.tau_thruster, 0.0, 1.0)
        T = s.thrust
        T.surge += (cmd.surge - T.surge) * k
        T.sway += (cmd.sway - T.sway) * k
        T.heave += (cmd.heave - T.heave) * k
        T.yaw += (cmd.yaw - T.yaw) * k

        # 2. Translational dynamics with drag (body frame)
        def accel(force: float, vel: float) -> float:
            drag = p.c_lin * vel + p.c_quad * vel * abs(vel)
            return (force - drag) / p.mass

        au = accel(T.surge * p.f_max, s.u)
        av = accel(T.sway * p.f_max, s.v)
        aw = accel(T.heave * p.f_max, s.w)
        s.u += au * dt
        s.v += av * dt
        s.w += aw * dt

        # 3. Yaw dynamics
        rot_drag = p.c_rot_lin * s.r + p.c_rot_quad * s.r * abs(s.r)
        r_dot = (T.yaw * p.torque_max - rot_drag) / p.inertia_z  # deg/s^2 (scaled)
        s.r += r_dot * dt
        s.yaw = wrap_deg(s.yaw + s.r * dt)

        # 4. Position in local NED-ish plane (x north, y east) + water current
        yaw_rad = math.radians(s.yaw)
        vn = s.u * math.cos(yaw_rad) - s.v * math.sin(yaw_rad) + p.current_north
        ve = s.u * math.sin(yaw_rad) + s.v * math.cos(yaw_rad) + p.current_east
        s.x += vn * dt
        s.y += ve * dt

        # 5. Depth, clamped at surface
        s.depth += s.w * dt
        if s.depth < 0.0:
            s.depth = 0.0
            if s.w < 0.0:
                s.w = 0.0

        # 6. Roll / pitch: damped response to lateral accel + small noise
        target_roll = clamp(av * 4.0, -15, 15)
        target_pitch = clamp(-au * 3.0, -15, 15)
        alpha = clamp(dt / 0.5, 0.0, 1.0)
        s.roll += (target_roll - s.roll) * alpha + self._rng.uniform(-p.noise, p.noise) * dt * 10
        s.pitch += (target_pitch - s.pitch) * alpha + self._rng.uniform(-p.noise, p.noise) * dt * 10

        # 7. Battery
        load = (abs(T.surge) + abs(T.sway) + abs(T.heave) + abs(T.yaw)) / 4.0
        s.t += dt
        nominal = p.battery_full - p.battery_drain_per_s * s.t - 0.02 * load * s.t
        s.battery_v = max(12.0, nominal - p.battery_sag * load)
        return s

    # --------------------------------------------------------------- helpers
    def lat_lon(self) -> tuple[float, float]:
        lat = self.origin_lat + self.s.x / _M_PER_DEG_LAT
        lon = self.origin_lon + self.s.y / (_M_PER_DEG_LAT * math.cos(math.radians(self.origin_lat)))
        return lat, lon

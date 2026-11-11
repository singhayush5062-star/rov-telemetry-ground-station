"""Telemetry CSV logger (optional extra). One row per call to `log`."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from rov_sim.simulator import ROVState

FIELDS = ["t_sim_s", "wall_time", "armed", "mode", "roll_deg", "pitch_deg", "yaw_deg",
          "depth_m", "battery_v", "lat", "lon", "thr_surge", "thr_sway", "thr_heave", "thr_yaw"]


class CsvLogger:
    def __init__(self, directory: str | Path = "logs"):
        self.directory = Path(directory)
        self._fh = None
        self._writer = None
        self.path: Path | None = None
        self.rows = 0

    @property
    def active(self) -> bool:
        return self._fh is not None

    def start(self) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / f"rov_{datetime.now():%Y%m%d_%H%M%S}.csv"
        self._fh = open(self.path, "w", newline="")
        self._writer = csv.DictWriter(self._fh, fieldnames=FIELDS)
        self._writer.writeheader()
        self.rows = 0
        return self.path

    def log(self, s: ROVState, armed: str, mode: str, lat: float, lon: float) -> None:
        if not self.active:
            return
        self._writer.writerow({
            "t_sim_s": f"{s.t:.2f}", "wall_time": datetime.now().isoformat(timespec="milliseconds"),
            "armed": armed, "mode": mode,
            "roll_deg": f"{s.roll:.2f}", "pitch_deg": f"{s.pitch:.2f}", "yaw_deg": f"{s.yaw:.2f}",
            "depth_m": f"{s.depth:.3f}", "battery_v": f"{s.battery_v:.3f}",
            "lat": f"{lat:.7f}", "lon": f"{lon:.7f}",
            "thr_surge": f"{s.thrust.surge:.3f}", "thr_sway": f"{s.thrust.sway:.3f}",
            "thr_heave": f"{s.thrust.heave:.3f}", "thr_yaw": f"{s.thrust.yaw:.3f}",
        })
        self.rows += 1
        if self.rows % 50 == 0:
            self._fh.flush()

    def stop(self) -> Path | None:
        if not self.active:
            return None
        self._fh.close()
        self._fh = self._writer = None
        return self.path

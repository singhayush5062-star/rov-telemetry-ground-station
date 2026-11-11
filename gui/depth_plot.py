"""Live depth-versus-time plot (pyqtgraph). Depth axis is inverted: down = deeper."""
from __future__ import annotations

from collections import deque

import pyqtgraph as pg
from PySide6.QtCore import Qt

from rov_sim.simulator import ROVState

WINDOW_S = 60.0


class DepthPlot(pg.PlotWidget):
    def __init__(self, parent=None, max_points: int = 1500):
        super().__init__(parent, background="#121620")
        self.setTitle("Depth vs time", color="#9fb3c8", size="11pt")
        self.setLabel("left", "Depth", units="m", color="#9fb3c8")
        self.setLabel("bottom", "Time", units="s", color="#9fb3c8")
        self.showGrid(x=True, y=True, alpha=0.2)
        self.invertY(True)
        self.setMouseEnabled(x=False, y=False)
        self.setMenuEnabled(False)
        self.getPlotItem().getViewBox().setDefaultPadding(0.05)

        self._t = deque(maxlen=max_points)
        self._d = deque(maxlen=max_points)
        self._curve = self.plot(pen=pg.mkPen("#7fc8ff", width=2))
        self._target = pg.InfiniteLine(angle=0, pen=pg.mkPen("#ffb347", width=1.5, style=Qt.DashLine),
                                       label="target {value:.1f} m", labelOpts={"color": "#ffb347", "position": 0.05})
        self.addItem(self._target)
        self._target.hide()

    def append(self, s: ROVState) -> None:
        self._t.append(s.t)
        self._d.append(s.depth)
        self._curve.setData(self._t, self._d)
        t_hi = max(s.t, WINDOW_S)
        self.setXRange(t_hi - WINDOW_S, t_hi, padding=0)
        lo, hi = min(self._d), max(self._d)
        if self._target.isVisible():
            lo, hi = min(lo, self._target.value()), max(hi, self._target.value())
        span = max(hi - lo, 1.0)
        self.setYRange(max(0.0, lo - 0.1 * span) if lo - 0.1 * span > 0 else -0.05 * span, hi + 0.1 * span, padding=0)

    def set_target(self, depth_m: float | None) -> None:
        if depth_m is None:
            self._target.hide()
        else:
            self._target.setValue(depth_m)
            self._target.show()

    def clear_history(self) -> None:
        self._t.clear(); self._d.clear(); self._curve.setData([], [])

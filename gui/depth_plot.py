"""
Live depth-versus-time plot drawn with QPainter (no plotting library).

Why not pyqtgraph: on the PySide6 build used here (6.12) pyqtgraph 0.14 aborts
with a refcount error after ~10 s of setData() calls. A rolling 60 s window at
20 Hz is only ~1200 points, so a hand-drawn QPainter polyline is trivial, fast
and has zero external dependencies.

API (unchanged from the previous pyqtgraph version):
    append(state)        add a sample and repaint
    set_target(depth|None)  show/hide the dashed target line
    clear_history()
"""
from __future__ import annotations

import math
from collections import deque

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QPolygonF
from PySide6.QtWidgets import QWidget

from rov_sim.simulator import ROVState

WINDOW_S = 60.0

BG = QColor("#121620"); GRID = QColor("#2a3140"); AXIS = QColor("#9fb3c8")
CURVE = QColor("#7fc8ff"); TARGET = QColor("#ffb347"); TEXT = QColor("#9fb3c8")


def _nice_step(span: float, target_ticks: int = 5) -> float:
    """Round the raw step to 1, 2 or 5 x 10^n so grid labels look sane."""
    raw = span / max(target_ticks, 1)
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1.0
    for m in (1, 2, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


class DepthPlot(QWidget):
    def __init__(self, parent=None, max_points: int = 1500):
        super().__init__(parent)
        self._t: deque[float] = deque(maxlen=max_points)
        self._d: deque[float] = deque(maxlen=max_points)
        self._target: float | None = None
        self.setMinimumHeight(180)
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    # ---------------------------------------------------------------- data
    def append(self, s: ROVState) -> None:
        self._t.append(s.t)
        self._d.append(s.depth)
        self.update()

    def set_target(self, depth_m: float | None) -> None:
        self._target = depth_m
        self.update()

    def clear_history(self) -> None:
        self._t.clear(); self._d.clear(); self.update()

    # ---------------------------------------------------------------- paint
    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), BG)

        margin_l, margin_r, margin_t, margin_b = 56, 16, 30, 36
        plot = QRectF(margin_l, margin_t, self.width() - margin_l - margin_r,
                      self.height() - margin_t - margin_b)
        if plot.width() < 20 or plot.height() < 20:
            return

        # --- axis ranges
        t_now = self._t[-1] if self._t else 0.0
        t_hi = max(t_now, WINDOW_S); t_lo = t_hi - WINDOW_S
        vis = [d for t, d in zip(self._t, self._d) if t >= t_lo]
        d_lo = min(vis) if vis else 0.0
        d_hi = max(vis) if vis else 1.0
        if self._target is not None:
            d_lo, d_hi = min(d_lo, self._target), max(d_hi, self._target)
        span = max(d_hi - d_lo, 1.0)
        d_lo = max(0.0, d_lo - 0.1 * span) if d_lo > 0.05 * span else -0.05 * span
        d_hi = d_hi + 0.1 * span

        def X(t: float) -> float:
            return plot.left() + (t - t_lo) / WINDOW_S * plot.width()

        def Y(d: float) -> float:          # inverted: deeper = lower on screen
            return plot.top() + (d - d_lo) / (d_hi - d_lo) * plot.height()

        # --- grid + labels
        p.setFont(QFont("DejaVu Sans", 8))
        grid_pen = QPen(GRID, 1, Qt.DotLine); text_pen = QPen(TEXT)
        step_t = _nice_step(WINDOW_S, 6)
        t0 = math.ceil(t_lo / step_t) * step_t
        t = t0
        while t <= t_hi + 1e-9:
            x = X(t)
            p.setPen(grid_pen); p.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            p.setPen(text_pen); p.drawText(QRectF(x - 25, plot.bottom() + 4, 50, 14), Qt.AlignCenter, f"{t:.0f}")
            t += step_t
        step_d = _nice_step(d_hi - d_lo, 5)
        d = math.ceil(d_lo / step_d) * step_d
        while d <= d_hi + 1e-9:
            y = Y(d)
            p.setPen(grid_pen); p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(text_pen); p.drawText(QRectF(0, y - 7, margin_l - 6, 14), Qt.AlignRight | Qt.AlignVCenter, f"{d:g}")
            d += step_d

        # --- axes frame + titles
        p.setPen(QPen(AXIS, 1)); p.drawRect(plot)
        p.setFont(QFont("DejaVu Sans", 9, QFont.Bold))
        p.drawText(QRectF(plot.left(), 6, plot.width(), 18), Qt.AlignCenter, "Depth vs time")
        p.setFont(QFont("DejaVu Sans", 8))
        p.drawText(QRectF(plot.left(), self.height() - 16, plot.width(), 14), Qt.AlignCenter, "Time (s)")
        p.save(); p.translate(12, plot.center().y()); p.rotate(-90)
        p.drawText(QRectF(-40, -8, 80, 16), Qt.AlignCenter, "Depth (m)"); p.restore()

        # --- target line
        p.setClipRect(plot)
        if self._target is not None:
            y = Y(self._target)
            p.setPen(QPen(TARGET, 1.5, Qt.DashLine))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.drawText(QRectF(plot.left() + 6, y - 16, 160, 14), Qt.AlignLeft | Qt.AlignVCenter, f"target {self._target:.1f} m")

        # --- depth curve
        if len(self._t) >= 2:
            poly = QPolygonF([QPointF(X(t), Y(d)) for t, d in zip(self._t, self._d) if t >= t_lo])
            p.setPen(QPen(CURVE, 2)); p.drawPolyline(poly)
            p.setBrush(CURVE); p.setPen(Qt.NoPen)
            p.drawEllipse(poly.last(), 3, 3)    # current-value dot
        p.end()

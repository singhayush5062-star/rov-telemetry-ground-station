"""Soak test: runs the real window for DUR seconds (default 120) with modes cycling,
CSV logging and water current on, and reports sim-tick jitter and memory.

    DUR=120 .venv/bin/python tools/soak.py
"""
import sys, time, statistics, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
from gui.style import QSS
from rov_sim.safety import Mode
DUR = int(os.environ.get("DUR", "120"))
OUT = os.path.join(ROOT, "docs", "soak_screenshot.png")
def rss_mb():
    for line in open("/proc/self/status"):
        if line.startswith("VmRSS"): return int(line.split()[1]) / 1024
def main():
    app = QApplication(sys.argv); app.setStyleSheet(QSS)
    w = MainWindow(); w.show()
    intervals = []; last = [time.monotonic()]
    orig = w._tick
    def wrapped():
        now = time.monotonic(); intervals.append(now - last[0]); last[0] = now; orig()
    w.sim_timer.timeout.disconnect(); w.sim_timer.timeout.connect(wrapped)
    mem = {}
    keys = [{Qt.Key_W}, {Qt.Key_W, Qt.Key_E}, {Qt.Key_S}, {Qt.Key_A, Qt.Key_F}, set(), {Qt.Key_D, Qt.Key_Q}]
    modes = [Mode.MANUAL, Mode.DEPTH_HOLD, Mode.HEADING_HOLD]
    phase = [0]
    def churn():
        phase[0] += 1
        w._keys.clear(); w._keys.update(keys[phase[0] % len(keys)])
        if phase[0] % 5 == 0:
            m = modes[(phase[0] // 5) % len(modes)]; w.controls.set_mode(m)
            if m is Mode.DEPTH_HOLD: w.controls.depth_spin.setValue(2 + (phase[0] % 7)); w.controls.depth_apply.click()
            if m is Mode.HEADING_HOLD: w.controls.heading_spin.setValue((phase[0] * 37) % 360); w.controls.heading_apply.click()
    QTimer.singleShot(500, lambda: (w.controls.arm_btn.click(), w.controls.log_btn.setChecked(True), w.controls.current_chk.setChecked(True)))
    ct = QTimer(); ct.timeout.connect(churn); ct.start(1500)
    QTimer.singleShot(5000, lambda: mem.update(start=rss_mb()))
    QTimer.singleShot(DUR * 1000 - 3000, lambda: w.grab().save(OUT))
    QTimer.singleShot(DUR * 1000 - 2000, lambda: mem.update(end=rss_mb()))
    QTimer.singleShot(DUR * 1000 - 1500, lambda: w.controls.log_btn.setChecked(False))
    QTimer.singleShot(DUR * 1000 - 1000, w.close); QTimer.singleShot(DUR * 1000 - 800, app.quit)
    app.exec()
    iv = intervals[50:]
    iv_ms = sorted(x * 1000 for x in iv)
    print(f"ticks={len(iv)} mean={statistics.mean(iv_ms):.2f}ms p50={iv_ms[len(iv_ms)//2]:.2f}ms p99={iv_ms[int(len(iv_ms)*0.99)]:.2f}ms max={iv_ms[-1]:.2f}ms expected=20ms")
    print(f"rss_start={mem.get('start'):.1f}MB rss_end={mem.get('end'):.1f}MB")
    print(f"sim_t={w.sim.s.t:.1f}s depth={w.sim.s.depth:.2f} yaw={w.sim.s.yaw:.1f} x={w.sim.s.x:.1f} y={w.sim.s.y:.1f} batt={w.sim.s.battery_v:.2f}")
    print(f"csv={w.logger.path} rows={w.logger.rows} joystick_available={w.joystick.available} device='{w.joystick.device_name}'")
    print(f"plot_points={len(w.depth_plot._t)}")
sys.exit(main())

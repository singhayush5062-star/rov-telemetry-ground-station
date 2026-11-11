"""Record docs/walkthrough.mp4: drives the real window through a scripted scenario,
grabs frames at 10 fps, then encodes with ffmpeg.

    .venv/bin/python tools/record_walkthrough.py
"""
import sys, os, subprocess, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
from gui.style import QSS
from rov_sim.safety import Mode
F = tempfile.mkdtemp(prefix="rov_frames_"); FPS = 10
def main():
    app = QApplication(sys.argv); app.setStyleSheet(QSS)
    w = MainWindow(); w.resize(1280, 760); w.show()
    n = [0]
    def frame():
        n[0] += 1; w.grab().save(f"{F}/f{n[0]:05d}.png", "PNG")
    cap = QTimer(); cap.timeout.connect(frame)
    def keys(*ks): w._keys.clear(); w._keys.update(ks)
    def banner(msg): w.status.showMessage(msg, 6000)
    sched = [
        (2500,  lambda: cap.start(1000 // FPS)),                       # map tiles have arrived by now
        (3000,  lambda: banner("Dashboard: telemetry (left), controls, depth plot (top right), OpenStreetMap (bottom right)")),
        (8000,  lambda: (w.controls.arm_btn.click(), banner("ARM pressed - thrust now allowed"))),
        (9500,  lambda: (keys(Qt.Key_W, Qt.Key_E), banner("Manual: W (surge) + E (yaw right) held"))),
        (17000, lambda: (keys(Qt.Key_A, Qt.Key_F), banner("Manual: A (sway left) + F (dive)"))),
        (22000, lambda: (keys(), banner("Keys released: watchdog zeroes thrust after 1 s"))),
        (26000, lambda: (w.controls.set_mode(Mode.DEPTH_HOLD), banner("Depth Hold selected - target seeded with current depth"))),
        (29000, lambda: (w.controls.depth_spin.setValue(5.0), w.controls.depth_apply.click(), banner("Target depth 5.0 m set - PID drives heave"))),
        (44000, lambda: (w.controls.set_mode(Mode.HEADING_HOLD), banner("Heading Hold selected"))),
        (46500, lambda: (w.controls.heading_spin.setValue(270.0), w.controls.heading_apply.click(), banner("Target heading 270 deg set - shortest turn"))),
        (50000, lambda: keys(Qt.Key_W)),                                # cruise while holding heading
        (60000, lambda: (keys(), w.controls.log_btn.setChecked(True), w.controls.current_chk.setChecked(True), banner("CSV logging started; simulated water current on"))),
        (66000, lambda: (w.controls.set_mode(Mode.MANUAL), keys(Qt.Key_R), banner("Manual: R (ascend)"))),
        (72000, lambda: (keys(), w.controls.disarm_btn.click(), banner("DISARM - thrust forced to zero immediately"))),
        (78000, lambda: w.controls.log_btn.setChecked(False)),
        (80000, cap.stop), (80500, w.close), (80800, app.quit),
    ]
    for ms, fn in sched: QTimer.singleShot(ms, fn)
    app.exec(); print(f"frames={n[0]} sim_t={w.sim.s.t:.1f}", flush=True)
    out = os.path.join(ROOT, "docs", "walkthrough.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", f"{F}/f%05d.png",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", out], check=True)
    print("wrote", out)
sys.exit(main())

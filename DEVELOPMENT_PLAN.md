# ROV Telemetry Ground Station — Development Plan

**Deadline:** 13 Nov 2026 (submission) · **Plan written:** 11 Nov 2026 evening
**Working time available:** ~1.5 days → the plan optimises for *proven libraries, minimal custom code, no build-system fights*.

---

## 1. Tech stack decision

| Concern | Choice | Why (verified on this machine) |
|---|---|---|
| Language | **Python 3.10** (system, already installed) | Assessment explicitly accepts Python. No compile/link cycle → fastest iteration in 2 days. |
| GUI toolkit | **PySide6 6.9.x** (official Qt for Python, LGPL) via pip — pinned `<6.12` | One `pip install` gives Qt 6 Widgets + QtCharts + **QtWebEngine** in a single wheel. System Qt 5 here lacks WebEngine/Location/Charts for both C++ and PyQt5, so C++ would need `sudo apt` for several `-dev` packages plus CMake setup — too slow for the window. |
| Depth-vs-time plot | **Hand-drawn `QPainter` widget** (~120 lines) | pyqtgraph 0.14 crashed on PySide6 6.12 during the Phase 4 soak; a rolling 1,200-point polyline needs no library, has zero dependencies and is fully explainable at interview. |
| OpenStreetMap view | **Leaflet 1.9 (CDN) + OSM tiles** inside `QWebEngineView` | The standard, verified way to embed OSM in a Qt desktop app. One static `map.html`, marker moved with `runJavaScript()`. Still a native desktop app (the web view is a widget inside the window, not a browser app). |
| Joystick | **pygame 2.6** joystick module, polled by a `QTimer` | Most reliable cross-platform gamepad API in Python; Qt 6 dropped QtGamepad. Keyboard works without it. |
| Simulation | Pure Python class (no Qt dependency), 50 Hz `QTimer` tick | Simple 4-DOF kinematics + first-order thruster lag + drag. Pure Python → unit-testable with pytest. |
| Hold modes | Discrete **PID** controllers (depth → heave, heading → yaw) | Easy to explain at interview, ~30 lines each. |
| Logging | stdlib `csv` | Optional extra, near-zero cost. |
| Tests | **pytest** | Safety invariants and controller behaviour; optional extra that scores well. |
| Packaging | `venv` + `requirements.txt` + `run.sh` | Reviewer can run in 3 commands. |

**Why not C++/Qt/QML (the "preferred" option):** it is preferred, not required. On this Ubuntu 22.04 box only Qt 5.15 Widgets/Qml dev packages exist; Charts, Location and WebEngine dev packages are absent. Getting a C++ build with map + plot working would consume most of day one. The assessment says *"Prefer a smaller, reliable implementation over an incomplete feature set"* — Python + PySide6 is the reliable path for this timeline. State this reasoning in the README.

**AI-tool disclosure (required by the assessment):** README will state Claude Code was used for planning, scaffolding and code review, and that every module was reviewed/understood by the author.

---

## 2. Architecture (keep it small, keep layers separate)

```
rov_ground_station/
├── main.py                  # entry point: creates QApplication, MainWindow
├── requirements.txt
├── run.sh
├── README.md
├── rov_sim/                 # NO Qt imports here → testable in isolation
│   ├── simulator.py         # ROVState, ROVSimulator.step(dt, cmd)
│   ├── controllers.py       # PID, DepthHold, HeadingHold
│   └── safety.py            # ArmState + ManualInputWatchdog (1 s timeout)
├── gui/
│   ├── main_window.py       # layout, 50 Hz QTimer, wires everything
│   ├── telemetry_panel.py   # armed, mode, roll, pitch, yaw, depth, battery
│   ├── controls_panel.py    # Arm/Disarm, mode selector, target depth/heading
│   ├── depth_plot.py        # pyqtgraph PlotWidget, rolling 60 s window
│   ├── map_view.py          # QWebEngineView + map.html (Leaflet/OSM)
│   ├── map.html
│   └── joystick.py          # pygame polling → normalised axes
├── logging_util/
│   └── csv_logger.py
└── tests/
    ├── test_safety.py
    ├── test_simulator.py
    └── test_controllers.py
```

**Data flow (one tick, 50 Hz):**
`input (keyboard/joystick/PID) → safety gate → simulator.step() → state → telemetry panel + plot + map + CSV`

**Responsiveness:** the sim step is ~µs of arithmetic, so it runs on the GUI thread via `QTimer` (no locking bugs). GUI widgets refresh at 20 Hz, plot at 10 Hz, map marker at 2 Hz — all decoupled by separate timers.

**Simulation model (explainable at interview):**
- State: `x, y, depth, yaw, roll, pitch, u, v, w, r` (body velocities), `battery_v`, `t`.
- Command: `surge, sway, heave, yaw_rate ∈ [-1, 1]`.
- Thruster lag: `T += (T_cmd − T) · dt/τ`, τ = 0.25 s.
- Drag: `a = (T·F_max − c_lin·v − c_quad·v|v|)/m` per axis.
- Roll/pitch: small damped response to sway/surge acceleration + low-amplitude noise (so the display moves).
- Depth clamped ≥ 0 (surface); heading wrapped 0–360°.
- Battery: slow linear discharge + sag proportional to total thrust.
- Position → lat/lon via flat-earth offset from a fixed origin (for the map marker).

**Safety rules (hard-coded, tested):**
1. `disarmed ⇒ thrust command = 0` before the simulator sees it.
2. Manual mode: if no operator input for 1.0 s → command = 0 (watchdog).
3. Switching to Disarmed also resets integrators in the PIDs.

---

## 3. Phase-wise plan with outcomes

### Phase 0 — Environment & skeleton (11 Nov evening, ~1 h)
**Do**
```bash
cd ~/Desktop/ROV_SIMULATOR
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
- Smoke test: a 20-line script that opens a `QMainWindow` with a `QWebEngineView` loading openstreetmap.org and a `pyqtgraph` plot. If the window appears, the stack is proven.
- Qt6 runtime deps (`libxcb-cursor0`, `libnss3`, `libegl1`) are already installed on this machine — checked 11 Nov.
- `git init`, create the folder tree above with empty modules, write `requirements.txt`.

**Outcome:** stack proven on this machine; repo skeleton committed. *Go/no-go for the whole plan.*

### Phase 1 — Simulation core + safety + tests (11 Nov night, ~3 h)
**Do**
- `simulator.py`: state dataclass + `step()` with thruster lag, drag, roll/pitch, battery.
- `safety.py`: `ArmState` enum, `apply_safety(cmd, armed, mode, last_input_time, now)`.
- `controllers.py`: generic `PID(kp, ki, kd, out_limit)` with anti-windup; `DepthHold`, `HeadingHold` (shortest-angle error wrap).
- `tests/`: disarmed ⇒ zero thrust; watchdog zeroes after 1 s; depth hold converges within tolerance in simulated 30 s; heading wrap 350°→10° goes the short way.

**Outcome:** `pytest` green. Sim can be driven from a terminal loop and prints sane telemetry. No GUI yet.

### Phase 2 — Dashboard window & controls (12 Nov morning, ~4 h)
**Do**
- `main_window.py`: `QMainWindow`, `QGridLayout`: left = telemetry + controls, right = plot (top) + map (bottom) placeholders.
- `telemetry_panel.py`: large-font `QLabel`s for armed state (green/red), mode, roll, pitch, yaw, depth, battery.
- `controls_panel.py`: Arm / Disarm `QPushButton`s, mode `QComboBox` (Manual / Depth Hold / Heading Hold), `QDoubleSpinBox` for target depth (m) and heading (°) with Apply.
- Keyboard: W/S surge, A/D sway, Q/E yaw, R/F heave via `keyPressEvent`/`keyReleaseEvent`; each press refreshes the watchdog timestamp.
- 50 Hz `QTimer` tick calls safety → sim → updates panel.
- Basic dark stylesheet (one `.qss` string).

**Outcome:** fully working *keyboard-driven* simulator with live telemetry, arm/disarm and all three modes. Already satisfies every functional requirement except plot/map/joystick.

### Phase 3 — Depth plot + OpenStreetMap view (12 Nov afternoon, ~3 h)
**Do**
- `depth_plot.py`: `pg.PlotWidget`, inverted Y axis (depth grows downward), rolling 60 s deque, target-depth dashed line when in Depth Hold.
- `map.html`: Leaflet from CDN, OSM tile layer, one marker + polyline trail; JS function `updateRov(lat, lon, heading)`.
- `map_view.py`: `QWebEngineView.load(QUrl.fromLocalFile(map.html))`; every 500 ms call `page().runJavaScript(f"updateRov({lat},{lon},{yaw})")`.
- Fallback if WebEngine misbehaves: Leaflet is the only risk; the fallback is `QtLocation` QML `Map` inside a `QQuickWidget` (also in the PySide6 wheel).

**Outcome:** complete dashboard matching the video checklist.

### Phase 4 — Joystick, CSV logging, polish (12 Nov evening, ~3 h)
**Do**
- `joystick.py`: `pygame.joystick` init; 50 Hz poll; axes mapped like keyboard; dead-zone 0.1; gracefully absent if no device (this machine has none → test with keyboard, code path kept simple).
- `csv_logger.py`: Start/Stop button writes `t, armed, mode, roll, pitch, yaw, depth, battery, lat, lon` at 10 Hz to `logs/`.
- Optional (only if ahead of schedule): simulated water current (constant drift vector added in `step()`); it is a 5-line change.
- Run a 10-minute soak: UI must remain responsive, memory flat (deque bounded).

**Outcome:** all required + optional-extra features done; feature-freeze.

### Phase 5 — README, video, submission package (13 Nov morning, ~3 h)
**Do**
- `README.md`: how to run (3 commands), controls table, architecture diagram (the tree above), simulation model equations, hold-method explanation, safety design, AI-tool disclosure, known limitations (map needs internet for tiles).
- Record 2–3 min walkthrough (`ffmpeg -f x11grab` is installed; OBS/SimpleScreenRecorder optional): window & layout → telemetry values changing → Arm/Disarm → each mode & target inputs → depth plot → map.
- Final `pytest`, fresh-venv install test from `requirements.txt`, zip/GitHub push.

**Outcome:** submitted before the 13 Nov deadline with buffer.

---

## 4. Timeline at a glance

| When | Phase | Done when… |
|---|---|---|
| 11 Nov 20:00–21:00 | 0 Env & skeleton | WebEngine + pyqtgraph window opens |
| 11 Nov 21:00–00:00 | 1 Sim core + tests | `pytest` passes |
| 12 Nov 09:00–13:00 | 2 Dashboard & controls | Keyboard-driven app with modes works |
| 12 Nov 14:00–17:00 | 3 Plot + map | Dashboard matches video checklist |
| 12 Nov 17:00–20:00 | 4 Joystick, CSV, polish | Feature-freeze, 10-min soak OK |
| 13 Nov 09:00–12:00 | 5 README + video + package | Submitted |

**Buffer:** 13 Nov afternoon is reserved for fixes only. If Phase 3 slips, drop the Leaflet trail/polyline and CSV logging first; never drop safety rules or the three modes.

---

## 5. Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| PySide6 install / Qt6 xcb error on Ubuntu 22.04 | Low–Med | `libxcb-cursor0` and other Qt6 runtime libs verified present; Phase 0 smoke test confirms. |
| QtWebEngine sandbox/GPU errors | Low | Set `QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu` or `--no-sandbox` in `run.sh` if needed. |
| No internet at demo → blank map tiles | Med | README notes it; marker/trail still render over blank base; optionally pre-cache a few tiles. |
| No joystick on dev machine | Certain | Keyboard is primary; joystick code is isolated and optional. |
| Interview: "explain every part" | — | Keep modules < 150 lines each; no magic frameworks; equations in README. |

---

## 6. Interview talking points to prepare (while building)
- Why first-order lag for thrusters and why τ = 0.25 s.
- Why PID for holds; how anti-windup and heading wrap are handled.
- Why the sim runs on the GUI thread (cost << 1 ms) and how you'd move it to a `QThread` if the model grew.
- How the safety gate sits *between* input and simulator so disarm/watchdog cannot be bypassed.
- Why Python/PySide6 over C++ for this timeline and what would change in a C++ port (same architecture, `QObject` signals instead of callbacks).

---

## 7. Decisions log (updated during build)

| Date | Decision | Reason |
|---|---|---|
| 11 Nov | Key handling via `keyPressEvent` on the window, not an app-wide event filter | An application-wide `QObject.eventFilter` segfaults PySide6 as soon as a `QWebEngineView` exists (Chromium's internal widget events). |
| 11 Nov | `LocalContentCanAccessRemoteUrls` + `LocalContentCanAccessFileUrls` set on the map view | file:// pages cannot load OSM tiles without the first; on Qt 6.12 the first alone silently breaks the local Leaflet script. |
| 11 Nov | Leaflet 1.9.4 vendored under `gui/vendor/leaflet` | No CDN dependency at demo time; only tiles need the network. |
| 11 Nov | Dropped pyqtgraph, wrote a `QPainter` plot | pyqtgraph aborted with a refcount error after ~10 s on PySide6 6.12. |
| 11 Nov | PySide6 pinned `<6.12` (6.9.3 installed) | The same refcount abort reproduced in a plain `QPainter.drawLine` call on 6.12.0; 6.9.3 passed a 2-minute soak (5,875 ticks, p99 22.7 ms, memory flat). |
| 11 Nov | Launch origin from the operator's location (`gui/location.py`): `--origin` → QtPositioning (GPS/OS) → IP geolocation → default | Requested after submission review: the map should show where the operator actually is. Each stage has a timeout; the map re-centres when a fix arrives. |
| 11 Nov | `pytest.ini` with `testpaths = tests` | `tools/soak_test.py` matched pytest's `*_test.py` pattern and ran the 2-minute soak during collection; renamed to `tools/soak.py` too. |

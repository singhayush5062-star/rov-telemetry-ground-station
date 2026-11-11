# Code walkthrough

How the ROV Telemetry Ground Station is put together, in the order you would
explain it to someone reading the code for the first time. Each section names
the file, the one idea it owns, and the question it answers.

## 1. The one-sentence version

> Every 20 ms the window reads the operator's input, lets the active hold
> controller take over one axis, passes the result through a safety gate, and
> steps a small physics model; separate slower timers redraw the telemetry,
> the depth plot and the map.

## 2. Layering (why the folders look the way they do)

```
rov_sim/      physics + control + safety   -> plain Python, no Qt, unit-tested
gui/          widgets and timers           -> PySide6; the only code that touches the sim
logging_util/ CSV writer
tools/        soak test, video recorder
tests/        30 pytest cases
```

The split is the first thing to point at: `rov_sim` can be imported in a
terminal or a test with no window at all. The GUI depends on the sim; the sim
never depends on the GUI.

## 3. The simulator – `rov_sim/simulator.py`

* `Command` – four normalised demands `surge, sway, heave, yaw` in [-1, 1].
* `ROVState` – position `x, y` (metres from the launch point), `depth`
  (positive down), `yaw`, `roll`, `pitch`, body velocities, yaw rate, battery.
* `ROVParams` – mass, max thrust, drag coefficients, thruster time constant.
* `ROVSimulator.step(cmd, dt)` does, in order:
  1. **Thruster lag** – a first-order filter `T += (T_cmd − T)·dt/τ`, τ = 0.25 s.
     This is the "short thruster-response delay" the brief asks for.
  2. **Drag** – `a = (T·F_max − c_lin·v − c_quad·v|v|) / m` per axis, so the
     vehicle reaches a terminal velocity instead of accelerating forever.
  3. **Yaw** – same shape with torque and rotational drag; heading wrapped 0–360.
  4. **Position** – body velocities rotated by yaw into north/east, plus an
     optional constant water current.
  5. **Depth** – integrated and clamped at 0 (surface).
  6. **Roll / pitch** – damped response to sway/surge acceleration plus a
     little noise, so the readouts look alive. They are not controlled axes.
  7. **Battery** – linear discharge plus sag proportional to total thrust.
* `lat_lon()` converts `x, y` to latitude/longitude as a flat-earth offset from
  `origin_lat/lon`, which `set_origin()` can move at any time.

Numbers to remember: mass 11 kg, 40 N per axis, τ = 0.25 s, terminal speed
≈ 1.3 m/s. The test `test_forward_thrust_reaches_terminal_velocity_due_to_drag`
checks the steady state against the drag equation.

## 4. Safety – `rov_sim/safety.py`

`apply_safety(cmd, armed, mode, watchdog, now)` is a pure function:

1. not armed → `Command.zero()`
2. Manual mode and `watchdog.expired(now)` (no input for 1.0 s) → zero
3. otherwise clamp to [-1, 1]

Why a pure function: it has no state of its own, so a test can call it with
any combination of inputs, and it sits in one place that every command must
pass through. `InputWatchdog.feed(now)` is called from the key handler and
the joystick poller; nothing else can keep thrust alive.

Two extra safety touches in the window: disarming also zeroes the stored
command immediately (not on the next tick), and the window clears held keys
when it loses focus, so a key can never be "stuck".

## 5. Hold modes – `rov_sim/controllers.py`

* `PID` – discrete PID with output clamping and anti-windup (the integrator
  only accumulates while the output is not saturated).
* `DepthHold.heave(depth, dt)` → error = target − depth → heave command.
* `HeadingHold.yaw(yaw, dt)` → error = `shortest_angle_deg(target, yaw)` →
  yaw command. The shortest-angle wrap means 350° → 10° turns 20° right, not
  340° left.
* `build_command(op, mode, ...)` merges operator input with the controller:
  in Depth Hold the controller owns heave and the operator keeps the rest; in
  Heading Hold the controller owns yaw.

Tuning story: depth gains 0.8 / 0.05 / 0.9 settle to ±15 cm in about 10 s
with no visible overshoot; heading gains 0.03 / 0.002 / 0.012 because the
error is in degrees (a 90° error must not saturate instantly).
Integrators reset on disarm and on mode change, and entering a hold mode
seeds the target with the current depth/heading so nothing lurches.

## 6. The window – `gui/main_window.py`

* Two timers: `sim_timer` at 50 Hz calls `_tick()`; `ui_timer` at 20 Hz calls
  `_refresh_ui()`. The sim step costs microseconds, so it runs on the GUI
  thread; no threads, no locks. If the model grew, the same `_tick()` would
  move into a `QThread` and hand the state back through a signal.
* `_tick()` is the one-sentence version from section 1, literally four lines.
* `_refresh_ui()` updates the telemetry labels, appends a plot sample,
  updates the map every 10th frame (2 Hz), and logs CSV every 2nd frame (10 Hz).
* Keyboard: `keyPressEvent`/`keyReleaseEvent` on the window keep a set of held
  keys. The plot and map have `NoFocus`, so unhandled keys bubble up from
  anywhere. (An application-wide event filter was tried first and crashes
  PySide6 as soon as a QtWebEngine widget exists.)
* `_on_located()` moves the launch origin once the operator's location arrives.

## 7. Widgets

* `telemetry_panel.py` – labels for armed, mode, roll, pitch, yaw, depth,
  battery. Colour comes from the stylesheet via dynamic properties
  (`armed="true"`, `low="true"`).
* `controls_panel.py` – ARM/DISARM, mode combo, target spin boxes with Set,
  CSV log toggle, water-current checkbox, joystick status. Target inputs are
  only enabled in their mode and release keyboard focus after Set.
* `depth_plot.py` – a `QWidget` whose `paintEvent` draws grid, axes, a dashed
  target line and the last 60 s of depth as a polyline. ~1,200 points, so no
  plotting library is needed. (pyqtgraph was dropped after it crashed on
  PySide6 6.12.)
* `map_view.py` + `map.html` – `QWebEngineView` showing a local Leaflet page
  with OpenStreetMap tiles. Python calls `updateRov(lat, lon, hdg)` through
  `runJavaScript`; the page moves the arrow marker, extends the trail and
  updates the HUD. `setOrigin()` re-centres when the location is known.
* `joystick.py` – pygame polled at 50 Hz, dead zone 0.12, Xbox-style map,
  A/B arm/disarm, hot-plug rescan. The pure `axes_to_command()` is unit-tested
  because no pad was available during development.

## 8. Launch origin – `gui/location.py`

Resolution chain, first success wins, each stage with a timeout:

1. `--origin LAT,LON` or `ROV_ORIGIN` – exact, skips lookups.
2. OS location via QtPositioning – a real GPS receiver if present, otherwise
   Wi-Fi positioning (Windows Location, macOS CoreLocation, geoclue2 on Linux).
3. IP geolocation over HTTPS – city level; the only stage that contacts a
   third party.
4. The built-in default.

The result is applied with `sim.set_origin()` and `map_view.set_origin()`;
the HUD and status bar name the source so the operator knows how exact it is.

## 9. Tests – `tests/`

30 cases in under a second. The ones worth quoting:

* disarmed ⇒ zero thrust in every mode; watchdog cuts thrust just after 1.0 s
* terminal velocity matches the drag equation; depth never goes negative
* depth hold converges within 15 cm from above and below; heading hold takes
  the short way round
* joystick dead zone rescales to full travel; CSV header and rows; IP payload
  parsing for both services

`tools/soak.py` is the responsiveness evidence: 2 minutes with modes cycling,
logging on and current on gave a mean tick of 20.03 ms, p99 22.7 ms, memory flat.

## 10. Decisions you may be asked about

| Question | Answer |
|---|---|
| Why Python/PySide6 and not C++/QML? | The brief accepts Python; one pip wheel gives Widgets + WebEngine, no build system. Same architecture would port to C++ with signals in place of callbacks. |
| Why does the sim run on the GUI thread? | A step is microseconds; a thread would add locking for no benefit. The soak test shows the UI stays at 20 ms. |
| Why PID for the holds? | Simple, explainable, enough for a first-order plant with drag; anti-windup and angle wrap are the two details that matter. |
| How can the safety rules not be bypassed? | Every command goes through `apply_safety()` before `step()`; nothing else calls `step()`. |
| Why vendor Leaflet? | So only the tiles need the network at demo time. |
| What broke along the way? | App-wide event filter + WebEngine segfault; file:// pages need two web-settings flags for tiles; pyqtgraph and plain QPainter both crashed on PySide6 6.12.0, so it is pinned below 6.12. |

import math
from rov_sim.simulator import ROVSimulator, Command, ROVParams

DT = 0.02


def run(sim, cmd, seconds):
    for _ in range(int(seconds / DT)):
        sim.step(cmd, DT)
    return sim.s


def test_thruster_lag_is_first_order():
    sim = ROVSimulator()
    sim.step(Command(surge=1.0), DT)
    assert 0 < sim.s.thrust.surge < 1.0
    run(sim, Command(surge=1.0), 2.0)  # 8 tau
    assert sim.s.thrust.surge > 0.99


def test_forward_thrust_reaches_terminal_velocity_due_to_drag():
    sim = ROVSimulator()
    s = run(sim, Command(surge=1.0), 15.0)
    p = sim.p
    # steady state: F = c_lin v + c_quad v^2
    v = s.u
    assert abs(p.f_max - (p.c_lin * v + p.c_quad * v * v)) < 0.5
    assert 0.5 < v < 3.0


def test_zero_command_decays_to_rest():
    sim = ROVSimulator()
    run(sim, Command(surge=1.0), 5.0)
    s = run(sim, Command.zero(), 10.0)
    assert abs(s.u) < 0.05 and abs(s.thrust.surge) < 1e-3


def test_depth_never_negative():
    sim = ROVSimulator()
    s = run(sim, Command(heave=-1.0), 5.0)
    assert s.depth == 0.0


def test_heave_increases_depth():
    sim = ROVSimulator()
    s = run(sim, Command(heave=1.0), 5.0)
    assert s.depth > 1.0


def test_yaw_wraps_and_turns_clockwise():
    sim = ROVSimulator()
    sim.s.yaw = 355.0
    s = run(sim, Command(yaw=1.0), 3.0)
    assert 0 <= s.yaw < 360 and s.r > 0


def test_battery_drains_and_sags_under_load():
    sim = ROVSimulator()
    v0 = sim.s.battery_v
    s = run(sim, Command.zero(), 10.0)
    idle_v = s.battery_v
    assert idle_v < v0
    run(sim, Command(1, 1, 1, 1), 2.0)
    assert sim.s.battery_v < idle_v - 0.3


def test_water_current_drifts_vehicle():
    sim = ROVSimulator(ROVParams(current_east=0.5))
    s = run(sim, Command.zero(), 10.0)
    assert abs(s.y - 5.0) < 0.1 and abs(s.x) < 1e-6


def test_lat_lon_offset_from_default_origin():
    sim = ROVSimulator()
    sim.s.x = 111.32  # ~0.001 deg lat
    lat, lon = sim.lat_lon()
    assert math.isclose(lat - 18.5204, 0.001, rel_tol=1e-3)


def test_set_origin_rebases_position():
    sim = ROVSimulator()
    sim.s.x = 111.32; sim.s.y = 0.0
    sim.set_origin(28.6654, 77.4391)
    lat, lon = sim.lat_lon()
    assert math.isclose(lat, 28.6664, abs_tol=1e-5) and math.isclose(lon, 77.4391, abs_tol=1e-9)


def test_reset_returns_to_fresh_state_but_keeps_origin():
    sim = ROVSimulator(); sim.set_origin(28.6654, 77.4391)
    run(sim, Command(surge=1.0, heave=1.0, yaw=0.5), 5.0)
    assert sim.s.depth > 0 and sim.s.t > 0 and sim.s.battery_v < sim.p.battery_full
    sim.reset()
    s = sim.s
    assert s.t == 0 and s.x == 0 and s.y == 0 and s.depth == 0 and s.yaw == 0
    assert s.u == s.v == s.w == s.r == 0 and s.thrust.is_zero()
    assert s.battery_v == sim.p.battery_full
    assert (sim.origin_lat, sim.origin_lon) == (28.6654, 77.4391)

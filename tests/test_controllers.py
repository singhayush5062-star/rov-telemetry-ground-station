from rov_sim.controllers import PID, DepthHold, HeadingHold, shortest_angle_deg, build_command
from rov_sim.safety import Mode
from rov_sim.simulator import ROVSimulator, Command

DT = 0.02


def test_shortest_angle():
    assert shortest_angle_deg(10, 350) == 20
    assert shortest_angle_deg(350, 10) == -20
    assert abs(shortest_angle_deg(180, 0)) == 180  # either direction is valid
    assert shortest_angle_deg(90, 90) == 0


def test_pid_output_is_clamped_and_integrator_bounded():
    pid = PID(kp=10, ki=10, kd=0, out_limit=1.0, i_limit=0.5)
    for _ in range(500):
        out = pid.update(100.0, DT)
    assert out == 1.0
    assert abs(pid._i) <= 0.5


def test_depth_hold_converges():
    sim = ROVSimulator()
    dh = DepthHold(); dh.set_target(5.0)
    for _ in range(int(40 / DT)):
        cmd = build_command(Command.zero(), Mode.DEPTH_HOLD, dh, HeadingHold(), sim.s, DT)
        sim.step(cmd, DT)
    assert abs(sim.s.depth - 5.0) < 0.15, sim.s.depth


def test_depth_hold_can_ascend():
    sim = ROVSimulator(); sim.s.depth = 8.0
    dh = DepthHold(); dh.set_target(2.0)
    for _ in range(int(40 / DT)):
        sim.step(build_command(Command.zero(), Mode.DEPTH_HOLD, dh, HeadingHold(), sim.s, DT), DT)
    assert abs(sim.s.depth - 2.0) < 0.15, sim.s.depth


def test_heading_hold_takes_short_way_round():
    sim = ROVSimulator(); sim.s.yaw = 350.0
    hh = HeadingHold(); hh.set_target(10.0)
    first = build_command(Command.zero(), Mode.HEADING_HOLD, DepthHold(), hh, sim.s, DT)
    assert first.yaw > 0  # clockwise through north, not 340 deg the other way
    for _ in range(int(40 / DT)):
        sim.step(build_command(Command.zero(), Mode.HEADING_HOLD, DepthHold(), hh, sim.s, DT), DT)
    assert abs(shortest_angle_deg(10.0, sim.s.yaw)) < 2.0, sim.s.yaw


def test_operator_keeps_other_axes_in_hold_modes():
    sim = ROVSimulator()
    op = Command(surge=0.5, sway=-0.2, heave=0.9, yaw=0.3)
    c = build_command(op, Mode.DEPTH_HOLD, DepthHold(), HeadingHold(), sim.s, DT)
    assert c.surge == 0.5 and c.sway == -0.2 and c.yaw == 0.3 and c.heave != 0.9
    c = build_command(op, Mode.HEADING_HOLD, DepthHold(), HeadingHold(), sim.s, DT)
    assert c.heave == 0.9 and c.yaw != 0.3

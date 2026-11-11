from rov_sim.safety import ArmState, Mode, InputWatchdog, apply_safety
from rov_sim.simulator import Command


def test_disarmed_always_zero_thrust():
    wd = InputWatchdog()
    wd.feed(0.0)
    cmd = Command(1, 1, 1, 1)
    for mode in Mode:
        out = apply_safety(cmd, ArmState.DISARMED, mode, wd, 0.1)
        assert out.is_zero()


def test_manual_watchdog_zeroes_after_one_second():
    wd = InputWatchdog()
    cmd = Command(surge=0.7)
    wd.feed(10.0)
    assert apply_safety(cmd, ArmState.ARMED, Mode.MANUAL, wd, 10.9).surge == 0.7
    assert apply_safety(cmd, ArmState.ARMED, Mode.MANUAL, wd, 11.0).surge == 0.7  # exactly 1 s still ok
    assert apply_safety(cmd, ArmState.ARMED, Mode.MANUAL, wd, 11.01).is_zero()


def test_watchdog_without_any_input_is_expired():
    wd = InputWatchdog()
    assert apply_safety(Command(surge=1), ArmState.ARMED, Mode.MANUAL, wd, 5.0).is_zero()


def test_hold_modes_not_subject_to_watchdog():
    wd = InputWatchdog()  # never fed
    cmd = Command(heave=0.5, yaw=0.5)
    assert apply_safety(cmd, ArmState.ARMED, Mode.DEPTH_HOLD, wd, 5.0).heave == 0.5
    assert apply_safety(cmd, ArmState.ARMED, Mode.HEADING_HOLD, wd, 5.0).yaw == 0.5


def test_command_is_clamped():
    wd = InputWatchdog(); wd.feed(0)
    out = apply_safety(Command(surge=5, sway=-5), ArmState.ARMED, Mode.MANUAL, wd, 0)
    assert out.surge == 1 and out.sway == -1

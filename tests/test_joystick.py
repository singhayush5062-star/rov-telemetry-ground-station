from gui.joystick import apply_dead_zone, axes_to_command, AxisMap, DEAD_ZONE


def test_dead_zone_zeroes_small_values_and_rescales():
    assert apply_dead_zone(0.05) == 0.0
    assert apply_dead_zone(-0.1) == 0.0
    assert apply_dead_zone(1.0) == 1.0
    assert apply_dead_zone(-1.0) == -1.0
    mid = apply_dead_zone(DEAD_ZONE + (1 - DEAD_ZONE) / 2)
    assert abs(mid - 0.5) < 1e-9


def test_axis_mapping_and_surge_inversion():
    axes = {0: 0.5, 1: -1.0, 3: 0.3, 4: 0.8}
    cmd = axes_to_command(lambda i: axes.get(i, 0.0), n_axes=6)
    assert cmd.surge == 1.0                  # stick pushed up (-1) -> full forward
    assert abs(cmd.sway - apply_dead_zone(0.5)) < 1e-9
    assert abs(cmd.yaw - apply_dead_zone(0.3)) < 1e-9
    assert abs(cmd.heave - apply_dead_zone(0.8)) < 1e-9


def test_missing_axes_read_as_zero():
    cmd = axes_to_command(lambda i: 1.0, n_axes=2, m=AxisMap())
    assert cmd.yaw == 0.0 and cmd.heave == 0.0 and cmd.sway == 1.0 and cmd.surge == -1.0

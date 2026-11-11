import csv
from logging_util.csv_logger import CsvLogger, FIELDS
from rov_sim.simulator import ROVState


def test_logger_writes_header_and_rows(tmp_path):
    lg = CsvLogger(tmp_path)
    assert not lg.active
    path = lg.start()
    s = ROVState(t=1.5, depth=2.25, yaw=90.0, battery_v=16.1)
    lg.log(s, "ARMED", "Manual", 18.52, 73.85)
    lg.log(s, "ARMED", "Depth Hold", 18.52, 73.85)
    assert lg.stop() == path and not lg.active
    with open(path) as fh:
        rows = list(csv.DictReader(fh))
    assert list(rows[0].keys()) == FIELDS
    assert len(rows) == 2
    assert rows[0]["depth_m"] == "2.250" and rows[1]["mode"] == "Depth Hold"


def test_log_is_noop_when_inactive(tmp_path):
    lg = CsvLogger(tmp_path)
    lg.log(ROVState(), "DISARMED", "Manual", 0, 0)   # must not raise
    assert lg.rows == 0 and lg.stop() is None

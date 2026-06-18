from app.sensors import get_user_controller_macs, check_sensor_access


class TestGetUserControllerMacs:
    def test_returns_empty_for_user_with_no_controllers(self):
        macs = get_user_controller_macs(999)
        assert macs == []

    def test_returns_macs_for_user_with_controllers(self, sample_data):
        macs = get_user_controller_macs(1)
        assert "AA:BB:CC:DD:EE:FF" in macs
        assert len(macs) == 1

    def test_returns_multiple_macs_when_assigned(self, db, sample_data):
        db.execute(
            "INSERT INTO user_controllers (user_id, controller_mac) VALUES (?, ?)",
            (1, "11:22:33:44:55:66"),
        )
        db.commit()
        macs = get_user_controller_macs(1)
        assert len(macs) == 2


class TestCheckSensorAccess:
    def test_returns_sensor_data_when_accessible(self, sample_data):
        row = check_sensor_access(1, 1)
        assert row is not None
        assert row[0] == 1
        assert row[1] == "SENSOR-001"
        assert row[2] == "Living Room"

    def test_returns_none_when_no_controllers(self):
        row = check_sensor_access(1, 999)
        assert row is None

    def test_returns_none_when_sensor_not_in_user_controllers(self, sample_data):
        row = check_sensor_access(3, 1)
        assert row is None

    def test_returns_none_for_nonexistent_sensor(self, sample_data):
        row = check_sensor_access(999, 1)
        assert row is None

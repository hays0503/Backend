"""B-00a: pydantic in requirements.

Regression: Test that pydantic is importable and present in requirements.
Behavioral: Test that schemas import correctly.
"""
import os
import time


class TestPydanticInstalled:
    """Regression: pydantic must be importable."""

    def test_pydantic_importable(self):
        import pydantic
        assert hasattr(pydantic, "BaseModel")

    def test_pydantic_version_2(self):
        import pydantic
        assert int(pydantic.__version__.split(".")[0]) >= 2


class TestSchemasImport:
    """Behavioral: schemas module must import cleanly."""

    def test_import_reading_item(self):
        from app.schemas import ReadingItem
        assert ReadingItem is not None

    def test_import_sensor_data_batch(self):
        from app.schemas import SensorDataBatch
        assert SensorDataBatch is not None

    def test_import_login_request(self):
        from app.schemas import LoginRequest
        assert LoginRequest is not None

    def test_import_use_schema(self):
        from app.schemas import use_schema
        assert callable(use_schema)

    def test_reading_item_validates(self):
        from app.schemas import ReadingItem
        item = ReadingItem(address="SENSOR-001", temperature=22.5, recorded_at=1000)
        assert item.address == "SENSOR-001"
        assert item.temperature == 22.5

    def test_sensor_data_batch_validates(self, app):
        from app.schemas import SensorDataBatch
        with app.app_context():
            now_ms = int(time.time() * 1000)
            batch = SensorDataBatch(
                controller_mac="AA:BB:CC:DD:EE:FF",
                readings=[{"address": "S1", "temperature": 20.0, "recorded_at": now_ms}],
            )
            assert len(batch.readings) == 1


class TestRequirementsTxt:
    """Behavioral: requirements.txt must list pydantic."""

    def test_pydantic_in_requirements(self):
        req_path = os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
        with open(req_path) as f:
            content = f.read().lower()
        assert "pydantic" in content

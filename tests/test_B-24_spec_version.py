"""B-24: spec_version handshake + sentinel rejection (X-04).

- `spec_version` is accepted by the schema and reflected in responses.
- Sentinel values (e.g. -127.0 disconnected) are rejected at ingestion.
- Values outside the shared spec valid range are rejected.
"""
import time

import pytest

from app import temperature_spec as spec


def _batch(controller_mac="AA:BB:CC:DD:EE:FF", temperature=20.0, recorded_at=None):
    ts = int(time.time() * 1000) if recorded_at is None else recorded_at
    return {
        "controller_mac": controller_mac,
        "spec_version": spec.SPEC_VERSION,
        "readings": [
            {"address": "S-SPEC-1", "temperature": temperature, "recorded_at": ts}
        ],
    }


class TestSpecVersionHandshake:
    def test_spec_version_constant_matches_json(self):
        import json
        from pathlib import Path

        spec_path = (
            Path(__file__).resolve().parent.parent.parent
            / "shared"
            / "temperature-spec.json"
        )
        with open(spec_path, encoding="utf-8") as fh:
            assert json.load(fh)["version"] == spec.SPEC_VERSION

    def test_payload_with_spec_version_accepted(
        self, app, client, device_key_data, device_headers
    ):
        resp = client.post(
            "/api/sensor/data",
            json=_batch(),
            headers=device_headers,
        )
        assert resp.status_code in (200, 201)

    def test_payload_without_spec_version_accepted(
        self, app, client, device_key_data, device_headers
    ):
        body = _batch()
        body.pop("spec_version")
        resp = client.post("/api/sensor/data", json=body, headers=device_headers)
        assert resp.status_code in (200, 201)


class TestSentinelRejection:
    def test_disconnected_sentinel_rejected(
        self, app, client, device_key_data, device_headers
    ):
        resp = client.post(
            "/api/sensor/data",
            json=_batch(temperature=spec.SENTINEL_DISCONNECTED),
            headers=device_headers,
        )
        assert resp.status_code == 400

    def test_wait_conversion_sentinel_rejected(
        self, app, client, device_key_data, device_headers
    ):
        resp = client.post(
            "/api/sensor/data",
            json=_batch(temperature=spec.SENTINEL_WAIT_CONVERSION),
            headers=device_headers,
        )
        assert resp.status_code == 400

    @pytest.mark.parametrize(
        "temperature", [-200.0, 500.0]
    )
    def test_out_of_range_rejected(
        self, app, client, device_key_data, device_headers, temperature
    ):
        resp = client.post(
            "/api/sensor/data",
            json=_batch(temperature=temperature),
            headers=device_headers,
        )
        assert resp.status_code == 400

    def test_spec_helpers(self):
        assert spec.is_sentinel(spec.SENTINEL_DISCONNECTED)
        assert spec.is_sentinel(spec.SENTINEL_WAIT_CONVERSION)
        assert not spec.is_sentinel(20.0)
        assert spec.is_valid(20.0)
        assert not spec.is_valid(spec.SENTINEL_DISCONNECTED)
        assert not spec.is_valid(200.0)

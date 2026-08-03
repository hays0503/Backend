"""B-12: API key auth for ingestion.

Regression: ingestion without device key is rejected.
Behavioral: API key tied to controller MAC; hash-only storage.
"""
from app.device_auth import hash_api_key


class TestDeviceKeyRequired:
    """Regression: ingestion endpoint requires device key (X-Device-Key header)."""

    def test_ingestion_without_device_key_rejected(self, app, client):
        resp = client.post(
            "/api/sensor/data",
            json={
                "controller_mac": "AA:BB:CC:DD:EE:FF",
                "readings": [{"address": "S1", "temperature": 22.0, "recorded_at": 1000}],
            },
        )
        assert resp.status_code in (401, 403), (
            f"Ingestion without device key should be rejected, got {resp.status_code}"
        )

    def test_ingestion_with_invalid_device_key_rejected(self, app, client):
        resp = client.post(
            "/api/sensor/data",
            headers={"X-Device-Key": "invalid-key-value"},
            json={
                "controller_mac": "AA:BB:CC:DD:EE:FF",
                "readings": [{"address": "S1", "temperature": 22.0, "recorded_at": 1000}],
            },
        )
        assert resp.status_code in (401, 403), (
            f"Ingestion with invalid device key should be rejected, got {resp.status_code}"
        )


class TestAPIKeyStorage:
    """Behavioral: API keys should be stored as hashes only."""

    def test_api_key_not_stored_in_plaintext(self, app, db):
        from app.device_auth import hash_api_key, store_api_key

        plain_key = "ysd-test-plain-key-not-hashed"
        hash_api_key(plain_key)
        store_api_key(db, "00:01:02:03:04:05", plain_key)
        row = db.execute(
            "SELECT key_hash FROM controller_api_keys WHERE controller_mac = ?",
            ("00:01:02:03:04:05",),
        ).fetchone()
        assert row is not None, "store_api_key should persist a key row"
        stored = row[0]
        assert stored != plain_key, "API key must not be stored in plaintext"
        assert stored == hash_api_key(plain_key), (
            "stored value should be the SHA-256 hash of the key"
        )

    def test_api_key_tied_to_controller_mac(self, app, db):
        from app.device_auth import set_api_key

        plain_key = set_api_key(db, "00:01:02:03:04:05")
        assert plain_key.startswith("ysd-"), "generated keys should use the ysd- prefix"
        assert len(plain_key) > 20, "generated keys should have enough entropy"
        rows = db.execute(
            "SELECT controller_mac FROM controller_api_keys "
            "WHERE key_hash = ?",
            (hash_api_key(plain_key),),
        ).fetchall()
        macs = [r[0] for r in rows]
        assert macs == ["00:01:02:03:04:05"], (
            f"key should be tied to exactly one controller, got: {macs}"
        )

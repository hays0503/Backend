"""B-12: API key auth for ingestion.

Regression: ingestion without device key is rejected.
Behavioral: API key tied to controller MAC; salted hash-only storage;
soft revocation; rotation; constant-time comparison.
"""
import time

from app.device_auth import hash_api_key, verify_device_key


def _ts():
    return int(time.time() * 1000)


class TestDeviceKeyRequired:
    """Regression: ingestion endpoint requires device key (X-Device-Key header)."""

    def test_ingestion_without_device_key_rejected(self, app, client):
        resp = client.post(
            "/api/sensor/data",
            json={
                "controller_mac": "AA:BB:CC:DD:EE:FF",
                "readings": [{"address": "S1", "temperature": 22.0, "recorded_at": _ts()}],
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
                "readings": [{"address": "S1", "temperature": 22.0, "recorded_at": _ts()}],
            },
        )
        assert resp.status_code in (401, 403), (
            f"Ingestion with invalid device key should be rejected, got {resp.status_code}"
        )

    def test_mac_mismatch_rejected(self, app, client, db):
        """A valid key bound to one MAC must not accept another MAC's payload."""
        from app.device_auth import set_api_key

        key_a = set_api_key(db, "AA:BB:CC:DD:EE:FF")
        db.execute(
            "INSERT OR IGNORE INTO controllers (mac, first_seen, last_seen, sensor_count) "
            "VALUES (?, 0, 0, 0)",
            ("00:DE:AD:BE:EF:00",),
        )
        db.commit()
        resp = client.post(
            "/api/sensor/data",
            headers={"X-Device-Key": key_a},
            json={
                "controller_mac": "00:DE:AD:BE:EF:00",
                "readings": [{"address": "S1", "temperature": 22.0, "recorded_at": _ts()}],
            },
        )
        assert resp.status_code == 401, (
            f"Key for MAC A must not authenticate MAC B, got {resp.status_code}"
        )

    def test_revoked_key_rejected(self, app, client, db):
        from app.device_auth import remove_api_key, set_api_key

        plain_key = set_api_key(db, "AA:BB:CC:DD:EE:FF")
        remove_api_key(db, "AA:BB:CC:DD:EE:FF")
        resp = client.post(
            "/api/sensor/data",
            headers={"X-Device-Key": plain_key},
            json={
                "controller_mac": "AA:BB:CC:DD:EE:FF",
                "readings": [{"address": "S1", "temperature": 22.0, "recorded_at": _ts()}],
            },
        )
        assert resp.status_code == 401, (
            f"Revoked device key should be rejected, got {resp.status_code}"
        )

    def test_rotation_invalidates_old_key(self, app, client, db):
        from app.device_auth import set_api_key

        old_key = set_api_key(db, "AA:BB:CC:DD:EE:FF")
        new_key = set_api_key(db, "AA:BB:CC:DD:EE:FF")
        assert old_key != new_key
        payload = {
            "controller_mac": "AA:BB:CC:DD:EE:FF",
            "readings": [{"address": "S1", "temperature": 22.0, "recorded_at": _ts()}],
        }
        old_resp = client.post(
            "/api/sensor/data", headers={"X-Device-Key": old_key}, json=payload
        )
        assert old_resp.status_code == 401, "rotated-out key should be rejected"
        new_resp = client.post(
            "/api/sensor/data", headers={"X-Device-Key": new_key}, json=payload
        )
        assert new_resp.status_code == 201, "new key should be accepted"


class TestAPIKeyStorage:
    """Behavioral: API keys should be stored as salted hashes only."""

    def test_api_key_not_stored_in_plaintext(self, app, db):
        from app.device_auth import store_api_key

        plain_key = "ysd-test-plain-key-not-hashed"
        store_api_key(db, "00:01:02:03:04:05", plain_key)
        row = db.execute(
            "SELECT key_hash, salt FROM controller_api_keys WHERE controller_mac = ?",
            ("00:01:02:03:04:05",),
        ).fetchone()
        assert row is not None, "store_api_key should persist a key row"
        stored, salt = row[0], row[1]
        assert stored != plain_key, "API key must not be stored in plaintext"
        assert salt, "a per-key salt must be generated"
        assert stored != hash_api_key(plain_key), "hash must be salted"
        assert verify_device_key(plain_key, stored, salt), (
            "stored hash should verify against the plain key with its salt"
        )

    def test_api_key_tied_to_controller_mac(self, app, db):
        from app.device_auth import set_api_key

        plain_key = set_api_key(db, "00:01:02:03:04:05")
        assert plain_key.startswith("ysd-"), "generated keys should use the ysd- prefix"
        assert len(plain_key) > 20, "generated keys should have enough entropy"
        row = db.execute(
            "SELECT key_hash, salt FROM controller_api_keys "
            "WHERE controller_mac = ?",
            ("00:01:02:03:04:05",),
        ).fetchone()
        assert row is not None
        assert verify_device_key(plain_key, row[0], row[1]), (
            "key should verify against the stored hash for its MAC"
        )

    def test_verify_is_constant_time(self, app, db):
        from app.device_auth import generate_api_key, verify_device_key

        _, key_hash, salt = generate_api_key()
        wrong = "ysd-" + "0" * 48
        assert not verify_device_key(wrong, key_hash, salt), (
            "wrong key must not verify"
        )

    def test_legacy_unsalted_hash_still_verifies(self, app, db):
        """Rows stored before salting (salt='') must keep working."""
        plain_key = "legacy-unsalted-key"
        db.execute(
            "INSERT OR REPLACE INTO controller_api_keys "
            "(controller_mac, key_hash, salt, is_active, created_at) "
            "VALUES (?, ?, '', 1, 0)",
            ("00:01:02:03:04:05", hash_api_key(plain_key)),
        )
        db.commit()
        assert verify_device_key(plain_key, hash_api_key(plain_key), ""), (
            "legacy unsalted row should verify"
        )


class TestLogOnlyMode:
    """Compatibility window: DEVICE_AUTH_LOG_ONLY logs but accepts (rollout)."""

    def test_log_only_accepts_missing_key(self, app, client, monkeypatch):
        monkeypatch.setattr("app.config.Config.DEVICE_AUTH_LOG_ONLY", True)
        resp = client.post(
            "/api/sensor/data",
            json={
                "controller_mac": "AA:BB:CC:DD:EE:FF",
                "readings": [{"address": "S1", "temperature": 22.0, "recorded_at": _ts()}],
            },
        )
        assert resp.status_code in (200, 201), (
            f"log-only mode must accept missing key, got {resp.status_code}"
        )

    def test_log_only_accepts_invalid_key(self, app, client, monkeypatch):
        monkeypatch.setattr("app.config.Config.DEVICE_AUTH_LOG_ONLY", True)
        resp = client.post(
            "/api/sensor/data",
            headers={"X-Device-Key": "wrong-key"},
            json={
                "controller_mac": "AA:BB:CC:DD:EE:FF",
                "readings": [{"address": "S1", "temperature": 22.0, "recorded_at": _ts()}],
            },
        )
        assert resp.status_code in (200, 201), (
            f"log-only mode must accept invalid key, got {resp.status_code}"
        )

    def test_log_only_logs_warning(self, app, client, monkeypatch, caplog):
        monkeypatch.setattr("app.config.Config.DEVICE_AUTH_LOG_ONLY", True)
        with caplog.at_level("WARNING"):
            client.post(
                "/api/sensor/data",
                json={
                    "controller_mac": "AA:BB:CC:DD:EE:FF",
                    "readings": [{"address": "S1", "temperature": 22.0, "recorded_at": _ts()}],
                },
            )
        assert "log-only" in caplog.text, (
            "log-only mode must emit a warning for unauthenticated ingestion"
        )

    def test_log_only_off_enforces_by_default(self, app, client):
        resp = client.post(
            "/api/sensor/data",
            json={
                "controller_mac": "AA:BB:CC:DD:EE:FF",
                "readings": [{"address": "S1", "temperature": 22.0, "recorded_at": _ts()}],
            },
        )
        assert resp.status_code in (401, 403), (
            f"enforcement is the default, got {resp.status_code}"
        )

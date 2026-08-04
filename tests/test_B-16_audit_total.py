"""B-16: Audit response has 'total' field.

Regression: audit response includes 'total' count.
Behavioral: pagination works with total field.
"""


class TestAuditTotalField:
    """Regression: audit response must include 'total' field."""

    def test_audit_response_has_total(self, app, client, admin_headers):
        resp = client.get("/api/admin/audit", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total" in data, (
            f"Audit response should have 'total' field, got keys: {list(data.keys())}"
        )

    def test_audit_total_is_integer(self, app, client, admin_headers):
        resp = client.get("/api/admin/audit", headers=admin_headers)
        data = resp.get_json()
        assert isinstance(data["total"], int)


class TestAuditPagination:
    """Behavioral: audit pagination should work with total field."""

    def test_audit_pagination_with_limit(self, app, client, admin_headers):
        resp = client.get("/api/admin/audit?limit=5", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total" in data
        assert "logs" in data
        assert len(data["logs"]) <= 5

    def test_audit_pagination_with_offset(self, app, client, admin_headers):
        resp1 = client.get("/api/admin/audit?limit=2&offset=0", headers=admin_headers)
        resp2 = client.get("/api/admin/audit?limit=2&offset=2", headers=admin_headers)
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        data1 = resp1.get_json()
        data2 = resp2.get_json()
        assert data1["total"] == data2["total"]

    def test_audit_total_matches_actual_count(self, app, client, admin_headers, db):
        resp = client.get("/api/admin/audit", headers=admin_headers)
        data = resp.get_json()
        actual_count = db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        assert data["total"] == actual_count, (
            f"Total {data['total']} should match actual count {actual_count}"
        )

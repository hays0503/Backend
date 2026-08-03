"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-03

"""
import time

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "controllers",
        sa.Column("mac", sa.Text, primary_key=True),
        sa.Column("first_seen", sa.Integer, nullable=False),
        sa.Column("last_seen", sa.Integer, nullable=False),
        sa.Column("sensor_count", sa.Integer, server_default="0"),
    )

    op.create_table(
        "sensors",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("sensor_address", sa.Text, nullable=False),
        sa.Column(
            "controller_mac",
            sa.Text,
            sa.ForeignKey("controllers.mac"),
            nullable=False,
        ),
        sa.Column("location", sa.Text),
        sa.UniqueConstraint("controller_mac", "sensor_address"),
    )

    op.create_table(
        "readings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "sensor_id", sa.Integer, sa.ForeignKey("sensors.id"), nullable=False
        ),
        sa.Column("temperature", sa.Float, nullable=False),
        sa.Column("recorded_at", sa.Integer, nullable=False),
        sa.UniqueConstraint("sensor_id", "recorded_at"),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.Text, unique=True, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False, server_default="user"),
        sa.Column("created_at", sa.Integer, nullable=False),
    )

    op.create_table(
        "user_controllers",
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "controller_mac",
            sa.Text,
            sa.ForeignKey("controllers.mac"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id", "controller_mac"),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("username", sa.Text, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("target_type", sa.Text),
        sa.Column("target_id", sa.Text),
        sa.Column("details", sa.Text),
        sa.Column("created_at", sa.Integer, nullable=False),
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("jti", sa.Text, unique=True, nullable=False),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("token_version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("expires_at", sa.Integer, nullable=False),
        sa.Column("revoked_at", sa.Integer),
        sa.Column("created_at", sa.Integer, nullable=False),
    )

    op.create_table(
        "controller_api_keys",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "controller_mac",
            sa.Text,
            sa.ForeignKey("controllers.mac"),
            nullable=False,
            unique=True,
        ),
        sa.Column("key_hash", sa.Text, nullable=False),
        sa.Column("created_at", sa.Integer, nullable=False),
    )

    op.create_table(
        "schema_version",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("applied_at", sa.Integer, nullable=False),
    )

    op.execute(
        "INSERT INTO schema_version (version, applied_at) "
        f"VALUES (1, {int(time.time())})"
    )

    op.execute(
        "CREATE INDEX idx_readings_sensor_time "
        "ON readings(sensor_id, recorded_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_auth_sessions_user ON auth_sessions(user_id)"
    )
    op.execute("CREATE INDEX idx_auth_sessions_jti ON auth_sessions(jti)")
    op.execute(
        "CREATE INDEX idx_sensors_controller_mac ON sensors(controller_mac)"
    )
    op.execute(
        "CREATE INDEX idx_user_controllers_controller_mac "
        "ON user_controllers(controller_mac)"
    )
    op.execute(
        "CREATE INDEX idx_audit_log_created_at ON audit_log(created_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_controllers_last_seen ON controllers(last_seen DESC)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_controllers_last_seen")
    op.execute("DROP INDEX IF EXISTS idx_audit_log_created_at")
    op.execute("DROP INDEX IF EXISTS idx_user_controllers_controller_mac")
    op.execute("DROP INDEX IF EXISTS idx_sensors_controller_mac")
    op.execute("DROP INDEX IF EXISTS idx_auth_sessions_jti")
    op.execute("DROP INDEX IF EXISTS idx_auth_sessions_user")
    op.execute("DROP INDEX IF EXISTS idx_readings_sensor_time")
    op.drop_table("schema_version")
    op.drop_table("controller_api_keys")
    op.drop_table("auth_sessions")
    op.drop_table("audit_log")
    op.drop_table("user_controllers")
    op.drop_table("users")
    op.drop_table("readings")
    op.drop_table("sensors")
    op.drop_table("controllers")

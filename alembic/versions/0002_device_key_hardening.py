"""device API key hardening

Adds per-key salt (16 bytes), soft-revocation flags and an (mac, is_active)
index to ``controller_api_keys`` so keys can be rotated/revoked without
deleting the row and verified against a salted hash in constant time.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-03

"""
import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "controller_api_keys",
        sa.Column("salt", sa.Text, nullable=False, server_default=""),
    )
    op.add_column(
        "controller_api_keys",
        sa.Column("is_active", sa.Integer, nullable=False, server_default="1"),
    )
    op.add_column(
        "controller_api_keys",
        sa.Column("revoked_at", sa.Integer),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_controller_api_keys_mac_active "
        "ON controller_api_keys(controller_mac, is_active)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_controller_api_keys_mac_active")
    op.drop_column("controller_api_keys", "revoked_at")
    op.drop_column("controller_api_keys", "is_active")
    op.drop_column("controller_api_keys", "salt")

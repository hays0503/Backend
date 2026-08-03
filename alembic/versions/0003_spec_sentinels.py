"""purge sentinel readings + constrain temperature

Removes any previously-ingested readings that hold spec sentinel values
(e.g. -127.0 disconnected) or fall outside the valid temperature range,
then locks the bounds with CHECK constraints so the API contract
(shared/temperature-spec.json) cannot be violated at the storage layer.

SQLite does not support ``ALTER TABLE ADD CONSTRAINT``, so the table is
recreated via Alembic's batch mode (reflect -> create -> copy -> rename).

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-03

"""
import json
from pathlib import Path

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_SPEC_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "shared"
    / "temperature-spec.json"
)


def _bounds():
    with open(_SPEC_PATH, encoding="utf-8") as fh:
        spec = json.load(fh)
    vr = spec["validRange"]
    sentinels = [float(v) for v in set(spec["sentinels"].values())]
    return float(vr["min"]), float(vr["max"]), sentinels


def _fmt(nums):
    return ", ".join(repr(n) for n in nums)


def upgrade():
    tmin, tmax, sentinels = _bounds()
    op.execute(
        f"DELETE FROM readings WHERE temperature IN ({_fmt(sentinels)}) "
        f"OR temperature < {tmin} OR temperature > {tmax}"
    )
    with op.batch_alter_table("readings", recreate="always") as batch_op:
        batch_op.create_check_constraint(
            "chk_readings_temperature",
            f"temperature >= {tmin} AND temperature <= {tmax}",
        )
        batch_op.create_check_constraint(
            "chk_readings_not_sentinel",
            f"temperature NOT IN ({_fmt(sentinels)})",
        )


def downgrade():
    with op.batch_alter_table("readings", recreate="always") as batch_op:
        batch_op.drop_constraint("chk_readings_not_sentinel", type_="check")
        batch_op.drop_constraint("chk_readings_temperature", type_="check")

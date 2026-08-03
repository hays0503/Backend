"""Single source of truth for the YESCADA temperature specification.

Loads ``shared/temperature-spec.json`` (repository root) and exposes the
values consumed by the Backend: the streamed ``spec_version`` handshake,
the sentinel values that must be rejected during ingestion, and the valid
temperature range used by schema validation.

The JSON file is the canonical document; editing thresholds in this module
will be overwritten the next time the file changes. Bump ``version`` in the
JSON (semver) and mirror it into ``HDataSync.cpp`` and the Emulator.
"""

import json
from pathlib import Path

_SPEC_PATH = (
    Path(__file__).resolve().parent.parent.parent / "shared" / "temperature-spec.json"
)

_SPEC: dict = json.loads(_SPEC_PATH.read_text(encoding="utf-8"))

SPEC_VERSION: str = str(_SPEC["version"])

VALID_RANGE_MIN: float = float(_SPEC["validRange"]["min"])
VALID_RANGE_MAX: float = float(_SPEC["validRange"]["max"])

SENTINEL_DISCONNECTED: float = float(_SPEC["sentinels"]["disconnected"])
SENTINEL_WAIT_CONVERSION: float = float(_SPEC["sentinels"]["waitConversion"])
SENTINELS: frozenset[float] = frozenset(
    {SENTINEL_DISCONNECTED, SENTINEL_WAIT_CONVERSION}
)

ALARM_HIGH: float = float(_SPEC["alarms"]["high"])
ALARM_LOW: float = float(_SPEC["alarms"]["low"])


def is_sentinel(temperature: float) -> bool:
    """Return True for spec-defined sentinel values (e.g. disconnected sensor).

    Controllers use these markers for non-measurements; they must never be
    persisted as real readings or surface on the monitoring chart.
    """
    return temperature in SENTINELS


def is_valid(temperature: float) -> bool:
    return (
        VALID_RANGE_MIN <= temperature <= VALID_RANGE_MAX
        and not is_sentinel(temperature)
    )

"""Decoders for the manufacturer-data payloads our sensors broadcast.

The firmware puts a msg_type byte first; each device kind registers a parser
here. Adding a future device (e.g. the sleepwalking sensor) means adding one
parser function -- nothing else in the service changes.

Byte layout (after the 0xFFFF company ID, which bleak strips):
  msg_type(1) schema(1) door_state(1) battery(1) seq(2 LE) field(2 LE, 0.1 mT)
"""

import logging
import struct

log = logging.getLogger("codec")

_PARSERS = {}


def register(msg_type: int):
    def decorator(fn):
        _PARSERS[msg_type] = fn
        return fn
    return decorator


def parse(data: bytes) -> dict | None:
    """Decode a manufacturer-data payload; None if unknown or malformed."""
    if len(data) < 2:
        return None
    parser = _PARSERS.get(data[0])
    if parser is None:
        return None
    try:
        return parser(data)
    except Exception:
        log.warning("Failed to parse payload %s", data.hex(), exc_info=True)
        return None


DOOR_MSG_TYPE = 0xD5
DOOR_SCHEMA_VERSION = 1
DOOR_STATES = {0x00: "closed", 0x01: "open", 0x02: "tamper", 0xFF: "fault"}


@register(DOOR_MSG_TYPE)
def _parse_door_sensor(data: bytes) -> dict | None:
    _, schema, state, battery, seq, field = struct.unpack("<BBBBHh", data[:8])
    if schema != DOOR_SCHEMA_VERSION:
        log.warning("Unknown door sensor schema version %d", schema)
        return None
    return {
        "device_type": "door-sensor",
        "state": DOOR_STATES.get(state, f"unknown(0x{state:02X})"),
        "battery": None if battery == 0xFF else battery,
        "seq": seq,
        "field_mt": field / 10.0,
    }

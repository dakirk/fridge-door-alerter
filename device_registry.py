"""In-memory state for every sensor we've heard from.

Deliberately no persistence: the registry rebuilds itself from live
advertisements within seconds of a restart.
"""

from __future__ import annotations

import collections
import logging
import time
from dataclasses import dataclass

log = logging.getLogger("registry")

# A sequence number this far below the previous one is a firmware reboot,
# not a uint16 wraparound.
_SEQ_REBOOT_MARGIN = 100


@dataclass
class Device:
    mac: str
    device_type: str
    state: str = "unknown"
    battery: int | None = None
    seq: int | None = None
    field_mt: float | None = None
    rssi: int | None = None
    first_seen: float = 0.0
    last_seen: float = 0.0
    opened_at: float | None = None  # wall time the current open episode began


class DeviceRegistry:
    def __init__(self, max_events: int = 50):
        self.devices: dict[str, Device] = {}
        self.events: collections.deque = collections.deque(maxlen=max_events)

    def add_event(self, text: str) -> None:
        self.events.appendleft((time.time(), text))
        log.info(text)

    def update(self, mac: str, parsed: dict, rssi: int | None) -> None:
        """Apply one decoded advertisement. Called for every packet received,
        including rebroadcasts of an unchanged payload."""
        now = time.time()
        dev = self.devices.get(mac)
        is_new = dev is None
        if is_new:
            dev = Device(mac=mac, device_type=parsed["device_type"], first_seen=now)
            self.devices[mac] = dev
            self.add_event(f"{mac}: discovered {parsed['device_type']}, "
                           f"state {parsed['state']}")

        if (dev.seq is not None
                and parsed["seq"] < dev.seq
                and dev.seq - parsed["seq"] > _SEQ_REBOOT_MARGIN):
            self.add_event(f"{mac}: sensor rebooted "
                           f"(seq {dev.seq} -> {parsed['seq']})")

        old_state = dev.state
        dev.state = parsed["state"]
        dev.battery = parsed["battery"]
        dev.seq = parsed["seq"]
        dev.field_mt = parsed["field_mt"]
        dev.rssi = rssi
        dev.last_seen = now

        if dev.state != old_state:
            if not is_new:
                self.add_event(f"{mac}: {old_state} -> {dev.state}")
            if dev.state == "open":
                dev.opened_at = now
            elif old_state == "open":
                dev.opened_at = None

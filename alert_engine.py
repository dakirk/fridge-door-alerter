"""Periodic checks over the registry: door open too long, sensor offline,
battery low. All alert timing lives here, Pi-side -- the firmware just
broadcasts raw state."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

log = logging.getLogger("alerts")

CHECK_PERIOD_SECONDS = 10


@dataclass
class _Bookkeeping:
    last_open_alert: float | None = None  # None = no alert this open episode
    offline_alerted: bool = False
    last_battery_alert: float = 0.0


class AlertEngine:
    def __init__(self, registry, notifier, cfg: dict):
        self._registry = registry
        self._notifier = notifier
        self._open_threshold = cfg["open_threshold_seconds"]
        self._realert_interval = cfg["realert_minutes"] * 60
        self._offline_threshold = cfg["offline_minutes"] * 60
        self._battery_low = cfg["battery_low_percent"]
        self._send_recovery = cfg["send_recovery"]
        self._bookkeeping: dict[str, _Bookkeeping] = {}

    def is_alerting(self, mac: str) -> bool:
        """True if this device currently has an active alert (for the web UI)."""
        bk = self._bookkeeping.get(mac)
        return bk is not None and (bk.last_open_alert is not None or bk.offline_alerted)

    async def run(self) -> None:
        while True:
            await asyncio.sleep(CHECK_PERIOD_SECONDS)
            try:
                await self._check_all(time.time())
            except Exception:
                log.exception("Alert check failed")

    async def _check_all(self, now: float) -> None:
        for mac, dev in list(self._registry.devices.items()):
            bk = self._bookkeeping.setdefault(mac, _Bookkeeping())
            await self._check_door_open(now, dev, bk)
            await self._check_offline(now, dev, bk)
            await self._check_battery(now, dev, bk)

    async def _check_door_open(self, now, dev, bk) -> None:
        if dev.state == "open" and dev.opened_at is not None:
            open_for = now - dev.opened_at
            if open_for < self._open_threshold:
                return
            if (bk.last_open_alert is None
                    or now - bk.last_open_alert >= self._realert_interval):
                await self._notifier.send(
                    "Fridge door open",
                    f"The fridge door has been open for {open_for / 60:.0f} min.",
                    priority="high",
                    tags="rotating_light",
                )
                bk.last_open_alert = now
        else:
            if bk.last_open_alert is not None and dev.state == "closed":
                if self._send_recovery:
                    await self._notifier.send(
                        "Fridge door closed",
                        "The fridge door is closed again.",
                        tags="white_check_mark",
                    )
            bk.last_open_alert = None

    async def _check_offline(self, now, dev, bk) -> None:
        if now - dev.last_seen >= self._offline_threshold:
            if not bk.offline_alerted:
                await self._notifier.send(
                    "Fridge sensor offline",
                    f"No broadcast from {dev.mac} for "
                    f"{(now - dev.last_seen) / 60:.0f} min "
                    "(dead battery or out of range?).",
                    tags="warning",
                )
                bk.offline_alerted = True
        elif bk.offline_alerted:
            bk.offline_alerted = False
            self._registry.add_event(f"{dev.mac}: back online")

    async def _check_battery(self, now, dev, bk) -> None:
        if (dev.battery is not None
                and dev.battery < self._battery_low
                and now - bk.last_battery_alert >= 24 * 3600):
            await self._notifier.send(
                "Fridge sensor battery low",
                f"Sensor {dev.mac} battery at {dev.battery}%.",
                tags="battery",
            )
            bk.last_battery_alert = now

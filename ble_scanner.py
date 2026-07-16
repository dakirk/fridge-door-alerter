"""Passive BLE listener: feeds decoded advertisements into the registry."""

import asyncio
import logging

from bleak import BleakScanner

import payload_codec

log = logging.getLogger("scanner")

# BLE SIG test/internal-use company ID used by our firmware's
# manufacturer-specific advertising data.
COMPANY_ID = 0xFFFF


class BleScannerService:
    def __init__(self, registry):
        self._registry = registry

    def _on_advertisement(self, device, adv) -> None:
        data = adv.manufacturer_data.get(COMPANY_ID)
        if data is None:
            return
        parsed = payload_codec.parse(data)
        if parsed is None:
            return
        self._registry.update(device.address, parsed, adv.rssi)

    async def run(self) -> None:
        log.info("Scanning for BLE advertisements (company ID 0x%04X)", COMPANY_ID)
        async with BleakScanner(detection_callback=self._on_advertisement):
            await asyncio.Event().wait()  # scan until cancelled

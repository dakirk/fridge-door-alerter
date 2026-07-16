"""Standalone reception check -- run this BEFORE setting up the full service.

Prints every advertisement from our sensors with a timestamp, so you can
verify the Pi hears both the slow closed-state heartbeat (10.24 s interval)
and the fast open-state rate (2 s). Ctrl-C to stop.

Usage: python scan_test.py
"""

import asyncio
import datetime

from bleak import BleakScanner

import payload_codec

COMPANY_ID = 0xFFFF


def on_advertisement(device, adv):
    data = adv.manufacturer_data.get(COMPANY_ID)
    if data is None:
        return
    parsed = payload_codec.parse(data)
    now = datetime.datetime.now().strftime("%H:%M:%S")
    if parsed is None:
        print(f"{now}  {device.address}  undecodable: {data.hex()}")
        return
    print(f"{now}  {device.address}  rssi {adv.rssi:>4}  "
          f"state={parsed['state']:<6}  battery={parsed['battery']}  "
          f"seq={parsed['seq']}  field={parsed['field_mt']:+.1f} mT")


async def main():
    print("Listening for door sensor advertisements (Ctrl-C to stop)...")
    async with BleakScanner(detection_callback=on_advertisement):
        await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

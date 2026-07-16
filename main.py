"""Entry point: wires the scanner, alert engine, and web server into one
asyncio event loop. Run with: python main.py"""

import asyncio
import logging
import pathlib
import sys
import tomllib

import uvicorn

from alert_engine import AlertEngine
from ble_scanner import BleScannerService
from device_registry import DeviceRegistry
from notifier import Notifier
from web import build_app

log = logging.getLogger("main")

DEFAULTS = {
    "ntfy": {"server": "https://ntfy.sh", "topic": ""},
    "alerts": {
        "open_threshold_seconds": 120,
        "realert_minutes": 10,
        "offline_minutes": 5,
        "battery_low_percent": 20,
        "send_recovery": True,
    },
    "web": {"host": "0.0.0.0", "port": 8000},
}


def load_config() -> dict:
    cfg = {section: dict(values) for section, values in DEFAULTS.items()}
    path = pathlib.Path(__file__).parent / "config.toml"
    if path.exists():
        with open(path, "rb") as f:
            for section, values in tomllib.load(f).items():
                cfg.setdefault(section, {}).update(values)
    else:
        log.warning("config.toml not found -- using defaults, ntfy disabled")
    return cfg


async def main() -> None:
    logging.basicConfig(
        stream=sys.stdout,  # systemd forwards stdout to journald
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    cfg = load_config()

    registry = DeviceRegistry()
    notifier = Notifier(cfg["ntfy"]["server"], cfg["ntfy"]["topic"])
    engine = AlertEngine(registry, notifier, cfg["alerts"])
    scanner = BleScannerService(registry)
    app = build_app(registry, engine, cfg["alerts"]["offline_minutes"])

    server = uvicorn.Server(uvicorn.Config(
        app,
        host=cfg["web"]["host"],
        port=cfg["web"]["port"],
        log_level="warning",
    ))

    tasks = [
        asyncio.create_task(scanner.run(), name="scanner"),
        asyncio.create_task(engine.run(), name="alerts"),
        asyncio.create_task(server.serve(), name="web"),
    ]
    # If any task dies (e.g. the BLE adapter disappears), take the whole
    # process down and let systemd restart it.
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    for task in done:
        task.result()  # re-raise the failure, exiting non-zero


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

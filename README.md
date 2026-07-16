# Fridge Door Alerter

Raspberry Pi companion to the Thunderboard Sense 2 fridge door sensor
firmware. Passively scans for the sensor's BLE advertisements, pushes an
[ntfy](https://ntfy.sh) notification when the door is open too long, and
serves a one-page status site.

Single asyncio process, all state in memory — a restart rebuilds everything
from live advertisements within seconds.

## Setup (on the Pi)

Requires Python 3.11+ and BlueZ (both standard on Raspberry Pi OS Bookworm).

```sh
cd ~/fridge-door-alerter
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 1. Verify reception first

With the sensor board powered somewhere nearby:

```sh
.venv/bin/python scan_test.py
```

You should see a line per received advertisement. Check both rates: with the
magnet held to the sensor (closed), packets arrive every ~10 s on battery
power; without it (open), every ~2 s. If the closed-state heartbeat is
spotty at the real fridge-to-Pi distance, shorten
`DOOR_SENSOR_ADV_SLOW_MS` in the firmware's `door_sensor.c`.

If scanning fails with a D-Bus/permission error, add yourself to the
bluetooth group: `sudo usermod -aG bluetooth $USER` (then log out and in).

### 2. Configure

```sh
cp config.example.toml config.toml
```

Set the ntfy topic to something unguessable, e.g.
`fridge-$(openssl rand -hex 8)` — it's the only thing protecting your
notifications — and subscribe to the same topic in the ntfy phone app.

### 3. Run

```sh
.venv/bin/python main.py
```

Status page: `http://<pi>:8000/`. Test the pipeline: hold the door "open"
(no magnet) for 2+ minutes → phone notification; restore the magnet →
recovery notification.

### 4. Install as a service

See the comments in `fridge-door-alerter.service`.

## Alert rules (all configurable in config.toml)

- Door open > 2 min → high-priority push, repeated every 10 min until closed,
  with a recovery note when it closes.
- No advertisements for 5 min → "sensor offline" (dead battery / range).
- Battery below 20% → push, at most once per day.

## Adding future sensors

A new broadcasting device (e.g. a sound+light sleepwalking sensor) needs a
new `msg_type` byte in the firmware and one decoder function in
`payload_codec.py`; the registry, status page, and scanner handle it
automatically. Alert rules for it go in `alert_engine.py`.

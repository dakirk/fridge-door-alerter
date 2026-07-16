"""The single GET / status page. No JSON API, no other endpoints."""

import html
import time
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

_STATE_COLORS = {"closed": "#2e7d32", "open": "#c62828",
                 "tamper": "#e65100", "fault": "#c62828"}


def _duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f} s"
    if seconds < 3600:
        return f"{seconds / 60:.0f} min"
    return f"{seconds / 3600:.1f} h"


def _ago(seconds: float) -> str:
    return _duration(seconds) + " ago"


def build_app(registry, alert_engine, offline_minutes: int) -> FastAPI:
    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    def status_page() -> str:
        now = time.time()
        rows = []
        for dev in registry.devices.values():
            offline = now - dev.last_seen >= offline_minutes * 60
            state = "offline" if offline else dev.state
            color = "#757575" if offline else _STATE_COLORS.get(dev.state, "#757575")
            open_for = ""
            if dev.state == "open" and dev.opened_at is not None and not offline:
                open_for = f" for {_duration(now - dev.opened_at)}"
            alert = " &#128680;" if alert_engine.is_alerting(dev.mac) else ""
            battery = f"{dev.battery}%" if dev.battery is not None else "n/a"
            field = f"{dev.field_mt:+.1f} mT" if dev.field_mt is not None else "?"
            rows.append(
                f"<tr><td>{html.escape(dev.device_type)}<br>"
                f"<small>{html.escape(dev.mac)}</small></td>"
                f"<td style='color:{color};font-weight:bold'>"
                f"{html.escape(state.upper())}{open_for}{alert}</td>"
                f"<td>{battery}</td><td>{field}</td>"
                f"<td>{dev.rssi if dev.rssi is not None else '?'} dBm</td>"
                f"<td>{_ago(now - dev.last_seen)}</td>"
                f"<td>{dev.seq}</td></tr>"
            )
        if not rows:
            rows.append("<tr><td colspan=7>No sensors heard from yet.</td></tr>")

        events = "".join(
            f"<li><small>{datetime.fromtimestamp(ts):%Y-%m-%d %H:%M:%S}</small> "
            f"{html.escape(text)}</li>"
            for ts, text in registry.events
        ) or "<li>None yet.</li>"

        return f"""<!doctype html>
<html><head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="10">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fridge Door Alerter</title>
<style>
  body {{ font-family: sans-serif; margin: 2em auto; max-width: 46em; padding: 0 1em; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; padding: 0.4em 0.7em; border-bottom: 1px solid #ccc; }}
  li {{ margin: 0.2em 0; }}
</style>
</head><body>
<h1>&#129482; Fridge Door Alerter</h1>
<table>
<tr><th>Device</th><th>State</th><th>Battery</th><th>Field</th>
<th>RSSI</th><th>Last seen</th><th>Seq</th></tr>
{"".join(rows)}
</table>
<h2>Recent events</h2>
<ul>{events}</ul>
<p><small>Page refreshes every 10 s.</small></p>
</body></html>"""

    return app

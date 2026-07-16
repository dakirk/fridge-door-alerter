"""Thin ntfy wrapper. The topic is a shared secret -- keep it in config.toml
(gitignored), never in code or README."""

import logging

import httpx

log = logging.getLogger("notifier")


class Notifier:
    def __init__(self, server: str, topic: str):
        self._url = f"{server.rstrip('/')}/{topic}" if topic else None
        self._client = httpx.AsyncClient(timeout=10)
        if self._url is None:
            log.warning("No ntfy topic configured -- alerts will be logged only")

    async def send(self, title: str, message: str,
                   priority: str = "default", tags: str = "") -> None:
        log.info("Alert: %s -- %s", title, message)
        if self._url is None:
            return
        try:
            response = await self._client.post(
                self._url,
                content=message.encode(),
                headers={"Title": title, "Priority": priority, "Tags": tags},
            )
            response.raise_for_status()
        except Exception:
            # Never let a notification failure kill the monitoring loop;
            # re-alerts give another chance later.
            log.exception("ntfy send failed: %s", title)

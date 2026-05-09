import asyncio
from typing import Protocol

from orchestrator.events.envelope import WsEvent


class WsClient(Protocol):
    async def send_json(self, data: dict[str, object]) -> None: ...


class WsBroadcaster(Protocol):
    async def publish(self, event: WsEvent) -> None: ...


class InMemoryWsBroadcaster:
    def __init__(self) -> None:
        self._subs: set[WsClient] = set()

    @property
    def subscribers(self) -> frozenset[WsClient]:
        return frozenset(self._subs)

    def subscribe(self, client: WsClient) -> None:
        self._subs.add(client)

    def unsubscribe(self, client: WsClient) -> None:
        self._subs.discard(client)

    async def publish(self, event: WsEvent) -> None:
        if not self._subs:
            return
        payload = event.to_dict()
        clients = list(self._subs)
        results = await asyncio.gather(
            *(client.send_json(payload) for client in clients),
            return_exceptions=True,
        )
        for client, result in zip(clients, results, strict=True):
            if isinstance(result, Exception):
                self._subs.discard(client)

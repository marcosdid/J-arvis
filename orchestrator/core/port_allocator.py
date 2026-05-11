"""F6 port allocator — range 31000-31999.

In-memory state com `asyncio.Lock` (thread/coroutine-safe). Cada
`allocate()` faz um socket.bind probe em ``127.0.0.1:<port>`` pra detectar
portas já ocupadas por processos não-J-arvis (Docker containers de outras
ferramentas, navegador, etc).

Quando o daemon reinicia, runs ainda ativas no DB devem chamar ``reserve()``
pra cada porta em ``ports_json`` (sem refazer o probe — a porta está em uso
pela run prévia).
"""
import asyncio
import socket
from collections.abc import Callable


class NoFreePortError(Exception):
    """All ports in 31000-31999 are either reserved or occupied by other procs."""


class PortAllocator:
    RANGE_START = 31000
    RANGE_END = 31999

    def __init__(
        self,
        socket_factory: Callable[[], socket.socket] | None = None,
    ) -> None:
        self._reserved: set[int] = set()
        self._lock = asyncio.Lock()
        self._socket_factory = socket_factory or self._default_socket_factory

    @staticmethod
    def _default_socket_factory() -> socket.socket:
        return socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    async def allocate(self) -> int:
        """Reserva e retorna a primeira porta livre no range.

        Free = não-`_reserved` AND `socket.bind(("127.0.0.1", port))` succeeds.
        Raises `NoFreePortError` se range exausto.
        """
        async with self._lock:
            for port in range(self.RANGE_START, self.RANGE_END + 1):
                if port in self._reserved:
                    continue
                if self._is_free(port):
                    self._reserved.add(port)
                    return port
            raise NoFreePortError(
                f"all {self.RANGE_END - self.RANGE_START + 1} ports "
                f"({self.RANGE_START}-{self.RANGE_END}) exhausted"
            )

    async def release(self, port: int) -> None:
        """Devolve porta pro pool. No-op se a porta não estava reservada
        (idempotente — chamadas duplicadas durante cleanup não falham)."""
        async with self._lock:
            self._reserved.discard(port)

    async def reserve(self, port: int) -> None:
        """Marca porta como em-uso sem rodar o probe.

        Use no startup pra restaurar `RunInstance.ports_json` de runs ativas
        encontradas no DB — a porta está literalmente bound por um container
        Docker da run prévia que sobreviveu ao restart, então o probe falharia
        e a porta ficaria "perdida".
        """
        async with self._lock:
            self._reserved.add(port)

    def _is_free(self, port: int) -> bool:
        """True se conseguimos bind em 127.0.0.1:port (porta não ocupada).

        SO_REUSEADDR é setado pra não falhar se há um socket em TIME_WAIT
        de uso prévio nosso. Socket é fechado imediatamente — só queremos
        o bind como probe.
        """
        s = self._socket_factory()
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return True
            except OSError:
                return False
        finally:
            s.close()


__all__ = ["NoFreePortError", "PortAllocator"]

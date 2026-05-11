"""F6.c: port allocator com socket bind probe."""
import asyncio
import socket
from collections.abc import Iterator

import pytest

from orchestrator.core.port_allocator import NoFreePortError, PortAllocator


class FakeSocket:
    """Stub do `socket.socket` pra testar o probe sem touchar a rede.

    `fails_for_ports` lista portas em que `bind()` levanta `OSError`
    (simulando que outro processo já ocupa). Demais ports retornam OK.
    """

    def __init__(self, fails_for_ports: set[int] | None = None) -> None:
        self.fails_for_ports = fails_for_ports or set()
        self.closed = False
        self.bound_to: tuple[str, int] | None = None
        self.sockopts: list[tuple[int, int, int]] = []

    def setsockopt(self, level: int, optname: int, value: int) -> None:
        self.sockopts.append((level, optname, value))

    def bind(self, addr: tuple[str, int]) -> None:
        host, port = addr
        if port in self.fails_for_ports:
            raise OSError(f"port {port} in use")
        self.bound_to = addr

    def close(self) -> None:
        self.closed = True


def _factory(fails_for_ports: set[int] | None = None) -> object:
    """Returns a factory callable that yields FakeSocket instances."""
    def make() -> FakeSocket:
        return FakeSocket(fails_for_ports=fails_for_ports)
    return make


@pytest.mark.unit
async def test_allocate_returns_first_port_in_range() -> None:
    alloc = PortAllocator(socket_factory=_factory())
    p = await alloc.allocate()
    assert p == PortAllocator.RANGE_START


@pytest.mark.unit
async def test_allocate_advances_when_port_already_reserved() -> None:
    alloc = PortAllocator(socket_factory=_factory())
    p1 = await alloc.allocate()
    p2 = await alloc.allocate()
    assert p1 == PortAllocator.RANGE_START
    assert p2 == PortAllocator.RANGE_START + 1


@pytest.mark.unit
async def test_allocate_skips_occupied_ports() -> None:
    """Probe falha em 31000 e 31001 → allocator retorna 31002."""
    alloc = PortAllocator(
        socket_factory=_factory(fails_for_ports={31000, 31001})
    )
    p = await alloc.allocate()
    assert p == 31002


@pytest.mark.unit
async def test_allocate_raises_when_range_exhausted() -> None:
    """Todas as portas no range falham no probe → NoFreePortError."""
    all_ports = set(range(PortAllocator.RANGE_START, PortAllocator.RANGE_END + 1))
    alloc = PortAllocator(socket_factory=_factory(fails_for_ports=all_ports))
    with pytest.raises(NoFreePortError) as exc:
        await alloc.allocate()
    assert "31000" in str(exc.value)
    assert "31999" in str(exc.value)


@pytest.mark.unit
async def test_release_returns_port_to_pool() -> None:
    alloc = PortAllocator(socket_factory=_factory())
    p1 = await alloc.allocate()
    await alloc.release(p1)
    p2 = await alloc.allocate()
    assert p2 == p1  # porta voltou pra disponibilidade


@pytest.mark.unit
async def test_release_is_idempotent_on_unknown_port() -> None:
    """Liberar porta não reservada é no-op (chamadas duplicadas durante
    cleanup não falham)."""
    alloc = PortAllocator(socket_factory=_factory())
    await alloc.release(99999)  # nunca foi alocada
    p = await alloc.allocate()
    assert p == PortAllocator.RANGE_START


@pytest.mark.unit
async def test_reserve_marks_port_without_probing() -> None:
    """`reserve()` aceita porta direto sem chamar bind (usado no startup
    pra restaurar runs ativas do DB). A porta reservada NUNCA é
    retornada por allocate."""
    alloc = PortAllocator(socket_factory=_factory())
    await alloc.reserve(31005)
    # Aloca 10 portas seguidas; nenhuma pode ser 31005.
    seen = [await alloc.allocate() for _ in range(10)]
    assert 31005 not in seen
    # As 10 alocações são contínuas exceto pelo skip de 31005.
    assert seen == [31000, 31001, 31002, 31003, 31004, 31006, 31007, 31008, 31009, 31010]


@pytest.mark.unit
async def test_concurrent_allocate_returns_distinct_ports() -> None:
    """asyncio.Lock garante que 2 corrotinas concorrentes não colidam."""
    alloc = PortAllocator(socket_factory=_factory())
    results = await asyncio.gather(*(alloc.allocate() for _ in range(10)))
    assert len(set(results)) == 10  # 10 portas distintas
    assert sorted(results) == list(range(31000, 31010))


@pytest.mark.unit
def test_default_socket_factory_returns_real_socket() -> None:
    """Smoke: factory default cria um socket TCP IPv4 real (não toca rede;
    só verifica que o tipo é o esperado pra contrato com `_is_free`)."""
    s = PortAllocator._default_socket_factory()
    try:
        assert s.family == socket.AF_INET
        assert s.type == socket.SOCK_STREAM
    finally:
        s.close()


@pytest.mark.unit
def test_socket_is_closed_even_when_bind_fails() -> None:
    """`finally: s.close()` deve rodar mesmo se bind levanta — evita FD leak."""
    seen_sockets: list[FakeSocket] = []

    def tracking_factory() -> FakeSocket:
        s = FakeSocket(fails_for_ports={31000})
        seen_sockets.append(s)
        return s

    alloc = PortAllocator(socket_factory=tracking_factory)
    asyncio.run(alloc.allocate())
    # 31000 falhou bind, 31001 OK → 2 sockets criados, ambos fechados
    assert len(seen_sockets) == 2
    assert all(s.closed for s in seen_sockets)

"""F6 Docker CLI wrapper — Protocol + Subprocess impl + Fake for tests.

`DockerOps` Protocol é o seam pra `core/runs.py` (F6.e). Não é abstração
pra múltiplos engines (ADR-0006 fixou Docker); existe pra permitir
`FakeDockerOps` em unit tests sem tocar o daemon Docker real.

Naming evita shadow de builtins Python: `container_start`/`run_in_container`
em vez de `run`/`exec` (PFC-12).
"""
import asyncio
import subprocess
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ContainerSpec:
    """Spec pra `docker run` (subset do que F6 usa)."""

    name: str
    image: str
    network: str
    env: dict[str, str] = field(default_factory=dict)
    port_map: dict[int, int] = field(default_factory=dict)  # {host: container}
    volumes: tuple[tuple[str, str], ...] = ()  # (host, container)
    command: tuple[str, ...] | None = None


class DockerError(Exception):
    """Comando docker retornou exit != 0."""

    def __init__(self, msg: str, stderr: str = "") -> None:
        super().__init__(msg)
        self.stderr = stderr


SyncRunner = Callable[[list[str]], tuple[int, str, str]]
"""Função que executa `argv` e retorna `(exit_code, stdout, stderr)`."""

StreamRunner = Callable[[list[str]], AsyncIterator[tuple[str, str]]]
"""Generator async que yields `(stream_name, line)` enquanto `argv` roda."""


class DockerOps(Protocol):
    async def build(self, *, context: Path, dockerfile: str, tag: str) -> None: ...
    async def network_create(self, name: str) -> None: ...
    async def network_rm(self, name: str) -> None: ...
    async def container_start(self, spec: ContainerSpec) -> str: ...
    async def run_in_container(
        self, container_id: str, cmd: list[str]
    ) -> tuple[int, str, str]: ...
    def stream_logs(self, container_id: str) -> AsyncIterator[tuple[str, str]]: ...
    async def stop(self, container_id: str, *, force: bool = False) -> None: ...
    async def rm(self, container_id: str) -> None: ...


def _default_sync_runner(argv: list[str]) -> tuple[int, str, str]:
    """Production sync runner: subprocess.run capturando stdout/stderr."""
    proc = subprocess.run(argv, capture_output=True, check=False)
    return (
        proc.returncode,
        proc.stdout.decode(errors="replace"),
        proc.stderr.decode(errors="replace"),
    )


async def _default_stream_runner(argv: list[str]) -> AsyncIterator[tuple[str, str]]:
    """Production stream runner: asyncio subprocess yields linhas conforme chegam.

    Cancel-safe: se o consumer parar de iterar (ex.: SSE client desconectou),
    o subprocess recebe terminate() via `__aexit__` do generator.
    """
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert proc.stdout is not None
    assert proc.stderr is not None

    async def _read(
        reader: asyncio.StreamReader, stream_name: str,
    ) -> AsyncIterator[tuple[str, str]]:
        while True:
            line_bytes = await reader.readline()
            if not line_bytes:
                return
            yield stream_name, line_bytes.decode(errors="replace").rstrip("\n")

    try:
        out_iter = _read(proc.stdout, "stdout")
        err_iter = _read(proc.stderr, "stderr")
        out_done = err_done = False
        while not (out_done and err_done):
            if not out_done:
                try:
                    yield await out_iter.__anext__()
                except StopAsyncIteration:
                    out_done = True
            if not err_done:
                try:
                    yield await err_iter.__anext__()
                except StopAsyncIteration:
                    err_done = True
        await proc.wait()
    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2)
            except TimeoutError:
                proc.kill()
                await proc.wait()


class SubprocessDockerOps:
    """Production `DockerOps`: invokes `docker` CLI via subprocess.

    `runner`/`streamer` são injetáveis pra unit tests não tocarem `docker`.
    """

    def __init__(
        self,
        runner: SyncRunner | None = None,
        streamer: StreamRunner | None = None,
    ) -> None:
        self._runner = runner or _default_sync_runner
        self._streamer = streamer or _default_stream_runner

    async def _run(self, *argv: str) -> tuple[int, str, str]:
        return await asyncio.to_thread(self._runner, ["docker", *argv])

    async def _run_or_raise(self, *argv: str, action: str) -> str:
        code, stdout, stderr = await self._run(*argv)
        if code != 0:
            raise DockerError(f"docker {action} failed (exit {code})", stderr=stderr)
        return stdout

    async def build(self, *, context: Path, dockerfile: str, tag: str) -> None:
        await self._run_or_raise(
            "build", "-t", tag, "-f", dockerfile, str(context),
            action="build",
        )

    async def network_create(self, name: str) -> None:
        await self._run_or_raise("network", "create", name, action="network create")

    async def network_rm(self, name: str) -> None:
        await self._run_or_raise("network", "rm", name, action="network rm")

    async def container_start(self, spec: ContainerSpec) -> str:
        argv: list[str] = ["run", "-d", "--name", spec.name, "--network", spec.network]
        for host, container in spec.port_map.items():
            argv.extend(["-p", f"{host}:{container}"])
        for host_path, container_path in spec.volumes:
            argv.extend(["-v", f"{host_path}:{container_path}"])
        for k, v in spec.env.items():
            argv.extend(["-e", f"{k}={v}"])
        argv.append(spec.image)
        if spec.command is not None:
            argv.extend(spec.command)
        stdout = await self._run_or_raise(*argv, action="run")
        return stdout.strip()

    async def run_in_container(
        self, container_id: str, cmd: list[str]
    ) -> tuple[int, str, str]:
        return await self._run("exec", container_id, *cmd)

    def stream_logs(self, container_id: str) -> AsyncIterator[tuple[str, str]]:
        return self._streamer(["docker", "logs", "-f", container_id])

    async def stop(self, container_id: str, *, force: bool = False) -> None:
        argv = ["kill" if force else "stop", container_id]
        await self._run_or_raise(*argv, action="stop")

    async def rm(self, container_id: str) -> None:
        await self._run_or_raise("rm", container_id, action="rm")


__all__ = [
    "ContainerSpec",
    "DockerError",
    "DockerOps",
    "StreamRunner",
    "SubprocessDockerOps",
    "SyncRunner",
]

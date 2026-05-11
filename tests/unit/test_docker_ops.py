"""F6.d: SubprocessDockerOps via injected runner/streamer (sem docker real)."""
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from orchestrator.sandbox.docker_ops import (
    ContainerSpec,
    DockerError,
    SubprocessDockerOps,
    _default_stream_runner,
    _default_sync_runner,
)


class _Recorder:
    """Sync runner fake: registra todas chamadas, retorna canned result."""

    def __init__(
        self,
        result: tuple[int, str, str] = (0, "", ""),
        results: list[tuple[int, str, str]] | None = None,
    ) -> None:
        self.calls: list[list[str]] = []
        self._results = results if results is not None else None
        self._default = result

    def __call__(self, argv: list[str]) -> tuple[int, str, str]:
        self.calls.append(list(argv))
        if self._results:
            return self._results.pop(0)
        return self._default


# === build ====================================================================


@pytest.mark.unit
async def test_build_invokes_docker_build_with_tag_and_dockerfile() -> None:
    rec = _Recorder(result=(0, "", ""))
    ops = SubprocessDockerOps(runner=rec)
    await ops.build(
        context=Path("/repo/backend"), dockerfile="Dockerfile", tag="jarvis-run-x",
    )
    assert rec.calls == [
        ["docker", "build", "-t", "jarvis-run-x", "-f", "Dockerfile", "/repo/backend"],
    ]


@pytest.mark.unit
async def test_build_failure_raises_docker_error_with_stderr() -> None:
    rec = _Recorder(result=(1, "", "Dockerfile: not found"))
    ops = SubprocessDockerOps(runner=rec)
    with pytest.raises(DockerError) as info:
        await ops.build(context=Path("/x"), dockerfile="Dockerfile", tag="t")
    assert info.value.stderr == "Dockerfile: not found"
    assert "exit 1" in str(info.value)


# === network ==================================================================


@pytest.mark.unit
async def test_network_create() -> None:
    rec = _Recorder()
    ops = SubprocessDockerOps(runner=rec)
    await ops.network_create("jarvis-run-abc")
    assert rec.calls == [["docker", "network", "create", "jarvis-run-abc"]]


@pytest.mark.unit
async def test_network_rm() -> None:
    rec = _Recorder()
    ops = SubprocessDockerOps(runner=rec)
    await ops.network_rm("jarvis-run-abc")
    assert rec.calls == [["docker", "network", "rm", "jarvis-run-abc"]]


@pytest.mark.unit
async def test_network_create_failure() -> None:
    rec = _Recorder(result=(1, "", "already exists"))
    ops = SubprocessDockerOps(runner=rec)
    with pytest.raises(DockerError):
        await ops.network_create("dup")


# === container_start =========================================================


@pytest.mark.unit
async def test_container_start_minimal() -> None:
    rec = _Recorder(result=(0, "abc123\n", ""))
    ops = SubprocessDockerOps(runner=rec)
    cid = await ops.container_start(ContainerSpec(name="db", image="postgres:16", network="net"))
    assert cid == "abc123"  # stripped
    assert rec.calls == [["docker", "run", "-d", "--name", "db", "--network", "net", "postgres:16"]]


@pytest.mark.unit
async def test_container_start_with_port_map() -> None:
    rec = _Recorder(result=(0, "cid\n", ""))
    ops = SubprocessDockerOps(runner=rec)
    await ops.container_start(ContainerSpec(
        name="back", image="i", network="n",
        port_map={31100: 8000, 31101: 8001},
    ))
    argv = rec.calls[0]
    assert "-p" in argv
    assert "31100:8000" in argv
    assert "31101:8001" in argv


@pytest.mark.unit
async def test_container_start_with_volumes() -> None:
    rec = _Recorder(result=(0, "cid\n", ""))
    ops = SubprocessDockerOps(runner=rec)
    await ops.container_start(ContainerSpec(
        name="back", image="i", network="n",
        volumes=(("/host/code", "/app"), ("/host/data", "/data")),
    ))
    argv = rec.calls[0]
    assert "-v" in argv
    assert "/host/code:/app" in argv
    assert "/host/data:/data" in argv


@pytest.mark.unit
async def test_container_start_with_env() -> None:
    rec = _Recorder(result=(0, "cid\n", ""))
    ops = SubprocessDockerOps(runner=rec)
    await ops.container_start(ContainerSpec(
        name="back", image="i", network="n",
        env={"DATABASE_URL": "postgres://x", "DEBUG": "1"},
    ))
    argv = rec.calls[0]
    assert "-e" in argv
    assert "DATABASE_URL=postgres://x" in argv
    assert "DEBUG=1" in argv


@pytest.mark.unit
async def test_container_start_with_command_override() -> None:
    rec = _Recorder(result=(0, "cid\n", ""))
    ops = SubprocessDockerOps(runner=rec)
    await ops.container_start(ContainerSpec(
        name="back", image="i", network="n",
        command=("pnpm", "dev", "--port", "5173"),
    ))
    argv = rec.calls[0]
    image_idx = argv.index("i")
    assert argv[image_idx + 1 : image_idx + 5] == ["pnpm", "dev", "--port", "5173"]


@pytest.mark.unit
async def test_container_start_failure() -> None:
    rec = _Recorder(result=(125, "", "Unable to find image"))
    ops = SubprocessDockerOps(runner=rec)
    with pytest.raises(DockerError) as info:
        await ops.container_start(ContainerSpec(name="x", image="bogus", network="n"))
    assert info.value.stderr == "Unable to find image"


# === run_in_container ========================================================


@pytest.mark.unit
async def test_run_in_container_returns_exit_stdout_stderr() -> None:
    rec = _Recorder(result=(0, "ok\n", ""))
    ops = SubprocessDockerOps(runner=rec)
    code, stdout, stderr = await ops.run_in_container("cid", ["psql", "-c", "SELECT 1"])
    assert code == 0
    assert stdout == "ok\n"
    assert stderr == ""
    assert rec.calls == [["docker", "exec", "cid", "psql", "-c", "SELECT 1"]]


@pytest.mark.unit
async def test_run_in_container_does_not_raise_on_nonzero_exit() -> None:
    """`run_in_container` é usado pra healthchecks/seeds — caller decide se
    exit != 0 é fatal, não levanta como build/network/start fazem."""
    rec = _Recorder(result=(7, "", "command failed"))
    ops = SubprocessDockerOps(runner=rec)
    code, _, stderr = await ops.run_in_container("cid", ["false"])
    assert code == 7
    assert stderr == "command failed"


# === stop / rm ===============================================================


@pytest.mark.unit
async def test_stop_default_uses_stop_command() -> None:
    rec = _Recorder()
    ops = SubprocessDockerOps(runner=rec)
    await ops.stop("cid")
    assert rec.calls == [["docker", "stop", "cid"]]


@pytest.mark.unit
async def test_stop_force_uses_kill_command() -> None:
    rec = _Recorder()
    ops = SubprocessDockerOps(runner=rec)
    await ops.stop("cid", force=True)
    assert rec.calls == [["docker", "kill", "cid"]]


@pytest.mark.unit
async def test_rm() -> None:
    rec = _Recorder()
    ops = SubprocessDockerOps(runner=rec)
    await ops.rm("cid")
    assert rec.calls == [["docker", "rm", "cid"]]


# === stream_logs =============================================================


@pytest.mark.unit
async def test_stream_logs_yields_lines_from_streamer() -> None:
    captured_argv: list[list[str]] = []

    async def fake_stream(argv: list[str]) -> AsyncIterator[tuple[str, str]]:
        captured_argv.append(argv)
        yield "stdout", "line 1"
        yield "stderr", "warn"
        yield "stdout", "line 2"

    ops = SubprocessDockerOps(streamer=fake_stream)
    lines = [item async for item in ops.stream_logs("cid")]
    assert lines == [("stdout", "line 1"), ("stderr", "warn"), ("stdout", "line 2")]
    assert captured_argv == [["docker", "logs", "-f", "cid"]]


@pytest.mark.unit
async def test_stream_logs_default_streamer_is_used_when_none_injected() -> None:
    """Smoke: SubprocessDockerOps() sem streamer usa o default; só verificamos
    que o atributo é callable (execução real depende de docker)."""
    ops = SubprocessDockerOps()
    assert callable(ops._streamer)


# === default runner / streamer ==============================================


@pytest.mark.unit
def test_default_sync_runner_returns_zero_for_true_command() -> None:
    """Smoke do `_default_sync_runner` com comando local (`true`)."""
    code, _, stderr = _default_sync_runner(["true"])
    assert code == 0
    assert stderr == ""


@pytest.mark.unit
def test_default_sync_runner_captures_stderr_on_failure() -> None:
    """`sh -c 'echo err >&2; exit 3'` retorna exit=3 + stderr."""
    code, _, stderr = _default_sync_runner(["sh", "-c", "echo err >&2; exit 3"])
    assert code == 3
    assert "err" in stderr


@pytest.mark.unit
async def test_default_stream_runner_yields_lines_from_real_subprocess() -> None:
    """End-to-end do `_default_stream_runner` com `sh`: valida parsing
    stdout/stderr sem docker."""
    lines = [item async for item in _default_stream_runner(
        ["sh", "-c", "echo a; echo b >&2"]
    )]
    streams = {stream for stream, _ in lines}
    texts = {text for _, text in lines}
    assert streams == {"stdout", "stderr"}
    assert texts == {"a", "b"}


@pytest.mark.unit
async def test_default_stream_runner_handles_stdout_finishing_before_stderr() -> None:
    """1 linha stdout + 2 linhas stderr → loop continua processando stderr
    depois do stdout esgotar. Cobre branch `if not out_done` False."""
    lines = [item async for item in _default_stream_runner(
        ["sh", "-c", "echo a; echo b >&2; echo c >&2"]
    )]
    stdouts = [t for s, t in lines if s == "stdout"]
    stderrs = [t for s, t in lines if s == "stderr"]
    assert stdouts == ["a"]
    assert set(stderrs) == {"b", "c"}


@pytest.mark.unit
async def test_default_stream_runner_handles_stderr_finishing_before_stdout() -> None:
    """1 linha stderr + 2 linhas stdout → loop continua processando stdout
    depois do stderr esgotar. Cobre branch `if not err_done` False."""
    lines = [item async for item in _default_stream_runner(
        ["sh", "-c", "echo a >&2; echo b; echo c"]
    )]
    stdouts = [t for s, t in lines if s == "stdout"]
    stderrs = [t for s, t in lines if s == "stderr"]
    assert set(stdouts) == {"b", "c"}
    assert stderrs == ["a"]


@pytest.mark.unit
async def test_default_stream_runner_terminates_subprocess_on_early_exit() -> None:
    """Se o consumer parar de iterar (raises do callsite), o `finally` mata
    o subprocess. Aqui simulamos quebrando o loop após a primeira linha de
    `sh -c 'echo a; sleep 60; echo b'` — sem o cleanup do generator, o `sh`
    sleep 60 ficaria órfão."""
    gen = _default_stream_runner(["sh", "-c", "echo a; sleep 60; echo b"])
    first = await gen.__anext__()
    assert first[1] == "a"
    # aclose triggers __aexit__ → finally block → terminate
    await gen.aclose()
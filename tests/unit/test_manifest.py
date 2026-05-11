"""F6.b: parser + validação + substituição do `.orchestrator/run.yml`."""
from pathlib import Path

import pytest

from orchestrator.core.manifest import (
    ManifestInvalidError,
    ManifestMissingError,
    ServiceSpec,
    load_manifest,
    resolve_substitutions,
)


def _write_manifest(project_path: Path, content: str) -> None:
    (project_path / ".orchestrator").mkdir(parents=True, exist_ok=True)
    (project_path / ".orchestrator" / "run.yml").write_text(content)


@pytest.mark.unit
def test_load_minimal_valid_with_image(tmp_path: Path) -> None:
    _write_manifest(tmp_path, """
version: "1"
services:
  db:
    image: postgres:16
""")
    m = load_manifest(tmp_path)
    assert m.version == "1"
    assert "db" in m.services
    assert m.services["db"].image == "postgres:16"
    assert m.services["db"].build is None
    assert m.services["db"].port is None


@pytest.mark.unit
def test_load_valid_with_depends_on_chain(tmp_path: Path) -> None:
    """3-service chain validates: Kahn's algo decrement is exercised
    (frontend←backend←db; visited == 3, no cycle). `frontend` has 2
    deps so its decrement-loop sees both the "in_degree==0 → enqueue"
    branch and the "still non-zero" branch."""
    _write_manifest(tmp_path, """
version: "1"
services:
  db: {image: postgres:16, port: 5432}
  backend: {image: foo, port: 8000, depends_on: [db]}
  frontend: {image: bar, port: 5173, depends_on: [db, backend]}
""")
    m = load_manifest(tmp_path)
    assert m.services["backend"].depends_on == ["db"]
    assert m.services["frontend"].depends_on == ["db", "backend"]


@pytest.mark.unit
def test_load_minimal_valid_with_build(tmp_path: Path) -> None:
    _write_manifest(tmp_path, """
version: "1"
services:
  backend:
    build: ./backend
    port: 8000
""")
    m = load_manifest(tmp_path)
    assert m.services["backend"].build == "./backend"
    assert m.services["backend"].dockerfile == "Dockerfile"
    assert m.services["backend"].port == 8000


@pytest.mark.unit
def test_rejects_service_with_both_image_and_build(tmp_path: Path) -> None:
    _write_manifest(tmp_path, """
version: "1"
services:
  x: {image: foo, build: ./bar}
""")
    with pytest.raises(ManifestInvalidError) as exc:
        load_manifest(tmp_path)
    assert "image" in str(exc.value) or "build" in str(exc.value)


@pytest.mark.unit
def test_rejects_service_with_neither_image_nor_build(tmp_path: Path) -> None:
    _write_manifest(tmp_path, """
version: "1"
services:
  x: {port: 8000}
""")
    with pytest.raises(ManifestInvalidError):
        load_manifest(tmp_path)


@pytest.mark.unit
def test_rejects_depends_on_referencing_unknown_service(tmp_path: Path) -> None:
    _write_manifest(tmp_path, """
version: "1"
services:
  backend:
    image: x
    depends_on: [ghost]
""")
    with pytest.raises(ManifestInvalidError) as exc:
        load_manifest(tmp_path)
    assert "ghost" in str(exc.value)


@pytest.mark.unit
def test_rejects_depends_on_cycle(tmp_path: Path) -> None:
    _write_manifest(tmp_path, """
version: "1"
services:
  a: {image: x, depends_on: [b]}
  b: {image: y, depends_on: [a]}
""")
    with pytest.raises(ManifestInvalidError) as exc:
        load_manifest(tmp_path)
    assert "cycle" in str(exc.value)


@pytest.mark.unit
def test_rejects_depends_on_self(tmp_path: Path) -> None:
    _write_manifest(tmp_path, """
version: "1"
services:
  a: {image: x, depends_on: [a]}
""")
    with pytest.raises(ManifestInvalidError) as exc:
        load_manifest(tmp_path)
    assert "self" in str(exc.value)


@pytest.mark.unit
def test_rejects_duplicate_ports(tmp_path: Path) -> None:
    _write_manifest(tmp_path, """
version: "1"
services:
  a: {image: x, port: 8000}
  b: {image: y, port: 8000}
""")
    with pytest.raises(ManifestInvalidError) as exc:
        load_manifest(tmp_path)
    assert "8000" in str(exc.value)


@pytest.mark.unit
def test_missing_manifest_raises_typed_error(tmp_path: Path) -> None:
    with pytest.raises(ManifestMissingError) as exc:
        load_manifest(tmp_path)
    assert ".orchestrator/run.yml" in str(exc.value)


@pytest.mark.unit
def test_empty_yaml_rejected(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "")
    with pytest.raises(ManifestInvalidError) as exc:
        load_manifest(tmp_path)
    assert "empty" in str(exc.value)


@pytest.mark.unit
def test_malformed_yaml_rejected(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "version: '1'\nservices: {a: [unterminated")
    with pytest.raises(ManifestInvalidError) as exc:
        load_manifest(tmp_path)
    assert "YAML" in str(exc.value)


@pytest.mark.unit
def test_extra_top_level_field_rejected(tmp_path: Path) -> None:
    _write_manifest(tmp_path, """
version: "1"
services: {db: {image: x}}
extra_field: forbidden
""")
    with pytest.raises(ManifestInvalidError):
        load_manifest(tmp_path)


@pytest.mark.unit
def test_extra_field_in_service_rejected(tmp_path: Path) -> None:
    _write_manifest(tmp_path, """
version: "1"
services:
  db: {image: x, weird_field: 42}
""")
    with pytest.raises(ManifestInvalidError):
        load_manifest(tmp_path)


@pytest.mark.unit
def test_version_must_be_string_one(tmp_path: Path) -> None:
    _write_manifest(tmp_path, """
version: "2"
services: {db: {image: x}}
""")
    with pytest.raises(ManifestInvalidError):
        load_manifest(tmp_path)


@pytest.mark.unit
def test_services_empty_rejected(tmp_path: Path) -> None:
    _write_manifest(tmp_path, """
version: "1"
services: {}
""")
    with pytest.raises(ManifestInvalidError):
        load_manifest(tmp_path)


@pytest.mark.unit
def test_healthcheck_and_seed_parsed(tmp_path: Path) -> None:
    _write_manifest(tmp_path, """
version: "1"
services:
  db:
    image: postgres:16
    healthcheck:
      command: ["pg_isready"]
      interval: 5
      retries: 10
    seed:
      command: ["psql", "-f", "/seed.sql"]
""")
    m = load_manifest(tmp_path)
    assert m.services["db"].healthcheck is not None
    assert m.services["db"].healthcheck.command == ["pg_isready"]
    assert m.services["db"].healthcheck.interval == 5
    assert m.services["db"].seed is not None
    assert m.services["db"].seed.command == ["psql", "-f", "/seed.sql"]


@pytest.mark.unit
def test_effective_mount_source_defaults() -> None:
    """Build → True; image → False; explicit override wins both ways."""
    build_svc = ServiceSpec(build="./x")
    image_svc = ServiceSpec(image="x")
    forced_off = ServiceSpec(build="./x", mount_source=False)
    forced_on = ServiceSpec(image="x", mount_source=True)
    assert build_svc.effective_mount_source() is True
    assert image_svc.effective_mount_source() is False
    assert forced_off.effective_mount_source() is False
    assert forced_on.effective_mount_source() is True


# --- resolve_substitutions ---------------------------------------------------


@pytest.mark.unit
def test_resolve_substitutes_port_and_url() -> None:
    result = resolve_substitutions(
        {"DB_URL": "postgres://u@$URL_db/d", "PORT": "$PORT_backend"},
        ports_host={"db": 5432, "backend": 31101},
        run_id="abcdef1234567890",
        cwd="/tmp/x",
    )
    assert result["DB_URL"] == "postgres://u@http://localhost:5432/d"
    assert result["PORT"] == "31101"


@pytest.mark.unit
def test_resolve_substitutes_run_id_and_cwd() -> None:
    result = resolve_substitutions(
        {"TAG": "build-$RUN_ID", "WORKDIR": "$CWD"},
        ports_host={},
        run_id="abcdef1234567890",
        cwd="/work/here",
    )
    # short_run_id = first 8 chars
    assert result["TAG"] == "build-abcdef12"
    assert result["WORKDIR"] == "/work/here"


@pytest.mark.unit
def test_resolve_preserves_unknown_dollar_vars() -> None:
    """`$HOME`, `$PATH`, etc devem ficar intactos pro container resolver."""
    result = resolve_substitutions(
        {"BIN": "$HOME/.bin", "PATH": "/usr/bin:$PATH"},
        ports_host={"a": 8000},
        run_id="x",
        cwd="/c",
    )
    assert result["BIN"] == "$HOME/.bin"
    assert result["PATH"] == "/usr/bin:$PATH"


@pytest.mark.unit
def test_resolve_empty_env_returns_empty_dict() -> None:
    assert resolve_substitutions({}, ports_host={}, run_id="x", cwd="/") == {}


@pytest.mark.unit
def test_resolve_no_ports_does_not_break_url_pattern() -> None:
    """`$URL_unknown` permanece inalterado se o serviço não tem porta."""
    result = resolve_substitutions(
        {"X": "$URL_unknown"},
        ports_host={"other": 8000},
        run_id="x",
        cwd="/c",
    )
    assert result["X"] == "$URL_unknown"


@pytest.mark.unit
def test_resolve_prefix_collision_longer_name_wins() -> None:
    """Se há `db` e `db2`, `$PORT_db2` deve resolver pra porta de `db2`
    — não pra `<porta_db>2` (collision via naive str.replace).
    Fix: sort por len(name) DESC."""
    result = resolve_substitutions(
        {"A": "$PORT_db2", "B": "$PORT_db", "C": "$URL_db2"},
        ports_host={"db": 5432, "db2": 5433},
        run_id="x",
        cwd="/c",
    )
    assert result["A"] == "5433"
    assert result["B"] == "5432"
    assert result["C"] == "http://localhost:5433"


@pytest.mark.unit
def test_rejects_service_name_with_invalid_charset(tmp_path: Path) -> None:
    """Spec §6.1: service names alfanumérico + hífens, lowercase,
    sem leading hyphen. Inválidos (espaço, dot, dollar, uppercase) → 422."""
    for bad in ("My Service", "svc.x", "svc$x", "-leading", "Backend"):
        _write_manifest(tmp_path, f"""
version: "1"
services:
  "{bad}": {{image: x}}
""")
        with pytest.raises(ManifestInvalidError) as exc:
            load_manifest(tmp_path)
        assert "service name" in str(exc.value) or "invalid" in str(exc.value)


@pytest.mark.unit
def test_rejects_port_out_of_valid_range(tmp_path: Path) -> None:
    """Port = -1 ou 0 ou >65535 não é porta TCP válida → 422 na Pydantic."""
    for bad_port in (-1, 0, 65536, 99999):
        _write_manifest(tmp_path, f"""
version: "1"
services:
  x: {{image: foo, port: {bad_port}}}
""")
        with pytest.raises(ManifestInvalidError):
            load_manifest(tmp_path)

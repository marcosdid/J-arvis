"""F6 manifest parser — `.orchestrator/run.yml`.

Pydantic v2 schema com ``extra="forbid"``. Validações:

- Cada ``ServiceSpec`` declara **exatamente um** de ``image`` ou ``build``.
- ``depends_on`` referencia só serviços declarados; sem ciclos.
- ``port`` (host-exposed) é único entre serviços.

Substituições em ``env`` values: ``$PORT_<svc>``, ``$URL_<svc>``,
``$RUN_ID``, ``$CWD``. Outras ``$KEY`` ficam intactas (deixadas pro container
resolver, ex.: ``$HOME``).
"""
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator

_SERVICE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ManifestError(Exception):
    """Base for manifest-related errors."""


class ManifestMissingError(ManifestError):
    """`.orchestrator/run.yml` doesn't exist; bootstrap suggested."""


class ManifestInvalidError(ManifestError):
    """Manifest parsed but failed schema/semantic validation."""

    def __init__(self, path: str, msg: str) -> None:
        self.path = path
        self.msg = msg
        super().__init__(f"{path}: {msg}")


class HealthcheckSpec(BaseModel):
    model_config = {"extra": "forbid"}
    command: list[str] = Field(..., min_length=1)
    interval: int = 2
    retries: int = 30


class SeedSpec(BaseModel):
    model_config = {"extra": "forbid"}
    command: list[str] = Field(..., min_length=1)


class ServiceSpec(BaseModel):
    model_config = {"extra": "forbid"}

    image: str | None = None
    build: str | None = None
    dockerfile: str = "Dockerfile"
    command: list[str] | None = None
    env: dict[str, str] = Field(default_factory=dict)
    port: int | None = Field(default=None, ge=1, le=65535)
    depends_on: list[str] = Field(default_factory=list)
    healthcheck: HealthcheckSpec | None = None
    seed: SeedSpec | None = None
    mount_source: bool | None = None  # None = auto (true se build, false se image)

    @model_validator(mode="after")
    def _image_xor_build(self) -> "ServiceSpec":
        if not self.image and not self.build:
            raise ValueError("must specify either image or build")
        if self.image and self.build:
            raise ValueError("cannot specify both image and build")
        return self

    def effective_mount_source(self) -> bool:
        """Default: True para serviços com `build`, False para `image:` pré-built."""
        if self.mount_source is not None:
            return self.mount_source
        return self.build is not None


class ManifestSpec(BaseModel):
    model_config = {"extra": "forbid"}

    version: Literal["1"]
    services: dict[str, ServiceSpec] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _service_names_valid(self) -> "ManifestSpec":
        for name in self.services:
            if not _SERVICE_NAME_RE.fullmatch(name):
                raise ValueError(
                    f"invalid service name '{name}': must match "
                    "^[a-z0-9][a-z0-9-]*$ (lowercase, digits, hyphens; "
                    "no leading hyphen)"
                )
        return self

    @model_validator(mode="after")
    def _depends_on_valid_and_acyclic(self) -> "ManifestSpec":
        names = set(self.services)
        for svc_name, svc in self.services.items():
            for dep in svc.depends_on:
                if dep not in names:
                    raise ValueError(
                        f"services.{svc_name}.depends_on references undefined service '{dep}'"
                    )
                if dep == svc_name:
                    raise ValueError(
                        f"services.{svc_name}.depends_on cannot include self"
                    )
        # Kahn topological sort to detect cycles
        in_degree: dict[str, int] = defaultdict(int)
        for svc_name, svc in self.services.items():
            in_degree[svc_name] = len(svc.depends_on)
        queue: deque[str] = deque(
            n for n, d in in_degree.items() if d == 0
        )
        visited = 0
        while queue:
            n = queue.popleft()
            visited += 1
            for other_name, other in self.services.items():
                if n in other.depends_on:
                    in_degree[other_name] -= 1
                    if in_degree[other_name] == 0:
                        queue.append(other_name)
        if visited != len(self.services):
            raise ValueError("depends_on has a cycle")
        return self

    @model_validator(mode="after")
    def _ports_unique(self) -> "ManifestSpec":
        seen: dict[int, str] = {}
        for svc_name, svc in self.services.items():
            if svc.port is None:
                continue
            if svc.port in seen:
                raise ValueError(
                    f"port {svc.port} duplicated between "
                    f"services '{seen[svc.port]}' and '{svc_name}'"
                )
            seen[svc.port] = svc_name
        return self


def load_manifest(project_path: Path) -> ManifestSpec:
    """Parse + validate `<project_path>/.orchestrator/run.yml`.

    Raises:
        ManifestMissingError: arquivo não existe.
        ManifestInvalidError: yaml malformado, schema falha ou semântica
            inválida (depends_on, ports, image/build).
    """
    yml_path = project_path / ".orchestrator" / "run.yml"
    if not yml_path.exists():
        raise ManifestMissingError(str(yml_path))
    try:
        data = yaml.safe_load(yml_path.read_text())
    except yaml.YAMLError as e:
        raise ManifestInvalidError(str(yml_path), f"invalid YAML: {e}") from e
    if data is None:
        raise ManifestInvalidError(str(yml_path), "file is empty")
    try:
        return ManifestSpec.model_validate(data)
    except ValidationError as e:
        first = e.errors()[0]
        loc = ".".join(str(p) for p in first["loc"])
        raise ManifestInvalidError(str(yml_path), f"{loc}: {first['msg']}") from e


_KNOWN_PREFIXES: tuple[str, ...] = ("PORT_", "URL_")


def resolve_substitutions(
    env: dict[str, str],
    *,
    ports_host: dict[str, int],
    run_id: str,
    cwd: str,
) -> dict[str, str]:
    """Substitui `$PORT_<svc>`, `$URL_<svc>`, `$RUN_ID`, `$CWD` em env values.

    Variáveis `$KEY` com prefixo desconhecido (ex.: ``$HOME``) ficam intactas
    pra deixar pro container resolver. Substituição é literal string-replace —
    não usa shell parsing.
    """
    short_run_id = run_id[:8]
    # Sort by name length DESC so longer service names ($PORT_db2) substitute
    # before shorter prefixes ($PORT_db) — naive string.replace otherwise turns
    # "$PORT_db2" into "<port_of_db>2".
    ordered = sorted(ports_host.items(), key=lambda kv: -len(kv[0]))
    result: dict[str, str] = {}
    for key, value in env.items():
        out = value
        for svc, port in ordered:
            out = out.replace(f"$PORT_{svc}", str(port))
            out = out.replace(f"$URL_{svc}", f"http://localhost:{port}")
        out = out.replace("$RUN_ID", short_run_id)
        out = out.replace("$CWD", cwd)
        result[key] = out
    return result


__all__ = [
    "HealthcheckSpec",
    "ManifestError",
    "ManifestInvalidError",
    "ManifestMissingError",
    "ManifestSpec",
    "SeedSpec",
    "ServiceSpec",
    "load_manifest",
    "resolve_substitutions",
]

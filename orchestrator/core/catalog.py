"""F7: catálogo curado de templates + perfis de permissão."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class CatalogValidationError(Exception):
    """Catálogo malformado em load-time. Daemon recusa subir."""


_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")


class PermissionProfileSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str
    claude_args: list[str] = []


class TemplateSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str
    default_permission_profile: str
    branch_prefix: str = Field(pattern=r"^[a-z][a-z0-9-]*/$")


class Catalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal["1"]
    fallback_permission_profile: str
    permission_profiles: dict[str, PermissionProfileSpec]
    templates: dict[str, TemplateSpec]

    @model_validator(mode="after")
    def _validate(self) -> Self:
        for name in self.permission_profiles:
            if not _NAME_RE.match(name):
                raise CatalogValidationError(
                    f"permission_profile name {name!r} must match {_NAME_RE.pattern}"
                )
        for name in self.templates:
            if not _NAME_RE.match(name):
                raise CatalogValidationError(
                    f"template name {name!r} must match {_NAME_RE.pattern}"
                )
        if self.fallback_permission_profile not in self.permission_profiles:
            raise CatalogValidationError(
                f"fallback_permission_profile {self.fallback_permission_profile!r} "
                f"not in permission_profiles"
            )
        for tname, tspec in self.templates.items():
            if tspec.default_permission_profile not in self.permission_profiles:
                raise CatalogValidationError(
                    f"template {tname!r}.default_permission_profile "
                    f"{tspec.default_permission_profile!r} not in permission_profiles"
                )
        return self


def load_catalog(path: Path) -> Catalog:
    """Lê YAML, valida via Pydantic + cross-field refs. Raise
    `FileNotFoundError` se ausente, `CatalogValidationError` se inválido
    (YAML malformado ou schema mismatch)."""
    text = path.read_text()
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CatalogValidationError(f"malformed YAML: {exc}") from exc
    try:
        return Catalog.model_validate(raw)
    except ValidationError as exc:
        raise CatalogValidationError(str(exc)) from exc

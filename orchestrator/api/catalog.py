"""F7.b: GET /api/catalog — read-only public listing."""
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from orchestrator.api._deps import resolve_catalog
from orchestrator.core.catalog import Catalog

router = APIRouter(tags=["catalog"])


class PermissionProfileRead(BaseModel):
    name: str
    description: str
    claude_args: list[str]


class TemplateRead(BaseModel):
    name: str
    description: str
    default_permission_profile: str
    branch_prefix: str


class CatalogRead(BaseModel):
    version: str
    fallback_permission_profile: str
    permission_profiles: list[PermissionProfileRead]
    templates: list[TemplateRead]


def _serialize(catalog: Catalog) -> CatalogRead:
    """Transforma dicts em listas ordenadas por name. UI espera arrays."""
    profiles = [
        PermissionProfileRead(
            name=name,
            description=spec.description,
            claude_args=spec.claude_args,
        )
        for name, spec in sorted(catalog.permission_profiles.items())
    ]
    templates = [
        TemplateRead(
            name=name,
            description=spec.description,
            default_permission_profile=spec.default_permission_profile,
            branch_prefix=spec.branch_prefix,
        )
        for name, spec in sorted(catalog.templates.items())
    ]
    return CatalogRead(
        version=catalog.version,
        fallback_permission_profile=catalog.fallback_permission_profile,
        permission_profiles=profiles,
        templates=templates,
    )


@router.get("/catalog", response_model=CatalogRead)
async def get_catalog(
    catalog: Annotated[Catalog, Depends(resolve_catalog)],
) -> CatalogRead:
    return _serialize(catalog)

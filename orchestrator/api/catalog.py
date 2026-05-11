"""F7.b: GET /api/catalog — read-only public listing."""
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from orchestrator.api._deps import resolve_catalog
from orchestrator.core.catalog import Catalog

router = APIRouter(tags=["catalog"])


def _serialize(catalog: Catalog) -> dict[str, Any]:
    """Transforma dicts em listas ordenadas por name. UI espera arrays."""
    profiles = [
        {"name": name, "description": spec.description, "claude_args": spec.claude_args}
        for name, spec in sorted(catalog.permission_profiles.items())
    ]
    templates = [
        {
            "name": name,
            "description": spec.description,
            "default_permission_profile": spec.default_permission_profile,
            "branch_prefix": spec.branch_prefix,
        }
        for name, spec in sorted(catalog.templates.items())
    ]
    return {
        "version": catalog.version,
        "fallback_permission_profile": catalog.fallback_permission_profile,
        "permission_profiles": profiles,
        "templates": templates,
    }


@router.get("/catalog")
async def get_catalog(
    catalog: Annotated[Catalog, Depends(resolve_catalog)],
) -> dict[str, Any]:
    return _serialize(catalog)

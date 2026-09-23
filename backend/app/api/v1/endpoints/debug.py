"""Debug endpoint to check configuration (production only for troubleshooting)."""

from fastapi import APIRouter, Depends

from app.core.config import AppSettings, get_settings

router = APIRouter()


@router.get("/debug/config")
async def debug_config(settings: AppSettings = Depends(get_settings)) -> dict[str, str | list[str]]:
    """Return non-sensitive configuration for debugging."""
    return {
        "environment": settings.environment,
        "api_prefix": settings.api_prefix,
        "allowed_origins": settings.allowed_origins,
        "app_version": settings.app_version,
        "azure_openai_endpoint": str(settings.azure_openai.endpoint),
        "azure_search_endpoint": str(settings.azure_search.endpoint),
    }

"""
Encoding Presets API Endpoints

Provides endpoints for retrieving encoding preset templates.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
import logging

from models.presets import (
    EncodingPreset,
    get_preset,
    get_all_presets,
    get_presets_by_category,
    get_presets_by_tag
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/presets", tags=["presets"])


@router.get("/", response_model=List[EncodingPreset])
async def list_presets(
    category: Optional[str] = Query(None, description="Filter by category"),
    tag: Optional[str] = Query(None, description="Filter by tag")
):
    """
    List all available encoding presets.

    Presets are pre-configured encoding templates for common use cases
    like HLS streaming, YouTube uploads, adaptive streaming, etc.

    Args:
        category: Optional category filter (streaming, upload, archive)
        tag: Optional tag filter (hls, abr, mobile, etc.)

    Returns:
        List[EncodingPreset]: List of preset templates

    Example:
        GET /api/v1/presets/
        GET /api/v1/presets/?category=streaming
        GET /api/v1/presets/?tag=abr
    """
    try:
        if category:
            presets = get_presets_by_category(category)
        elif tag:
            presets = get_presets_by_tag(tag)
        else:
            presets = get_all_presets()

        preset_list = list(presets.values())
        logger.info(f"Returning {len(preset_list)} presets (category={category}, tag={tag})")

        return preset_list

    except Exception as e:
        logger.error(f"Failed to list presets: {e}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to list presets", "error": str(e)}
        )


@router.get("/{preset_id}", response_model=EncodingPreset)
async def get_preset_by_id(preset_id: str):
    """
    Get a specific encoding preset by ID.

    Args:
        preset_id: Preset identifier (e.g., 'hls-720p', 'abr-full-hd')

    Returns:
        EncodingPreset: The requested preset template

    Raises:
        HTTPException: 404 if preset not found

    Example:
        GET /api/v1/presets/abr-full-hd
    """
    try:
        preset = get_preset(preset_id)

        if not preset:
            raise HTTPException(
                status_code=404,
                detail={"message": f"Preset '{preset_id}' not found"}
            )

        logger.info(f"Retrieved preset: {preset_id}")
        return preset

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get preset {preset_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to get preset", "error": str(e)}
        )


@router.get("/categories/list", response_model=List[str])
async def list_categories():
    """
    Get list of all available preset categories.

    Returns:
        List[str]: List of category names

    Example:
        GET /api/v1/presets/categories/list
        Response: ["streaming", "upload", "archive"]
    """
    try:
        presets = get_all_presets()
        categories = list(set(preset.category for preset in presets.values()))
        categories.sort()

        logger.info(f"Returning {len(categories)} categories")
        return categories

    except Exception as e:
        logger.error(f"Failed to list categories: {e}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to list categories", "error": str(e)}
        )


@router.get("/tags/list", response_model=List[str])
async def list_tags():
    """
    Get list of all available preset tags.

    Returns:
        List[str]: List of tag names

    Example:
        GET /api/v1/presets/tags/list
        Response: ["hls", "abr", "mobile", "1080p", ...]
    """
    try:
        presets = get_all_presets()
        tags = set()
        for preset in presets.values():
            tags.update(preset.tags)

        tag_list = list(tags)
        tag_list.sort()

        logger.info(f"Returning {len(tag_list)} tags")
        return tag_list

    except Exception as e:
        logger.error(f"Failed to list tags: {e}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to list tags", "error": str(e)}
        )

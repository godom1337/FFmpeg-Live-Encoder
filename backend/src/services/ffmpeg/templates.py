"""
Predefined encoding templates for common use cases.

This module defines 5 templates that cover common encoding scenarios:
1. Standard Web Streaming - balanced quality for web delivery
2. High-Quality Archive - maximum quality preservation
3. Low-Bandwidth Mobile - optimized for mobile networks
4. 4K HDR - ultra-high definition with HDR
5. Fast Preview - quick low-quality encoding for previews
"""

from typing import Dict, List, Optional
from models.templates import Template, TemplateId, TemplateSummary


# ============================================================================
# Template Definitions
# ============================================================================

TEMPLATES: Dict[str, Template] = {
    # ========================================================================
    # 1. Standard Web Streaming
    # ========================================================================
    TemplateId.WEB_STREAMING: Template(
        id=TemplateId.WEB_STREAMING,
        name="Standard Web Streaming",
        description="Balanced quality and file size for web delivery and social media platforms",
        video_codec="libx264",
        audio_codec="aac",
        video_bitrate="2500k",
        audio_bitrate="128k",
        video_profile="baseline",
        video_framerate=30,
        encoding_preset="medium",
        hardware_accel="none",
        recommended_use="General web streaming, social media (YouTube, Facebook, Twitter), embedded video players",
        tags=["web", "streaming", "balanced", "social-media", "h264"]
    ),

    # ========================================================================
    # 2. High-Quality Archive
    # ========================================================================
    TemplateId.HIGH_QUALITY: Template(
        id=TemplateId.HIGH_QUALITY,
        name="High-Quality Archive",
        description="Maximum quality preservation with H.265 for long-term storage and archival",
        video_codec="libx265",
        audio_codec="aac",
        video_bitrate="10000k",
        audio_bitrate="256k",
        video_profile="high",
        video_framerate=None,  # Preserve original framerate
        encoding_preset="slow",
        hardware_accel="none",
        recommended_use="Long-term archival, master copies, high-quality downloads, professional storage",
        tags=["archive", "high-quality", "h265", "hevc", "master", "preservation"]
    ),

    # ========================================================================
    # 3. Low-Bandwidth Mobile
    # ========================================================================
    TemplateId.LOW_BANDWIDTH: Template(
        id=TemplateId.LOW_BANDWIDTH,
        name="Low-Bandwidth Mobile",
        description="Optimized for mobile networks with reduced resolution and bitrate",
        video_codec="libx264",
        audio_codec="aac",
        video_bitrate="800k",
        audio_bitrate="64k",
        video_profile="baseline",
        video_framerate=24,
        video_resolution="854:480",  # 480p resolution
        encoding_preset="fast",
        hardware_accel="none",
        recommended_use="Mobile streaming, low-bandwidth networks, 3G/4G delivery, data-conscious users",
        tags=["mobile", "low-bandwidth", "480p", "data-saver", "h264"]
    ),

    # ========================================================================
    # 4. 4K HDR
    # ========================================================================
    TemplateId.FOUR_K_HDR: Template(
        id=TemplateId.FOUR_K_HDR,
        name="4K HDR",
        description="Ultra-high definition 4K with HDR (High Dynamic Range) support",
        video_codec="libx265",
        audio_codec="aac",
        video_bitrate="25000k",
        audio_bitrate="256k",
        video_profile="main10",  # 10-bit for HDR
        video_framerate=None,  # Preserve original framerate
        video_resolution="3840:2160",  # 4K resolution
        encoding_preset="slow",
        hardware_accel="none",
        recommended_use="4K displays, HDR content, premium streaming, high-end video production",
        tags=["4k", "uhd", "hdr", "high-bitrate", "h265", "10-bit", "premium"]
    ),

    # ========================================================================
    # 5. Fast Preview
    # ========================================================================
    TemplateId.FAST_PREVIEW: Template(
        id=TemplateId.FAST_PREVIEW,
        name="Fast Preview",
        description="Quick low-quality encoding for rapid previews and testing",
        video_codec="libx264",
        audio_codec="copy",  # Don't re-encode audio for speed
        video_bitrate="500k",
        audio_bitrate=None,
        video_profile="baseline",
        video_framerate=None,  # Preserve framerate
        video_resolution="640:360",  # 360p resolution
        encoding_preset="ultrafast",
        hardware_accel="none",
        recommended_use="Quick previews, testing encoding settings, rough cuts, draft versions",
        tags=["preview", "fast", "360p", "testing", "draft", "low-quality"]
    ),
}


# ============================================================================
# Template Service Functions
# ============================================================================

def get_all_templates() -> List[TemplateSummary]:
    """
    Get summaries of all available templates.

    Returns:
        List of template summaries (lightweight, no full encoding settings)
    """
    return [
        TemplateSummary(
            id=template.id,
            name=template.name,
            description=template.description,
            tags=template.tags,
            recommended_use=template.recommended_use
        )
        for template in TEMPLATES.values()
    ]


def get_template_by_id(template_id: str) -> Optional[Template]:
    """
    Get a specific template by ID.

    Args:
        template_id: Template identifier (e.g., "web_streaming")

    Returns:
        Full template with all encoding settings, or None if not found
    """
    return TEMPLATES.get(template_id)


def get_template_by_enum(template_id: TemplateId) -> Optional[Template]:
    """
    Get a specific template by enum value.

    Args:
        template_id: TemplateId enum value

    Returns:
        Full template with all encoding settings
    """
    return TEMPLATES.get(template_id)


def list_template_names() -> Dict[str, str]:
    """
    Get a simple mapping of template IDs to names.

    Returns:
        Dict mapping template ID to display name
    """
    return {
        template.id: template.name
        for template in TEMPLATES.values()
    }


def search_templates_by_tag(tag: str) -> List[TemplateSummary]:
    """
    Search templates by tag.

    Args:
        tag: Tag to search for (case-insensitive)

    Returns:
        List of matching template summaries
    """
    tag_lower = tag.lower()
    matching = [
        template for template in TEMPLATES.values()
        if tag_lower in [t.lower() for t in template.tags]
    ]

    return [
        TemplateSummary(
            id=template.id,
            name=template.name,
            description=template.description,
            tags=template.tags,
            recommended_use=template.recommended_use
        )
        for template in matching
    ]

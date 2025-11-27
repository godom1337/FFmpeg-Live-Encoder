"""
FFmpeg service package.

This module is being rewritten. The compatibility stubs below maintain
backward compatibility with the existing application while the new
implementation is developed.

TEMPORARY: These stubs will be replaced with the new implementation.
"""

import logging

logger = logging.getLogger(__name__)


# TEMPORARY COMPATIBILITY STUB
# This maintains backward compatibility while the new FFmpeg service is being implemented
def ffmpeg_launcher(*args, **kwargs):
    """
    TEMPORARY STUB: Placeholder for legacy ffmpeg_launcher function.

    This is a compatibility shim that prevents import errors while the new
    FFmpeg job creation system is being implemented.

    DO NOT USE: This function is deprecated and will be removed once the
    new implementation in command_builder.py is complete.
    """
    logger.warning(
        "Legacy ffmpeg_launcher called - this is a compatibility stub. "
        "New implementation in services.ffmpeg.command_builder should be used instead."
    )
    raise NotImplementedError(
        "Legacy ffmpeg_launcher has been removed. "
        "Please use the new FFmpeg job creation API at POST /api/jobs/create"
    )


__all__ = ['ffmpeg_launcher']

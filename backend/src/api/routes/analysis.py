"""
Input Analysis API Endpoints

Provides endpoints for analyzing media inputs using ffprobe to extract
detailed stream information before job creation.
"""

from fastapi import APIRouter, HTTPException, Body
import logging

from models.stream_info import AnalyzeInputRequest, InputAnalysisResult
from services.ffprobe_service import get_ffprobe_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])


@router.post("/input", response_model=InputAnalysisResult)
async def analyze_input(request: AnalyzeInputRequest = Body(...)):
    """
    Analyze a media input source using ffprobe.

    This endpoint examines the provided input URL/path and returns detailed
    information about all detected streams (video, audio, subtitle).

    Use this endpoint before creating a job to:
    - Discover available streams in the input
    - Extract codec and format information
    - Determine optimal encoding parameters
    - Validate that the input is accessible

    Args:
        request: Analysis request with URL and optional parameters

    Returns:
        InputAnalysisResult: Detailed stream information

    Raises:
        HTTPException: If analysis fails or times out
    """
    try:
        logger.info(f"Analyzing input: {request.url} (type: {request.type})")

        # Get ffprobe service
        ffprobe = get_ffprobe_service()

        # Perform analysis
        result = await ffprobe.analyze_input(
            url=request.url,
            timeout=request.timeout,
            input_type=request.type
        )

        # Check if analysis had errors
        if result.error:
            logger.warning(f"Analysis completed with error: {result.error}")
            # Still return the result, but with error information
            # This allows the client to display the error to the user
            return result

        # Log successful analysis
        logger.info(
            f"Analysis successful for {request.url}: "
            f"{len(result.video_streams)} video, "
            f"{len(result.audio_streams)} audio, "
            f"{len(result.subtitle_streams)} subtitle streams"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to analyze input {request.url}: {e}")
        # Return analysis result with error instead of raising exception
        # This provides better UX as the client can display the error
        return InputAnalysisResult(
            url=request.url,
            error=f"Analysis failed: {str(e)}"
        )


@router.post("/validate-input", response_model=dict)
async def validate_input(request: AnalyzeInputRequest = Body(...)):
    """
    Quick validation check for input accessibility.

    This is a lighter-weight endpoint that just checks if the input
    can be accessed without performing full stream analysis.

    Args:
        request: Validation request with URL

    Returns:
        dict: Validation result with accessible flag and optional error

    Example response:
        {
            "accessible": true,
            "url": "udp://239.255.0.1:5000"
        }

        or

        {
            "accessible": false,
            "url": "invalid://bad-url",
            "error": "Invalid protocol"
        }
    """
    try:
        logger.info(f"Validating input accessibility: {request.url}")

        # Get ffprobe service
        ffprobe = get_ffprobe_service()

        # Perform quick analysis with short timeout
        result = await ffprobe.analyze_input(
            url=request.url,
            timeout=5,  # Short timeout for quick validation
            input_type=request.type
        )

        # Check if we got any streams or encountered error
        accessible = (
            result.error is None and
            (len(result.video_streams) > 0 or len(result.audio_streams) > 0)
        )

        response = {
            "accessible": accessible,
            "url": request.url
        }

        if result.error:
            response["error"] = result.error

        if accessible:
            response["stream_count"] = {
                "video": len(result.video_streams),
                "audio": len(result.audio_streams),
                "subtitle": len(result.subtitle_streams)
            }

        logger.info(f"Validation result for {request.url}: accessible={accessible}")

        return response

    except Exception as e:
        logger.error(f"Failed to validate input {request.url}: {e}")
        return {
            "accessible": False,
            "url": request.url,
            "error": str(e)
        }

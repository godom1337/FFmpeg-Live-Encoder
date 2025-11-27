"""
FFprobe integration service for analyzing media input sources.

This service provides functionality to analyze media files and streams
using ffprobe to extract detailed information about video, audio, and
subtitle streams.
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

from models.stream_info import (
    InputAnalysisResult,
    VideoStreamInfo,
    AudioStreamInfo,
    SubtitleStreamInfo,
    StreamType
)

logger = logging.getLogger(__name__)


class FFprobeService:
    """Service for analyzing media inputs using ffprobe."""

    def __init__(self, ffprobe_path: str = "ffprobe"):
        """
        Initialize the FFprobe service.

        Args:
            ffprobe_path: Path to ffprobe binary (default: "ffprobe" from PATH)
        """
        self.ffprobe_path = ffprobe_path

    async def analyze_input(
        self,
        url: str,
        timeout: int = 10,
        input_type: Optional[str] = None
    ) -> InputAnalysisResult:
        """
        Analyze a media input using ffprobe.

        Args:
            url: Input URL/path to analyze
            timeout: Analysis timeout in seconds
            input_type: Optional input type hint (udp, http, file)

        Returns:
            InputAnalysisResult with extracted stream information

        Raises:
            TimeoutError: If analysis exceeds timeout
            RuntimeError: If ffprobe execution fails
        """
        try:
            logger.info(f"Analyzing input: {url}")

            # Build ffprobe command
            command = self._build_ffprobe_command(url, input_type)

            # Execute ffprobe with timeout
            result = await self._execute_ffprobe(command, timeout)

            # Parse the result
            analysis = self._parse_ffprobe_output(result, url)

            logger.info(
                f"Analysis complete: {len(analysis.video_streams)} video, "
                f"{len(analysis.audio_streams)} audio, "
                f"{len(analysis.subtitle_streams)} subtitle streams"
            )

            return analysis

        except asyncio.TimeoutError:
            logger.error(f"FFprobe analysis timed out after {timeout}s for {url}")
            return InputAnalysisResult(
                url=url,
                error=f"Analysis timed out after {timeout} seconds"
            )
        except Exception as e:
            logger.error(f"FFprobe analysis failed for {url}: {str(e)}")
            return InputAnalysisResult(
                url=url,
                error=f"Analysis failed: {str(e)}"
            )

    def _build_ffprobe_command(
        self,
        url: str,
        input_type: Optional[str] = None
    ) -> List[str]:
        """
        Build the ffprobe command for analyzing input.

        Args:
            url: Input URL/path
            input_type: Optional input type hint

        Returns:
            List of command arguments
        """
        command = [
            self.ffprobe_path,
            "-v", "quiet",  # Suppress log output
            "-print_format", "json",  # Output as JSON
            "-show_format",  # Show format/container info
            "-show_streams",  # Show stream info
        ]

        # Add protocol-specific options
        if input_type == "udp":
            command.extend([
                "-timeout", "3000000",  # 3 second timeout for UDP
                "-analyzeduration", "2000000",  # Analyze only 2 seconds (fast)
                "-probesize", "5000000"  # Probe size 5MB (reduced)
            ])
        elif input_type == "http" or url.startswith("http"):
            command.extend([
                "-timeout", "5000000",  # 5 second timeout for HTTP (reduced from 10s)
                "-analyzeduration", "2000000",  # Analyze only 2 seconds (fast, reduced from 10s)
                "-probesize", "10000000"  # Probe size 10MB (reduced from 20MB)
            ])
        elif input_type == "file" or Path(url).exists():
            # For files, use fast analysis without frame counting
            # Removed -count_frames to speed up analysis (User Story 7 optimization)
            pass

        command.append(url)
        return command

    async def _execute_ffprobe(
        self,
        command: List[str],
        timeout: int
    ) -> Dict[str, Any]:
        """
        Execute ffprobe command and return parsed JSON output.

        Args:
            command: Command arguments
            timeout: Execution timeout in seconds

        Returns:
            Parsed JSON output from ffprobe

        Raises:
            TimeoutError: If execution exceeds timeout
            RuntimeError: If ffprobe returns non-zero exit code
        """
        logger.debug(f"Executing: {' '.join(command)}")

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise

        if process.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="ignore")
            logger.error(f"FFprobe failed with code {process.returncode}: {error_msg}")
            raise RuntimeError(f"FFprobe failed: {error_msg}")

        # Parse JSON output
        output = stdout.decode("utf-8", errors="ignore")
        try:
            return json.loads(output)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse ffprobe JSON output: {e}")
            raise RuntimeError(f"Invalid JSON output from ffprobe: {e}")

    def _parse_ffprobe_output(
        self,
        data: Dict[str, Any],
        url: str
    ) -> InputAnalysisResult:
        """
        Parse ffprobe JSON output into InputAnalysisResult.

        Args:
            data: Parsed JSON data from ffprobe
            url: Original input URL

        Returns:
            InputAnalysisResult with extracted information
        """
        # Extract format information
        format_info = data.get("format", {})

        # Extract streams
        streams = data.get("streams", [])

        video_streams = []
        audio_streams = []
        subtitle_streams = []

        # Track audio stream index separately (0-based audio-only index)
        audio_index = 0

        for stream in streams:
            codec_type = stream.get("codec_type", "").lower()

            if codec_type == "video":
                video_stream = self._parse_video_stream(stream)
                if video_stream:
                    video_streams.append(video_stream)

            elif codec_type == "audio":
                audio_stream = self._parse_audio_stream(stream, audio_index)
                if audio_stream:
                    audio_streams.append(audio_stream)
                    audio_index += 1

            elif codec_type == "subtitle":
                subtitle_stream = self._parse_subtitle_stream(stream)
                if subtitle_stream:
                    subtitle_streams.append(subtitle_stream)

        return InputAnalysisResult(
            url=url,
            format_name=format_info.get("format_name"),
            format_long_name=format_info.get("format_long_name"),
            duration=self._parse_float(format_info.get("duration")),
            size=self._parse_int(format_info.get("size")),
            bit_rate=format_info.get("bit_rate"),
            video_streams=video_streams,
            audio_streams=audio_streams,
            subtitle_streams=subtitle_streams
        )

    def _parse_video_stream(self, stream: Dict[str, Any]) -> Optional[VideoStreamInfo]:
        """Parse video stream information."""
        try:
            width = stream.get("width")
            height = stream.get("height")

            if not width or not height:
                return None

            # Calculate FPS from frame rate
            fps = None
            if "r_frame_rate" in stream:
                fps = self._parse_frame_rate(stream["r_frame_rate"])
            elif "avg_frame_rate" in stream:
                fps = self._parse_frame_rate(stream["avg_frame_rate"])

            return VideoStreamInfo(
                index=stream.get("index", 0),
                codec_name=stream.get("codec_name", "unknown"),
                codec_long_name=stream.get("codec_long_name"),
                profile=stream.get("profile"),
                width=width,
                height=height,
                resolution=f"{width}x{height}",
                fps=fps,
                bit_rate=stream.get("bit_rate"),
                pix_fmt=stream.get("pix_fmt"),
                color_space=stream.get("color_space"),
                color_range=stream.get("color_range"),
                duration=self._parse_float(stream.get("duration")),
                nb_frames=self._parse_int(stream.get("nb_frames"))
            )
        except Exception as e:
            logger.warning(f"Failed to parse video stream: {e}")
            return None

    def _parse_audio_stream(self, stream: Dict[str, Any], audio_index: int) -> Optional[AudioStreamInfo]:
        """Parse audio stream information."""
        try:
            sample_rate = self._parse_int(stream.get("sample_rate"))
            channels = stream.get("channels")

            if not sample_rate or not channels:
                return None

            # Get language and title from tags
            tags = stream.get("tags", {})
            language = tags.get("language")
            title = tags.get("title")

            return AudioStreamInfo(
                index=stream.get("index", 0),  # Global stream index (0, 1, 2...)
                audio_index=audio_index,  # Audio-only index (0:a:0, 0:a:1...)
                codec_name=stream.get("codec_name", "unknown"),
                codec_long_name=stream.get("codec_long_name"),
                sample_rate=sample_rate,
                channels=channels,
                channel_layout=stream.get("channel_layout"),
                bit_rate=stream.get("bit_rate"),
                duration=self._parse_float(stream.get("duration")),
                language=language,
                title=title
            )
        except Exception as e:
            logger.warning(f"Failed to parse audio stream: {e}")
            return None

    def _parse_subtitle_stream(
        self,
        stream: Dict[str, Any]
    ) -> Optional[SubtitleStreamInfo]:
        """Parse subtitle stream information."""
        try:
            return SubtitleStreamInfo(
                index=stream.get("index", 0),
                codec_name=stream.get("codec_name", "unknown"),
                codec_long_name=stream.get("codec_long_name"),
                language=stream.get("tags", {}).get("language"),
                title=stream.get("tags", {}).get("title")
            )
        except Exception as e:
            logger.warning(f"Failed to parse subtitle stream: {e}")
            return None

    @staticmethod
    def _parse_frame_rate(rate_str: str) -> Optional[float]:
        """
        Parse frame rate string (e.g., "30/1", "30000/1001") to float.

        Args:
            rate_str: Frame rate as fraction string

        Returns:
            Frame rate as float, or None if parsing fails
        """
        try:
            if "/" in rate_str:
                num, den = rate_str.split("/")
                num_val = float(num)
                den_val = float(den)
                if den_val == 0:
                    return None
                return round(num_val / den_val, 2)
            return float(rate_str)
        except (ValueError, ZeroDivisionError):
            return None

    @staticmethod
    def _parse_float(value: Any) -> Optional[float]:
        """Safely parse value to float."""
        try:
            return float(value) if value is not None else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_int(value: Any) -> Optional[int]:
        """Safely parse value to int."""
        try:
            return int(value) if value is not None else None
        except (ValueError, TypeError):
            return None


# Global service instance
_ffprobe_service: Optional[FFprobeService] = None


def get_ffprobe_service() -> FFprobeService:
    """
    Get the global FFprobe service instance.

    Returns:
        FFprobeService instance
    """
    global _ffprobe_service
    if _ffprobe_service is None:
        _ffprobe_service = FFprobeService()
    return _ffprobe_service

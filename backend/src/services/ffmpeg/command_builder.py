"""
FFmpeg command builder for job creation.

This module provides functions to build FFmpeg commands from job requests.
It implements the minimal-default approach: commands start simple and only
add complexity when explicitly requested.
"""

from typing import List
from pathlib import Path
import logging
from models.encoding_settings import CreateJobRequest
from models.rendition import Rendition

logger = logging.getLogger(__name__)


def build_ffmpeg_command(request: CreateJobRequest) -> List[str]:
    """
    Build FFmpeg command list from job request.

    This implements the minimal-default strategy:
    - Default command: ffmpeg -i INPUT -c:v libx264 -c:a copy OUTPUT
    - Additional options only added if explicitly provided
    - ABR-enabled HLS jobs use filter_complex for multi-variant encoding

    Args:
        request: Job creation request with encoding settings

    Returns:
        List of command arguments (safe for subprocess.run without shell=True)

    Example:
        >>> request = CreateJobRequest(input_file="/input/video.mp4", output_file="/output/output.mp4")
        >>> cmd = build_ffmpeg_command(request)
        >>> cmd
        ['ffmpeg', '-i', '/input/video.mp4', '-c:v', 'libx264', '-c:a', 'copy', '/output/output.mp4']
    """
    # Check if ABR is enabled (top-level or in HLS output)
    abr_enabled = request.abr_enabled or (request.hls_output and request.hls_output.abr_enabled)
    abr_renditions = request.abr_renditions or (request.hls_output and request.hls_output.renditions)

    if abr_enabled and abr_renditions:
        # Determine output type for ABR
        if request.hls_output:
            return build_abr_hls_command(request, abr_renditions)
        elif request.udp_outputs and len(request.udp_outputs) > 0:
            return build_abr_udp_command(request, abr_renditions)
        # If neither HLS nor UDP, fall through to standard command

    # Standard single-output command
    cmd = ["ffmpeg"]

    # Hardware acceleration (must be BEFORE input)
    if request.hardware_accel and request.hardware_accel != "none":
        if request.hardware_accel == "nvenc":
            cmd.extend(["-hwaccel", "cuda"])
        elif request.hardware_accel == "vaapi":
            cmd.extend(["-hwaccel", "vaapi"])
        elif request.hardware_accel == "videotoolbox":
            cmd.extend(["-hwaccel", "videotoolbox"])

    # Loop input (must be BEFORE input for continuous streaming)
    if request.loop_input:
        cmd.extend(["-stream_loop", "-1"])  # -1 = infinite loop
        cmd.extend(["-re"])  # Read input at native framerate (real-time)

    # Input format (e.g., avfoundation, v4l2)
    if request.input_format:
        cmd.extend(["-f", request.input_format])

    # Additional input arguments
    if request.input_args:
        cmd.extend(request.input_args)

    # Input file
    cmd.extend(["-i", request.input_file])

    # Stream mapping (User Story 7)
    # Must come AFTER input but BEFORE codec options
    # FFmpeg processes -map flags to select which input streams to include
    has_audio_map = False
    if request.stream_maps:
        for stream_map in request.stream_maps:
            cmd.extend(["-map", stream_map.input_stream])
            if stream_map.output_label == 'a':
                has_audio_map = True

    # AVFoundation timestamp fix for HLS output (must come after -map but before encoding options)
    # These flags fix timestamp issues when capturing from AVFoundation devices
    if request.input_format and request.input_format == "avfoundation" and request.hls_output:
        cmd.extend(["-vsync", "cfr"])  # Constant frame rate
        cmd.extend(["-copytb", "1"])   # Copy input timestamps to output
        cmd.extend(["-start_at_zero"])  # Start timestamps at zero

        # Set keyframe interval for better HLS segmentation
        # Calculate GOP size based on framerate (2 seconds worth of frames)
        fps = request.video_framerate or 30
        gop_size = fps * 2
        cmd.extend(["-g", str(gop_size)])
        cmd.extend(["-keyint_min", str(gop_size)])

    # Video codec (default: libx264)
    # Convert to hardware encoder if hardware acceleration is enabled
    video_codec = request.video_codec.value if hasattr(request.video_codec, 'value') else request.video_codec

    if request.hardware_accel and request.hardware_accel != "none":
        codec_map = {
            "nvenc": {
                "libx264": "h264_nvenc",
                "h264": "h264_nvenc",
                "libx265": "hevc_nvenc",
                "h265": "hevc_nvenc",
                "libaom-av1": "av1_nvenc",
                "av1": "av1_nvenc",
            },
            "vaapi": {
                "libx264": "h264_vaapi",
                "h264": "h264_vaapi",
                "libx265": "hevc_vaapi",
                "h265": "hevc_vaapi",
                "libaom-av1": "av1_vaapi",
                "av1": "av1_vaapi",
            },
            "videotoolbox": {
                "libx264": "h264_videotoolbox",
                "h264": "h264_videotoolbox",
                "libx265": "hevc_videotoolbox",
                "h265": "hevc_videotoolbox",
                # Note: AV1 is not supported by VideoToolbox
            },
        }
        # Convert software codec to hardware equivalent if mapping exists
        if request.hardware_accel in codec_map:
            video_codec = codec_map[request.hardware_accel].get(video_codec, video_codec)

    cmd.extend(["-c:v", video_codec])

    # Add video codec tag for HEVC compatibility (hvc1 works better than hev1 on Apple devices)
    if "hevc" in video_codec.lower() or "265" in video_codec.lower():
        cmd.extend(["-tag:v", "hvc1"])

    # Optional video settings
    if request.video_bitrate:
        cmd.extend(["-b:v", request.video_bitrate])

    if request.video_profile:
        cmd.extend(["-profile:v", request.video_profile])

    if request.video_framerate:
        cmd.extend(["-r", str(request.video_framerate)])

    if request.encoding_preset:
        cmd.extend(["-preset", request.encoding_preset])

    # Video filters (scale and custom filters)
    filters = []
    if request.video_resolution:
        filters.append(f"scale={request.video_resolution}")
    if request.video_filters:
        filters.append(request.video_filters)

    if filters:
        cmd.extend(["-vf", ",".join(filters)])

    # Audio handling - check if audio stream map exists
    # If stream_maps is defined but has no audio map, it means audio is intentionally disabled
    if request.stream_maps and not has_audio_map:
        # Disable audio completely
        cmd.extend(["-an"])
    else:
        # Audio codec (default: copy)
        cmd.extend(["-c:a", request.audio_codec.value if hasattr(request.audio_codec, 'value') else request.audio_codec])

        # Optional audio settings
        if request.audio_bitrate:
            cmd.extend(["-b:a", request.audio_bitrate])

        if request.audio_channels:
            cmd.extend(["-ac", str(request.audio_channels)])

        if request.audio_volume is not None:
            # Convert 0-100 scale to FFmpeg volume filter (0-100 becomes 0.0-1.0)
            volume_multiplier = request.audio_volume / 100.0
            cmd.extend(["-af", f"volume={volume_multiplier}"])

    # Output handling (User Story 3: Multi-output support)
    # FFmpeg supports multiple outputs in a single command
    # In FFmpeg, options specified BEFORE an output apply to that specific output
    # Options must be repeated for each output that needs them

    # Primary output
    if request.hls_output:
        # HLS output replaces primary file output
        hls = request.hls_output
        cmd.extend(["-f", "hls"])
        cmd.extend(["-hls_time", str(hls.segment_duration)])

        # Set segment type: mpegts (universal) or fmp4 (required for HEVC/AV1)
        # FFmpeg automatically sets EXT-X-VERSION based on segment type and codec
        # - mpegts → Version 3 (H.264 compatible)
        # - fmp4 → Version 7 (HEVC/AV1 compatible)
        # Note: User can select either format; HEVC/AV1 work best with fMP4 but mpegts is also supported
        segment_type = hls.segment_type if hasattr(hls, 'segment_type') else "mpegts"

        cmd.extend(["-hls_segment_type", segment_type])

        # Set fmp4 init filename if using fragmented MP4
        if segment_type == "fmp4":
            cmd.extend(["-hls_fmp4_init_filename", "init.mp4"])

        # HLS playlist type handling
        # 'live' = rolling window (no playlist_type set, use list_size + delete_segments)
        # 'event' = seekable live (keeps all segments)
        # 'vod' = video on demand
        if hls.playlist_type == "live":
            cmd.extend(["-hls_list_size", str(hls.playlist_size)])
            cmd.extend(["-hls_flags", "delete_segments"])
        elif hls.playlist_type == "event":
            cmd.extend(["-hls_playlist_type", "event"])
        else:
            # Default: VOD
            cmd.extend(["-hls_playlist_type", "vod"])

        cmd.extend(["-hls_segment_filename", f"{hls.output_dir}/{hls.segment_pattern}"])

        # Add additional file outputs BEFORE HLS playlist (so they're processed first)
        for file_out in request.additional_outputs:
            # Add output-specific options right before each output
            if file_out.video_codec:
                cmd.extend(["-c:v", file_out.video_codec])
            if file_out.video_bitrate:
                cmd.extend(["-b:v", file_out.video_bitrate])
            if file_out.audio_codec:
                cmd.extend(["-c:a", file_out.audio_codec])
            if file_out.audio_bitrate:
                cmd.extend(["-b:a", file_out.audio_bitrate])
            if file_out.scale:
                cmd.extend(["-vf", f"scale={file_out.scale}"])

            cmd.append(file_out.output_file)

        # HLS playlist goes last
        cmd.append(f"{hls.output_dir}/{hls.playlist_name}")

    elif request.udp_outputs:
        # UDP streaming output (multiple UDP destinations possible)
        for idx, udp in enumerate(request.udp_outputs):
            # Add format for first UDP output only
            if idx == 0:
                cmd.extend(["-f", "mpegts"])
            cmd.append(udp.url)

        # Additional file outputs after UDP
        for file_out in request.additional_outputs:
            # Add output-specific options
            if file_out.video_codec:
                cmd.extend(["-c:v", file_out.video_codec])
            if file_out.video_bitrate:
                cmd.extend(["-b:v", file_out.video_bitrate])
            if file_out.audio_codec:
                cmd.extend(["-c:a", file_out.audio_codec])
            if file_out.audio_bitrate:
                cmd.extend(["-b:a", file_out.audio_bitrate])
            if file_out.scale:
                cmd.extend(["-vf", f"scale={file_out.scale}"])

            cmd.append(file_out.output_file)

    elif request.rtmp_outputs:
        # RTMP streaming output (e.g., YouTube)
        for rtmp in request.rtmp_outputs:
            cmd.extend(["-f", "flv"])
            cmd.append(rtmp.full_url)

        # Additional file outputs after RTMP
        for file_out in request.additional_outputs:
            # Add output-specific options
            if file_out.video_codec:
                cmd.extend(["-c:v", file_out.video_codec])
            if file_out.video_bitrate:
                cmd.extend(["-b:v", file_out.video_bitrate])
            if file_out.audio_codec:
                cmd.extend(["-c:a", file_out.audio_codec])
            if file_out.audio_bitrate:
                cmd.extend(["-b:a", file_out.audio_bitrate])
            if file_out.scale:
                cmd.extend(["-vf", f"scale={file_out.scale}"])

            cmd.append(file_out.output_file)

    else:
        # Standard file output
        if request.output_file:
            cmd.append(request.output_file)

        # Additional file outputs
        for file_out in request.additional_outputs:
            # Add output-specific options right before each output
            if file_out.video_codec:
                cmd.extend(["-c:v", file_out.video_codec])
            if file_out.video_bitrate:
                cmd.extend(["-b:v", file_out.video_bitrate])
            if file_out.audio_codec:
                cmd.extend(["-c:a", file_out.audio_codec])
            if file_out.audio_bitrate:
                cmd.extend(["-b:a", file_out.audio_bitrate])
            if file_out.scale:
                cmd.extend(["-vf", f"scale={file_out.scale}"])

            cmd.append(file_out.output_file)

    return cmd


def generate_output_path(input_file: str) -> str:
    """
    Generate output file path from input file path.

    Takes the input filename and creates a corresponding output path
    in the /output directory with the same extension.

    Args:
        input_file: Path to input file (e.g., "/input/my_video.mp4")

    Returns:
        Generated output path (e.g., "/output/my_video_encoded.mp4")

    Example:
        >>> generate_output_path("/input/video.mp4")
        '/output/video_encoded.mp4'
    """
    input_path = Path(input_file)

    # Get filename without extension
    basename = input_path.stem

    # Get extension
    extension = input_path.suffix

    # Generate output path in /output directory
    output_filename = f"{basename}_encoded{extension}"
    output_path = Path("/output") / output_filename

    return str(output_path)


# ============================================================================
# ABR (Adaptive Bitrate) Multi-Variant Encoding
# ============================================================================


def build_abr_hls_command(request: CreateJobRequest, renditions) -> List[str]:
    """
    Build FFmpeg command for ABR (Adaptive Bitrate) HLS multi-variant encoding.

    Uses filter_complex with split and scale filters to generate multiple
    quality variants from a single input in one FFmpeg process.

    Args:
        request: Job creation request
        renditions: List of Rendition objects for quality variants

    Returns:
        List of FFmpeg command arguments

    Example:
        >>> # Creates 3 variants: 1080p, 720p, 480p
        >>> request = CreateJobRequest(...)
        >>> cmd = build_abr_hls_command(request, renditions)
        >>> # Returns: ['ffmpeg', '-i', 'input.mp4', '-filter_complex', '...', '-map', ...]
    """
    cmd = ["ffmpeg"]
    hls = request.hls_output

    # Hardware acceleration (must be BEFORE input)
    if request.hardware_accel and request.hardware_accel != "none":
        if request.hardware_accel == "nvenc":
            cmd.extend(["-hwaccel", "cuda"])
        elif request.hardware_accel == "vaapi":
            cmd.extend(["-hwaccel", "vaapi"])
        elif request.hardware_accel == "videotoolbox":
            cmd.extend(["-hwaccel", "videotoolbox"])

    # Loop input (must be BEFORE input for continuous streaming)
    if request.loop_input:
        cmd.extend(["-stream_loop", "-1"])
        cmd.extend(["-re"])

    # Input format (e.g., avfoundation, v4l2)
    if request.input_format:
        cmd.extend(["-f", request.input_format])

    # Additional input arguments
    if request.input_args:
        cmd.extend(request.input_args)

    # Input file
    cmd.extend(["-i", request.input_file])

    # AVFoundation timestamp fix for HLS output (must come after input but before filter_complex)
    # These flags fix timestamp issues when capturing from AVFoundation devices
    if request.input_format and request.input_format == "avfoundation":
        cmd.extend(["-vsync", "cfr"])  # Constant frame rate
        cmd.extend(["-copytb", "1"])   # Copy input timestamps to output
        cmd.extend(["-start_at_zero"])  # Start timestamps at zero

        # Set keyframe interval for better HLS segmentation
        # Calculate GOP size based on framerate (2 seconds worth of frames)
        fps = request.video_framerate or 30
        gop_size = fps * 2
        cmd.extend(["-g", str(gop_size)])
        cmd.extend(["-keyint_min", str(gop_size)])

    # Determine video and audio track from stream_maps (if provided)
    video_input = "0:v"  # Default to first video stream
    audio_input = "0:a?"  # Default to first audio stream (optional)

    if request.stream_maps:
        for stream_map in request.stream_maps:
            if stream_map.output_label == 'v':
                video_input = stream_map.input_stream
            elif stream_map.output_label == 'a':
                audio_input = stream_map.input_stream

    # Generate filter_complex for multi-variant encoding
    filter_complex = generate_split_and_scale_filters(renditions, video_input)
    cmd.extend(["-filter_complex", filter_complex])

    # Generate outputs for each variant
    for rendition in renditions:
        variant_args = build_variant_output(rendition, hls, request.hardware_accel, audio_input)
        cmd.extend(variant_args)

    return cmd


def generate_split_and_scale_filters(renditions: List[Rendition], video_input: str = "0:v") -> str:
    """
    Generate FFmpeg filter_complex for splitting and scaling video to multiple variants.

    Creates a filter graph that:
    1. Splits input video into N streams (one per rendition)
    2. Scales each stream to its target resolution with aspect ratio preservation

    Args:
        renditions: List of Rendition objects with target resolutions
        video_input: Video stream specifier (e.g., "0:v", "0:v:1", "0:v:2")

    Returns:
        Filter_complex string for FFmpeg

    Example:
        >>> renditions = [
        ...     Rendition(name="1080p", video_resolution="1920x1080", ...),
        ...     Rendition(name="720p", video_resolution="1280x720", ...)
        ... ]
        >>> filter = generate_split_and_scale_filters(renditions, "0:v:1")
        >>> print(filter)
        '[0:v:1]split=2[v1][v2]; [v1]scale=1920:1080:force_original_aspect_ratio=decrease[v1080p]; ...'
    """
    num_variants = len(renditions)

    # Split input video into N streams
    split_outputs = [f"[v{i}]" for i in range(num_variants)]
    split_filter = f"[{video_input}]split={num_variants}{''.join(split_outputs)}"

    # Scale each stream to target resolution with aspect ratio preservation
    scale_filters = []
    for i, rendition in enumerate(renditions):
        width, height = rendition.video_resolution.split('x')
        input_label = f"[v{i}]"
        output_label = f"[v{rendition.name}]"

        # Use force_original_aspect_ratio=decrease to maintain aspect ratio
        # This ensures video fits within target dimensions without distortion
        # If source is 16:9 and target is also 16:9, it scales perfectly
        # If source is 4:3 and target is 16:9, it will be letterboxed
        scale_filter = f"{input_label} scale={width}:{height}:force_original_aspect_ratio=decrease {output_label}"
        scale_filters.append(scale_filter)

    # Combine all filters with semicolon separator
    all_filters = [split_filter] + scale_filters
    filter_complex = "; ".join(all_filters)

    return filter_complex


def build_variant_output(rendition: Rendition, hls_config, hardware_accel=None, audio_input: str = "0:a?") -> List[str]:
    """
    Build FFmpeg output arguments for a single ABR variant.

    Generates the -map, codec, bitrate, and output path arguments for
    one quality variant in an ABR ladder.

    Args:
        rendition: Rendition configuration for this variant
        hls_config: HLS output configuration
        hardware_accel: Hardware acceleration type (nvenc, vaapi, videotoolbox, or None)
        audio_input: Audio stream specifier (e.g., "0:a?", "0:a:1", "0:a:2")

    Returns:
        List of FFmpeg arguments for this variant

    Example:
        >>> rendition = Rendition(name="1080p", video_bitrate="5M", ...)
        >>> args = build_variant_output(rendition, hls_config, "nvenc", "0:a:2")
        >>> # Returns: ['-map', '[v1080p]', '-map', '0:a:2', '-c:v', 'h264_nvenc', ...]
    """
    args = []

    # Map the scaled video stream
    args.extend(["-map", f"[v{rendition.name}]"])

    # Map selected audio stream (shared across all variants)
    args.extend(["-map", audio_input])

    # Video codec with hardware acceleration support
    video_codec = rendition.video_codec or "libx264"

    # Convert to hardware encoder if hardware acceleration is enabled
    if hardware_accel and hardware_accel != "none":
        codec_map = {
            "nvenc": {
                "h264": "h264_nvenc",
                "libx264": "h264_nvenc",
                "h265": "hevc_nvenc",
                "libx265": "hevc_nvenc",
                "av1": "av1_nvenc",
                "libaom-av1": "av1_nvenc",
            },
            "vaapi": {
                "h264": "h264_vaapi",
                "libx264": "h264_vaapi",
                "h265": "hevc_vaapi",
                "libx265": "hevc_vaapi",
                "av1": "av1_vaapi",
                "libaom-av1": "av1_vaapi",
            },
            "videotoolbox": {
                "h264": "h264_videotoolbox",
                "libx264": "h264_videotoolbox",
                "h265": "hevc_videotoolbox",
                "libx265": "hevc_videotoolbox",
                # Note: AV1 is not supported by VideoToolbox
            },
        }

        if hardware_accel in codec_map and video_codec in codec_map[hardware_accel]:
            video_codec = codec_map[hardware_accel][video_codec]

    args.extend(["-c:v", video_codec])

    # Add video codec tag for HEVC compatibility (hvc1 works better than hev1 on Apple devices)
    if "hevc" in video_codec.lower() or "265" in video_codec.lower():
        args.extend(["-tag:v", "hvc1"])

    # Video bitrate
    args.extend(["-b:v", rendition.video_bitrate])

    # Max bitrate (for CBR-like encoding)
    if rendition.max_bitrate:
        args.extend(["-maxrate", rendition.max_bitrate])
    else:
        # Default to same as target bitrate
        args.extend(["-maxrate", rendition.video_bitrate])

    # Buffer size (typically 2x bitrate for HLS)
    if rendition.buffer_size:
        args.extend(["-bufsize", rendition.buffer_size])
    else:
        # Calculate as 2x bitrate
        bitrate_val = rendition.video_bitrate
        if bitrate_val.endswith('M'):
            buffer = f"{int(float(bitrate_val[:-1]) * 2)}M"
        elif bitrate_val.endswith('k'):
            buffer = f"{int(float(bitrate_val[:-1]) * 2)}k"
        else:
            buffer = str(int(bitrate_val) * 2)
        args.extend(["-bufsize", buffer])

    # Video profile
    if rendition.video_profile:
        args.extend(["-profile:v", rendition.video_profile])

    # Encoding preset
    preset = rendition.preset or "medium"
    args.extend(["-preset", preset])

    # Video framerate (FPS)
    if rendition.video_framerate:
        args.extend(["-r", str(rendition.video_framerate)])

    # Audio codec
    audio_codec = rendition.audio_codec or "aac"
    args.extend(["-c:a", audio_codec])

    # Audio bitrate
    if rendition.audio_bitrate:
        args.extend(["-b:a", rendition.audio_bitrate])

    # Audio channels
    if rendition.audio_channels:
        args.extend(["-ac", str(rendition.audio_channels)])

    # Audio sample rate
    if rendition.audio_sample_rate:
        args.extend(["-ar", str(rendition.audio_sample_rate)])

    # Audio volume (0-100 scale, where 100 is original volume)
    # FFmpeg uses a multiplier (1.0 = original), so we convert: volume/100
    if rendition.audio_volume is not None and rendition.audio_volume != 100:
        volume_multiplier = rendition.audio_volume / 100.0
        args.extend(["-af", f"volume={volume_multiplier}"])

    # HLS output settings
    args.extend(["-f", "hls"])
    args.extend(["-hls_time", str(hls_config.segment_duration)])

    # Segment type
    segment_type = hls_config.segment_type if hasattr(hls_config, 'segment_type') else "mpegts"
    args.extend(["-hls_segment_type", segment_type])

    if segment_type == "fmp4":
        # Init file goes in same directory as segments (already includes rendition path in segment_filename)
        args.extend(["-hls_fmp4_init_filename", "init.mp4"])

    # Playlist type
    playlist_type = hls_config.playlist_type if hasattr(hls_config, 'playlist_type') else "vod"
    if playlist_type == "live":
        # Live rolling window: use list_size + delete_segments without playlist_type
        args.extend(["-hls_list_size", str(hls_config.playlist_size if hasattr(hls_config, 'playlist_size') else 5)])
        args.extend(["-hls_flags", "delete_segments"])
    elif playlist_type == "event":
        args.extend(["-hls_playlist_type", "event"])
    else:
        args.extend(["-hls_playlist_type", "vod"])

    # Segment filename pattern
    segment_pattern = hls_config.segment_pattern if hasattr(hls_config, 'segment_pattern') else "segment_%03d.ts"
    args.extend(["-hls_segment_filename", f"{hls_config.output_dir}/{rendition.name}/{segment_pattern}"])

    # Output variant playlist
    args.append(f"{hls_config.output_dir}/{rendition.name}/index.m3u8")

    return args


def build_abr_udp_command(request: CreateJobRequest, renditions) -> List[str]:
    """
    Build FFmpeg command for ABR (Adaptive Bitrate) UDP multi-variant streaming.

    Sends each quality variant to its specified UDP destination from rendition.output_url,
    or auto-increments ports from base UDP address if output_url not specified.

    Args:
        request: Job creation request
        renditions: List of Rendition objects for quality variants

    Returns:
        List of FFmpeg command arguments
    """
    cmd = ["ffmpeg"]

    # Hardware acceleration
    if request.hardware_accel and request.hardware_accel != "none":
        if request.hardware_accel == "nvenc":
            cmd.extend(["-hwaccel", "cuda"])
        elif request.hardware_accel == "vaapi":
            cmd.extend(["-hwaccel", "vaapi"])
        elif request.hardware_accel == "videotoolbox":
            cmd.extend(["-hwaccel", "videotoolbox"])

    # Loop input
    if request.loop_input:
        cmd.extend(["-stream_loop", "-1"])
        cmd.extend(["-re"])

    # Input format (e.g., avfoundation, v4l2)
    if request.input_format:
        cmd.extend(["-f", request.input_format])

    # Additional input arguments
    if request.input_args:
        cmd.extend(request.input_args)

    # Input
    cmd.extend(["-i", request.input_file])

    # AVFoundation timestamp fix (must come after input but before filter_complex)
    # These flags fix timestamp issues when capturing from AVFoundation devices
    if request.input_format and request.input_format == "avfoundation":
        cmd.extend(["-vsync", "cfr"])  # Constant frame rate
        cmd.extend(["-copytb", "1"])   # Copy input timestamps to output
        cmd.extend(["-start_at_zero"])  # Start timestamps at zero

        # Set keyframe interval for better segmentation
        # Calculate GOP size based on framerate (2 seconds worth of frames)
        fps = request.video_framerate or 30
        gop_size = fps * 2
        cmd.extend(["-g", str(gop_size)])
        cmd.extend(["-keyint_min", str(gop_size)])

    # Determine video and audio track from stream_maps (if provided)
    video_input = "0:v"  # Default to first video stream
    audio_input = "0:a?"  # Default to first audio stream (optional)

    if request.stream_maps:
        for stream_map in request.stream_maps:
            if stream_map.output_label == 'v':
                video_input = stream_map.input_stream
            elif stream_map.output_label == 'a':
                audio_input = stream_map.input_stream

    # Generate filter_complex for multi-variant encoding
    filter_complex = generate_split_and_scale_filters(renditions, video_input)
    cmd.extend(["-filter_complex", filter_complex])

    # Get base UDP address and port for fallback (if renditions don't specify output_url)
    base_udp = request.udp_outputs[0] if request.udp_outputs else None
    base_address = None
    base_port = None
    base_ttl = 16
    base_pkt_size = 1316

    if base_udp:
        # Parse base address, port, and get ttl/pkt_size from the UDPOutput object
        import re
        udp_url_str = base_udp.url if hasattr(base_udp, 'url') else str(base_udp)
        udp_match = re.match(r'udp://([^:]+):(\d+)', udp_url_str)
        if udp_match:
            base_address = udp_match.group(1)
            base_port = int(udp_match.group(2))
        # Get ttl and pkt_size from the UDPOutput object attributes
        if hasattr(base_udp, 'ttl'):
            base_ttl = base_udp.ttl
        if hasattr(base_udp, 'pkt_size'):
            base_pkt_size = base_udp.pkt_size

    # Generate outputs for each variant
    for idx, rendition in enumerate(renditions):
        # Use rendition's output_url if specified, otherwise auto-increment from base
        if hasattr(rendition, 'output_url') and rendition.output_url:
            udp_url = rendition.output_url
        elif base_address and base_port:
            variant_port = base_port + idx
            udp_url = f"udp://{base_address}:{variant_port}?ttl={base_ttl}&pkt_size={base_pkt_size}"
        else:
            raise ValueError(f"No output URL specified for rendition '{rendition.name}' and no base UDP output provided")

        # Map the scaled video stream and selected audio stream
        cmd.extend(["-map", f"[v{rendition.name}]"])
        cmd.extend(["-map", audio_input])

        # Video codec with hardware acceleration
        video_codec = rendition.video_codec or "libx264"
        if request.hardware_accel and request.hardware_accel != "none":
            codec_map = {
                "nvenc": {"h264": "h264_nvenc", "libx264": "h264_nvenc", "h265": "hevc_nvenc", "libx265": "hevc_nvenc", "av1": "av1_nvenc", "libaom-av1": "av1_nvenc"},
                "vaapi": {"h264": "h264_vaapi", "libx264": "h264_vaapi", "h265": "hevc_vaapi", "libx265": "hevc_vaapi", "av1": "av1_vaapi", "libaom-av1": "av1_vaapi"},
                "videotoolbox": {"h264": "h264_videotoolbox", "libx264": "h264_videotoolbox", "h265": "hevc_videotoolbox", "libx265": "hevc_videotoolbox"},
            }
            if request.hardware_accel in codec_map and video_codec in codec_map[request.hardware_accel]:
                video_codec = codec_map[request.hardware_accel][video_codec]

        cmd.extend(["-c:v", video_codec])
        cmd.extend(["-b:v", rendition.video_bitrate])
        cmd.extend(["-maxrate", rendition.video_bitrate])

        # Calculate buffer size
        bitrate_val = rendition.video_bitrate
        if bitrate_val.endswith('M'):
            buffer = f"{int(float(bitrate_val[:-1]) * 2)}M"
        elif bitrate_val.endswith('k'):
            buffer = f"{int(float(bitrate_val[:-1]) * 2)}k"
        else:
            buffer = str(int(bitrate_val) * 2)
        cmd.extend(["-bufsize", buffer])

        if rendition.video_profile:
            cmd.extend(["-profile:v", rendition.video_profile])

        preset = rendition.preset or "medium"
        cmd.extend(["-preset", preset])

        # Video framerate (FPS)
        if rendition.video_framerate:
            cmd.extend(["-r", str(rendition.video_framerate)])

        # Audio
        audio_codec = rendition.audio_codec or "aac"
        cmd.extend(["-c:a", audio_codec])
        if rendition.audio_bitrate:
            cmd.extend(["-b:a", rendition.audio_bitrate])
        if rendition.audio_channels:
            cmd.extend(["-ac", str(rendition.audio_channels)])
        if rendition.audio_sample_rate:
            cmd.extend(["-ar", str(rendition.audio_sample_rate)])

        # Audio volume (0-100 scale, where 100 is original volume)
        # FFmpeg uses a multiplier (1.0 = original), so we convert: volume/100
        if rendition.audio_volume is not None and rendition.audio_volume != 100:
            volume_multiplier = rendition.audio_volume / 100.0
            cmd.extend(["-af", f"volume={volume_multiplier}"])

        # UDP output format
        cmd.extend(["-f", "mpegts"])

        # UDP destination
        cmd.append(udp_url)

        logger.info(f"[ABR_UDP] Variant {rendition.name} → {udp_url}")

    return cmd

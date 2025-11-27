"""
Output Manager
HLS output directory structure creation and management
"""

import os
import shutil
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any

from models.output import OutputConfiguration
from models.profile import EncodingProfile
from models.variant import BitrateVariant

logger = logging.getLogger(__name__)


class OutputManager:
    """Manages HLS output directory structures"""

    def __init__(self, output_root: str = None):
        """Initialize output manager

        Args:
            output_root: Root directory for all outputs
        """
        self.output_root = output_root or os.getenv('OUTPUT_ROOT', '/output')

    async def create_output_structure(
        self,
        output_config: OutputConfiguration,
        profile: EncodingProfile = None
    ) -> bool:
        """Create HLS output directory structure

        Supports both traditional profile variants and ABR renditions.

        Args:
            output_config: Output configuration
            profile: Encoding profile with variants (optional for ABR)

        Returns:
            bool: True if structure created successfully
        """
        try:
            base_path = output_config.base_path

            # Create base directory
            await self._create_directory(base_path)

            # Check if ABR is enabled with renditions
            if output_config.abr_enabled and output_config.renditions:
                # ABR mode: Create directories for each rendition
                for rendition in output_config.renditions:
                    variant_path = output_config.get_variant_path(rendition.name)
                    await self._create_directory(variant_path)

                    # Create initial playlist file (will be overwritten by FFmpeg)
                    playlist_path = output_config.get_variant_playlist_path(rendition.name)
                    await self._create_empty_playlist(playlist_path)

                logger.info(f"Created ABR output structure with {len(output_config.renditions)} variants at {base_path}")

            elif profile and profile.variants:
                # Traditional mode: Create variant directories from profile
                for variant in profile.variants:
                    variant_path = output_config.get_variant_path(variant.label)
                    await self._create_directory(variant_path)

                    # Create initial playlist file (will be overwritten by FFmpeg)
                    playlist_path = output_config.get_variant_playlist_path(variant.label)
                    await self._create_empty_playlist(playlist_path)

                # Create master playlist
                master_playlist_path = output_config.get_master_playlist_path()
                await self._create_master_playlist(
                    master_playlist_path,
                    profile,
                    output_config
                )

                logger.info(f"Created output structure with {len(profile.variants)} variants at {base_path}")

            else:
                # Single output mode: Create base directory only
                logger.info(f"Created single output structure at {base_path}")

            return True

        except Exception as e:
            logger.error(f"Failed to create output structure: {e}")
            return False

    async def _create_directory(self, path: str) -> None:
        """Create directory if it doesn't exist

        Args:
            path: Directory path
        """
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {path}")
        except Exception as e:
            logger.error(f"Failed to create directory {path}: {e}")
            raise

    async def _create_empty_playlist(self, path: str) -> None:
        """Create an empty HLS playlist file

        Args:
            path: Playlist file path
        """
        try:
            with open(path, 'w') as f:
                f.write("#EXTM3U\n")
                f.write("#EXT-X-VERSION:3\n")
                f.write("#EXT-X-TARGETDURATION:10\n")
                f.write("#EXT-X-MEDIA-SEQUENCE:0\n")
                f.write("#EXT-X-ENDLIST\n")
            logger.debug(f"Created empty playlist: {path}")
        except Exception as e:
            logger.error(f"Failed to create playlist {path}: {e}")
            raise

    async def _create_master_playlist(
        self,
        path: str,
        profile: EncodingProfile,
        output_config: OutputConfiguration
    ) -> None:
        """Create HLS master playlist

        Args:
            path: Master playlist path
            profile: Encoding profile with variants
            output_config: Output configuration
        """
        try:
            lines = ["#EXTM3U", "#EXT-X-VERSION:3"]

            for variant in profile.variants:
                # Calculate bandwidth
                bandwidth = self._calculate_bandwidth(variant)
                resolution = f"{variant.width}x{variant.height}"

                # Add variant entry
                lines.append(
                    f"#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},"
                    f"RESOLUTION={resolution}"
                )

                # Add relative path to variant playlist
                lines.append(f"{variant.label}/index.m3u8")

            content = "\n".join(lines) + "\n"

            with open(path, 'w') as f:
                f.write(content)

            logger.info(f"Created master playlist: {path}")

        except Exception as e:
            logger.error(f"Failed to create master playlist {path}: {e}")
            raise

    def _calculate_bandwidth(self, variant: BitrateVariant) -> int:
        """Calculate bandwidth from variant bitrate

        Args:
            variant: Bitrate variant

        Returns:
            int: Bandwidth in bits per second
        """
        bitrate_str = variant.video_bitrate

        if bitrate_str.endswith('M'):
            return int(float(bitrate_str[:-1]) * 1000000)
        elif bitrate_str.endswith('k'):
            return int(float(bitrate_str[:-1]) * 1000)
        else:
            return int(bitrate_str)

    async def cleanup_output(self, output_config: OutputConfiguration) -> bool:
        """Clean up output directory

        Args:
            output_config: Output configuration

        Returns:
            bool: True if cleanup successful
        """
        try:
            base_path = output_config.base_path

            if os.path.exists(base_path):
                shutil.rmtree(base_path)
                logger.info(f"Cleaned up output directory: {base_path}")

            return True

        except Exception as e:
            logger.error(f"Failed to cleanup output directory: {e}")
            return False

    async def validate_output_structure(
        self,
        output_config: OutputConfiguration,
        profile: EncodingProfile
    ) -> Dict[str, Any]:
        """Validate output directory structure exists

        Args:
            output_config: Output configuration
            profile: Encoding profile

        Returns:
            Dict: Validation results
        """
        results = {
            'valid': True,
            'missing_dirs': [],
            'missing_files': []
        }

        # Check base directory
        if not os.path.exists(output_config.base_path):
            results['missing_dirs'].append(output_config.base_path)
            results['valid'] = False

        # Check variant directories
        for variant in profile.variants:
            variant_path = output_config.get_variant_path(variant.label)
            if not os.path.exists(variant_path):
                results['missing_dirs'].append(variant_path)
                results['valid'] = False

        # Check master playlist
        master_path = output_config.get_master_playlist_path()
        if not os.path.exists(master_path):
            results['missing_files'].append(master_path)
            # This is not critical, can be recreated

        return results

    async def get_output_size(self, output_config: OutputConfiguration) -> int:
        """Get total size of output directory

        Args:
            output_config: Output configuration

        Returns:
            int: Total size in bytes
        """
        total_size = 0
        base_path = output_config.base_path

        if not os.path.exists(base_path):
            return 0

        try:
            for dirpath, dirnames, filenames in os.walk(base_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.isfile(filepath):
                        total_size += os.path.getsize(filepath)

            return total_size

        except Exception as e:
            logger.error(f"Failed to calculate output size: {e}")
            return 0

    async def list_segments(
        self,
        output_config: OutputConfiguration,
        variant_label: str
    ) -> List[str]:
        """List segments in a variant directory

        Args:
            output_config: Output configuration
            variant_label: Variant label

        Returns:
            List[str]: List of segment filenames
        """
        variant_path = output_config.get_variant_path(variant_label)
        segments = []

        if not os.path.exists(variant_path):
            return segments

        try:
            for filename in os.listdir(variant_path):
                if filename.endswith(('.ts', '.m4s')):
                    segments.append(filename)

            # Sort by segment number
            segments.sort(key=lambda x: self._extract_segment_number(x))
            return segments

        except Exception as e:
            logger.error(f"Failed to list segments: {e}")
            return []

    def _extract_segment_number(self, filename: str) -> int:
        """Extract segment number from filename

        Args:
            filename: Segment filename

        Returns:
            int: Segment number
        """
        import re
        match = re.search(r'(\d+)\.(ts|m4s)$', filename)
        if match:
            return int(match.group(1))
        return 0

    async def cleanup_old_segments(
        self,
        output_config: OutputConfiguration,
        keep_count: int = 10
    ) -> int:
        """Clean up old segments keeping only recent ones

        Args:
            output_config: Output configuration
            keep_count: Number of segments to keep

        Returns:
            int: Number of segments deleted
        """
        deleted = 0

        for variant_dir in output_config.variant_paths.values():
            if not os.path.exists(variant_dir):
                continue

            try:
                segments = await self.list_segments(output_config, variant_dir)

                # Delete older segments
                if len(segments) > keep_count:
                    for segment in segments[:-keep_count]:
                        segment_path = os.path.join(variant_dir, segment)
                        os.remove(segment_path)
                        deleted += 1

            except Exception as e:
                logger.error(f"Failed to cleanup segments in {variant_dir}: {e}")

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old segments")

        return deleted

    async def prepare_preview_files(
        self,
        output_config: OutputConfiguration,
        profile: EncodingProfile
    ) -> Dict[str, str]:
        """Prepare files for stream preview

        Args:
            output_config: Output configuration
            profile: Encoding profile

        Returns:
            Dict: Preview URLs for each variant
        """
        preview_urls = {}

        for variant in profile.variants:
            if output_config.nginx_served:
                # Use Nginx served URL
                preview_url = output_config.get_preview_url(variant.label)
            else:
                # Use file path
                preview_url = output_config.get_variant_playlist_path(variant.label)

            preview_urls[variant.label] = preview_url

        # Add master playlist
        if output_config.nginx_served:
            preview_urls['master'] = output_config.get_preview_url()
        else:
            preview_urls['master'] = output_config.get_master_playlist_path()

        return preview_urls


# Global instance
output_manager = OutputManager()
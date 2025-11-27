"""
Output Validator
Output directory conflict checking and validation
"""

import os
from typing import List, Optional, Set, Union
from pathlib import Path
import asyncio


class OutputValidator:
    """Validates output configuration and checks for conflicts"""

    @staticmethod
    async def check_directory_conflicts(
        base_path: str,
        job_id: str,
        active_jobs: Union[List[dict], List]
    ) -> List[str]:
        """Check for output directory conflicts with other jobs

        Args:
            base_path: Proposed output base path
            job_id: Current job ID (to exclude from check)
            active_jobs: List of active jobs (EncodingJob objects or dicts)

        Returns:
            List[str]: List of conflict errors
        """
        from models.job import EncodingJob
        from services.job_manager import job_manager

        errors = []

        # Normalize the base path
        normalized_path = os.path.abspath(base_path)

        # Check against other active jobs
        for job in active_jobs:
            # Handle both EncodingJob objects and dict formats
            if isinstance(job, EncodingJob):
                # Skip self
                if job.id == job_id:
                    continue

                # Fetch the full config for this job
                job_config = await job_manager.get_job_with_config(job.id)
                if not job_config or not job_config.get('output'):
                    continue

                other_path = os.path.abspath(job_config['output'].get('base_path', ''))
                job_name = job.name
                job_id_str = job.id
            else:
                # Legacy dict format
                if job['id'] == job_id:
                    continue

                if not job.get('output_config'):
                    continue

                other_path = os.path.abspath(job['output_config'].get('base_path', ''))
                job_name = job['name']
                job_id_str = job['id']

            # Check for exact match
            if normalized_path == other_path:
                errors.append(
                    f"Output directory conflicts with job '{job_name}' (ID: {job_id_str})"
                )

            # Check if one path is a subdirectory of another
            if normalized_path.startswith(other_path + os.sep):
                errors.append(
                    f"Output directory is inside job '{job_name}' output path"
                )
            elif other_path.startswith(normalized_path + os.sep):
                errors.append(
                    f"Output directory contains job '{job_name}' output path"
                )

        return errors

    @staticmethod
    async def validate_output_path(base_path: str) -> List[str]:
        """Validate the output path is writable and safe

        Args:
            base_path: Output base path

        Returns:
            List[str]: List of validation errors
        """
        errors = []

        # Check for dangerous patterns
        if '..' in base_path:
            errors.append("Output path cannot contain '..' for security reasons")

        # Check if path is absolute
        if not os.path.isabs(base_path):
            # Convert to absolute path based on configured output root
            output_root = os.getenv('OUTPUT_ROOT', '/output')
            base_path = os.path.join(output_root, base_path)

        # Check for restricted paths
        restricted_paths = ['/etc', '/usr', '/bin', '/sbin', '/dev', '/proc', '/sys']
        for restricted in restricted_paths:
            if base_path.startswith(restricted):
                errors.append(f"Output path cannot be in system directory: {restricted}")

        # Check parent directory exists or can be created
        parent_dir = os.path.dirname(base_path)
        if parent_dir and parent_dir != '/':
            try:
                # Check if parent exists
                if not os.path.exists(parent_dir):
                    # Try to check if we can create it (without actually creating)
                    grandparent = os.path.dirname(parent_dir)
                    if grandparent and os.path.exists(grandparent):
                        if not os.access(grandparent, os.W_OK):
                            errors.append(f"Cannot create output directory: no write permission in {grandparent}")
                elif not os.access(parent_dir, os.W_OK):
                    errors.append(f"No write permission for output directory: {parent_dir}")
            except Exception as e:
                errors.append(f"Cannot validate output path: {str(e)}")

        return errors

    @staticmethod
    async def check_disk_space(base_path: str, required_mb: int = 1000) -> Optional[str]:
        """Check if there's enough disk space for output

        Args:
            base_path: Output base path
            required_mb: Required space in megabytes

        Returns:
            Optional[str]: Error message if insufficient space
        """
        try:
            # Get the mount point for the path
            path = Path(base_path)
            while not path.exists() and path.parent != path:
                path = path.parent

            if not path.exists():
                # Can't check, assume it's ok
                return None

            # Get disk usage statistics
            stat = os.statvfs(str(path))
            available_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)

            if available_mb < required_mb:
                return f"Insufficient disk space: {available_mb:.0f}MB available, {required_mb}MB required"

            return None

        except Exception as e:
            # If we can't check, don't block the operation
            return None

    @staticmethod
    async def cleanup_stale_directories(
        output_root: str,
        active_job_ids: Set[str],
        dry_run: bool = True
    ) -> List[str]:
        """Clean up output directories from jobs that no longer exist

        Args:
            output_root: Root output directory
            active_job_ids: Set of currently active job IDs
            dry_run: If True, only report what would be deleted

        Returns:
            List[str]: List of directories cleaned up
        """
        cleaned = []

        if not os.path.exists(output_root):
            return cleaned

        try:
            # List all directories in output root
            for entry in os.listdir(output_root):
                dir_path = os.path.join(output_root, entry)

                # Skip if not a directory
                if not os.path.isdir(dir_path):
                    continue

                # Check if directory name looks like a job ID (UUID format)
                if len(entry) == 36 and entry.count('-') == 4:
                    # Check if this job ID is active
                    if entry not in active_job_ids:
                        cleaned.append(dir_path)

                        if not dry_run:
                            # Actually remove the directory
                            import shutil
                            try:
                                shutil.rmtree(dir_path)
                            except Exception as e:
                                # Log but don't fail
                                pass

        except Exception as e:
            # Don't fail on cleanup errors
            pass

        return cleaned

    @classmethod
    async def validate_output_configuration(
        cls,
        base_path: str,
        job_id: str,
        active_jobs: List[dict]
    ) -> dict:
        """Complete output configuration validation

        Args:
            base_path: Proposed output base path
            job_id: Current job ID
            active_jobs: List of active jobs

        Returns:
            dict: Validation result with errors and warnings
        """
        result = {
            'valid': True,
            'errors': [],
            'warnings': []
        }

        # Validate the path itself
        path_errors = await cls.validate_output_path(base_path)
        if path_errors:
            result['errors'].extend(path_errors)
            result['valid'] = False

        # Check for conflicts
        conflict_errors = await cls.check_directory_conflicts(base_path, job_id, active_jobs)
        if conflict_errors:
            result['errors'].extend(conflict_errors)
            result['valid'] = False

        # Check disk space (warning only)
        space_error = await cls.check_disk_space(base_path)
        if space_error:
            result['warnings'].append(space_error)

        return result
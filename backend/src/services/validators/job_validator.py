"""
Job Validator
Input validation for job parameters
"""

import re
from typing import Dict, Any, List, Optional
from models.job import EncodingJobCreate
from models.input import InputSourceCreate, InputType


class JobValidator:
    """Validates job creation and update parameters"""

    @staticmethod
    def validate_job_name(name: str) -> List[str]:
        """Validate job name

        Args:
            name: Job name

        Returns:
            List[str]: List of validation errors (empty if valid)
        """
        errors = []

        if not name or not name.strip():
            errors.append("Job name cannot be empty")
        elif len(name) > 100:
            errors.append("Job name cannot exceed 100 characters")
        elif not re.match(r'^[\w\s\-\.]+$', name):
            errors.append("Job name can only contain letters, numbers, spaces, hyphens, and dots")

        return errors

    @staticmethod
    def validate_priority(priority: int) -> List[str]:
        """Validate job priority

        Args:
            priority: Priority value

        Returns:
            List[str]: List of validation errors
        """
        errors = []

        if priority < 1 or priority > 10:
            errors.append("Priority must be between 1 and 10")

        return errors

    @staticmethod
    def validate_input_url(url: str, input_type: InputType) -> List[str]:
        """Validate input URL based on type

        Args:
            url: Input URL or file path
            input_type: Type of input

        Returns:
            List[str]: List of validation errors
        """
        errors = []

        if not url or not url.strip():
            errors.append("Input URL cannot be empty")
            return errors

        if input_type == InputType.UDP:
            if not re.match(r'^udp://[^:]+:\d+$', url):
                errors.append(f"Invalid UDP URL format. Expected: udp://host:port, got: {url}")
            else:
                # Extract port and validate
                port = int(url.split(':')[-1])
                if port < 1 or port > 65535:
                    errors.append(f"Invalid port number: {port}")

        elif input_type == InputType.HTTP:
            if not re.match(r'^https?://[^\s]+$', url):
                errors.append(f"Invalid HTTP URL format. Expected: http(s)://host[:port]/path, got: {url}")
            else:
                # Validate port if present
                port_match = re.search(r':(\d+)(/|$)', url)
                if port_match:
                    port = int(port_match.group(1))
                    if port < 1 or port > 65535:
                        errors.append(f"Invalid port number: {port}")

        elif input_type == InputType.FILE:
            # Basic path validation
            if url.startswith('http://') or url.startswith('https://'):
                errors.append("File input should be a local path, not a URL")
            elif '..' in url:
                errors.append("File path cannot contain '..' for security reasons")

        return errors

    @staticmethod
    def validate_hardware_acceleration(hw_accel: Optional[Dict[str, Any]]) -> List[str]:
        """Validate hardware acceleration settings

        Args:
            hw_accel: Hardware acceleration config

        Returns:
            List[str]: List of validation errors
        """
        errors = []

        if not hw_accel:
            return errors

        # Validate acceleration type
        valid_types = ['cuda', 'nvenc', 'vulkan']
        hw_type = hw_accel.get('type')

        if not hw_type:
            errors.append("Hardware acceleration type is required")
        elif hw_type not in valid_types:
            errors.append(f"Invalid hardware acceleration type: {hw_type}. Must be one of: {', '.join(valid_types)}")

        # Validate device index if present
        if 'device' in hw_accel:
            device = hw_accel['device']
            if not isinstance(device, int) or device < 0:
                errors.append("Device index must be a non-negative integer")

        # Validate output format if present and not None
        if 'output_format' in hw_accel and hw_accel['output_format'] is not None:
            output_format = hw_accel['output_format']
            valid_formats = ['cuda', 'nv12', 'yuv420p', 'p010le']
            if output_format not in valid_formats:
                errors.append(f"Invalid output format: {output_format}")

        return errors

    @classmethod
    def validate_job_creation(
        cls,
        job_data: EncodingJobCreate,
        input_data: InputSourceCreate
    ) -> Dict[str, List[str]]:
        """Validate complete job creation request

        Args:
            job_data: Job creation data
            input_data: Input source data

        Returns:
            Dict[str, List[str]]: Dictionary of field errors
        """
        all_errors = {}

        # Validate job name
        name_errors = cls.validate_job_name(job_data.name)
        if name_errors:
            all_errors['name'] = name_errors

        # Validate priority
        priority_errors = cls.validate_priority(job_data.priority)
        if priority_errors:
            all_errors['priority'] = priority_errors

        # Validate input URL
        url_errors = cls.validate_input_url(input_data.url, input_data.type)
        if url_errors:
            all_errors['input_url'] = url_errors

        # Validate hardware acceleration
        hw_errors = cls.validate_hardware_acceleration(input_data.hardware_accel)
        if hw_errors:
            all_errors['hardware_acceleration'] = hw_errors

        # Validate loop option (only valid for file inputs)
        if input_data.loop_enabled and input_data.type != InputType.FILE:
            all_errors['loop_enabled'] = ["Loop option is only valid for file inputs"]

        return all_errors

    @classmethod
    def validate_concurrent_jobs(cls, active_job_count: int, max_jobs: int = None) -> Optional[str]:
        """Validate if a new job can be started based on concurrent limit

        Args:
            active_job_count: Number of currently active jobs
            max_jobs: Maximum allowed concurrent jobs (defaults to env var MAX_CONCURRENT_JOBS or 20)

        Returns:
            Optional[str]: Error message if limit exceeded
        """
        import os

        # Use provided max_jobs, or fall back to env var, or default to 20
        if max_jobs is None:
            max_jobs = int(os.getenv("MAX_CONCURRENT_JOBS", "20"))

        if active_job_count >= max_jobs:
            return f"Maximum concurrent jobs limit ({max_jobs}) reached. Please stop some jobs before starting new ones."
        return None
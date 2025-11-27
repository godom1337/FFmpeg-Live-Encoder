/**
 * API Client for Job Management
 * T037: Implements job creation API client
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

/**
 * Handle API response and errors
 * @param {Response} response - Fetch response
 * @returns {Promise<any>} Parsed response data
 */
async function handleResponse(response) {
    const contentType = response.headers.get('content-type');
    const isJson = contentType && contentType.includes('application/json');
    const data = isJson ? await response.json() : await response.text();

    if (!response.ok) {
        const error = new Error(
            (isJson && data.detail?.message) || data.message || `HTTP ${response.status}`
        );
        error.status = response.status;
        error.data = data;
        throw error;
    }

    return data;
}

/**
 * Job API endpoints
 */
export const jobApi = {
    // NOTE: Old create() method removed - use createMinimal() instead (line 205)
    // Old method used POST /jobs/ with separate job/input_source/output_config objects
    // New method uses POST /jobs/create with flat CreateJobRequest structure

    /**
     * Get job by ID
     * @param {string} jobId - Job ID
     * @returns {Promise<Object>} Job with configuration
     */
    async get(jobId) {
        const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`);
        return handleResponse(response);
    },

    // ========================================================================
    // Unified Configuration API (Feature: 001-edit-api-simplification)
    // Simplified endpoints using single unified configuration object
    // ========================================================================

    /**
     * Get job configuration as unified object (Simplified Edit API)
     * @param {string} jobId - Job ID
     * @returns {Promise<Object>} Complete unified job configuration
     *
     * Example response:
     * {
     *   id: "123",
     *   jobName: "My Job",
     *   inputFile: "/input/video.mp4",
     *   videoCodec: "h264",
     *   videoBitrate: "5M",
     *   audioCodec: "aac",
     *   audioBitrate: "128k",
     *   outputFormat: "hls",
     *   outputDir: "/output/test",
     *   abrEnabled: false,
     *   ...
     * }
     */
    async getUnified(jobId) {
        const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/unified`);
        return handleResponse(response);
    },

    /**
     * Update job configuration using unified object (Simplified Edit API)
     * @param {string} jobId - Job ID
     * @param {Object} config - Complete unified configuration
     * @returns {Promise<Object>} Update status and FFmpeg command
     *
     * Example request:
     * {
     *   jobName: "Updated Job",
     *   inputFile: "/input/video.mp4",
     *   videoCodec: "h264",
     *   videoBitrate: "8M",
     *   audioCodec: "aac",
     *   audioBitrate: "192k",
     *   outputFormat: "hls",
     *   outputDir: "/output/test",
     *   abrEnabled: false
     * }
     *
     * Example response:
     * {
     *   status: "updated",
     *   jobId: "123",
     *   ffmpegCommand: "ffmpeg -i /input/video.mp4 ..."
     * }
     */
    async updateUnified(jobId, config) {
        const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/unified`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config)
        });
        return handleResponse(response);
    },

    /**
     * Update FFmpeg command directly for a job
     * @param {string} jobId - Job ID
     * @param {string} command - New FFmpeg command
     * @returns {Promise<Object>} Status response with updated command
     *
     * Example response:
     * {
     *   status: "updated",
     *   jobId: "123",
     *   command: "ffmpeg -i ..."
     * }
     */
    async updateCommand(jobId, command) {
        const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/command`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ command })
        });
        return handleResponse(response);
    },

    /**
     * List all jobs
     * @param {Object} params - Query parameters
     * @param {string} params.status - Filter by status
     * @param {number} params.limit - Maximum results
     * @param {number} params.offset - Skip results
     * @returns {Promise<Array>} List of jobs
     */
    async list(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = `${API_BASE_URL}/jobs/${queryString ? `?${queryString}` : ''}`;
        const response = await fetch(url);
        return handleResponse(response);
    },

    /**
     * Start an encoding job
     * @param {string} jobId - Job ID
     * @returns {Promise<Object>} Status response
     */
    async start(jobId) {
        const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/start`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        return handleResponse(response);
    },

    /**
     * Stop an encoding job
     * @param {string} jobId - Job ID
     * @returns {Promise<Object>} Status response
     */
    async stop(jobId) {
        const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/stop`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        return handleResponse(response);
    },

    /**
     * Force kill all FFmpeg processes for a job
     * @param {string} jobId - Job ID
     * @returns {Promise<Object>} Status response with killed process count
     */
    async forceKill(jobId) {
        const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/force-kill`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        return handleResponse(response);
    },

    /**
     * Reset job status to PENDING
     * @param {string} jobId - Job ID
     * @returns {Promise<Object>} Reset confirmation with updated job
     */
    async resetStatus(jobId) {
        const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/reset-status`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        return handleResponse(response);
    },

    /**
     * Delete a job
     * @param {string} jobId - Job ID
     * @returns {Promise<Object>} Deletion confirmation
     */
    async delete(jobId) {
        const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`, {
            method: 'DELETE'
        });
        return handleResponse(response);
    },

    /**
     * Update job configuration
     * @param {string} jobId - Job ID
     * @param {Object} jobUpdate - Job fields to update
     * @param {Object} inputUpdate - Input configuration to update
     * @param {Object} outputUpdate - Output configuration to update
     * @returns {Promise<Object>} Updated job
     */
    async update(jobId, jobUpdate = null, inputUpdate = null, outputUpdate = null) {
        const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                job_update: jobUpdate,
                input_update: inputUpdate,
                output_update: outputUpdate
            })
        });
        return handleResponse(response);
    },

    /**
     * Get tail of job log file
     * @param {string} jobId - Job ID
     * @param {number} lines - Number of lines to fetch (default: 20)
     * @returns {Promise<Object>} Log tail data
     */
    async getLogTail(jobId, lines = 20) {
        const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/logs/tail?lines=${lines}`);
        return handleResponse(response);
    },

    /**
     * Get download URL for full log file
     * @param {string} jobId - Job ID
     * @returns {string} Download URL
     */
    getLogDownloadUrl(jobId) {
        return `${API_BASE_URL}/jobs/${jobId}/logs/download`;
    },

    /**
     * Create a minimal encoding job (NEW API - Rewrite)
     * @param {Object} jobRequest - Minimal job request
     * @param {string} jobRequest.input_file - Path to input file (required)
     * @param {string} jobRequest.output_file - Path to output file (optional)
     * @param {string} jobRequest.video_codec - Video codec (optional, default: libx264)
     * @param {string} jobRequest.audio_codec - Audio codec (optional, default: copy)
     * @returns {Promise<Object>} Created job with command and job_id
     */
    async createMinimal(jobRequest) {
        const response = await fetch(`${API_BASE_URL}/jobs/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(jobRequest)
        });
        return handleResponse(response);
    },

    /**
     * Create a new job using unified configuration format (Feature 008).
     *
     * This is the NEW recommended API that uses the unified configuration format,
     * which is consistent with GET /jobs/{id}/unified and PUT /jobs/{id}/unified.
     *
     * @param {Object} config - Unified job configuration
     * @param {string} config.jobName - Job name (required)
     * @param {string} config.inputFile - Input file path or URL (required)
     * @param {string} config.outputFormat - Output format: hls, udp, file, rtmp (required)
     * @param {string} config.outputDir - Output directory (for hls/file formats)
     * @param {string} config.videoCodec - Video codec (default: libx264)
     * @param {string} config.audioCodec - Audio codec (default: aac)
     * @param {string} config.videoBitrate - Video bitrate (default: 2M)
     * @param {string} config.audioBitrate - Audio bitrate (default: 128k)
     * @returns {Promise<Object>} Created job with jobId and ffmpegCommand
     *
     * Feature: 008-migrate-unified-db
     */
    async createUnified(config) {
        const response = await fetch(`${API_BASE_URL}/jobs/create-unified`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config)
        });
        return handleResponse(response);
    },

    /**
     * Validate job configuration without creating (dry-run)
     * @param {Object} jobRequest - Job configuration to validate
     * @returns {Promise<Object>} Validation result with warnings
     */
    async validate(jobRequest) {
        const response = await fetch(`${API_BASE_URL}/jobs/validate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(jobRequest)
        });
        return handleResponse(response);
    },

    /**
     * Probe input file metadata using FFprobe
     * @param {string} filePath - Path to input file
     * @returns {Promise<Object>} File metadata with tracks, duration, format
     */
    async probeFile(filePath) {
        const response = await fetch(`${API_BASE_URL}/jobs/metadata/probe`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ file_path: filePath })
        });
        return handleResponse(response);
    },

    /**
     * Get all available encoding templates
     * @returns {Promise<Object>} Object with templates array
     */
    async getTemplates() {
        const response = await fetch(`${API_BASE_URL}/jobs/templates`);
        return handleResponse(response);
    },

    /**
     * Get a specific template by ID
     * @param {string} templateId - Template ID (e.g., 'web_streaming', 'high_quality_archive')
     * @returns {Promise<Object>} Full template with encoding settings
     */
    async getTemplate(templateId) {
        const response = await fetch(`${API_BASE_URL}/jobs/templates/${templateId}`);
        return handleResponse(response);
    }
};

/**
 * Profile API endpoints
 */
export const profileApi = {
    /**
     * List encoding profiles
     * @returns {Promise<Array>} List of profiles
     */
    async list() {
        const response = await fetch(`${API_BASE_URL}/profiles/`);
        return handleResponse(response);
    },

    /**
     * Get profile by ID
     * @param {string} profileId - Profile ID
     * @returns {Promise<Object>} Profile with variants
     */
    async get(profileId) {
        const response = await fetch(`${API_BASE_URL}/profiles/${profileId}`);
        return handleResponse(response);
    }
};

/**
 * System API endpoints
 */
export const systemApi = {
    /**
     * Check system health
     * @returns {Promise<Object>} Health status
     */
    async health() {
        const response = await fetch(`${API_BASE_URL}/system/health`);
        return handleResponse(response);
    },

    /**
     * Get system information
     * @returns {Promise<Object>} System info
     */
    async info() {
        const response = await fetch(`${API_BASE_URL}/system/info`);
        return handleResponse(response);
    },

    /**
     * Get real-time system metrics
     * @returns {Promise<Object>} System metrics (CPU, memory, disk)
     */
    async metrics() {
        const response = await fetch(`${API_BASE_URL}/system/metrics`);
        return handleResponse(response);
    }
};

/**
 * Analysis API endpoints
 */
export const analysisApi = {
    /**
     * Analyze input source with ffprobe
     * @param {string} url - Input URL/path
     * @param {string} type - Input type (udp, http, file)
     * @param {number} timeout - Analysis timeout in seconds
     * @returns {Promise<Object>} Analysis result with stream information
     */
    async analyzeInput(url, type = null, timeout = 10) {
        const response = await fetch(`${API_BASE_URL}/analysis/input`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url, type, timeout })
        });
        return handleResponse(response);
    },

    /**
     * Validate input accessibility
     * @param {string} url - Input URL/path
     * @param {string} type - Input type
     * @returns {Promise<Object>} Validation result
     */
    async validateInput(url, type = null) {
        const response = await fetch(`${API_BASE_URL}/analysis/validate-input`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url, type, timeout: 5 })
        });
        return handleResponse(response);
    }
};

/**
 * Presets API endpoints
 */
export const presetsApi = {
    /**
     * List all encoding presets
     * @param {Object} params - Query parameters
     * @param {string} params.category - Filter by category
     * @param {string} params.tag - Filter by tag
     * @returns {Promise<Array>} List of presets
     */
    async list(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = `${API_BASE_URL}/presets/${queryString ? `?${queryString}` : ''}`;
        const response = await fetch(url);
        return handleResponse(response);
    },

    /**
     * Get preset by ID
     * @param {string} presetId - Preset ID
     * @returns {Promise<Object>} Preset with configuration
     */
    async get(presetId) {
        const response = await fetch(`${API_BASE_URL}/presets/${presetId}`);
        return handleResponse(response);
    },

    /**
     * List all preset categories
     * @returns {Promise<Array>} List of categories
     */
    async listCategories() {
        const response = await fetch(`${API_BASE_URL}/presets/categories/list`);
        return handleResponse(response);
    },

    /**
     * List all preset tags
     * @returns {Promise<Array>} List of tags
     */
    async listTags() {
        const response = await fetch(`${API_BASE_URL}/presets/tags/list`);
        return handleResponse(response);
    }
};

/**
 * Logs API endpoints
 */
export const logsApi = {
    /**
     * Get container logs tail (snapshot)
     * @param {number} lines - Number of lines to fetch (default: 100)
     * @returns {Promise<Object>} Container logs
     */
    async getContainerLogsTail(lines = 100) {
        const response = await fetch(`${API_BASE_URL}/logs/container/tail?lines=${lines}`);
        return handleResponse(response);
    },

    /**
     * Get streaming URL for container logs
     * @param {number} lines - Number of historical lines (default: 100)
     * @param {boolean} follow - Follow/stream logs (default: true)
     * @returns {string} Streaming endpoint URL
     */
    getContainerLogsStreamUrl(lines = 100, follow = true) {
        return `${API_BASE_URL}/logs/container/stream?lines=${lines}&follow=${follow}`;
    },

    /**
     * Get API logs tail (snapshot)
     * @param {number} lines - Number of lines to fetch (default: 100)
     * @returns {Promise<Object>} API logs
     */
    async getApiLogsTail(lines = 100) {
        const response = await fetch(`${API_BASE_URL}/logs/api/tail?lines=${lines}`);
        return handleResponse(response);
    },

    /**
     * Get streaming URL for API logs
     * @param {number} lines - Number of historical lines (default: 100)
     * @param {boolean} follow - Follow/stream logs (default: true)
     * @returns {string} Streaming endpoint URL
     */
    getApiLogsStreamUrl(lines = 100, follow = true) {
        return `${API_BASE_URL}/logs/api/stream?lines=${lines}&follow=${follow}`;
    }
};

/**
 * Archives API endpoints
 */
export const archivesApi = {
    /**
     * List all archived jobs
     * @param {Object} params - Query parameters
     * @param {number} params.limit - Maximum results (default: 100)
     * @param {number} params.offset - Skip results (default: 0)
     * @param {string} params.order_by - Sort order (default: 'archived_at DESC')
     * @returns {Promise<Object>} Paginated list of archived jobs
     */
    async list(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = `${API_BASE_URL}/archives/${queryString ? `?${queryString}` : ''}`;
        const response = await fetch(url);
        return handleResponse(response);
    },

    /**
     * Get archived job by ID
     * @param {string} jobId - Archived job ID
     * @returns {Promise<Object>} Archived job with configuration
     */
    async get(jobId) {
        const response = await fetch(`${API_BASE_URL}/archives/${jobId}`);
        return handleResponse(response);
    },

    /**
     * Restore an archived job back to active jobs
     * @param {string} jobId - Archived job ID
     * @returns {Promise<Object>} Restored job
     */
    async restore(jobId) {
        const response = await fetch(`${API_BASE_URL}/archives/${jobId}/restore`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        return handleResponse(response);
    },

    /**
     * Permanently delete an archived job
     * @param {string} jobId - Archived job ID
     * @returns {Promise<Object>} Deletion confirmation
     */
    async deletePermanently(jobId) {
        const response = await fetch(`${API_BASE_URL}/archives/${jobId}`, {
            method: 'DELETE'
        });
        return handleResponse(response);
    },

    /**
     * Get archives statistics
     * @returns {Promise<Object>} Statistics about archived jobs
     */
    async getStats() {
        const response = await fetch(`${API_BASE_URL}/archives/stats/summary`);
        return handleResponse(response);
    }
};

/**
 * Default export with all API modules
 */
export default {
    jobs: jobApi,
    profiles: profileApi,
    system: systemApi,
    analysis: analysisApi,
    presets: presetsApi,
    archives: archivesApi,
    logs: logsApi
};
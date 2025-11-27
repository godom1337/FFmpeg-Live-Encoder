/**
 * ABR Calculation Utilities
 *
 * Helper functions for calculating bandwidth, storage, and other metrics
 * for Adaptive Bitrate streaming configurations.
 *
 * User Story 3: Preview ABR Configuration
 */

/**
 * Convert bitrate string to bits per second
 *
 * @param {string} bitrate - Bitrate string (e.g., "5M", "3000k", "128k")
 * @returns {number} Bitrate in bits per second
 *
 * @example
 * bitrateToBps("5M") // 5000000
 * bitrateToBps("3000k") // 3000000
 * bitrateToBps("128k") // 128000
 */
export function bitrateToBps(bitrate) {
    if (!bitrate || bitrate === '0') {
        return 0;
    }

    const value = parseFloat(bitrate);
    const suffix = bitrate.slice(-1).toLowerCase();

    if (suffix === 'k') {
        return value * 1000;
    } else if (suffix === 'm') {
        return value * 1000000;
    } else if (suffix === 'g') {
        return value * 1000000000;
    } else {
        // Plain number (already in bps)
        return parseInt(bitrate);
    }
}

/**
 * Convert resolution string to total pixel count
 *
 * @param {string} resolution - Resolution string (e.g., "1920x1080", "1280x720")
 * @returns {number} Total pixels (width × height)
 *
 * @example
 * resolutionToPixels("1920x1080") // 2073600
 * resolutionToPixels("1280x720")  // 921600
 */
export function resolutionToPixels(resolution) {
    if (!resolution || !resolution.includes('x')) {
        return 0;
    }

    const [width, height] = resolution.split('x').map(v => parseInt(v));
    return width * height;
}

/**
 * Estimate storage requirements per hour for ABR ladder
 *
 * @param {Array} renditions - Array of rendition objects with videoBitrate and audioBitrate
 * @returns {Object} Storage estimates
 *
 * @example
 * const renditions = [
 *   {videoBitrate: "5M", audioBitrate: "128k"},
 *   {videoBitrate: "3M", audioBitrate: "128k"}
 * ];
 * estimateStoragePerHour(renditions)
 * // { totalBitrate: 8256000, storagePerHour: "3.68 GB", bytesPerHour: 3960000000 }
 */
export function estimateStoragePerHour(renditions) {
    if (!renditions || renditions.length === 0) {
        return {
            totalBitrate: 0,
            storagePerHour: '0 GB',
            bytesPerHour: 0
        };
    }

    let totalBitsPerSecond = 0;

    for (const rendition of renditions) {
        const videoBps = bitrateToBps(rendition.videoBitrate || '0');
        const audioBps = bitrateToBps(rendition.audioBitrate || '0');
        totalBitsPerSecond += videoBps + audioBps;
    }

    // Calculate bytes per hour
    const bytesPerSecond = totalBitsPerSecond / 8;
    const bytesPerHour = bytesPerSecond * 3600;

    // Convert to GB
    const gbPerHour = bytesPerHour / (1024 * 1024 * 1024);

    return {
        totalBitrate: totalBitsPerSecond,
        storagePerHour: `${gbPerHour.toFixed(2)} GB`,
        bytesPerHour: bytesPerHour,
        megabitsPerSecond: (totalBitsPerSecond / 1000000).toFixed(2)
    };
}

/**
 * Check if a resolution is standard (commonly used)
 *
 * @param {string} resolution - Resolution string (e.g., "1920x1080")
 * @returns {boolean} True if standard resolution
 */
export function isStandardResolution(resolution) {
    const standardResolutions = [
        '7680x4320',  // 8K
        '3840x2160',  // 4K
        '2560x1440',  // 1440p
        '1920x1080',  // 1080p
        '1280x720',   // 720p
        '960x540',    // 540p
        '854x480',    // 480p
        '640x360',    // 360p
        '426x240'     // 240p
    ];

    return standardResolutions.includes(resolution);
}

/**
 * Get target device profile for a resolution
 *
 * @param {string} resolution - Resolution string
 * @returns {string} Device profile description
 */
export function getDeviceProfile(resolution) {
    const pixels = resolutionToPixels(resolution);

    if (pixels >= 7680 * 4320) return '8K displays, future-proofing';
    if (pixels >= 3840 * 2160) return '4K TVs, high-end displays';
    if (pixels >= 2560 * 1440) return '1440p monitors, gaming displays';
    if (pixels >= 1920 * 1080) return 'Desktop, laptop, smart TV';
    if (pixels >= 1280 * 720) return 'Tablets, smaller laptops';
    if (pixels >= 854 * 480) return 'Mobile devices, slow connections';
    if (pixels >= 640 * 360) return 'Mobile, very slow connections';
    return 'Low bandwidth, legacy devices';
}

/**
 * Format bitrate for display
 *
 * @param {string} bitrate - Bitrate string
 * @returns {string} Formatted display string
 */
export function formatBitrate(bitrate) {
    const bps = bitrateToBps(bitrate);

    if (bps >= 1000000) {
        return `${(bps / 1000000).toFixed(1)} Mbps`;
    } else if (bps >= 1000) {
        return `${(bps / 1000).toFixed(0)} kbps`;
    } else {
        return `${bps} bps`;
    }
}

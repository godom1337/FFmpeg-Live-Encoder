/**
 * Form Validation Utilities
 * T038: Add form validation for job parameters
 */

/**
 * Validate job name
 * @param {string} name - Job name
 * @returns {string|null} Error message or null if valid
 */
export function validateJobName(name) {
    if (!name || !name.trim()) {
        return 'Job name is required';
    }
    if (name.length > 100) {
        return 'Job name must be less than 100 characters';
    }
    if (!/^[\w\s\-\.]+$/.test(name)) {
        return 'Job name can only contain letters, numbers, spaces, hyphens, and dots';
    }
    return null;
}

/**
 * Validate priority
 * @param {number} priority - Priority value
 * @returns {string|null} Error message or null if valid
 */
export function validatePriority(priority) {
    const num = parseInt(priority, 10);
    if (isNaN(num)) {
        return 'Priority must be a number';
    }
    if (num < 1 || num > 10) {
        return 'Priority must be between 1 and 10';
    }
    return null;
}

/**
 * Validate input URL based on type
 * @param {string} url - Input URL or file path
 * @param {string} type - Input type (udp, http, file)
 * @returns {string|null} Error message or null if valid
 */
export function validateInputUrl(url, type) {
    if (!url || !url.trim()) {
        return 'Input URL is required';
    }

    switch (type) {
        case 'udp':
            if (!/^udp:\/\/[^:]+:\d+$/.test(url)) {
                return 'Invalid UDP URL format. Expected: udp://host:port';
            }
            const udpPort = parseInt(url.split(':').pop(), 10);
            if (udpPort < 1 || udpPort > 65535) {
                return 'Invalid port number';
            }
            break;

        case 'http':
            if (!/^https?:\/\/[^\s]+$/.test(url)) {
                return 'Invalid HTTP URL format. Expected: http(s)://host[:port]/path';
            }
            // Validate port if present
            const urlParts = url.match(/:(\d+)(\/|$)/);
            if (urlParts) {
                const httpPort = parseInt(urlParts[1], 10);
                if (httpPort < 1 || httpPort > 65535) {
                    return 'Invalid port number';
                }
            }
            break;

        case 'file':
            if (url.startsWith('http://') || url.startsWith('https://')) {
                return 'File input should be a local path, not a URL';
            }
            if (url.includes('..')) {
                return 'File path cannot contain ".." for security reasons';
            }
            break;

        default:
            return 'Invalid input type';
    }

    return null;
}

/**
 * Validate hardware acceleration settings
 * @param {Object} hwAccel - Hardware acceleration config
 * @returns {string|null} Error message or null if valid
 */
export function validateHardwareAcceleration(hwAccel) {
    if (!hwAccel || !hwAccel.enabled) {
        return null; // Hardware acceleration is optional
    }

    const validTypes = ['cuda', 'nvenc', 'vulkan', 'apple'];
    if (!hwAccel.type) {
        return 'Hardware acceleration type is required when enabled';
    }
    if (!validTypes.includes(hwAccel.type)) {
        return `Invalid hardware acceleration type. Must be one of: ${validTypes.join(', ')}`;
    }

    if (hwAccel.device !== undefined) {
        const device = parseInt(hwAccel.device, 10);
        if (isNaN(device) || device < 0) {
            return 'Device index must be a non-negative integer';
        }
    }

    return null;
}

/**
 * Validate output path
 * @param {string} path - Output base path
 * @returns {string|null} Error message or null if valid
 */
export function validateOutputPath(path) {
    if (path && path.includes('..')) {
        return 'Output path cannot contain ".." for security reasons';
    }

    const restrictedPaths = ['/etc', '/usr', '/bin', '/sbin', '/dev', '/proc', '/sys'];
    if (path) {
        for (const restricted of restrictedPaths) {
            if (path.startsWith(restricted)) {
                return `Output path cannot be in system directory: ${restricted}`;
            }
        }
    }

    return null;
}

/**
 * Validate complete job creation form
 * @param {Object} formData - Form data
 * @returns {Object} Validation results with errors
 */
export function validateJobForm(formData) {
    const errors = {};

    // Validate job name
    const nameError = validateJobName(formData.name);
    if (nameError) {
        errors.name = nameError;
    }

    // Validate priority
    const priorityError = validatePriority(formData.priority);
    if (priorityError) {
        errors.priority = priorityError;
    }

    // Validate input URL
    const urlError = validateInputUrl(formData.inputUrl, formData.inputType);
    if (urlError) {
        errors.inputUrl = urlError;
    }

    // Validate hardware acceleration
    if (formData.hardwareAccel) {
        const hwError = validateHardwareAcceleration(formData.hardwareAccel);
        if (hwError) {
            errors.hardwareAccel = hwError;
        }
    }

    // Validate loop option (only valid for file inputs)
    if (formData.loopEnabled && formData.inputType !== 'file') {
        errors.loopEnabled = 'Loop option is only valid for file inputs';
    }

    // Validate output path if provided
    if (formData.outputPath) {
        const pathError = validateOutputPath(formData.outputPath);
        if (pathError) {
            errors.outputPath = pathError;
        }
    }

    return {
        valid: Object.keys(errors).length === 0,
        errors
    };
}

/**
 * Format validation errors for display
 * @param {Object} errors - Validation errors object
 * @returns {string[]} Array of error messages
 */
export function formatErrors(errors) {
    const messages = [];
    for (const [field, error] of Object.entries(errors)) {
        if (typeof error === 'string') {
            messages.push(error);
        } else if (Array.isArray(error)) {
            messages.push(...error);
        }
    }
    return messages;
}

/**
 * Validate email (for future notification features)
 * @param {string} email - Email address
 * @returns {string|null} Error message or null if valid
 */
export function validateEmail(email) {
    if (!email) {
        return 'Email is required';
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        return 'Invalid email format';
    }
    return null;
}

/**
 * Validate profile selection
 * @param {string} profileId - Profile ID
 * @param {Array} availableProfiles - Available profiles
 * @returns {string|null} Error message or null if valid
 */
export function validateProfileSelection(profileId, availableProfiles = []) {
    if (!profileId) {
        return 'Encoding profile is required';
    }
    if (availableProfiles.length > 0 && !availableProfiles.find(p => p.id === profileId)) {
        return 'Selected profile is not available';
    }
    return null;
}

/**
 * Debounce validation function
 * @param {Function} fn - Validation function
 * @param {number} delay - Delay in milliseconds
 * @returns {Function} Debounced function
 */
export function debounceValidation(fn, delay = 300) {
    let timeoutId;
    return (...args) => {
        clearTimeout(timeoutId);
        return new Promise((resolve) => {
            timeoutId = setTimeout(() => {
                resolve(fn(...args));
            }, delay);
        });
    };
}
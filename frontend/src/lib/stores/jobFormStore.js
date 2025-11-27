/**
 * Job Form Store
 *
 * Manages state for the job creation form including:
 * - Form data (minimal and advanced options)
 * - Real-time command preview
 * - Validation state
 *
 * User Stories 1, 2, 6: Minimal job creation + Advanced customization + Command preview
 */

import { writable, derived } from 'svelte/store';
// Phase 7: fieldRegistry.js deleted - using inline conversion helpers

/**
 * Initial form state with minimal defaults
 */
const initialFormData = {
    // Basic fields (User Story 1)
    jobName: '',
    inputFile: '',
    outputFile: '',
    loopInput: false,

    // Input device fields
    inputFormat: '',
    inputFramerate: '', // Device input framerate
    inputVideoSize: '', // Device input video size (e.g., "1920x1080")
    inputPixelFormat: '', // Device input pixel format
    inputArgs: '', // Additional custom arguments (store as string, convert to array when sending to API)

    // Basic encoding settings
    videoCodec: 'libx264',
    audioCodec: 'copy',

    // Advanced video options (User Story 2)
    videoBitrate: '',
    videoProfile: '',
    fps: '',
    scale: '',
    videoFilters: '',
    preset: 'medium',
    videoTrackIndex: '0', // Simple track index (0, 1, 2, etc.) - defaults to first track

    // Advanced audio options (User Story 2)
    audioBitrate: '',
    audioChannels: '',
    audioVolume: '',
    audioStreamIndex: '',
    audioTrackIndex: '0', // Simple track index (0, 1, 2, etc.) - defaults to first track
    subtitleTrackIndex: '-1', // Default to disabled

    // Subtitle options
    subtitleTrackIndex: '-1', // Simple track index (0, 1, 2, etc.) - defaults to disabled (-1)
    subtitleCodec: '',
    subtitleLanguage: '',
    burnSubtitles: false,

    // Hardware acceleration (User Story 2)
    hardwareAccel: 'none',
    hardwareAccelDevice: 0,
    hardwareAccelOutputFormat: '',

    // Template support (User Story 4)
    templateId: '',

    // Advanced encoding parameters (quality control)
    crf: '',
    keyframeInterval: '',
    tune: '',
    twoPass: false,
    rateControlMode: '',
    level: '',
    maxBitrate: '',
    bufferSize: '',
    lookAhead: '',
    pixelFormat: '',

    // Multi-output settings (User Story 3)
    hlsOutput: null,
    udpOutputs: [],
    rtmpOutputs: [],
    additionalOutputs: [],

    // Streaming outputs (YouTube, Twitch)
    youtubeOutput: null,
    twitchOutput: null,

    // ABR ladder (User Story 5)
    abrEnabled: false,
    abrPreset: 'standard',
    abrLadder: [],

    // Stream mapping - now handled via videoTrackIndex and audioTrackIndex

    // Custom args (User Story 8)
    customArgs: [],
    customArgsEnabled: false
};

/**
 * Writable store for form data
 */
export const formData = writable({ ...initialFormData });

/**
 * Validation state store
 */
export const validationState = writable({
    isValidating: false,
    lastValidation: null,
    warnings: [],
    isValid: true
});

/**
 * Minimal fallback command builder (only used if backend API fails)
 * For accurate command preview, always use backend API
 */
function buildCommandFallback(data) {
    const cmd = ['ffmpeg'];
    if (data.hardwareAccel && data.hardwareAccel !== 'none') {
        cmd.push('-hwaccel', data.hardwareAccel);
    }
    if (data.loopInput) {
        cmd.push('-stream_loop', '-1', '-re');
    }
    // Input format (device input)
    if (data.inputFormat) {
        cmd.push('-f', data.inputFormat);
    }
    // Input args (device input)
    if (data.inputFramerate) {
        cmd.push('-framerate', String(data.inputFramerate));
    }
    if (data.inputVideoSize) {
        cmd.push('-video_size', data.inputVideoSize);
    }
    if (data.inputPixelFormat) {
        cmd.push('-pixel_format', data.inputPixelFormat);
    }
    if (data.inputArgs) {
        const trimmed = data.inputArgs.trim();
        if (trimmed) {
            const parsed = trimmed.match(/(?:[^\s"]+|"[^"]*")+/g)?.map(arg => arg.replace(/^"|"$/g, ''));
            if (parsed) cmd.push(...parsed);
        }
    }
    cmd.push('-i', data.inputFile || '<input-file>');

    // Stream mapping (User Story 7)
    if (data.streamMaps && data.streamMaps.length > 0) {
        for (const streamMap of data.streamMaps) {
            cmd.push('-map', streamMap.input_stream);
        }
    }

    cmd.push('-c:v', data.videoCodec || 'libx264');
    if (data.videoBitrate) cmd.push('-b:v', data.videoBitrate);
    if (data.fps) cmd.push('-r', String(data.fps));
    cmd.push('-c:a', data.audioCodec || 'copy');

    // Check for streaming outputs (YouTube, Twitch)
    const hasYouTubeStream = data.youtubeOutput && data.youtubeOutput.enabled && data.youtubeOutput.streamKey;
    const hasTwitchStream = data.twitchOutput && data.twitchOutput.enabled && data.twitchOutput.streamKey;

    if (hasYouTubeStream) {
        // YouTube Live streaming
        const fps = data.fps || 30;
        cmd.push('-g', String(fps * 2)); // 2-second keyframe interval
        cmd.push('-f', 'flv');
        const serverUrl = (data.youtubeOutput.serverUrl || 'rtmp://a.rtmp.youtube.com/live2').replace(/\/$/, '');
        cmd.push(`${serverUrl}/${data.youtubeOutput.streamKey}`);
    } else if (hasTwitchStream) {
        // Twitch streaming
        const fps = data.fps || 30;
        cmd.push('-g', String(fps * 2)); // 2-second keyframe interval
        cmd.push('-f', 'flv');
        const serverUrl = (data.twitchOutput.serverUrl || 'rtmp://live.twitch.tv/app').replace(/\/$/, '');
        cmd.push(`${serverUrl}/${data.twitchOutput.streamKey}`);
    } else if (data.rtmpOutputs && data.rtmpOutputs.length > 0) {
        // RTMP streaming outputs
        for (const rtmp of data.rtmpOutputs) {
            let fullUrl = rtmp.url || '';
            if (rtmp.streamKey) {
                if (!fullUrl.endsWith('/')) fullUrl += '/';
                fullUrl += rtmp.streamKey;
            }
            if (fullUrl) {
                cmd.push('-f', 'flv', fullUrl);
            }
        }
    } else if (data.udpOutputs && data.udpOutputs.length > 0) {
        // UDP streaming outputs
        for (const udp of data.udpOutputs) {
            if (udp.url) {
                cmd.push('-f', 'mpegts', udp.url);
            }
        }
    } else if (data.outputFile) {
        cmd.push(data.outputFile);
    } else if (data.hlsOutput) {
        cmd.push('-f', 'hls');
        cmd.push(data.hlsOutput.outputDir || '/output/hls/master.m3u8');
    } else {
        cmd.push('<output-file>');
    }
    return cmd.join(' ');
}

/**
 * Custom store for command preview with async backend support
 * Fetches accurate FFmpeg command from backend, falls back to minimal builder
 */
function createCommandPreview() {
    const { subscribe, set } = writable(buildCommandFallback(initialFormData));

    // Debounce API calls to avoid spam (250ms for responsive preview)
    let debounceTimer;
    let lastRequestData = null;
    let isInitializing = true;

    formData.subscribe(async ($formData) => {
        clearTimeout(debounceTimer);

        debounceTimer = setTimeout(async () => {
            try {
                // Skip API calls if input file is not set (likely still initializing)
                if (!$formData.inputFile) {
                    set(buildCommandFallback($formData));
                    return;
                }

                // Convert track indices to stream_maps format
                let streamMaps = [];

                // Add video track mapping if specified (convert index to 0:v:N format)
                if ($formData.videoTrackIndex !== '' && $formData.videoTrackIndex !== null && $formData.videoTrackIndex !== undefined) {
                    streamMaps.push({
                        input_stream: `0:v:${$formData.videoTrackIndex}`,
                        output_label: 'v'
                    });
                }

                // Add audio track mapping if specified (convert index to 0:a:N format)
                // Skip if audioTrackIndex is -1 (audio disabled)
                if ($formData.audioTrackIndex !== '' && $formData.audioTrackIndex !== null && $formData.audioTrackIndex !== undefined && $formData.audioTrackIndex != -1) {
                    streamMaps.push({
                        input_stream: `0:a:${$formData.audioTrackIndex}`,
                        output_label: 'a'
                    });
                }

                // Add subtitle track mapping if specified (convert index to 0:s:N format)
                // Skip if subtitleTrackIndex is -1 (subtitle disabled)
                // Note: When burnSubtitles is true WITH a track selected, we still map it (burned from mapped stream)
                //       When burnSubtitles is true WITHOUT a track, we don't map (closed captions from video)
                if ($formData.subtitleTrackIndex !== '' &&
                    $formData.subtitleTrackIndex !== null &&
                    $formData.subtitleTrackIndex !== undefined &&
                    $formData.subtitleTrackIndex != -1) {
                    streamMaps.push({
                        input_stream: `0:s:${$formData.subtitleTrackIndex}`,
                        output_label: 's'
                    });
                }

                // Build request for backend validation API
                // Simple camelCase to snake_case conversion (Phase 7 cleanup)
                // Helper: Convert empty strings to undefined for optional fields
                const toValue = (val) => (val === '' || val === null || val === undefined) ? undefined : val;
                const toInt = (val) => (val === '' || val === null || val === undefined) ? undefined : parseInt(val, 10);

                // Build input_args array from device input fields
                const buildInputArgs = () => {
                    const args = [];
                    if ($formData.inputFramerate) {
                        args.push('-framerate', String($formData.inputFramerate));
                    }
                    if ($formData.inputVideoSize) {
                        args.push('-video_size', $formData.inputVideoSize);
                    }
                    if ($formData.inputPixelFormat) {
                        args.push('-pixel_format', $formData.inputPixelFormat);
                    }
                    if ($formData.inputArgs) {
                        const trimmed = $formData.inputArgs.trim();
                        if (trimmed) {
                            const parsed = trimmed.match(/(?:[^\s"]+|"[^"]*")+/g)?.map(arg => arg.replace(/^"|"$/g, ''));
                            if (parsed) args.push(...parsed);
                        }
                    }
                    return args.length > 0 ? args : undefined;
                };

                const requestData = {
                    input_file: $formData.inputFile || '/input/video.mp4',
                    output_file: toValue($formData.outputFile),
                    job_name: $formData.jobName || 'Preview',
                    loop_input: $formData.loopInput || false,
                    input_format: toValue($formData.inputFormat),
                    input_args: buildInputArgs(),
                    video_codec: $formData.videoCodec || 'libx264',
                    audio_codec: $formData.audioCodec || 'copy',
                    video_bitrate: toValue($formData.videoBitrate),
                    audio_bitrate: toValue($formData.audioBitrate),
                    video_framerate: toInt($formData.fps),
                    encoding_preset: toValue($formData.preset),
                    video_resolution: toValue($formData.scale),
                    video_profile: toValue($formData.videoProfile),
                    hardware_accel: toValue($formData.hardwareAccel),
                    audio_channels: toInt($formData.audioChannels),
                    audio_volume: toInt($formData.audioVolume),
                    subtitle_codec: toValue($formData.subtitleCodec),
                    subtitle_language: toValue($formData.subtitleLanguage),
                    burn_subtitles: $formData.burnSubtitles || false,
                    custom_args: toValue($formData.customFFmpegArgs)
                };

                // Remove undefined values to avoid sending them
                Object.keys(requestData).forEach(key => {
                    if (requestData[key] === undefined) {
                        delete requestData[key];
                    }
                });

                // Handle multi-output fields (not in core registry)
                if ($formData.hlsOutput) {
                    requestData.hls_output = $formData.hlsOutput;
                }
                if ($formData.udpOutputs && $formData.udpOutputs.length > 0) {
                    requestData.udp_outputs = $formData.udpOutputs;
                }
                if ($formData.rtmpOutputs && $formData.rtmpOutputs.length > 0) {
                    requestData.rtmp_outputs = $formData.rtmpOutputs;
                }
                // Streaming outputs (YouTube, Twitch)
                if ($formData.youtubeOutput && $formData.youtubeOutput.enabled) {
                    requestData.youtube_output = $formData.youtubeOutput;
                }
                if ($formData.twitchOutput && $formData.twitchOutput.enabled) {
                    requestData.twitch_output = $formData.twitchOutput;
                }
                if (streamMaps.length > 0) {
                    requestData.stream_maps = streamMaps;
                }

                // Skip API call if request data hasn't changed
                const requestStr = JSON.stringify(requestData);
                if (requestStr === JSON.stringify(lastRequestData)) {
                    return;
                }
                lastRequestData = JSON.parse(requestStr);

                // Call backend validation endpoint to get the exact command
                const response = await fetch('/api/v1/jobs/validate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestData),
                    signal: AbortSignal.timeout(5000)  // 5 second timeout
                });

                if (response.ok) {
                    const result = await response.json();
                    if (result.command) {
                        set(result.command);
                    } else {
                        set(buildCommandFallback($formData));
                    }
                } else {
                    // Fall back to minimal builder if API fails
                    set(buildCommandFallback($formData));
                }
            } catch (error) {
                // Fall back to minimal builder on any error
                console.debug('Command preview API call failed, using fallback builder:', error);
                set(buildCommandFallback($formData));
            }
        }, 250);  // 250ms debounce for faster feedback
    });

    return { subscribe };
}

export const commandPreview = createCommandPreview();

/**
 * Reset form to initial state
 */
export function resetForm() {
    formData.set({ ...initialFormData });
    validationState.set({
        isValidating: false,
        lastValidation: null,
        warnings: [],
        isValid: true
    });
}

/**
 * Update a single form field
 */
export function updateField(field, value) {
    formData.update(data => ({
        ...data,
        [field]: value
    }));
}

/**
 * Get current form data as plain object (for API calls)
 */
export function getFormData() {
    let currentData;
    formData.subscribe(data => currentData = data)();
    return currentData;
}

/**
 * Apply template settings to form (User Story 4)
 */
export function applyTemplate(template) {
    if (!template) {
        formData.update(data => ({ ...data, templateId: '' }));
        return;
    }

    formData.update(data => {
        const updated = { ...data, templateId: template.id };

        if (template.video_codec) updated.videoCodec = template.video_codec;
        if (template.audio_codec) updated.audioCodec = template.audio_codec;
        if (template.video_bitrate) updated.videoBitrate = template.video_bitrate;
        if (template.audio_bitrate) updated.audioBitrate = template.audio_bitrate;
        if (template.video_profile) updated.videoProfile = template.video_profile;
        if (template.fps) updated.fps = template.fps;
        if (template.scale) updated.scale = template.scale;
        if (template.preset) updated.preset = template.preset;
        if (template.hardware_accel) updated.hardwareAccel = template.hardware_accel;

        return updated;
    });
}

/**
 * Validate job configuration (User Story 6)
 */
export async function validateJob() {
    validationState.update(state => ({ ...state, isValidating: true }));

    try {
        const data = getFormData();

        // Convert to API format (camelCase to snake_case)
        const requestData = {
            input_file: data.inputFile,
            output_file: data.outputFile || undefined,
            video_codec: data.videoCodec,
            audio_codec: data.audioCodec,
            video_bitrate: data.videoBitrate || undefined,
            video_profile: data.videoProfile || undefined,
            fps: data.fps || undefined,
            scale: data.scale || undefined,
            video_filters: data.videoFilters || undefined,
            preset: data.preset || undefined,
            audio_bitrate: data.audioBitrate || undefined,
            audio_channels: data.audioChannels || undefined,
            audio_volume: data.audioVolume || undefined,
            hardware_accel: data.hardwareAccel !== 'none' ? data.hardwareAccel : undefined
        };

        const response = await fetch('/api/v1/jobs/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            throw new Error('Validation request failed');
        }

        const result = await response.json();

        validationState.set({
            isValidating: false,
            lastValidation: new Date(),
            warnings: result.warnings || [],
            isValid: result.valid
        });

        return result;
    } catch (error) {
        validationState.set({
            isValidating: false,
            lastValidation: new Date(),
            warnings: [{
                code: 'validation_error',
                message: error.message || 'Validation failed',
                severity: 'error'
            }],
            isValid: false
        });
        throw error;
    }
}


// ============================================================================
// ABR (Adaptive Bitrate) Helper Functions
// ============================================================================

/**
 * ABR preset definitions matching backend presets
 */
const ABR_PRESETS = {
    standard: {
        name: 'Standard',
        description: 'General purpose: 1080p, 720p, 480p',
        renditions: [
            { name: '1080p', videoBitrate: '5M', videoResolution: '1920x1080', videoProfile: 'high', audioBitrate: '128k' },
            { name: '720p', videoBitrate: '3M', videoResolution: '1280x720', videoProfile: 'main', audioBitrate: '128k' },
            { name: '480p', videoBitrate: '1.5M', videoResolution: '854x480', videoProfile: 'main', audioBitrate: '96k' }
        ]
    },
    high_quality: {
        name: 'High Quality',
        description: 'Premium content: 1080p, 720p, 540p, 360p',
        renditions: [
            { name: '1080p', videoBitrate: '5M', videoResolution: '1920x1080', videoProfile: 'high', audioBitrate: '128k' },
            { name: '720p', videoBitrate: '3M', videoResolution: '1280x720', videoProfile: 'main', audioBitrate: '128k' },
            { name: '540p', videoBitrate: '2M', videoResolution: '960x540', videoProfile: 'main', audioBitrate: '128k' },
            { name: '360p', videoBitrate: '800k', videoResolution: '640x360', videoProfile: 'baseline', audioBitrate: '64k' }
        ]
    },
    mobile_optimized: {
        name: 'Mobile Optimized',
        description: 'Low bandwidth: 720p, 480p, 360p, 240p',
        renditions: [
            { name: '720p', videoBitrate: '2.5M', videoResolution: '1280x720', videoProfile: 'main', audioBitrate: '128k' },
            { name: '480p', videoBitrate: '1.2M', videoResolution: '854x480', videoProfile: 'main', audioBitrate: '96k' },
            { name: '360p', videoBitrate: '600k', videoResolution: '640x360', videoProfile: 'baseline', audioBitrate: '64k' },
            { name: '240p', videoBitrate: '400k', videoResolution: '426x240', videoProfile: 'baseline', audioBitrate: '64k' }
        ]
    }
};

/**
 * Load an ABR preset into the form
 */
export function loadABRPreset(presetName) {
    if (!ABR_PRESETS[presetName]) {
        console.warn(`Unknown ABR preset: ${presetName}`);
        return;
    }

    const preset = ABR_PRESETS[presetName];

    formData.update(data => ({
        ...data,
        abrPreset: presetName,
        abrLadder: [...preset.renditions],
        // Set audio codec to 'aac' when ABR is enabled (instead of 'copy')
        // This ensures audio channels and volume settings are editable
        audioCodec: data.audioCodec === 'copy' ? 'aac' : data.audioCodec
    }));
}

/**
 * Get all available ABR presets
 */
export function getABRPresets() {
    return ABR_PRESETS;
}

/**
 * Add a new rendition to the custom ladder
 * Note: Video/audio codecs inherited from main settings, not stored per variant
 */
export function addRendition() {
    formData.update(data => ({
        ...data,
        abrLadder: [
            ...data.abrLadder,
            {
                name: `variant-${data.abrLadder.length + 1}`,
                videoBitrate: '2M',
                videoResolution: '1280x720',
                videoProfile: 'main',
                audioBitrate: '128k',
                audioChannels: 2,
                audioSampleRate: 48000,
                preset: 'medium'
            }
        ]
    }));
}

/**
 * Remove a rendition from the custom ladder
 */
export function removeRendition(index) {
    formData.update(data => ({
        ...data,
        abrLadder: data.abrLadder.filter((_, i) => i !== index)
    }));
}

/**
 * Update a specific field in a rendition
 */
export function updateRendition(index, field, value) {
    formData.update(data => {
        const newLadder = [...data.abrLadder];
        newLadder[index] = {
            ...newLadder[index],
            [field]: value
        };
        return {
            ...data,
            abrLadder: newLadder
        };
    });
}

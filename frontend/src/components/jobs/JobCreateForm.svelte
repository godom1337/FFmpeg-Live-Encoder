<script>
    /**
     * Job Creation/Edit Form - Main Container
     *
     * Integrates all job creation/editing components:
     * - MinimalJobView: Basic input/output configuration
     * - TemplateSelector: Quick template selection (User Story 4)
     * - AdvancedOptions: Video/audio/output encoding settings (User Stories 2 & 3)
     * - Command Preview: Real-time FFmpeg command display
     * - ValidationWarnings: Validation feedback
     * - Submit: Create/update and optionally start the job
     *
     * Supports both CREATE and EDIT modes via props
     *
     * User Stories 1, 2, 3, 4, 6: Minimal job creation, advanced customization, multi-output, templates, validation
     */
    import { onMount } from "svelte";
    import MinimalJobView from "./MinimalJobView.svelte";
    import TemplateSelector from "./TemplateSelector.svelte";
    import AdvancedOptions from "./AdvancedOptions.svelte";
    import ValidationWarnings from "./ValidationWarnings.svelte";
    import InputAnalysis from "../InputAnalysis.svelte";
    import {
        formData,
        commandPreview,
        validationState,
        resetForm,
        validateJob,
        applyTemplate,
        loadABRPreset,
    } from "../../lib/stores/jobFormStore.js";
    import ABRPresetSelector from "./ABRPresetSelector.svelte";
    import CustomLadderEditor from "./CustomLadderEditor.svelte";
    import ABRPreviewPanel from "./ABRPreviewPanel.svelte";
    import ABRVideoSettings from "./ABRVideoSettings.svelte";
    import ABRAudioSettings from "./ABRAudioSettings.svelte";
    import { jobApi } from "../../services/api.js";
    import { showSuccess, showError } from "../Notification.svelte";
    // Phase 7: Deleted imports (fieldMapper.js and fieldRegistry.js removed)

    // Props
    export let mode = "create"; // 'create' or 'edit'
    export let jobId = null; // Required when mode='edit'
    export let onJobCreated = null; // Callback when job is created
    export let onJobUpdated = null; // Callback when job is updated
    export let onCancel = null; // Callback for cancel action

    // Local state
    let isSubmitting = false;
    let isLoadingJob = false;
    let showCommandPreview = true;
    let submitError = null;
    let job = null;
    let dataLoaded = false; // Track when edit data is fully loaded

    // Load job data for edit mode
    async function loadJob() {
        if (mode !== "edit" || !jobId) return;

        isLoadingJob = true;
        try {
            // BEFORE (001-edit-api-simplification): ~150 lines of field mapping
            // AFTER: ~30 lines using unified API with formData structure mapping
            const config = await jobApi.getUnified(jobId);

            console.log("[JobCreateForm] Loaded unified config:", config);
            console.log("[JobCreateForm] Raw HLS values from API:", {
                outputFormat: config.outputFormat,
                outputDir: config.outputDir,
                hlsSegmentDuration: config.hlsSegmentDuration,
                hlsPlaylistType: config.hlsPlaylistType,
                hlsPlaylistSize: config.hlsPlaylistSize,
                hlsSegmentType: config.hlsSegmentType,
                hlsSegmentFilename: config.hlsSegmentFilename,
            });

            // Build hlsOutput object (use snake_case to match form bindings!)
            const hlsOutput =
                config.outputFormat === "hls"
                    ? {
                          output_dir: config.outputDir || "", // snake_case!
                          segment_duration: config.hlsSegmentDuration || 6,
                          segment_pattern:
                              config.hlsSegmentFilename || "segment_%03d.ts",
                          playlist_type: config.hlsPlaylistType || "vod",
                          playlist_size: config.hlsPlaylistSize || 5,
                          segment_type: config.hlsSegmentType || "mpegts",
                          playlist_name: "master.m3u8",
                      }
                    : null;

            console.log(
                "[JobCreateForm] Built hlsOutput object (snake_case):",
                hlsOutput,
            );

            // Extract track indices from streamMaps
            let videoTrackIndex = "0";
            let audioTrackIndex = "0";

            if (config.streamMaps && Array.isArray(config.streamMaps)) {
                console.log(
                    "[JobCreateForm] Stream maps found:",
                    config.streamMaps,
                );

                for (const streamMap of config.streamMaps) {
                    // Parse video track: "0:v:0" -> index is 0, "0:v:1" -> index is 1
                    if (
                        streamMap.output_label === "v" &&
                        streamMap.input_stream
                    ) {
                        const match = streamMap.input_stream.match(/0:v:(\d+)/);
                        if (match) {
                            videoTrackIndex = match[1];
                            console.log(
                                "[JobCreateForm] Extracted video track index:",
                                videoTrackIndex,
                            );
                        }
                    }

                    // Parse audio track: "0:a:0" -> index is 0, "0:a:1" -> index is 1
                    if (
                        streamMap.output_label === "a" &&
                        streamMap.input_stream
                    ) {
                        const match = streamMap.input_stream.match(/0:a:(\d+)/);
                        if (match) {
                            audioTrackIndex = match[1];
                            console.log(
                                "[JobCreateForm] Extracted audio track index:",
                                audioTrackIndex,
                            );
                        }
                    }
                }
            }

            // Map unified config to formData structure expected by form components
            formData.set({
                // Basic fields
                jobName: config.jobName || "",
                inputFile: config.inputFile || "",
                loopInput: config.loopInput || false,

                // Input device fields
                inputFormat: config.inputFormat || "",
                inputFramerate: (() => {
                    // Extract framerate from inputArgs array
                    if (config.inputArgs && Array.isArray(config.inputArgs)) {
                        const frIndex = config.inputArgs.indexOf("-framerate");
                        if (
                            frIndex !== -1 &&
                            frIndex + 1 < config.inputArgs.length
                        ) {
                            return config.inputArgs[frIndex + 1];
                        }
                    }
                    return "";
                })(),
                inputPixelFormat: (() => {
                    // Extract pixel_format from inputArgs array
                    if (config.inputArgs && Array.isArray(config.inputArgs)) {
                        const pfIndex =
                            config.inputArgs.indexOf("-pixel_format");
                        if (
                            pfIndex !== -1 &&
                            pfIndex + 1 < config.inputArgs.length
                        ) {
                            return config.inputArgs[pfIndex + 1];
                        }
                    }
                    return "";
                })(),
                inputVideoSize: (() => {
                    // Extract video_size from inputArgs array
                    if (config.inputArgs && Array.isArray(config.inputArgs)) {
                        const vsIndex = config.inputArgs.indexOf("-video_size");
                        if (
                            vsIndex !== -1 &&
                            vsIndex + 1 < config.inputArgs.length
                        ) {
                            return config.inputArgs[vsIndex + 1];
                        }
                    }
                    return "";
                })(),
                inputArgs: (() => {
                    // Extract remaining args (exclude framerate, pixel_format, and video_size)
                    if (config.inputArgs && Array.isArray(config.inputArgs)) {
                        const filtered = [];
                        for (let i = 0; i < config.inputArgs.length; i++) {
                            if (
                                config.inputArgs[i] === "-framerate" ||
                                config.inputArgs[i] === "-pixel_format" ||
                                config.inputArgs[i] === "-video_size"
                            ) {
                                i++; // Skip the value too
                            } else {
                                filtered.push(config.inputArgs[i]);
                            }
                        }
                        return filtered.join(" ");
                    }
                    return "";
                })(),

                // Video settings (map unified names to form field names)
                // Unified API returns simplified codecs (h264), need to expand to FFmpeg names (libx264) for form
                videoCodec:
                    config.videoCodec === "h264"
                        ? "libx264"
                        : config.videoCodec === "h265"
                          ? "libx265"
                          : config.videoCodec === "vp9"
                            ? "libvpx-vp9"
                            : config.videoCodec === "av1"
                              ? "libaom-av1"
                              : config.videoCodec || "libx264",
                videoBitrate: config.videoBitrate || "",
                videoProfile: config.videoProfile || "",
                fps: config.videoFrameRate ? String(config.videoFrameRate) : "",
                scale: config.videoResolution || "",
                preset: config.videoPreset || "medium",
                videoTrackIndex: videoTrackIndex,

                // Audio settings
                audioCodec: config.audioCodec || "copy",
                audioBitrate: config.audioBitrate || "",
                audioChannels: config.audioChannels
                    ? String(config.audioChannels)
                    : "",
                audioVolume: config.audioVolume
                    ? String(config.audioVolume)
                    : "",
                audioStreamIndex: "",
                audioTrackIndex: audioTrackIndex,

                // Hardware acceleration
                hardwareAccel: config.hardwareAccel || "none",
                hardwareAccelDevice: 0,
                hardwareAccelOutputFormat: "",

                // HLS output (use the object we built above)
                hlsOutput: hlsOutput,

                // Multi-output (check if we already built them above for consistency)
                // Parse UDP URL to extract all parameters including ttl and pktSize
                udpOutputs:
                    config.outputFormat === "udp" && config.outputUrl
                        ? (() => {
                              const url = config.outputUrl;
                              // Parse UDP URL: udp://address:port?ttl=X&pkt_size=Y
                              const addressMatch = url.match(
                                  /udp:\/\/([^:]+):(\d+)/,
                              );
                              const address = addressMatch
                                  ? addressMatch[1]
                                  : "";
                              const port = addressMatch
                                  ? parseInt(addressMatch[2])
                                  : 5000;

                              // Parse query parameters for ttl and pkt_size
                              const ttlMatch = url.match(/ttl=(\d+)/);
                              const ttl = ttlMatch ? parseInt(ttlMatch[1]) : 16;

                              const pktSizeMatch = url.match(/pkt_size=(\d+)/);
                              const pktSize = pktSizeMatch
                                  ? parseInt(pktSizeMatch[1])
                                  : 1316;

                              return [
                                  {
                                      url: url,
                                      address: address,
                                      port: port,
                                      ttl: ttl,
                                      pktSize: pktSize,
                                  },
                              ];
                          })()
                        : [],
                rtmpOutputs:
                    config.rtmpOutputs ||
                    (config.outputFormat === "rtmp" && config.outputUrl
                        ? [
                              {
                                  url: config.outputUrl,
                                  streamKey: "",
                              },
                          ]
                        : []),
                additionalOutputs: [],

                // Also set outputFile for compatibility
                outputFile: config.outputUrl || config.outputDir || "",

                // ABR settings
                abrEnabled: config.abrEnabled || false,
                abrPreset:
                    config.abrLadder && config.abrLadder.length > 0
                        ? "custom"
                        : "standard",
                abrLadder: config.abrLadder || [],

                // Advanced encoding
                crf: "",
                keyframeInterval: "",
                tune: "",
                twoPass: false,
                rateControlMode: "",
                level: config.videoLevel || "",
                maxBitrate: "",
                bufferSize: "",
                lookAhead: "",
                pixelFormat: "",

                // Template
                templateId: "",

                // Custom args
                customArgs: [],
                customArgsEnabled: false,
            });

            // Mark data as loaded
            dataLoaded = true;
            isLoadingJob = false;

            console.log("[JobCreateForm] Edit mode: Loaded with unified API");
            console.log(
                "[JobCreateForm] hlsOutput object that was set:",
                hlsOutput,
            );

            // IMPORTANT: Trigger the OutputSettings component to switch to the correct tab
            // This is needed because OutputSettings has its own activeTab state
            // We dispatch a custom event that OutputSettings can listen to
            setTimeout(() => {
                const event = new CustomEvent("jobLoaded", {
                    detail: {
                        outputFormat: config.outputFormat,
                        hasHLS: !!hlsOutput,
                        hasUDP: config.outputFormat === "udp",
                        hasRTMP:
                            config.outputFormat === "rtmp" ||
                            (config.rtmpOutputs &&
                                config.rtmpOutputs.length > 0),
                    },
                });
                window.dispatchEvent(event);
                console.log(
                    "[JobCreateForm] Dispatched jobLoaded event, outputFormat:",
                    config.outputFormat,
                );
            }, 100);
        } catch (error) {
            console.error("Failed to load job:", error);
            showError(
                `Failed to load job: ${error.message || "Unknown error"}`,
            );
            if (onCancel) onCancel();
            isLoadingJob = false;
            dataLoaded = false;
        }
    }

    // Validation
    async function handleValidate() {
        try {
            // This would call the backend validation API
            // For now, we'll simulate it
            validationState.set({
                isValidating: true,
                lastValidation: null,
                warnings: [],
                isValid: true,
            });

            // Simulate API call
            setTimeout(() => {
                validationState.set({
                    isValidating: false,
                    lastValidation: new Date(),
                    warnings: [],
                    isValid: true,
                });
            }, 1000);
        } catch (error) {
            console.error("Validation failed:", error);
        }
    }

    // Submit job (create or update)
    async function handleSubmit(event) {
        event.preventDefault();

        if (isSubmitting) return;

        // Validate required fields
        if (!$formData.inputFile) {
            submitError = "Input file is required";
            return;
        }

        submitError = null;
        isSubmitting = true;

        try {
            if (mode === "create") {
                // CREATE MODE (Feature 008: Unified format migration)
                // Uses same unified config format as EDIT mode for consistency

                console.log("[JobCreateForm] Creating job with unified API");

                // Helper function to convert FFmpeg codec names to simple format
                const simplifyCodec = (codec) => {
                    if (!codec) return "h264";
                    const codecMap = {
                        libx264: "h264",
                        libx265: "h265",
                        "libvpx-vp9": "vp9",
                        "libaom-av1": "av1",
                        h264_nvenc: "h264",
                        hevc_nvenc: "h265",
                    };
                    return codecMap[codec] || codec;
                };

                // Helper to normalize bitrate format (remove decimals)
                const normalizeBitrate = (bitrate) => {
                    if (!bitrate) return "";
                    // Convert "1.5M" → "1500k", "2.5M" → "2500k"
                    const match = bitrate.match(/^(\d+(?:\.\d+)?)\s*([KMG])$/i);
                    if (match) {
                        const value = parseFloat(match[1]);
                        const unit = match[2].toUpperCase();
                        if (unit === "M" && value % 1 !== 0) {
                            // Has decimal, convert to kilobits
                            return Math.round(value * 1000) + "k";
                        }
                    }
                    return bitrate;
                };

                // Convert track indices to stream_maps format (same logic as jobFormStore.js)
                const buildStreamMaps = () => {
                    const streamMaps = [];

                    // Add video track mapping if specified
                    if (
                        $formData.videoTrackIndex !== "" &&
                        $formData.videoTrackIndex !== null &&
                        $formData.videoTrackIndex !== undefined
                    ) {
                        streamMaps.push({
                            input_stream: `0:v:${$formData.videoTrackIndex}`,
                            output_label: "v",
                        });
                    }

                    // Add audio track mapping if specified (skip if audioTrackIndex is -1 = audio disabled)
                    if (
                        $formData.audioTrackIndex !== "" &&
                        $formData.audioTrackIndex !== null &&
                        $formData.audioTrackIndex !== undefined &&
                        $formData.audioTrackIndex != -1
                    ) {
                        streamMaps.push({
                            input_stream: `0:a:${$formData.audioTrackIndex}`,
                            output_label: "a",
                        });
                    }

                    return streamMaps.length > 0 ? streamMaps : undefined;
                };

                // Determine output format and destination
                let outputFormat = "hls"; // Default
                let outputDir = "";
                let outputUrl = "";

                if ($formData.hlsOutput) {
                    // HLS output configured (read from snake_case fields!)
                    outputFormat = "hls";
                    outputDir = $formData.hlsOutput.output_dir || "";
                } else if (
                    $formData.udpOutputs &&
                    $formData.udpOutputs.length > 0
                ) {
                    // UDP output configured
                    outputFormat = "udp";
                    outputUrl = $formData.udpOutputs[0].url || "";
                } else if (
                    $formData.rtmpOutputs &&
                    $formData.rtmpOutputs.length > 0
                ) {
                    // RTMP output configured
                    outputFormat = "rtmp";
                    // Use the first RTMP output's full URL
                    const rtmp = $formData.rtmpOutputs[0];
                    let fullUrl = rtmp.url;
                    if (rtmp.streamKey) {
                        if (!fullUrl.endsWith("/")) fullUrl += "/";
                        fullUrl += rtmp.streamKey;
                    }
                    outputUrl = fullUrl;
                } else if ($formData.outputFile) {
                    // Detect from file extension or protocol
                    const output = $formData.outputFile.toLowerCase();
                    if (output.startsWith("udp://")) {
                        outputFormat = "udp";
                        outputUrl = $formData.outputFile;
                    } else if (output.startsWith("rtmp://")) {
                        outputFormat = "rtmp";
                        outputUrl = $formData.outputFile;
                    } else if (output.startsWith("srt://")) {
                        outputFormat = "rtmp"; // Map srt to rtmp for now
                        outputUrl = $formData.outputFile;
                    } else if (output.includes(".mp4")) {
                        outputFormat = "mp4";
                        outputDir = $formData.outputFile;
                    } else if (output.includes(".webm")) {
                        outputFormat = "webm";
                        outputDir = $formData.outputFile;
                    } else if (output.includes(".mkv")) {
                        outputFormat = "mkv";
                        outputDir = $formData.outputFile;
                    } else if (output.includes(".avi")) {
                        outputFormat = "avi";
                        outputDir = $formData.outputFile;
                    } else if (output.includes(".mov")) {
                        outputFormat = "mov";
                        outputDir = $formData.outputFile;
                    } else {
                        // Fallback: treat as file path - default to mp4 for file outputs
                        outputFormat = "mp4";
                        outputDir = $formData.outputFile;
                    }
                }

                // Ensure we have either outputDir or outputUrl based on format
                if (!outputDir && !outputUrl) {
                    // No output configured - default to file output (mp4)
                    // Set a default output path (backend will append job_id)
                    outputFormat = "mp4";
                    outputDir = "/output/files";
                }

                const unifiedConfig = {
                    jobName: $formData.jobName || "Unnamed Job",
                    inputFile: $formData.inputFile,
                    loopInput: $formData.loopInput || false,

                    // Input device settings
                    inputFormat: $formData.inputFormat || undefined,
                    inputArgs: (() => {
                        const args = [];
                        // Add framerate if specified
                        if ($formData.inputFramerate) {
                            args.push(
                                "-framerate",
                                String($formData.inputFramerate),
                            );
                        }
                        // Add video size if specified
                        if ($formData.inputVideoSize) {
                            args.push("-video_size", $formData.inputVideoSize);
                        }
                        // Add pixel format if specified
                        if ($formData.inputPixelFormat) {
                            args.push(
                                "-pixel_format",
                                $formData.inputPixelFormat,
                            );
                        }
                        // Add custom arguments if specified
                        if ($formData.inputArgs) {
                            const trimmed = $formData.inputArgs.trim();
                            if (trimmed) {
                                const parsed = trimmed
                                    .match(/(?:[^\s"]+|"[^"]*")+/g)
                                    ?.map((arg) => arg.replace(/^"|"$/g, ""));
                                if (parsed) args.push(...parsed);
                            }
                        }
                        return args.length > 0 ? args : undefined;
                    })(),

                    // Video settings (with required field defaults)
                    videoCodec: simplifyCodec($formData.videoCodec),
                    videoBitrate:
                        normalizeBitrate($formData.videoBitrate) || undefined,
                    videoResolution:
                        $formData.scale || $formData.videoResolution,
                    videoFrameRate:
                        $formData.fps || $formData.videoFrameRate
                            ? parseInt(
                                  $formData.fps || $formData.videoFrameRate,
                              )
                            : undefined,
                    videoPreset:
                        $formData.preset || $formData.videoPreset || "medium",
                    videoProfile: $formData.videoProfile,
                    videoLevel: $formData.level,

                    // Hardware acceleration
                    hardwareAccel: $formData.hardwareAccel || "none",

                    // Audio settings (with required field defaults)
                    audioCodec: $formData.audioCodec || "aac",
                    audioBitrate:
                        normalizeBitrate($formData.audioBitrate) || "128k",
                    audioChannels: $formData.audioChannels
                        ? parseInt($formData.audioChannels)
                        : undefined,
                    audioVolume: $formData.audioVolume
                        ? parseInt($formData.audioVolume)
                        : undefined,
                    audioSampleRate: 48000,

                    // Output settings (conditional based on format)
                    outputFormat: outputFormat,
                    outputDir: outputDir || undefined,
                    outputUrl: outputUrl || undefined,

                    // Multi-output settings (RTMP and UDP arrays)
                    rtmpOutputs: $formData.rtmpOutputs || [],
                    udpOutputs: $formData.udpOutputs || [],

                    // HLS settings (send all HLS-specific fields - read from snake_case!)
                    hlsSegmentDuration:
                        $formData.hlsOutput?.segment_duration || 6,
                    hlsPlaylistType:
                        $formData.hlsOutput?.playlist_type || "vod",
                    hlsPlaylistSize: $formData.hlsOutput?.playlist_size || 5,
                    hlsSegmentType:
                        $formData.hlsOutput?.segment_type || "mpegts",
                    hlsSegmentFilename:
                        $formData.hlsOutput?.segment_pattern ||
                        "segment_%03d.ts",

                    // ABR settings (normalize bitrates in ladder)
                    abrEnabled: $formData.abrEnabled || false,
                    abrLadder: ($formData.abrLadder || []).map((r) => ({
                        ...r,
                        videoBitrate: normalizeBitrate(r.videoBitrate),
                        audioBitrate: r.audioBitrate
                            ? normalizeBitrate(r.audioBitrate)
                            : undefined,
                    })),

                    // Track selection (video/audio track indices)
                    streamMaps: buildStreamMaps(),

                    // Custom FFmpeg args
                    customFFmpegArgs: $formData.customFFmpegArgs || undefined,
                };

                // Remove undefined values
                Object.keys(unifiedConfig).forEach((key) => {
                    if (unifiedConfig[key] === undefined) {
                        delete unifiedConfig[key];
                    }
                });

                console.log(
                    "[JobCreateForm] CREATE MODE - Unified config being sent:",
                    {
                        jobName: unifiedConfig.jobName,
                        inputFile: unifiedConfig.inputFile,
                        videoCodec: unifiedConfig.videoCodec,
                        videoFrameRate: unifiedConfig.videoFrameRate,
                        videoPreset: unifiedConfig.videoPreset,
                        hardwareAccel: unifiedConfig.hardwareAccel,
                        audioCodec: unifiedConfig.audioCodec,
                        audioChannels: unifiedConfig.audioChannels,
                        audioVolume: unifiedConfig.audioVolume,
                        outputFormat: unifiedConfig.outputFormat,
                        abrEnabled: unifiedConfig.abrEnabled,
                        abrLadder: unifiedConfig.abrLadder,
                        streamMaps: unifiedConfig.streamMaps,
                    },
                );
                console.log(
                    "[JobCreateForm] Full unified config:",
                    unifiedConfig,
                );

                // Call unified create API (Feature 008)
                const result = await jobApi.createUnified(unifiedConfig);

                console.log("[JobCreateForm] Job created:", result);

                showSuccess(
                    `Job "${unifiedConfig.jobName}" created successfully!`,
                );

                // Success callback
                if (onJobCreated) {
                    onJobCreated(result);
                }

                // Reset form
                resetForm();
            } else {
                // EDIT MODE (SIMPLIFIED with 001-edit-api-simplification)
                // BEFORE: ~160 lines of complex field mapping and three separate update objects
                // AFTER: ~30 lines mapping formData to unified format

                console.log("[JobCreateForm] Updating job with unified API");

                // Map formData to unified config format
                // Helper function to convert FFmpeg codec names to simple format
                const simplifyCodec = (codec) => {
                    if (!codec) return "h264";
                    const codecMap = {
                        libx264: "h264",
                        libx265: "h265",
                        "libvpx-vp9": "vp9",
                        "libaom-av1": "av1",
                        h264_nvenc: "h264",
                        hevc_nvenc: "h265",
                    };
                    return codecMap[codec] || codec;
                };

                // Helper to normalize bitrate format (remove decimals)
                const normalizeBitrate = (bitrate) => {
                    if (!bitrate) return "";
                    // Convert "1.5M" → "1500k", "2.5M" → "2500k"
                    const match = bitrate.match(/^(\d+(?:\.\d+)?)\s*([KMG])$/i);
                    if (match) {
                        const value = parseFloat(match[1]);
                        const unit = match[2].toUpperCase();
                        if (unit === "M" && value % 1 !== 0) {
                            // Has decimal, convert to kilobits
                            return Math.round(value * 1000) + "k";
                        }
                    }
                    return bitrate;
                };

                // Convert track indices to stream_maps format (same logic as jobFormStore.js)
                const buildStreamMaps = () => {
                    const streamMaps = [];

                    // Add video track mapping if specified
                    if (
                        $formData.videoTrackIndex !== "" &&
                        $formData.videoTrackIndex !== null &&
                        $formData.videoTrackIndex !== undefined
                    ) {
                        streamMaps.push({
                            input_stream: `0:v:${$formData.videoTrackIndex}`,
                            output_label: "v",
                        });
                    }

                    // Add audio track mapping if specified (skip if audioTrackIndex is -1 = audio disabled)
                    if (
                        $formData.audioTrackIndex !== "" &&
                        $formData.audioTrackIndex !== null &&
                        $formData.audioTrackIndex !== undefined &&
                        $formData.audioTrackIndex != -1
                    ) {
                        streamMaps.push({
                            input_stream: `0:a:${$formData.audioTrackIndex}`,
                            output_label: "a",
                        });
                    }

                    return streamMaps.length > 0 ? streamMaps : undefined;
                };

                // Determine output format and destination
                let outputFormat = "hls"; // Default
                let outputDir = "";
                let outputUrl = "";

                if ($formData.hlsOutput) {
                    // HLS output configured (read from snake_case fields!)
                    outputFormat = "hls";
                    outputDir = $formData.hlsOutput.output_dir || "";
                    console.log(
                        "[JobCreateForm] HLS output detected, dir:",
                        outputDir,
                    );
                } else if (
                    $formData.udpOutputs &&
                    $formData.udpOutputs.length > 0
                ) {
                    // UDP output configured
                    outputFormat = "udp";
                    outputUrl = $formData.udpOutputs[0].url || "";
                    console.log(
                        "[JobCreateForm] UDP output detected, url:",
                        outputUrl,
                    );
                } else if (
                    $formData.rtmpOutputs &&
                    $formData.rtmpOutputs.length > 0
                ) {
                    // RTMP output configured
                    outputFormat = "rtmp";
                    // Use the first RTMP output's full URL
                    const rtmp = $formData.rtmpOutputs[0];
                    let fullUrl = rtmp.url;
                    if (rtmp.streamKey) {
                        if (!fullUrl.endsWith("/")) fullUrl += "/";
                        fullUrl += rtmp.streamKey;
                    }
                    outputUrl = fullUrl;
                    console.log(
                        "[JobCreateForm] RTMP output detected, url:",
                        outputUrl,
                    );
                } else if ($formData.outputFile) {
                    // Detect from file extension or protocol
                    const output = $formData.outputFile.toLowerCase();
                    if (output.startsWith("udp://")) {
                        outputFormat = "udp";
                        outputUrl = $formData.outputFile;
                    } else if (output.startsWith("rtmp://")) {
                        outputFormat = "rtmp";
                        outputUrl = $formData.outputFile;
                    } else if (output.startsWith("srt://")) {
                        outputFormat = "rtmp"; // Map srt to rtmp for now
                        outputUrl = $formData.outputFile;
                    } else if (output.includes(".mp4")) {
                        outputFormat = "mp4";
                        outputDir = $formData.outputFile;
                    } else if (output.includes(".webm")) {
                        outputFormat = "webm";
                        outputDir = $formData.outputFile;
                    } else if (output.includes(".mkv")) {
                        outputFormat = "mkv";
                        outputDir = $formData.outputFile;
                    } else if (output.includes(".avi")) {
                        outputFormat = "avi";
                        outputDir = $formData.outputFile;
                    } else if (output.includes(".mov")) {
                        outputFormat = "mov";
                        outputDir = $formData.outputFile;
                    } else {
                        // Fallback: treat as file path - default to mp4 for file outputs
                        outputFormat = "mp4";
                        outputDir = $formData.outputFile;
                    }
                    console.log(
                        "[JobCreateForm] Output from outputFile, format:",
                        outputFormat,
                        "dir/url:",
                        outputDir || outputUrl,
                    );
                }

                // Ensure we have either outputDir or outputUrl based on format
                if (!outputDir && !outputUrl) {
                    // No output configured - default to file output (mp4)
                    // Backend will auto-generate output path with job_id
                    outputFormat = "mp4";
                    outputDir = "/output/files";
                    console.log(
                        "[JobCreateForm] No output configured, using default file output (mp4)",
                    );
                }

                const unifiedConfig = {
                    jobName: $formData.jobName,
                    inputFile: $formData.inputFile,
                    loopInput: $formData.loopInput || false,

                    // Input device settings
                    inputFormat: $formData.inputFormat || undefined,
                    inputArgs: (() => {
                        const args = [];
                        // Add framerate if specified
                        if ($formData.inputFramerate) {
                            args.push(
                                "-framerate",
                                String($formData.inputFramerate),
                            );
                        }
                        // Add video size if specified
                        if ($formData.inputVideoSize) {
                            args.push("-video_size", $formData.inputVideoSize);
                        }
                        // Add pixel format if specified
                        if ($formData.inputPixelFormat) {
                            args.push(
                                "-pixel_format",
                                $formData.inputPixelFormat,
                            );
                        }
                        // Add custom arguments if specified
                        if ($formData.inputArgs) {
                            const trimmed = $formData.inputArgs.trim();
                            if (trimmed) {
                                const parsed = trimmed
                                    .match(/(?:[^\s"]+|"[^"]*")+/g)
                                    ?.map((arg) => arg.replace(/^"|"$/g, ""));
                                if (parsed) args.push(...parsed);
                            }
                        }
                        return args.length > 0 ? args : undefined;
                    })(),

                    // Video settings (with required field defaults)
                    videoCodec: simplifyCodec($formData.videoCodec),
                    videoBitrate:
                        normalizeBitrate($formData.videoBitrate) || undefined,
                    videoResolution: $formData.scale,
                    videoFrameRate: $formData.fps
                        ? parseInt($formData.fps)
                        : undefined,
                    videoPreset: $formData.preset || "medium",
                    videoProfile: $formData.videoProfile,
                    videoLevel: $formData.level,

                    // Hardware acceleration
                    hardwareAccel: $formData.hardwareAccel || "none",

                    // Audio settings (with required field defaults)
                    audioCodec: $formData.audioCodec || "aac", // Don't convert 'copy' - it's valid!
                    audioBitrate:
                        normalizeBitrate($formData.audioBitrate) || "128k", // Required field with default
                    audioChannels: $formData.audioChannels
                        ? parseInt($formData.audioChannels)
                        : undefined,
                    audioVolume: $formData.audioVolume
                        ? parseInt($formData.audioVolume)
                        : undefined,
                    audioSampleRate: 48000,

                    // Output settings (conditional based on format)
                    outputFormat: outputFormat,
                    outputDir: outputDir || undefined, // Only set if present
                    outputUrl: outputUrl || undefined, // Only set if present

                    // Multi-output settings (RTMP and UDP arrays)
                    rtmpOutputs: $formData.rtmpOutputs || [],
                    udpOutputs: $formData.udpOutputs || [],

                    // HLS settings (send all HLS-specific fields - read from snake_case!)
                    hlsSegmentDuration:
                        $formData.hlsOutput?.segment_duration || 6,
                    hlsPlaylistType:
                        $formData.hlsOutput?.playlist_type || "vod",
                    hlsPlaylistSize: $formData.hlsOutput?.playlist_size || 5,
                    hlsSegmentType:
                        $formData.hlsOutput?.segment_type || "mpegts",
                    hlsSegmentFilename:
                        $formData.hlsOutput?.segment_pattern ||
                        "segment_%03d.ts",

                    // ABR settings (normalize bitrates in ladder)
                    abrEnabled: $formData.abrEnabled || false,
                    abrLadder: ($formData.abrLadder || []).map((r) => ({
                        ...r,
                        videoBitrate: normalizeBitrate(r.videoBitrate),
                        audioBitrate: r.audioBitrate
                            ? normalizeBitrate(r.audioBitrate)
                            : undefined,
                    })),

                    // Track selection (video/audio track indices)
                    streamMaps: buildStreamMaps(),
                };

                // Remove undefined values
                Object.keys(unifiedConfig).forEach((key) => {
                    if (unifiedConfig[key] === undefined) {
                        delete unifiedConfig[key];
                    }
                });

                console.log(
                    "[JobCreateForm] EDIT MODE - Unified config being sent:",
                    {
                        jobName: unifiedConfig.jobName,
                        videoCodec: unifiedConfig.videoCodec,
                        videoBitrate: unifiedConfig.videoBitrate,
                        videoFrameRate: unifiedConfig.videoFrameRate,
                        videoPreset: unifiedConfig.videoPreset,
                        hardwareAccel: unifiedConfig.hardwareAccel,
                        audioCodec: unifiedConfig.audioCodec,
                        audioBitrate: unifiedConfig.audioBitrate,
                        audioChannels: unifiedConfig.audioChannels,
                        audioVolume: unifiedConfig.audioVolume,
                        outputFormat: unifiedConfig.outputFormat,
                        outputDir: unifiedConfig.outputDir,
                        abrEnabled: unifiedConfig.abrEnabled,
                        abrLadder: unifiedConfig.abrLadder,
                        streamMaps: unifiedConfig.streamMaps,
                    },
                );
                console.log(
                    "[JobCreateForm] Full unified config:",
                    unifiedConfig,
                );
                console.log("[JobCreateForm] Form data before conversion:", {
                    videoCodec: $formData.videoCodec,
                    audioCodec: $formData.audioCodec,
                    fps: $formData.fps,
                    audioChannels: $formData.audioChannels,
                    audioVolume: $formData.audioVolume,
                });

                const result = await jobApi.updateUnified(jobId, unifiedConfig);

                console.log("[JobCreateForm] Job updated:", result);

                showSuccess(
                    `Job "${$formData.jobName || jobId}" updated successfully!`,
                );

                // Success callback
                if (onJobUpdated) {
                    onJobUpdated(result);
                }
            }
        } catch (error) {
            console.error(`Failed to ${mode} job:`, error);

            // Extract detailed error message
            console.error("Full error object:", error);
            if (error.data) {
                console.error("Error data:", error.data);
            }

            let errorMessage = error.message || "Unknown error";

            if (error.data) {
                if (typeof error.data === "string") {
                    errorMessage = error.data;
                } else if (error.data.detail) {
                    if (typeof error.data.detail === "string") {
                        errorMessage = error.data.detail;
                    } else if (
                        error.data.detail.message &&
                        typeof error.data.detail.message === "string"
                    ) {
                        errorMessage = error.data.detail.message;
                    }
                } else if (error.data.message) {
                    // Handle top-level message field
                    if (typeof error.data.message === "string") {
                        errorMessage = error.data.message;
                    } else if (typeof error.data.message === "object") {
                        errorMessage = JSON.stringify(error.data.message);
                    }
                } else if (error.data.error) {
                    // Handle top-level error field
                    if (typeof error.data.error === "string") {
                        errorMessage = error.data.error;
                    } else if (typeof error.data.error === "object") {
                        errorMessage = JSON.stringify(error.data.error);
                    }
                }
            }

            submitError = errorMessage;
            showError(`Failed to ${mode} job: ${errorMessage}`);
        } finally {
            isSubmitting = false;
        }
    }

    // Toggle command preview
    function toggleCommandPreview() {
        showCommandPreview = !showCommandPreview;
    }

    // Format command for better readability - each argument on separate line
    function formatCommand(command) {
        if (!command) return "";
        // Format command for better readability by adding line breaks before each flag
        return command.replace(/ -/g, " \\\n  -").replace(/^ffmpeg/, "ffmpeg");
    }

    // Handle template selection (User Story 4)
    function handleTemplateSelected(template) {
        if (template) {
            applyTemplate(template);
        } else {
            // Clear template
            applyTemplate(null);
        }
    }

    // Load job data on mount if in edit mode
    onMount(() => {
        if (mode === "edit") {
            loadJob();
        } else {
            // In create mode, mark as loaded immediately
            dataLoaded = true;
        }
    });

    // Reactive statement to ensure formData stays in sync with loaded data
    $: if (dataLoaded && mode === "edit") {
        // Force an immediate update to ensure all reactive statements execute
        // This helps child components pick up the latest store values
        console.log(
            "[JobCreateForm] Data loaded, ensuring store subscriptions are active",
        );
    }
</script>

{#if isLoadingJob}
    <div class="loading">
        <div class="spinner"></div>
        <p>Loading job data...</p>
    </div>
{:else if dataLoaded}
    {#key mode === "edit" ? `edit-${jobId}` : "create"}
        <form class="job-create-form" on:submit={handleSubmit}>
            <!-- Minimal Job Configuration -->
            <MinimalJobView />

            <!-- Input Analysis (FFprobe) -->
            {#if $formData.inputFile}
                <InputAnalysis
                    inputUrl={$formData.inputFile}
                    inputType="file"
                />
            {/if}

            <!-- Template Selector (User Story 4) -->
            <TemplateSelector onTemplateSelected={handleTemplateSelected} />

            <!-- ABR (Adaptive Bitrate) Toggle - Moved from VideoSettings -->
            <div class="form-group full-width abr-section">
                <div class="abr-toggle">
                    <label for="abr-enabled" class="checkbox-label">
                        <input
                            id="abr-enabled"
                            type="checkbox"
                            bind:checked={$formData.abrEnabled}
                            on:change={() => {
                                if ($formData.abrEnabled) {
                                    // When enabling ABR
                                    if (
                                        !$formData.abrLadder ||
                                        $formData.abrLadder.length === 0
                                    ) {
                                        // Load default preset when enabling ABR
                                        loadABRPreset("standard");
                                    }
                                    // Ensure audio codec is not 'copy' so channels/volume are editable
                                    if ($formData.audioCodec === "copy") {
                                        formData.update((data) => ({
                                            ...data,
                                            audioCodec: "aac",
                                        }));
                                    }
                                }
                            }}
                            class="checkbox"
                        />
                        Enable Adaptive Bitrate (ABR)
                    </label>
                    <small class="help-text">
                        Generate multiple quality variants (1080p, 720p, 480p,
                        etc.) for adaptive streaming
                    </small>
                </div>

                <!-- Show preset selector when ABR is enabled -->
                {#if $formData.abrEnabled}
                    <div class="abr-config">
                        <ABRPresetSelector />

                        <!-- Show custom ladder editor when "Custom" preset is selected -->
                        {#if $formData.abrPreset === "custom"}
                            <CustomLadderEditor />
                        {/if}

                        <!-- Show preview panel for all configurations -->
                        {#if $formData.abrLadder && $formData.abrLadder.length > 0}
                            <ABRPreviewPanel />
                        {/if}

                        <!-- ABR Video Settings (replaces VideoSettings when ABR enabled) -->
                        <div class="abr-settings-divider"></div>
                        <ABRVideoSettings />

                        <!-- ABR Audio Settings (replaces AudioSettings when ABR enabled) -->
                        <ABRAudioSettings />
                    </div>
                {/if}
            </div>

            <!-- Advanced Options (Expandable) - includes Video/Audio/Output settings -->
            <AdvancedOptions />

            <!-- Command Preview -->
            <div class="command-preview-section">
                <button
                    type="button"
                    class="preview-toggle"
                    on:click={toggleCommandPreview}
                >
                    <span class="icon">{showCommandPreview ? "▼" : "▶"}</span>
                    <span class="title">Command Preview</span>
                    <span class="subtitle">Real-time FFmpeg command</span>
                </button>

                {#if showCommandPreview}
                    <div class="preview-content">
                        <pre class="command-display"><code
                                >{formatCommand($commandPreview)}</code
                            ></pre>
                        <div class="preview-actions">
                            <button
                                type="button"
                                class="btn-secondary"
                                on:click={handleValidate}
                                disabled={$validationState.isValidating}
                            >
                                {$validationState.isValidating
                                    ? "Validating..."
                                    : "Dry Run Validation"}
                            </button>
                        </div>
                    </div>
                {/if}
            </div>

            <!-- Validation Warnings -->
            <ValidationWarnings
                warnings={$validationState.warnings}
                isValidating={$validationState.isValidating}
            />

            <!-- Submit Error -->
            {#if submitError}
                <div class="alert alert-error">
                    ❌ {submitError}
                </div>
            {/if}

            <!-- Submit Actions -->
            <div class="form-actions">
                <button
                    type="submit"
                    class="btn-primary"
                    disabled={isSubmitting || !$formData.inputFile}
                >
                    {#if mode === "create"}
                        {isSubmitting ? "Creating Job..." : "Create Job"}
                    {:else}
                        {isSubmitting ? "Updating Job..." : "Update Job"}
                    {/if}
                </button>

                {#if mode === "create"}
                    <button
                        type="button"
                        class="btn-secondary"
                        on:click={resetForm}
                        disabled={isSubmitting}
                    >
                        Reset Form
                    </button>
                {:else}
                    <button
                        type="button"
                        class="btn-secondary"
                        on:click={() => onCancel && onCancel()}
                        disabled={isSubmitting}
                    >
                        Cancel
                    </button>
                {/if}
            </div>
        </form>
    {/key}
{/if}

<style>
    .job-create-form {
        max-width: 1000px;
        margin: 0 auto;
        padding: 1.5rem;
        display: flex;
        flex-direction: column;
        gap: 1.5rem;
    }

    .command-preview-section {
        border: 1px solid rgba(0, 0, 0, 0.08);
        border-radius: 16px;
        background-color: #fff;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
        overflow: hidden;
    }

    .preview-toggle {
        width: 100%;
        padding: 1.25rem 1.5rem;
        border: none;
        background-color: transparent;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 0.75rem;
        text-align: left;
        transition: background-color 0.2s;
    }

    .preview-toggle:hover {
        background-color: #f8fafc;
    }

    .icon {
        font-size: 0.75rem;
        color: #64748b;
        flex-shrink: 0;
    }

    .title {
        font-weight: 600;
        color: #1e293b;
        font-size: 1rem;
    }

    .subtitle {
        color: #64748b;
        font-size: 0.875rem;
        margin-left: auto;
        font-weight: 500;
    }

    .preview-content {
        border-top: 1px solid #e2e8f0;
        padding: 1.25rem;
        background-color: #f8fafc;
    }

    .command-display {
        background-color: #0f172a;
        color: #22c55e;
        padding: 1.25rem;
        border-radius: 12px;
        overflow-x: auto;
        font-family: "SF Mono", "Fira Code", monospace;
        font-size: 0.85rem;
        line-height: 1.6;
        margin: 0 0 1rem 0;
        white-space: pre-wrap;
        word-break: break-all;
        border: 1px solid #1e293b;
    }

    .command-display code {
        color: inherit;
        background: none;
    }

    .preview-actions {
        display: flex;
        gap: 0.75rem;
        justify-content: flex-end;
    }

    .form-actions {
        display: flex;
        gap: 1rem;
        padding-top: 1.5rem;
        border-top: 1px solid #e2e8f0;
    }

    .btn-primary,
    .btn-secondary {
        padding: 0.875rem 1.75rem;
        border-radius: 10px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
        font-size: 0.95rem;
        border: none;
    }

    /* ABR Section Styles */
    .abr-section {
        margin-top: 0.5rem;
        padding: 1.5rem;
        background-color: #fff;
        border: 1px solid rgba(0, 0, 0, 0.08);
        border-radius: 16px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
    }

    .abr-toggle {
        margin-bottom: 1rem;
    }

    .checkbox-label {
        display: flex;
        align-items: center;
        gap: 0.625rem;
        cursor: pointer;
        font-weight: 600;
        color: #1e293b;
        font-size: 1rem;
    }

    .checkbox {
        width: 1.25rem;
        height: 1.25rem;
        cursor: pointer;
        accent-color: #3b82f6;
    }

    .abr-config {
        margin-top: 1.5rem;
        padding-left: 1.5rem;
        border-left: 3px solid #3b82f6;
    }

    .abr-settings-divider {
        height: 1px;
        background: linear-gradient(90deg, #e2e8f0, transparent);
        margin: 2rem 0 1.5rem 0;
    }

    .help-text {
        display: block;
        margin-top: 0.5rem;
        color: #64748b;
        font-size: 0.85rem;
        margin-left: 1.875rem;
        font-weight: 400;
    }

    .btn-primary {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: #fff;
        box-shadow: 0 2px 8px rgba(16, 185, 129, 0.4);
    }

    .btn-primary:hover:not(:disabled) {
        background: linear-gradient(135deg, #059669 0%, #047857 100%);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.5);
    }

    .btn-primary:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        transform: none;
        box-shadow: none;
    }

    .btn-secondary {
        background-color: #f1f5f9;
        color: #475569;
        border: 1px solid #e2e8f0;
    }

    .btn-secondary:hover:not(:disabled) {
        background-color: #e2e8f0;
        transform: translateY(-1px);
    }

    .btn-secondary:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        transform: none;
    }

    .alert {
        padding: 1rem 1.25rem;
        border-radius: 12px;
        border: 1px solid;
        font-weight: 500;
    }

    .alert-error {
        background: linear-gradient(135deg, #ffffff 0%, #fef2f2 100%);
        border-color: #fecaca;
        color: #dc2626;
    }

    .loading {
        text-align: center;
        padding: 80px 40px;
        background: white;
        border-radius: 16px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
    }

    .spinner {
        display: inline-block;
        width: 44px;
        height: 44px;
        border: 4px solid #e2e8f0;
        border-top-color: #3b82f6;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin-bottom: 20px;
    }

    @keyframes spin {
        to {
            transform: rotate(360deg);
        }
    }

    .loading p {
        color: #64748b;
        font-size: 15px;
        font-weight: 500;
    }

    @media (max-width: 768px) {
        .job-create-form {
            padding: 1rem;
        }

        .form-actions {
            flex-direction: column;
        }

        .btn-primary,
        .btn-secondary {
            width: 100%;
        }
    }
</style>

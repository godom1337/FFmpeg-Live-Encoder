<script>
    /**
     * Minimal Job View Component
     *
     * Provides the minimal interface for job creation:
     * - Input file selector
     * - Job name (optional)
     * - Loop input option (for live streaming)
     *
     * User Story 1: Quick Minimal Job Creation
     * Note: Output file configuration moved to Output Settings in Advanced Options
     */
    import { formData } from "../../lib/stores/jobFormStore.js";
    import FileBrowser from "../FileBrowser.svelte";

    let showFileBrowser = false;
    let isDeviceInput = false;

    // Reactive statement to detect device input mode from form data
    $: {
        // If inputFormat has a value, we're in device input mode
        if ($formData.inputFormat && $formData.inputFormat !== '') {
            isDeviceInput = true;
        }
    }

    // Helper function to update fields
    function updateField(field, value) {
        formData.update((data) => ({
            ...data,
            [field]: value,
        }));
    }

    // File browser - open modal
    function browseInputFile() {
        showFileBrowser = true;
    }

    // Handle file selection from browser
    function handleFileSelected(filePath) {
        updateField("inputFile", filePath);
    }
</script>

<div class="minimal-job-view">
    <h3>Create Encoding Job</h3>
    <p class="subtitle">
        Quickly create a transcoding job with H.264 video and copied audio (no
        re-encoding)
    </p>

    <div class="form-section">
        <!-- Job Name (Optional) -->
        <div class="form-group">
            <label for="job-name">
                Job Name
                <span class="optional">(optional)</span>
            </label>
            <input
                id="job-name"
                type="text"
                bind:value={$formData.jobName}
                placeholder="e.g., My Encoding Job"
                class="form-control"
            />
            <small class="help-text">
                If not provided, will be auto-generated from input file name
            </small>
        </div>

        <!-- Input File (Required) -->
        <div class="form-group required">
            <label for="input-file">
                Input File
                <span class="required-indicator">*</span>
            </label>
            <div class="file-input-group">
                <input
                    id="input-file"
                    type="text"
                    bind:value={$formData.inputFile}
                    placeholder="/input/my_video.mp4 or http://..."
                    class="form-control"
                    required
                />
                <button
                    type="button"
                    class="browse-button"
                    on:click={browseInputFile}
                >
                    Browse
                </button>
            </div>
            <small class="help-text">
                Full path to input video file (must be in /input directory) or
                URL http://... or udp://...
            </small>
        </div>

        <!-- Loop Input Option -->
        <div class="form-group checkbox-group">
            <label class="checkbox-label">
                <input
                    type="checkbox"
                    checked={$formData.loopInput}
                    on:change={(e) =>
                        updateField("loopInput", e.target.checked)}
                />
                <span>Loop input file (for live streaming)</span>
            </label>
            <small class="help-text">
                Continuously loop the input file for live streaming scenarios
            </small>
        </div>

        <!-- Device Input Toggle -->
        <div class="form-group checkbox-group">
            <label class="checkbox-label">
                <input
                    type="checkbox"
                    checked={isDeviceInput}
                    on:change={(e) => {
                        isDeviceInput = e.target.checked;
                        if (isDeviceInput) {
                            // Clear file input when switching to device mode
                            updateField("inputFile", "");

                            // Set default encoding values for device input
                            // Device inputs must be encoded, so ensure audio codec is not "copy"
                            if (!$formData.audioCodec || $formData.audioCodec === 'copy') {
                                updateField("audioCodec", "aac");
                            }
                            // Ensure video codec has a valid default
                            if (!$formData.videoCodec) {
                                updateField("videoCodec", "libx264");
                            }
                            // Set default audio bitrate if not set
                            if (!$formData.audioBitrate) {
                                updateField("audioBitrate", "128k");
                            }
                        } else {
                            // Clear device fields when switching to file mode
                            updateField("inputFormat", "");
                            updateField("inputArgs", "");
                            updateField("inputFramerate", "");
                            updateField("inputPixelFormat", "");
                            updateField("inputVideoSize", "");
                        }
                    }}
                />
                <span>Use device input (camera/microphone)</span>
            </label>
            <small class="help-text">
                Enable to capture from a device instead of a file
            </small>
        </div>

        <!-- Device Input Fields (shown when device input is enabled) -->
        {#if isDeviceInput}
            <div class="device-inputs">
                <!-- Input Format -->
                <div class="form-group">
                    <label for="input-format">
                        Input Format
                        <span class="required-indicator">*</span>
                    </label>
                    <select
                        id="input-format"
                        bind:value={$formData.inputFormat}
                        class="form-control"
                        required
                    >
                        <option value="">Select format...</option>
                        <option value="avfoundation">AVFoundation (macOS)</option>
                        <option value="v4l2">Video4Linux2 (Linux)</option>
                        <option value="dshow">DirectShow (Windows)</option>
                        <option value="gdigrab">GDI Screen Capture (Windows)</option>
                        <option value="x11grab">X11 Screen Capture (Linux)</option>
                    </select>
                    <small class="help-text">
                        Select the input format for your device
                    </small>
                </div>

                <!-- Device Identifier -->
                <div class="form-group">
                    <label for="device-id">
                        Device Identifier
                        <span class="required-indicator">*</span>
                    </label>
                    <input
                        id="device-id"
                        type="text"
                        bind:value={$formData.inputFile}
                        placeholder="e.g., 0:0 (video:audio) for macOS"
                        class="form-control"
                        required
                    />
                    <small class="help-text">
                        Device ID (e.g., "0:0" for macOS, "/dev/video0" for Linux, device name for Windows)
                    </small>
                </div>

                <!-- Framerate -->
                <div class="form-group">
                    <label for="input-framerate">
                        Framerate
                        <span class="optional">(optional)</span>
                    </label>
                    <input
                        id="input-framerate"
                        type="number"
                        bind:value={$formData.inputFramerate}
                        placeholder="e.g., 30"
                        class="form-control"
                        min="1"
                        max="120"
                    />
                    <small class="help-text">
                        Input device framerate (fps)
                    </small>
                </div>

                <!-- Pixel Format -->
                <div class="form-group">
                    <label for="input-pixel-format">
                        Pixel Format
                        <span class="optional">(optional)</span>
                    </label>
                    <select
                        id="input-pixel-format"
                        bind:value={$formData.inputPixelFormat}
                        class="form-control"
                    >
                        <option value="">Default</option>
                        <option value="uyvy422">UYVY422</option>
                        <option value="yuyv422">YUYV422</option>
                        <option value="nv12">NV12</option>
                        <option value="yuv420p">YUV420P</option>
                        <option value="bgr0">BGR0</option>
                        <option value="rgb24">RGB24</option>
                    </select>
                    <small class="help-text">
                        Pixel format for device capture
                    </small>
                </div>

                <!-- Video Size -->
                <div class="form-group">
                    <label for="input-video-size">
                        Video Size
                        <span class="optional">(optional)</span>
                    </label>
                    <input
                        id="input-video-size"
                        type="text"
                        bind:value={$formData.inputVideoSize}
                        placeholder="e.g., 1920x1080 or 1280x720"
                        class="form-control"
                    />
                    <small class="help-text">
                        Video resolution for device capture (format: WIDTHxHEIGHT)
                    </small>
                </div>

                <!-- Input Arguments (Optional) -->
                <div class="form-group">
                    <label for="input-args">
                        Additional Arguments
                        <span class="optional">(optional)</span>
                    </label>
                    <input
                        id="input-args"
                        type="text"
                        bind:value={$formData.inputArgs}
                        placeholder='e.g., -capture_cursor 0'
                        class="form-control"
                    />
                    <small class="help-text">
                        Additional FFmpeg input arguments (advanced users only)
                    </small>
                </div>
            </div>
        {/if}
    </div>
</div>

<FileBrowser bind:isOpen={showFileBrowser} onSelect={handleFileSelected} />

<style>
    .minimal-job-view {
        padding: 1.75rem;
        background-color: #fff;
        border-radius: 16px;
        border: 1px solid rgba(0, 0, 0, 0.06);
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
    }

    h3 {
        margin: 0 0 0.5rem 0;
        color: #1e293b;
        font-size: 1.5rem;
        font-weight: 700;
        letter-spacing: -0.25px;
    }

    .subtitle {
        margin: 0 0 1.75rem 0;
        color: #64748b;
        font-size: 0.9rem;
    }

    .form-section {
        display: flex;
        flex-direction: column;
        gap: 1.5rem;
    }

    .form-group {
        display: flex;
        flex-direction: column;
    }

    .form-group.required label {
        font-weight: 600;
    }

    label {
        display: block;
        margin-bottom: 0.625rem;
        font-weight: 500;
        color: #1e293b;
        font-size: 0.95rem;
    }

    .optional {
        font-weight: 400;
        color: #94a3b8;
        font-size: 0.85rem;
    }

    .required-indicator {
        color: #ef4444;
        font-weight: 600;
    }

    .form-control {
        padding: 0.75rem 1rem;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        font-size: 0.95rem;
        font-family: inherit;
        background: #f8fafc;
        transition: all 0.2s ease;
    }

    .form-control:hover {
        border-color: #cbd5e1;
    }

    .form-control:focus {
        outline: none;
        border-color: #3b82f6;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        background: #fff;
    }

    .file-input-group {
        display: flex;
        gap: 0.625rem;
    }

    .file-input-group .form-control {
        flex: 1;
    }

    .browse-button {
        padding: 0.75rem 1.25rem;
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        font-size: 0.9rem;
        font-weight: 600;
        color: #475569;
        cursor: pointer;
        transition: all 0.2s ease;
    }

    .browse-button:hover {
        background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
        border-color: #cbd5e1;
        transform: translateY(-1px);
    }

    .browse-button:active {
        transform: translateY(0);
    }

    .checkbox-group {
        gap: 0.625rem;
    }

    .checkbox-label {
        display: flex;
        align-items: center;
        gap: 0.625rem;
        cursor: pointer;
        margin-bottom: 0.375rem;
        padding: 0.625rem 0.875rem;
        border-radius: 8px;
        transition: background 0.15s;
    }

    .checkbox-label:hover {
        background: #f8fafc;
    }

    .checkbox-label input[type="checkbox"] {
        width: 1.125rem;
        height: 1.125rem;
        cursor: pointer;
        accent-color: #3b82f6;
    }

    .help-text {
        display: block;
        margin-top: 0.5rem;
        color: #64748b;
        font-size: 0.85rem;
        line-height: 1.5;
    }

    .device-inputs {
        padding: 1.25rem;
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        display: flex;
        flex-direction: column;
        gap: 1.25rem;
    }

    select.form-control {
        cursor: pointer;
        background-color: white;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%2364748b'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'%3E%3C/path%3E%3C/svg%3E");
        background-repeat: no-repeat;
        background-position: right 0.75rem center;
        background-size: 1.25rem;
        padding-right: 2.5rem;
        appearance: none;
    }

    @media (max-width: 600px) {
        .minimal-job-view {
            padding: 1.25rem;
        }

        .file-input-group {
            flex-direction: column;
        }

        .browse-button {
            width: 100%;
        }
    }
</style>

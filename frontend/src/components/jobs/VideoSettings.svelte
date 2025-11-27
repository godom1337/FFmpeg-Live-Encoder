<script>
    /**
     * Video Encoding Settings Component
     *
     * Provides controls for advanced video encoding parameters:
     * - Codec selection
     * - Bitrate, FPS, Profile
     * - Scale/resolution
     * - Hardware acceleration
     * - Filters
     * - Encoding preset
     * - ABR (Adaptive Bitrate) configuration
     *
     * User Story 2: Advanced Encoding Customization
     * User Story 1 (US1): Enable ABR for HLS Output
     */
    import { formData } from "../../lib/stores/jobFormStore.js";
    import { onMount, tick } from "svelte";

    // Helper function to update individual fields
    function updateField(field, value) {
        formData.update((data) => ({
            ...data,
            [field]: value,
        }));
    }

    // Watch for codec changes and handle profile compatibility
    $: if ($formData.videoCodec === "libaom-av1" && $formData.videoProfile) {
        console.log("[VideoSettings] Clearing profile for AV1 codec");
        updateField("videoProfile", "");
    }

    // Clear baseline profile when switching to H.265 (not supported)
    $: if (
        $formData.videoCodec === "libx265" &&
        $formData.videoProfile === "baseline"
    ) {
        console.log(
            "[VideoSettings] Clearing baseline profile for H.265 codec",
        );
        updateField("videoProfile", "");
    }

    // Hardware encoder mapping
    const codecMap = {
        nvenc: {
            libx264: "h264_nvenc",
            libx265: "hevc_nvenc",
            "libaom-av1": "av1_nvenc",
        },
        vaapi: {
            libx264: "h264_vaapi",
            libx265: "hevc_vaapi",
            "libaom-av1": "av1_vaapi",
        },
        videotoolbox: {
            libx264: "h264_videotoolbox",
            libx265: "hevc_videotoolbox",
            // Note: AV1 is not supported by VideoToolbox
        },
    };

    // Compute the actual encoder that will be used
    $: actualEncoder = (() => {
        const hwAccel = $formData.hardwareAccel;
        const codec = $formData.videoCodec;

        if (!hwAccel || hwAccel === "none" || !codec) {
            return null;
        }

        if (codecMap[hwAccel] && codecMap[hwAccel][codec]) {
            return codecMap[hwAccel][codec];
        }

        return null; // Hardware acceleration not available for this codec
    })();

    // Get valid presets for current codec
    $: validPresets = (() => {
        const codec = $formData.videoCodec;
        const hwAccel = $formData.hardwareAccel;

        // Check if we're using AV1 with NVENC
        const isAv1Nvenc = codec === "libaom-av1" && hwAccel === "nvenc";

        if (isAv1Nvenc) {
            // AV1 NVENC uses p1-p7 presets
            return [
                { value: "", label: "Default" },
                { value: "p1", label: "P1 - Fastest (lowest quality)" },
                { value: "p2", label: "P2" },
                { value: "p3", label: "P3" },
                { value: "p4", label: "P4 - Balanced" },
                { value: "p5", label: "P5" },
                { value: "p6", label: "P6" },
                { value: "p7", label: "P7 - Slowest (highest quality)" },
            ];
        } else {
            // H.264/H.265 use standard presets
            return [
                { value: "", label: "Default" },
                { value: "ultrafast", label: "Ultrafast - Fastest encode" },
                { value: "superfast", label: "Superfast" },
                { value: "veryfast", label: "Very Fast" },
                { value: "faster", label: "Faster" },
                { value: "fast", label: "Fast" },
                { value: "medium", label: "Medium (balanced)" },
                { value: "slow", label: "Slow - Better quality" },
                { value: "slower", label: "Slower" },
                { value: "veryslow", label: "Very Slow - Best quality" },
            ];
        }
    })();

    // Debug reactive statement
    $: {
        console.log("[VideoSettings] Current values:", {
            videoCodec: $formData.videoCodec,
            videoBitrate: $formData.videoBitrate,
            preset: $formData.preset,
            hardwareAccel: $formData.hardwareAccel,
            actualEncoder,
            validPresets,
        });
    }

    onMount(async () => {
        // Force a tick to ensure all reactive statements have run
        // This fixes an issue where form values don't populate on first edit
        await tick();

        console.log("[VideoSettings] After tick - formData:", {
            videoCodec: $formData.videoCodec,
            videoBitrate: $formData.videoBitrate,
            preset: $formData.preset,
        });
    });
</script>

<div class="video-settings">
    <h4>📹 Video Settings</h4>

    <div class="settings-grid">
        <!-- Video Codec -->
        <div class="form-group">
            <label for="video-codec">Video Codec</label>
            <select
                id="video-codec"
                bind:value={$formData.videoCodec}
                class="form-control"
            >
                <option value="libx264"
                    >H.264 (libx264) - Most compatible</option
                >
                <option value="libx265"
                    >H.265 (libx265) - Better compression</option
                >

                <option value="libaom-av1">AV1 - Best compression</option>
            </select>
            {#if actualEncoder}
                <small class="encoder-indicator success">
                    ✓ Using hardware encoder: <strong>{actualEncoder}</strong>
                </small>
            {:else if $formData.hardwareAccel && $formData.hardwareAccel !== "none" && $formData.videoCodec}
                <small class="encoder-indicator warning">
                    ⚠ Hardware encoding not available for this codec
                </small>
            {/if}
        </div>

        <!-- Video Bitrate -->
        <div class="form-group">
            <label for="video-bitrate">Video Bitrate</label>
            <input
                id="video-bitrate"
                type="text"
                bind:value={$formData.videoBitrate}
                placeholder="e.g., 2500k, 5M (optional)"
                class="form-control"
            />
        </div>

        <!-- FPS -->
        <div class="form-group">
            <label for="fps">Framerate (FPS)</label>
            <input
                id="fps"
                type="number"
                bind:value={$formData.fps}
                placeholder="e.g., 24, 30, 60 (optional)"
                min="1"
                max="120"
                class="form-control"
            />
        </div>

        <!-- Profile (not available for AV1) -->
        {#if $formData.videoCodec !== "libaom-av1"}
            <div class="form-group">
                <label for="video-profile">Profile</label>
                <select
                    id="video-profile"
                    bind:value={$formData.videoProfile}
                    class="form-control"
                >
                    <option value="">Auto (default)</option>
                    {#if $formData.videoCodec !== "libx265"}
                        <option value="baseline"
                            >Baseline - Widest compatibility</option
                        >
                    {/if}
                    <option value="main">Main - Good balance</option>
                    <option value="high">High - Best quality</option>
                    <option value="main10">Main10 - HDR support</option>
                </select>
            </div>
        {/if}

        <!-- Scale/Resolution -->
        <div class="form-group">
            <label for="scale">Scale/Resolution</label>
            <input
                id="scale"
                type="text"
                bind:value={$formData.scale}
                placeholder="e.g., 1280x720, 1920x1080 (optional)"
                class="form-control"
            />
        </div>

        <!-- Encoding Preset -->
        <div class="form-group">
            <label for="preset">Encoding Preset</label>
            <select
                id="preset"
                bind:value={$formData.preset}
                class="form-control"
            >
                {#each validPresets as preset}
                    <option value={preset.value}>{preset.label}</option>
                {/each}
            </select>
            {#if $formData.videoCodec === "libaom-av1" && $formData.hardwareAccel === "nvenc"}
                <small class="help-text">
                    AV1 NVENC uses performance presets (p1-p7) instead of
                    standard presets
                </small>
            {/if}
        </div>
    </div>

    <!-- Hardware Acceleration -->
    <div class="form-group full-width">
        <label for="hardware-accel">Hardware Acceleration</label>
        <select
            id="hardware-accel"
            bind:value={$formData.hardwareAccel}
            class="form-control"
        >
            <option value="none">None (CPU encoding)</option>
            <option value="nvenc"
                >NVENC (NVIDIA GPU) - Supports H.264, H.265, AV1</option
            >
            <option value="vaapi"
                >VAAPI (Intel/AMD GPU) - Supports H.264, H.265, AV1</option
            >
            <option value="videotoolbox"
                >VideoToolbox (Apple GPU) - Supports H.264, H.265</option
            >
        </select>
        <small class="help-text">
            {#if $formData.hardwareAccel === "nvenc"}
                NVENC automatically converts libx264 → h264_nvenc, libx265 →
                hevc_nvenc, AV1 → av1_nvenc
            {:else if $formData.hardwareAccel === "vaapi"}
                VAAPI automatically converts libx264 → h264_vaapi, libx265 →
                hevc_vaapi, AV1 → av1_vaapi
            {:else if $formData.hardwareAccel === "videotoolbox"}
                VideoToolbox automatically converts libx264 → h264_videotoolbox,
                libx265 → hevc_videotoolbox (AV1 not supported)
            {:else}
                Hardware acceleration requires compatible hardware. Select an
                option to see supported codecs.
            {/if}
        </small>
    </div>

    <!-- Video Filters -->
    <div class="form-group full-width">
        <label for="video-filters">Custom Video Filters</label>
        <input
            id="video-filters"
            type="text"
            bind:value={$formData.videoFilters}
            placeholder="e.g., hqdn3d,unsharp (optional)"
            class="form-control"
        />
        <small class="help-text"> FFmpeg filter syntax (advanced users) </small>
    </div>

    <!-- Video Track Selection -->
    <div class="form-group">
        <label for="video-track-select">Video Track</label>
        <select
            id="video-track-select"
            bind:value={$formData.videoTrackIndex}
            class="form-control"
        >
            <option value="0">Track 0 (first video) - Default</option>
            <option value="1">Track 1 (second video)</option>
            <option value="2">Track 2 (third video)</option>
            <option value="3">Track 3 (fourth video)</option>
        </select>
        <small class="help-text">
            Select which video track to use from multi-track input
        </small>
    </div>
</div>

<style>
    .video-settings {
        margin-bottom: 2rem;
    }

    h4 {
        margin: 0 0 1rem 0;
        color: #2c3e50;
        font-size: 1.1rem;
    }

    .settings-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin-bottom: 1rem;
    }

    .form-group {
        display: flex;
        flex-direction: column;
    }

    .form-group.full-width {
        grid-column: 1 / -1;
    }

    label {
        display: block;
        margin-bottom: 0.5rem;
        font-weight: 500;
        color: #444;
        font-size: 0.9rem;
    }

    .form-control {
        padding: 0.5rem;
        border: 1px solid #ddd;
        border-radius: 4px;
        font-size: 0.9rem;
    }

    .form-control:focus {
        outline: none;
        border-color: #3498db;
        box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
    }

    .help-text {
        display: block;
        margin-top: 0.375rem;
        color: #7f8c8d;
        font-size: 0.8rem;
    }

    .encoder-indicator {
        display: block;
        margin-top: 0.5rem;
        padding: 0.5rem;
        border-radius: 4px;
        font-size: 0.8rem;
    }

    .encoder-indicator.success {
        background-color: #d4edda;
        color: #155724;
        border: 1px solid #c3e6cb;
    }

    .encoder-indicator.warning {
        background-color: #fff3cd;
        color: #856404;
        border: 1px solid #ffeaa7;
    }

    .encoder-indicator strong {
        font-family: "Courier New", monospace;
        font-weight: 600;
    }

    select.form-control {
        cursor: pointer;
    }
</style>

<script>
    /**
     * Output Settings Component
     *
     * Provides tabbed interface for configuring multiple output types:
     * - File Output: Standard file output (default)
     * - HLS Output: HTTP Live Streaming with segmentation
     * - UDP Outputs: Multiple UDP multicast/unicast streams
     * - Additional Files: Extra file outputs with per-output codec overrides
     *
     * User Story 3: Multi-Output Job Creation
     */
    import { formData } from "../../lib/stores/jobFormStore.js";
    // Phase 7: Deleted import (fieldMapper.js removed)
    import { onMount, onDestroy } from "svelte";
    import FileBrowser from "../FileBrowser.svelte";

    // Tab state
    let activeTab = "file"; // 'file', 'hls', 'udp', 'additional'

    // File browser state
    let showFileBrowser = false;
    let fileBrowserTarget = null; // 'outputFile', 'hlsOutputDir', or index for additional outputs

    function openFileBrowser(target) {
        fileBrowserTarget = target;
        showFileBrowser = true;
    }

    function handleFileSelected(path) {
        if (fileBrowserTarget === "outputFile") {
            updateField("outputFile", path);
        } else if (fileBrowserTarget === "hlsOutputDir") {
            updateHLS("output_dir", path);
        } else if (typeof fileBrowserTarget === "number") {
            updateFileOutput(fileBrowserTarget, "output_file", path);
        }
        showFileBrowser = false;
        fileBrowserTarget = null;
    }

    // Listen for job loaded event to auto-switch tabs (Feature: 001-edit-api-simplification)
    function handleJobLoaded(event) {
        const { outputFormat, hasHLS, hasUDP } = event.detail;
        console.log("[OutputSettings] Job loaded event received:", {
            outputFormat,
            hasHLS,
            hasUDP,
        });

        if (hasHLS) {
            activeTab = "hls";
            console.log("[OutputSettings] Switched to HLS tab");
        } else if (hasUDP) {
            activeTab = "udp";
            console.log("[OutputSettings] Switched to UDP tab");
        } else if (event.detail.hasRTMP) {
            activeTab = "rtmp";
            console.log("[OutputSettings] Switched to RTMP tab");
        } else {
            activeTab = "file";
            console.log("[OutputSettings] Switched to File tab");
        }
    }

    onMount(() => {
        window.addEventListener("jobLoaded", handleJobLoaded);

        // Also check current formData state (in case data already loaded)
        if ($formData.hlsOutput) {
            activeTab = "hls";
            console.log(
                "[OutputSettings] onMount: HLS detected, switching tab",
            );
        } else if ($formData.udpOutputs && $formData.udpOutputs.length > 0) {
            activeTab = "udp";
            console.log(
                "[OutputSettings] onMount: UDP detected, switching tab",
            );
        } else if ($formData.rtmpOutputs && $formData.rtmpOutputs.length > 0) {
            activeTab = "rtmp";
            console.log(
                "[OutputSettings] onMount: RTMP detected, switching tab",
            );
        }
    });

    onDestroy(() => {
        window.removeEventListener("jobLoaded", handleJobLoaded);
    });

    // Helper function to update formData
    function updateField(field, value) {
        formData.update((data) => ({
            ...data,
            [field]: value,
        }));
    }

    // HLS Output handlers
    function toggleHLS(enabled) {
        if (enabled) {
            // Default HLS configuration
            const hlsDefaults = {
                output_dir: "/output/hls",
                segment_duration: 6,
                playlist_type: "live",
                playlist_size: 5,
                segment_type: "mpegts",
                playlist_name: "master.m3u8",
                segment_pattern: "segment_%03d.ts",
                abr_enabled: false,
                renditions: [],
            };

            formData.update((data) => ({
                ...data,
                hlsOutput: hlsDefaults,
                outputFile: "", // Clear standard output when HLS is enabled
            }));

            console.log("[hls] Initialized HLS with default configuration");
        } else {
            formData.update((data) => ({
                ...data,
                hlsOutput: null,
            }));
        }
    }

    function updateHLS(field, value) {
        formData.update((data) => ({
            ...data,
            hlsOutput: {
                ...data.hlsOutput,
                [field]: value,
            },
        }));
    }

    // UDP Output handlers
    function addUDPOutput() {
        formData.update((data) => ({
            ...data,
            udpOutputs: [
                ...data.udpOutputs,
                {
                    url: "udp://239.1.1.1:5000?ttl=16&pkt_size=1316",
                    address: "239.1.1.1",
                    port: 5000,
                    ttl: 16,
                    pktSize: 1316,
                },
            ],
            outputFile: "", // Clear standard output when UDP is added
        }));
    }

    function removeUDPOutput(index) {
        formData.update((data) => ({
            ...data,
            udpOutputs: data.udpOutputs.filter((_, i) => i !== index),
        }));
    }

    function updateUDPOutput(index, field, value) {
        formData.update((data) => {
            const updated = [...data.udpOutputs];
            updated[index] = {
                ...updated[index],
                [field]: value,
            };
            // Update URL based on address/port/ttl/pktSize
            if (
                field === "address" ||
                field === "port" ||
                field === "ttl" ||
                field === "pktSize"
            ) {
                const udp = updated[index];
                updated[index].url =
                    `udp://${udp.address}:${udp.port}?ttl=${udp.ttl}&pkt_size=${udp.pktSize}`;
            }
            return {
                ...data,
                udpOutputs: updated,
            };
        });
    }

    // RTMP Output handlers
    function addRTMPOutput() {
        formData.update((data) => ({
            ...data,
            rtmpOutputs: [
                ...(data.rtmpOutputs || []),
                {
                    url: "rtmp://a.rtmp.youtube.com/live2",
                    streamKey: "",
                },
            ],
            outputFile: "", // Clear standard output
        }));
    }

    function removeRTMPOutput(index) {
        formData.update((data) => ({
            ...data,
            rtmpOutputs: (data.rtmpOutputs || []).filter((_, i) => i !== index),
        }));
    }

    function updateRTMPOutput(index, field, value) {
        formData.update((data) => {
            const updated = [...(data.rtmpOutputs || [])];
            updated[index] = {
                ...updated[index],
                [field]: value,
            };
            return {
                ...data,
                rtmpOutputs: updated,
            };
        });
    }

    // Additional File Output handlers
    function addFileOutput() {
        formData.update((data) => ({
            ...data,
            additionalOutputs: [
                ...data.additionalOutputs,
                {
                    output_file: "/output/additional.mp4",
                    video_codec: "",
                    video_bitrate: "",
                    audio_codec: "",
                    audio_bitrate: "",
                    scale: "",
                },
            ],
        }));
    }

    function removeFileOutput(index) {
        formData.update((data) => ({
            ...data,
            additionalOutputs: data.additionalOutputs.filter(
                (_, i) => i !== index,
            ),
        }));
    }

    function updateFileOutput(index, field, value) {
        formData.update((data) => {
            const updated = [...data.additionalOutputs];
            updated[index] = {
                ...updated[index],
                [field]: value,
            };
            return {
                ...data,
                additionalOutputs: updated,
            };
        });
    }
    // Handle tab switching with state updates
    function switchTab(tab) {
        activeTab = tab;

        if (tab === "file") {
            // Switch to File: Clear HLS and UDP
            formData.update((data) => ({
                ...data,
                hlsOutput: null,
                udpOutputs: [],
            }));
            console.log(
                "[OutputSettings] Switched to File: Cleared HLS and UDP",
            );
        } else if (tab === "hls") {
            // Switch to HLS: Clear UDP and File, but DON'T auto-enable HLS
            // This allows the user to view the tab without forcing it on.
            formData.update((data) => ({
                ...data,
                udpOutputs: [],
                outputFile: "",
            }));
            console.log(
                "[OutputSettings] Switched to HLS: Cleared UDP and File",
            );
        } else if (tab === "udp") {
            // Switch to UDP: Clear HLS and File, but DON'T auto-enable UDP
            formData.update((data) => ({
                ...data,
                hlsOutput: null,
                outputFile: "",
            }));
            console.log(
                "[OutputSettings] Switched to UDP: Cleared HLS and File",
            );
            console.log(
                "[OutputSettings] Switched to UDP: Cleared HLS and File",
            );
        } else if (tab === "rtmp") {
            // Switch to RTMP: Clear HLS, UDP, File
            formData.update((data) => ({
                ...data,
                hlsOutput: null,
                udpOutputs: [],
                outputFile: "",
            }));
            console.log(
                "[OutputSettings] Switched to RTMP: Cleared HLS, UDP and File",
            );
        }
        // 'additional' tab doesn't change primary output mode
    }
</script>

<div class="output-settings">
    <h4>📤 Output Settings</h4>

    <!-- Tab Navigation -->
    <div class="tabs">
        <button
            class="tab"
            class:active={activeTab === "file"}
            on:click={() => switchTab("file")}
            type="button"
        >
            Archives File Output
        </button>
        <button
            class="tab"
            class:active={activeTab === "hls"}
            on:click={() => switchTab("hls")}
            type="button"
        >
            HLS Output
        </button>
        <button
            class="tab"
            class:active={activeTab === "udp"}
            on:click={() => switchTab("udp")}
            type="button"
        >
            UDP Outputs ({$formData.udpOutputs.length})
        </button>
        <button
            class="tab"
            class:active={activeTab === "rtmp"}
            on:click={() => switchTab("rtmp")}
            type="button"
        >
            YouTube & Twitch / RTMP ({$formData.rtmpOutputs
                ? $formData.rtmpOutputs.length
                : 0})
        </button>
        <button
            class="tab"
            class:active={activeTab === "additional"}
            on:click={() => (activeTab = "additional")}
            type="button"
        >
            Additional Files ({$formData.additionalOutputs.length})
        </button>
    </div>

    <!-- Tab Content -->
    <div class="tab-content">
        <!-- File Output Tab -->
        {#if activeTab === "file"}
            <div class="tab-panel">
                <p class="help-text">
                    Standard file output. Leave empty for auto-generated path.
                </p>
                <div class="form-group">
                    <label for="output-file">Output File Path</label>
                    <div class="input-with-button">
                        <input
                            id="output-file"
                            type="text"
                            value={$formData.outputFile}
                            on:input={(e) =>
                                updateField("outputFile", e.target.value)}
                            placeholder="/output/encoded.mp4 (optional)"
                            class="form-control"
                            disabled={$formData.hlsOutput !== null ||
                                $formData.udpOutputs.length > 0}
                        />
                        <button
                            type="button"
                            class="btn-browse"
                            on:click={() => openFileBrowser("outputFile")}
                            disabled={$formData.hlsOutput !== null ||
                                $formData.udpOutputs.length > 0}
                        >
                            Browse
                        </button>
                    </div>
                    {#if $formData.hlsOutput || $formData.udpOutputs.length > 0}
                        <small class="help-text warning">
                            ⚠️ Primary output replaced by HLS or UDP. Use
                            "Additional Files" tab for extra file outputs.
                        </small>
                    {/if}
                </div>
            </div>
        {/if}

        <!-- HLS Output Tab -->
        {#if activeTab === "hls"}
            <div class="tab-panel">
                <div class="form-group">
                    <label class="checkbox-label">
                        <input
                            type="checkbox"
                            checked={$formData.hlsOutput !== null}
                            on:change={(e) => toggleHLS(e.target.checked)}
                        />
                        Enable HLS Output
                    </label>
                    <small class="help-text">
                        Generate HTTP Live Streaming playlist and segments
                    </small>
                </div>

                {#if $formData.hlsOutput}
                    <!-- Output Directory with Browse - full width above the grid -->
                    <div class="form-group">
                        <label for="hls-output-dir">Output Directory</label>
                        <div class="input-with-button">
                            <input
                                id="hls-output-dir"
                                type="text"
                                value={$formData.hlsOutput.output_dir}
                                on:input={(e) =>
                                    updateHLS("output_dir", e.target.value)}
                                placeholder="/output/hls"
                                class="form-control"
                            />
                            <button
                                type="button"
                                class="btn-browse"
                                on:click={() => openFileBrowser("hlsOutputDir")}
                            >
                                Browse
                            </button>
                        </div>
                    </div>

                    <div class="settings-grid">
                        <div class="form-group">
                            <label for="hls-playlist-name">Playlist Name</label>
                            <input
                                id="hls-playlist-name"
                                type="text"
                                value={$formData.hlsOutput.playlist_name}
                                on:input={(e) =>
                                    updateHLS("playlist_name", e.target.value)}
                                placeholder="master.m3u8"
                                class="form-control"
                            />
                        </div>

                        <div class="form-group">
                            <label for="hls-segment-duration"
                                >Segment Duration (seconds)</label
                            >
                            <input
                                id="hls-segment-duration"
                                type="number"
                                value={$formData.hlsOutput.segment_duration}
                                on:input={(e) =>
                                    updateHLS(
                                        "segment_duration",
                                        parseInt(e.target.value),
                                    )}
                                min="1"
                                max="30"
                                class="form-control"
                            />
                        </div>

                        <div class="form-group">
                            <label for="hls-playlist-type">Playlist Type</label>
                            <select
                                id="hls-playlist-type"
                                value={$formData.hlsOutput.playlist_type}
                                on:change={(e) =>
                                    updateHLS("playlist_type", e.target.value)}
                                class="form-control"
                            >
                                <option value="vod"
                                    >VOD - Video on Demand</option
                                >
                                <option value="live"
                                    >Live - Rolling window</option
                                >
                                <option value="event"
                                    >Event - Seekable live</option
                                >
                            </select>
                        </div>

                        <div class="form-group">
                            <label for="hls-segment-type">Segment Type</label>
                            <select
                                id="hls-segment-type"
                                value={$formData.hlsOutput.segment_type ||
                                    "mpegts"}
                                on:change={(e) =>
                                    updateHLS("segment_type", e.target.value)}
                                class="form-control"
                            >
                                <option value="mpegts"
                                    >MPEG-TS (Universal, Version 3)</option
                                >
                                <option value="fmp4"
                                    >fMP4 (Required for HEVC/AV1, Version 7)</option
                                >
                            </select>
                            <small class="help-text">
                                HEVC/H.265 and AV1 require fMP4 segments for
                                proper browser support
                            </small>
                        </div>

                        {#if $formData.hlsOutput.playlist_type === "live" || $formData.hlsOutput.playlist_type === "event"}
                            <div class="form-group">
                                <label for="hls-playlist-size"
                                    >Playlist Size (segments)</label
                                >
                                <input
                                    id="hls-playlist-size"
                                    type="number"
                                    value={$formData.hlsOutput.playlist_size}
                                    on:input={(e) =>
                                        updateHLS(
                                            "playlist_size",
                                            parseInt(e.target.value),
                                        )}
                                    min="1"
                                    max="20"
                                    class="form-control"
                                />
                                <small class="help-text">
                                    Number of segments to keep in playlist
                                </small>
                            </div>
                        {/if}

                        <div class="form-group full-width">
                            <label for="hls-segment-pattern"
                                >Segment Filename Pattern</label
                            >
                            <input
                                id="hls-segment-pattern"
                                type="text"
                                value={$formData.hlsOutput.segment_pattern}
                                on:input={(e) =>
                                    updateHLS(
                                        "segment_pattern",
                                        e.target.value,
                                    )}
                                placeholder="segment_%03d.ts"
                                class="form-control"
                            />
                            <small class="help-text">
                                Use %03d for zero-padded numbers (e.g.,
                                segment_001.ts)
                            </small>
                        </div>
                    </div>
                {/if}
            </div>
        {/if}

        <!-- UDP Outputs Tab -->
        {#if activeTab === "udp"}
            <div class="tab-panel">
                <p class="help-text">
                    Stream to UDP destinations (multicast or unicast). Multiple
                    outputs supported.
                </p>

                {#each $formData.udpOutputs as udp, index}
                    <div class="output-item">
                        <div class="output-header">
                            <span class="output-label"
                                >UDP Output {index + 1}</span
                            >
                            <button
                                type="button"
                                class="btn-remove"
                                on:click={() => removeUDPOutput(index)}
                            >
                                Remove
                            </button>
                        </div>

                        <div class="settings-grid">
                            <div class="form-group">
                                <label for="udp-address-{index}">Address</label>
                                <input
                                    id="udp-address-{index}"
                                    type="text"
                                    value={udp.address}
                                    on:input={(e) =>
                                        updateUDPOutput(
                                            index,
                                            "address",
                                            e.target.value,
                                        )}
                                    placeholder="239.1.1.1"
                                    class="form-control"
                                />
                            </div>

                            <div class="form-group">
                                <label for="udp-port-{index}">Port</label>
                                <input
                                    id="udp-port-{index}"
                                    type="number"
                                    value={udp.port}
                                    on:input={(e) =>
                                        updateUDPOutput(
                                            index,
                                            "port",
                                            parseInt(e.target.value),
                                        )}
                                    min="1"
                                    max="65535"
                                    class="form-control"
                                />
                            </div>

                            <div class="form-group">
                                <label for="udp-ttl-{index}">TTL</label>
                                <input
                                    id="udp-ttl-{index}"
                                    type="number"
                                    value={udp.ttl}
                                    on:input={(e) =>
                                        updateUDPOutput(
                                            index,
                                            "ttl",
                                            parseInt(e.target.value),
                                        )}
                                    min="1"
                                    max="255"
                                    class="form-control"
                                />
                            </div>

                            <div class="form-group">
                                <label for="udp-pktsize-{index}"
                                    >Packet Size</label
                                >
                                <input
                                    id="udp-pktsize-{index}"
                                    type="number"
                                    value={udp.pktSize}
                                    on:input={(e) =>
                                        updateUDPOutput(
                                            index,
                                            "pktSize",
                                            parseInt(e.target.value),
                                        )}
                                    min="188"
                                    max="65507"
                                    class="form-control"
                                />
                            </div>

                            <div class="form-group full-width">
                                <span class="label-text">Generated URL</span>
                                <code class="url-display">{udp.url}</code>
                            </div>
                        </div>
                    </div>
                {/each}

                <button type="button" class="btn-add" on:click={addUDPOutput}>
                    + Add UDP Output
                </button>
            </div>
        {/if}

        <!-- RTMP Output Tab -->
        {#if activeTab === "rtmp"}
            <div class="tab-panel">
                <p class="help-text">
                    Stream to YouTube, Twitch, or other RTMP servers.
                </p>

                {#if $formData.rtmpOutputs}
                    {#each $formData.rtmpOutputs as rtmp, index}
                        <div class="output-item">
                            <div class="output-header">
                                <span class="output-label"
                                    >RTMP Output {index + 1}</span
                                >
                                <button
                                    type="button"
                                    class="btn-remove"
                                    on:click={() => removeRTMPOutput(index)}
                                >
                                    Remove
                                </button>
                            </div>

                            <div class="settings-grid">
                                <div class="form-group full-width">
                                    <label for="rtmp-url-{index}"
                                        >Server URL</label
                                    >
                                    <input
                                        id="rtmp-url-{index}"
                                        type="text"
                                        value={rtmp.url}
                                        on:input={(e) =>
                                            updateRTMPOutput(
                                                index,
                                                "url",
                                                e.target.value,
                                            )}
                                        placeholder="rtmp://a.rtmp.youtube.com/live2"
                                        class="form-control"
                                    />
                                </div>

                                <div class="form-group full-width">
                                    <label for="rtmp-key-{index}"
                                        >Stream Key</label
                                    >
                                    <input
                                        id="rtmp-key-{index}"
                                        type="password"
                                        value={rtmp.streamKey}
                                        on:input={(e) =>
                                            updateRTMPOutput(
                                                index,
                                                "streamKey",
                                                e.target.value,
                                            )}
                                        placeholder="abcd-1234-efgh-5678"
                                        class="form-control"
                                    />
                                </div>

                                <div class="form-group full-width">
                                    <span class="label-text">Full RTMP URL</span
                                    >
                                    <code class="url-display">
                                        {rtmp.url}{rtmp.url &&
                                        !rtmp.url.endsWith("/")
                                            ? "/"
                                            : ""}{rtmp.streamKey}
                                    </code>
                                </div>
                            </div>
                        </div>
                    {/each}
                {/if}

                <button type="button" class="btn-add" on:click={addRTMPOutput}>
                    + Add RTMP Output
                </button>
            </div>
        {/if}

        <!-- Additional File Outputs Tab -->
        {#if activeTab === "additional"}
            <div class="tab-panel">
                <p class="help-text">
                    Create additional file outputs with independent
                    codec/bitrate settings.
                </p>

                {#each $formData.additionalOutputs as fileOut, index}
                    <div class="output-item">
                        <div class="output-header">
                            <span class="output-label"
                                >File Output {index + 1}</span
                            >
                            <button
                                type="button"
                                class="btn-remove"
                                on:click={() => removeFileOutput(index)}
                            >
                                Remove
                            </button>
                        </div>

                        <div class="form-group full-width">
                            <label for="file-output-path-{index}"
                                >Output File Path</label
                            >
                            <div class="input-with-button">
                                <input
                                    id="file-output-path-{index}"
                                    type="text"
                                    value={fileOut.output_file}
                                    on:input={(e) =>
                                        updateFileOutput(
                                            index,
                                            "output_file",
                                            e.target.value,
                                        )}
                                    placeholder="/output/additional_{index +
                                        1}.mp4"
                                    class="form-control"
                                />
                                <button
                                    type="button"
                                    class="btn-browse"
                                    on:click={() => openFileBrowser(index)}
                                >
                                    Browse
                                </button>
                            </div>
                        </div>

                        <div class="settings-grid">
                            <div class="form-group">
                                <label for="file-video-codec-{index}"
                                    >Video Codec</label
                                >
                                <select
                                    id="file-video-codec-{index}"
                                    value={fileOut.video_codec}
                                    on:change={(e) =>
                                        updateFileOutput(
                                            index,
                                            "video_codec",
                                            e.target.value,
                                        )}
                                    class="form-control"
                                >
                                    <option value="">Use default</option>
                                    <option value="copy"
                                        >Copy (no re-encode)</option
                                    >
                                    <option value="libx264"
                                        >H.264 (libx264)</option
                                    >
                                    <option value="libx265"
                                        >H.265 (libx265)</option
                                    >
                                    <option value="libvpx-vp9">VP9</option>
                                </select>
                            </div>

                            <div class="form-group">
                                <label for="file-video-bitrate-{index}"
                                    >Video Bitrate</label
                                >
                                <input
                                    id="file-video-bitrate-{index}"
                                    type="text"
                                    value={fileOut.video_bitrate}
                                    on:input={(e) =>
                                        updateFileOutput(
                                            index,
                                            "video_bitrate",
                                            e.target.value,
                                        )}
                                    placeholder="2500k (optional)"
                                    class="form-control"
                                />
                            </div>

                            <div class="form-group">
                                <label for="file-audio-codec-{index}"
                                    >Audio Codec</label
                                >
                                <select
                                    id="file-audio-codec-{index}"
                                    value={fileOut.audio_codec}
                                    on:change={(e) =>
                                        updateFileOutput(
                                            index,
                                            "audio_codec",
                                            e.target.value,
                                        )}
                                    class="form-control"
                                >
                                    <option value="">Use default</option>
                                    <option value="copy"
                                        >Copy (no re-encode)</option
                                    >
                                    <option value="aac">AAC</option>
                                    <option value="mp3">MP3</option>
                                </select>
                            </div>

                            <div class="form-group">
                                <label for="file-audio-bitrate-{index}"
                                    >Audio Bitrate</label
                                >
                                <input
                                    id="file-audio-bitrate-{index}"
                                    type="text"
                                    value={fileOut.audio_bitrate}
                                    on:input={(e) =>
                                        updateFileOutput(
                                            index,
                                            "audio_bitrate",
                                            e.target.value,
                                        )}
                                    placeholder="128k (optional)"
                                    class="form-control"
                                />
                            </div>

                            <div class="form-group full-width">
                                <label for="file-scale-{index}"
                                    >Scale/Resolution</label
                                >
                                <input
                                    id="file-scale-{index}"
                                    type="text"
                                    value={fileOut.scale}
                                    on:input={(e) =>
                                        updateFileOutput(
                                            index,
                                            "scale",
                                            e.target.value,
                                        )}
                                    placeholder="1280:720 (optional)"
                                    class="form-control"
                                />
                            </div>
                        </div>
                    </div>
                {/each}

                <button type="button" class="btn-add" on:click={addFileOutput}>
                    + Add File Output
                </button>
            </div>
        {/if}
    </div>
</div>

<!-- File Browser Modal (directory mode for output paths) -->
<FileBrowser
    bind:isOpen={showFileBrowser}
    onSelect={handleFileSelected}
    mode="directory"
/>

<style>
    /* Input with Browse button */
    .input-with-button {
        display: flex;
        gap: 0.5rem;
    }

    .input-with-button .form-control {
        flex: 1;
    }

    .btn-browse {
        padding: 0.625rem 1.125rem;
        border: 1px solid #3b82f6;
        border-radius: 8px;
        background-color: #fff;
        color: #3b82f6;
        font-weight: 600;
        cursor: pointer;
        font-size: 0.9rem;
        transition: all 0.2s ease;
        white-space: nowrap;
    }

    .btn-browse:hover:not(:disabled) {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: #fff;
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
    }

    .btn-browse:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }
    .output-settings {
        margin-bottom: 2rem;
    }

    h4 {
        margin: 0 0 1.25rem 0;
        color: #1e293b;
        font-size: 1.1rem;
        font-weight: 600;
    }

    /* Tab Navigation */
    .tabs {
        display: flex;
        gap: 0.375rem;
        border-bottom: 2px solid #e2e8f0;
        margin-bottom: 1.25rem;
    }

    .tab {
        padding: 0.875rem 1.25rem;
        border: none;
        background: transparent;
        color: #64748b;
        font-weight: 600;
        cursor: pointer;
        border-bottom: 3px solid transparent;
        margin-bottom: -2px;
        transition: all 0.2s;
        font-size: 0.9rem;
        border-radius: 8px 8px 0 0;
    }

    .tab:hover {
        color: #1e293b;
        background-color: #f8fafc;
    }

    .tab.active {
        color: #3b82f6;
        border-bottom-color: #3b82f6;
        background: white;
    }

    /* Tab Content */
    .tab-content {
        min-height: 200px;
    }

    .tab-panel {
        animation: fadeIn 0.25s ease;
    }

    @keyframes fadeIn {
        from {
            opacity: 0;
            transform: translateY(4px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* Form Elements */
    .form-group {
        display: flex;
        flex-direction: column;
        margin-bottom: 1.125rem;
    }

    .form-group.full-width {
        grid-column: 1 / -1;
    }

    .settings-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1.125rem;
        margin-bottom: 1.125rem;
    }

    label,
    .label-text {
        display: block;
        margin-bottom: 0.5rem;
        font-weight: 500;
        color: #1e293b;
        font-size: 0.9rem;
    }

    .checkbox-label {
        display: flex;
        align-items: center;
        gap: 0.625rem;
        cursor: pointer;
        font-weight: 500;
        padding: 0.5rem 0.625rem;
        border-radius: 6px;
        transition: background 0.15s;
    }

    .checkbox-label:hover {
        background: #f8fafc;
    }

    .checkbox-label input[type="checkbox"] {
        width: 1.125rem;
        height: 1.125rem;
        margin: 0;
        accent-color: #3b82f6;
    }

    .form-control {
        padding: 0.625rem 0.875rem;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        font-size: 0.9rem;
        background: #f8fafc;
        transition: all 0.2s;
    }

    .form-control:hover {
        border-color: #cbd5e1;
    }

    .form-control:focus {
        outline: none;
        border-color: #3b82f6;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        background: white;
    }

    .form-control:disabled {
        background-color: #f1f5f9;
        color: #94a3b8;
        cursor: not-allowed;
    }

    .help-text {
        display: block;
        margin-top: 0.5rem;
        color: #64748b;
        font-size: 0.8rem;
        line-height: 1.4;
    }

    .help-text.warning {
        color: #f59e0b;
        font-weight: 500;
    }

    /* Output Items */
    .output-item {
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        transition: all 0.2s;
    }

    .output-item:hover {
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
    }

    .output-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1.125rem;
        padding-bottom: 0.875rem;
        border-bottom: 1px solid #e2e8f0;
    }

    .output-label {
        font-weight: 600;
        color: #1e293b;
        font-size: 0.95rem;
    }

    .url-display {
        display: block;
        padding: 0.625rem 0.875rem;
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        font-family: "SF Mono", "Fira Code", monospace;
        font-size: 0.85rem;
        color: #3b82f6;
        word-break: break-all;
    }

    /* Buttons */
    .btn-add {
        padding: 0.75rem 1.125rem;
        border: 2px dashed #3b82f6;
        border-radius: 10px;
        background-color: transparent;
        color: #3b82f6;
        font-weight: 600;
        cursor: pointer;
        width: 100%;
        transition: all 0.2s;
        font-size: 0.9rem;
    }

    .btn-add:hover {
        background-color: #eff6ff;
        border-style: solid;
        transform: translateY(-1px);
    }

    .btn-remove {
        padding: 0.5rem 0.875rem;
        border: 1px solid #fecaca;
        border-radius: 8px;
        background-color: #fef2f2;
        color: #dc2626;
        font-weight: 600;
        cursor: pointer;
        font-size: 0.85rem;
        transition: all 0.2s;
    }

    .btn-remove:hover {
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        color: #fff;
        border-color: transparent;
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
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

    @media (max-width: 768px) {
        .tabs {
            flex-wrap: wrap;
        }

        .tab {
            font-size: 0.8rem;
            padding: 0.625rem 0.875rem;
        }

        .settings-grid {
            grid-template-columns: 1fr;
        }
    }
</style>

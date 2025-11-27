<script>
    /**
     * Advanced Options Expandable Panel
     *
     * Provides an expandable panel containing advanced encoding options:
     * - Video settings (codec, bitrate, fps, profile, scale, filters, hwaccel, preset)
     * - Audio settings (codec, bitrate, channels)
     * - Output settings (HLS, UDP, additional file outputs)
     *
     * User Story 2: Advanced Encoding Customization
     * User Story 3: Multi-Output Job Creation
     */
    import { slide } from 'svelte/transition';
    import VideoSettings from './VideoSettings.svelte';
    import AudioSettings from './AudioSettings.svelte';
    import OutputSettings from './OutputSettings.svelte';

    // Expandable state - always start expanded
    import { formData } from '../../lib/stores/jobFormStore.js';
    import { onMount } from 'svelte';

    // Always start expanded
    let isExpanded = true;

    function toggleExpanded() {
        isExpanded = !isExpanded;
    }

    // Reactive: check if ABR is enabled
    $: abrEnabled = $formData.abrEnabled;

    // Reactive: check if device input is enabled
    $: isDeviceInput = $formData.inputFormat && $formData.inputFormat !== '';
</script>

<div class="advanced-options" class:abr-mode={abrEnabled}>
    <button
        type="button"
        class="expand-toggle"
        on:click={toggleExpanded}
        aria-expanded={isExpanded}
    >
        <span class="icon">{isExpanded ? '▼' : '▶'}</span>
        <span class="title">Advanced Options</span>
        {#if abrEnabled && !isDeviceInput}
            <span class="subtitle notice">
                Video/Audio in ABR section - Output settings below
            </span>
        {:else if isDeviceInput}
            <span class="subtitle notice">
                Device input mode - encoding settings required
            </span>
        {:else}
            <span class="subtitle">
                {isExpanded ? 'Hide' : 'Show'} video/audio/output settings
            </span>
        {/if}
    </button>

    {#if isExpanded}
        <div class="options-content" transition:slide>
            <div class="options-inner">
                {#if !abrEnabled || isDeviceInput}
                    <!-- Video Settings Section (always shown when ABR is disabled OR device input is enabled) -->
                    <VideoSettings />

                    <!-- Divider -->
                    <div class="divider"></div>

                    <!-- Audio Settings Section (always shown when ABR is disabled OR device input is enabled) -->
                    <AudioSettings />

                    <!-- Divider -->
                    <div class="divider"></div>
                {:else}
                    <!-- Info message when ABR is enabled and NOT using device input -->
                    <div class="info-message">
                        <p>
                            <strong>ℹ️ Video and Audio Settings</strong>
                        </p>
                        <p>
                            Video and audio encoding settings are configured in the ABR section above when Adaptive Bitrate is enabled.
                        </p>
                    </div>

                    <!-- Divider -->
                    <div class="divider"></div>
                {/if}

                <!-- Output Settings Section (User Story 3) - ALWAYS AVAILABLE -->
                <OutputSettings />
            </div>
        </div>
    {/if}
</div>

<style>
    .advanced-options {
        margin: 1.5rem 0;
        border: 1px solid #e1e4e8;
        border-radius: 6px;
        background-color: #fff;
    }

    .advanced-options.abr-mode {
        border-color: #3498db;
        background-color: #f8f9fa;
    }

    .expand-toggle {
        width: 100%;
        padding: 1rem 1.25rem;
        border: none;
        background-color: transparent;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 0.75rem;
        text-align: left;
        transition: background-color 0.2s;
    }

    .expand-toggle:hover {
        background-color: #f6f8fa;
    }

    .expand-toggle:focus {
        outline: none;
        box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
    }


    .icon {
        font-size: 0.75rem;
        color: #586069;
        flex-shrink: 0;
        transition: transform 0.2s;
    }

    .title {
        font-weight: 600;
        color: #24292e;
        font-size: 1rem;
        flex-shrink: 0;
    }

    .subtitle {
        color: #586069;
        font-size: 0.875rem;
        margin-left: auto;
    }

    .subtitle.notice {
        color: #3498db;
        font-weight: 500;
    }

    .options-content {
        border-top: 1px solid #e1e4e8;
        padding: 1.5rem 1.25rem;
        background-color: #fafbfc;
    }

    .options-inner {
        max-width: 100%;
    }

    .divider {
        height: 1px;
        background-color: #e1e4e8;
        margin: 2rem 0;
    }

    .info-message {
        padding: 1rem;
        background-color: #e7f3ff;
        border: 1px solid #3498db;
        border-left: 4px solid #3498db;
        border-radius: 6px;
        color: #2c3e50;
        margin-bottom: 1rem;
    }

    .info-message p {
        margin: 0.5rem 0;
    }

    .info-message p:first-child {
        margin-top: 0;
    }

    .info-message p:last-child {
        margin-bottom: 0;
    }

    .info-message strong {
        color: #3498db;
    }
</style>

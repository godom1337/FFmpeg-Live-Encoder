<script>
    /**
     * Audio Encoding Settings Component
     *
     * Provides controls for advanced audio encoding parameters:
     * - Codec selection
     * - Bitrate
     * - Channels
     *
     * User Story 2: Advanced Encoding Customization
     */
    import { formData } from '../../lib/stores/jobFormStore.js';
    import { onMount, tick } from 'svelte';

    // Helper function to update individual fields
    function updateField(field, value) {
        formData.update(data => ({
            ...data,
            [field]: value
        }));
    }

    // Reactive: check if device input is enabled
    $: isDeviceInput = $formData.inputFormat && $formData.inputFormat !== '';

    // Reactive: if device input is enabled and audio codec is "copy", auto-switch to AAC
    $: {
        if (isDeviceInput && $formData.audioCodec === 'copy') {
            console.log('[AudioSettings] Device input detected, switching from copy to aac');
            updateField('audioCodec', 'aac');
            if (!$formData.audioBitrate) {
                updateField('audioBitrate', '128k');
            }
        }
    }

    // Debug reactive statement
    $: {
        console.log('[AudioSettings] Current values:', {
            audioCodec: $formData.audioCodec,
            audioBitrate: $formData.audioBitrate,
            audioChannels: $formData.audioChannels,
            isDeviceInput
        });
    }

    onMount(async () => {
        await tick();

        console.log('[AudioSettings] After tick - formData:', {
            audioCodec: $formData.audioCodec,
            audioBitrate: $formData.audioBitrate,
            audioChannels: $formData.audioChannels
        });
    });
</script>

<div class="audio-settings">
    <h4>🎵 Audio Settings</h4>

    <div class="settings-grid">
        <!-- Audio Codec -->
        <div class="form-group">
            <label for="audio-codec">Audio Codec</label>
            <select
                id="audio-codec"
                bind:value={$formData.audioCodec}
                class="form-control"
                disabled={$formData.audioTrackIndex == -1 || $formData.audioTrackIndex === '-1'}
            >
                {#if !isDeviceInput}
                    <option value="copy">Copy (no re-encode)</option>
                {/if}
                <option value="aac">AAC - Most compatible</option>
                <option value="libopus">Opus - Best quality/bitrate</option>
                <option value="libmp3lame">MP3 - Legacy compatibility</option>
            </select>
            <small class="help-text">
                {#if $formData.audioTrackIndex == -1 || $formData.audioTrackIndex === '-1'}
                    N/A when audio is disabled
                {:else if isDeviceInput}
                    Device input requires audio encoding (copy not available)
                {:else}
                    Use "Copy" for fastest encoding (no audio re-encoding)
                {/if}
            </small>
        </div>

        <!-- Audio Bitrate -->
        <div class="form-group">
            <label for="audio-bitrate">Audio Bitrate</label>
            <input
                id="audio-bitrate"
                type="text"
                bind:value={$formData.audioBitrate}
                placeholder="e.g., 128k, 192k, 256k (optional)"
                class="form-control"
                disabled={$formData.audioTrackIndex == -1 || $formData.audioTrackIndex === '-1' || $formData.audioCodec === 'copy'}
            />
            <small class="help-text">
                {($formData.audioTrackIndex == -1 || $formData.audioTrackIndex === '-1') ? 'N/A when audio is disabled' : $formData.audioCodec === 'copy' ? 'N/A when copying audio' : 'Higher = better quality, larger file'}
            </small>
        </div>

        <!-- Audio Channels -->
        <div class="form-group">
            <label for="audio-channels">Audio Channels</label>
            <select
                id="audio-channels"
                bind:value={$formData.audioChannels}
                class="form-control"
                disabled={$formData.audioTrackIndex == -1 || $formData.audioTrackIndex === '-1' || $formData.audioCodec === 'copy'}
            >
                <option value="">Auto (default)</option>
                <option value="1">Mono (1)</option>
                <option value="2">Stereo (2)</option>
                <option value="6">5.1 Surround (6)</option>
                <option value="8">7.1 Surround (8)</option>
            </select>
            <small class="help-text">
                {($formData.audioTrackIndex == -1 || $formData.audioTrackIndex === '-1') ? 'N/A when audio is disabled' : $formData.audioCodec === 'copy' ? 'N/A when copying audio' : 'Channel configuration'}
            </small>
        </div>

        <!-- Audio Volume -->
        <div class="form-group">
            <label for="audio-volume">Volume Level</label>
            <input
                id="audio-volume"
                type="number"
                bind:value={$formData.audioVolume}
                min="0"
                max="100"
                placeholder="100 (normal)"
                class="form-control"
                disabled={$formData.audioTrackIndex == -1 || $formData.audioTrackIndex === '-1' || $formData.audioCodec === 'copy'}
            />
            <small class="help-text">
                {($formData.audioTrackIndex == -1 || $formData.audioTrackIndex === '-1') ? 'N/A when audio is disabled' : $formData.audioCodec === 'copy' ? 'N/A when copying audio' : '0-100, where 100 is normal volume'}
            </small>
        </div>
    </div>

    <!-- Audio Track Selection -->
    <div class="form-group">
        <label for="audio-track-select">Audio Track</label>
        <select
            id="audio-track-select"
            bind:value={$formData.audioTrackIndex}
            class="form-control"
        >
            <option value="-1">Disable (no audio)</option>
            <option value="0">Track 0 (first audio) - Default</option>
            <option value="1">Track 1 (second audio)</option>
            <option value="2">Track 2 (third audio)</option>
            <option value="3">Track 3 (fourth audio)</option>
            <option value="4">Track 4 (fifth audio)</option>
            <option value="5">Track 5 (sixth audio)</option>
        </select>
        <small class="help-text">
            Select which audio track to use from multi-track input or disable audio entirely
        </small>
    </div>
</div>

<style>
    .audio-settings {
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
    }

    .form-group {
        display: flex;
        flex-direction: column;
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

    .form-control:disabled {
        background-color: #f5f5f5;
        cursor: not-allowed;
        opacity: 0.6;
    }

    .help-text {
        display: block;
        margin-top: 0.375rem;
        color: #7f8c8d;
        font-size: 0.8rem;
    }

    select.form-control {
        cursor: pointer;
    }

    select.form-control:disabled {
        cursor: not-allowed;
    }
</style>

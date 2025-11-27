<script>
    /**
     * ABR Preset Selector Component
     *
     * Dropdown for selecting ABR bitrate ladder presets:
     * - Standard (1080p, 720p, 480p)
     * - High Quality (1080p, 720p, 540p, 360p)
     * - Mobile Optimized (720p, 480p, 360p, 240p)
     * - Custom (user-defined ladder)
     *
     * User Story 1: Enable ABR for HLS Output
     */
    import { formData, loadABRPreset, getABRPresets } from '../../lib/stores/jobFormStore.js';

    const presets = getABRPresets();

    // Handle preset selection
    function handlePresetChange(event) {
        const selectedPreset = event.target.value;

        if (selectedPreset === 'custom') {
            // Custom ladder - don't load preset, let user configure manually
            formData.update(data => ({
                ...data,
                abrPreset: 'custom'
                // Keep existing abrLadder for editing
            }));
        } else {
            // Load preset renditions
            loadABRPreset(selectedPreset);
        }
    }
</script>

<div class="abr-preset-selector">
    <label for="abr-preset">Bitrate Ladder Preset</label>
    <select
        id="abr-preset"
        bind:value={$formData.abrPreset}
        on:change={handlePresetChange}
        class="form-control"
    >
        <option value="standard">Standard - {presets.standard.description}</option>
        <option value="high_quality">High Quality - {presets.high_quality.description}</option>
        <option value="mobile_optimized">Mobile Optimized - {presets.mobile_optimized.description}</option>
        <option value="custom">Custom - Define your own ladder</option>
    </select>

    <!-- Show rendition summary -->
    {#if $formData.abrPreset && $formData.abrPreset !== 'custom'}
        <small class="help-text">
            {#if $formData.abrLadder && $formData.abrLadder.length > 0}
                {$formData.abrLadder.length} variants: {$formData.abrLadder.map(r => r.name).join(', ')}
            {/if}
        </small>
    {/if}
</div>

<style>
    .abr-preset-selector {
        margin-bottom: 1rem;
    }

    label {
        display: block;
        margin-bottom: 0.25rem;
        font-weight: 600;
        color: #34495e;
    }

    .form-control {
        width: 100%;
        padding: 0.5rem;
        border: 1px solid #ddd;
        border-radius: 4px;
        font-size: 0.9rem;
    }

    .form-control:focus {
        outline: none;
        border-color: #3498db;
        box-shadow: 0 0 0 2px rgba(52, 152, 219, 0.1);
    }

    .help-text {
        display: block;
        margin-top: 0.25rem;
        font-size: 0.8rem;
        color: #7f8c8d;
    }
</style>

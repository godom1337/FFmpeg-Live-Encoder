<script>
    /**
     * Custom Bitrate Ladder Editor
     *
     * Allows users to manually configure ABR variants with custom:
     * - Name (e.g., "1080p", "720p-custom")
     * - Resolution (e.g., "1920x1080")
     * - Video bitrate (e.g., "5M", "3000k")
     * - Video codec (h264, h265, av1)
     * - Audio bitrate (e.g., "128k")
     *
     * User Story 2: Configure Custom Bitrate Ladder
     */
    import { formData } from '../../lib/stores/jobFormStore.js';

    // Add new rendition
    function addRendition() {
        formData.update(data => ({
            ...data,
            abrLadder: [
                ...data.abrLadder,
                {
                    name: `variant-${data.abrLadder.length + 1}`,
                    videoBitrate: '2M',
                    videoResolution: '1280x720',
                    // Video codec inherited from main Video Settings
                    videoProfile: 'main',
                    audioBitrate: '128k',
                    // Audio codec inherited from main Audio Settings
                    audioChannels: 2,
                    audioSampleRate: 48000,
                    preset: 'medium'
                }
            ]
        }));
    }

    // Remove rendition by index
    function removeRendition(index) {
        formData.update(data => ({
            ...data,
            abrLadder: data.abrLadder.filter((_, i) => i !== index)
        }));
    }

    // Update specific rendition field
    function updateRendition(index, field, value) {
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

    // Validation errors
    let validationErrors = [];

    // Validate ladder
    function validateLadder() {
        validationErrors = [];

        if (!$formData.abrLadder || $formData.abrLadder.length === 0) {
            return;
        }

        // Check minimum renditions
        if ($formData.abrLadder.length < 2) {
            validationErrors.push('ABR requires at least 2 renditions');
        }

        // Check maximum renditions
        if ($formData.abrLadder.length > 6) {
            validationErrors.push('Maximum 6 renditions supported');
        }

        // Check for duplicate resolutions
        const resolutions = $formData.abrLadder.map(r => r.videoResolution);
        const uniqueResolutions = new Set(resolutions);
        if (resolutions.length !== uniqueResolutions.size) {
            validationErrors.push('Duplicate resolutions not allowed');
        }

        // Check for duplicate names
        const names = $formData.abrLadder.map(r => r.name);
        const uniqueNames = new Set(names);
        if (names.length !== uniqueNames.size) {
            validationErrors.push('Duplicate variant names not allowed');
        }

        return validationErrors.length === 0;
    }

    // Validate on changes
    $: if ($formData.abrLadder) {
        validateLadder();
    }
</script>

<div class="custom-ladder-editor">
    <div class="editor-header">
        <h5>Custom Bitrate Ladder</h5>
        <button type="button" on:click={addRendition} class="btn-add">
            + Add Variant
        </button>
    </div>

    {#if validationErrors.length > 0}
        <div class="validation-errors">
            {#each validationErrors as error}
                <div class="error-message">⚠️ {error}</div>
            {/each}
        </div>
    {/if}

    <div class="renditions-list">
        {#each $formData.abrLadder as rendition, index}
            <div class="rendition-card">
                <div class="rendition-header">
                    <span class="rendition-number">Variant {index + 1}</span>
                    <button
                        type="button"
                        on:click={() => removeRendition(index)}
                        class="btn-remove"
                        title="Remove this variant"
                    >
                        ✕
                    </button>
                </div>

                <div class="rendition-fields">
                    <!-- Name -->
                    <div class="field-group">
                        <label for="rendition-name-{index}">Name</label>
                        <input
                            id="rendition-name-{index}"
                            type="text"
                            bind:value={rendition.name}
                            on:input={(e) => updateRendition(index, 'name', e.target.value)}
                            placeholder="e.g., 1080p, 720p-custom"
                            class="form-input small"
                        />
                    </div>

                    <!-- Resolution -->
                    <div class="field-group">
                        <label for="rendition-resolution-{index}">Resolution</label>
                        <input
                            id="rendition-resolution-{index}"
                            type="text"
                            bind:value={rendition.videoResolution}
                            on:input={(e) => updateRendition(index, 'videoResolution', e.target.value)}
                            placeholder="e.g., 1920x1080"
                            class="form-input small"
                        />
                    </div>

                    <!-- Video Bitrate -->
                    <div class="field-group">
                        <label for="rendition-video-bitrate-{index}">Video Bitrate</label>
                        <input
                            id="rendition-video-bitrate-{index}"
                            type="text"
                            bind:value={rendition.videoBitrate}
                            on:input={(e) => updateRendition(index, 'videoBitrate', e.target.value)}
                            placeholder="e.g., 5M, 3000k"
                            class="form-input small"
                        />
                    </div>

                    <!-- Video Profile -->
                    <div class="field-group">
                        <label for="rendition-profile-{index}">Profile</label>
                        <select
                            id="rendition-profile-{index}"
                            bind:value={rendition.videoProfile}
                            on:change={(e) => updateRendition(index, 'videoProfile', e.target.value)}
                            class="form-input small"
                        >
                            <option value="">Default</option>
                            <option value="baseline">Baseline</option>
                            <option value="main">Main</option>
                            <option value="high">High</option>
                        </select>
                    </div>

                    <!-- Audio Bitrate -->
                    <div class="field-group">
                        <label for="rendition-audio-bitrate-{index}">Audio Bitrate</label>
                        <input
                            id="rendition-audio-bitrate-{index}"
                            type="text"
                            bind:value={rendition.audioBitrate}
                            on:input={(e) => updateRendition(index, 'audioBitrate', e.target.value)}
                            placeholder="e.g., 128k"
                            class="form-input small"
                        />
                    </div>
                </div>
            </div>
        {/each}

        {#if $formData.abrLadder.length === 0}
            <div class="empty-state">
                <p>No variants configured</p>
                <button type="button" on:click={addRendition} class="btn-add-large">
                    + Add First Variant
                </button>
            </div>
        {/if}
    </div>
</div>

<style>
    .custom-ladder-editor {
        margin-top: 1rem;
        padding: 1rem;
        background-color: white;
        border: 1px solid #ddd;
        border-radius: 4px;
    }

    .editor-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 2px solid #e9ecef;
    }

    h5 {
        margin: 0;
        font-size: 1rem;
        color: #2c3e50;
        font-weight: 600;
    }

    .btn-add {
        padding: 0.375rem 0.75rem;
        background-color: #3498db;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 0.875rem;
        font-weight: 500;
    }

    .btn-add:hover {
        background-color: #2980b9;
    }

    .validation-errors {
        margin-bottom: 1rem;
        padding: 0.75rem;
        background-color: #fff3cd;
        border: 1px solid #ffc107;
        border-radius: 4px;
    }

    .error-message {
        color: #856404;
        font-size: 0.875rem;
        margin: 0.25rem 0;
    }

    .renditions-list {
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }

    .rendition-card {
        padding: 1rem;
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 4px;
    }

    .rendition-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.75rem;
    }

    .rendition-number {
        font-weight: 600;
        color: #495057;
        font-size: 0.9rem;
    }

    .btn-remove {
        padding: 0.25rem 0.5rem;
        background-color: #dc3545;
        color: white;
        border: none;
        border-radius: 3px;
        cursor: pointer;
        font-size: 0.875rem;
    }

    .btn-remove:hover {
        background-color: #c82333;
    }

    .rendition-fields {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 0.75rem;
    }

    .field-group {
        display: flex;
        flex-direction: column;
    }

    .field-group label {
        display: block;
        margin-bottom: 0.25rem;
        font-size: 0.8rem;
        font-weight: 600;
        color: #495057;
    }

    .form-input {
        padding: 0.375rem 0.5rem;
        border: 1px solid #ced4da;
        border-radius: 3px;
        font-size: 0.875rem;
    }

    .form-input:focus {
        outline: none;
        border-color: #3498db;
        box-shadow: 0 0 0 2px rgba(52, 152, 219, 0.1);
    }

    .form-input.small {
        width: 100%;
    }

    .empty-state {
        padding: 2rem;
        text-align: center;
        color: #6c757d;
    }

    .empty-state p {
        margin-bottom: 1rem;
    }

    .btn-add-large {
        padding: 0.5rem 1.5rem;
        background-color: #3498db;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 0.95rem;
        font-weight: 500;
    }

    .btn-add-large:hover {
        background-color: #2980b9;
    }
</style>

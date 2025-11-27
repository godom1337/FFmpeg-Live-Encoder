<script>
    export let renditions = [];
    export let abrEnabled = false;
    export let outputType = 'hls';
    export let onRenditionsChange = null;

    function addRendition() {
        const newRendition = {
            name: `${renditions.length === 0 ? '720p' : '480p'}`,
            video_bitrate: renditions.length === 0 ? '3M' : '1.5M',
            video_resolution: renditions.length === 0 ? '1280x720' : '854x480',
            video_framerate: 30,
            video_codec: 'h264',
            video_profile: 'main',
            audio_codec: 'aac',
            audio_bitrate: '128k',
            audio_channels: 2,
            audio_sample_rate: 48000,
            preset: 'medium'
        };

        // Add output_url field for UDP/RTMP/SRT outputs
        if (outputType !== 'hls') {
            newRendition.output_url = '';
        }

        renditions = [...renditions, newRendition];
        notifyChange();
    }

    function removeRendition(index) {
        renditions = renditions.filter((_, i) => i !== index);
        notifyChange();
    }

    function updateRendition(index, field, value) {
        // Create a new object to ensure reactivity
        const updatedRendition = { ...renditions[index], [field]: value };

        // If changing to AV1 codec, clear the profile
        if (field === 'video_codec' && value === 'av1') {
            updatedRendition.video_profile = null;
        }

        // Create a new array with the updated rendition
        renditions = renditions.map((r, i) => i === index ? updatedRendition : r);
        notifyChange();
    }

    function notifyChange() {
        if (onRenditionsChange) {
            onRenditionsChange(renditions);
        }
    }

    const resolutionPresets = [
        { label: '4K (3840x2160)', value: '3840x2160' },
        { label: '1080p (1920x1080)', value: '1920x1080' },
        { label: '720p (1280x720)', value: '1280x720' },
        { label: '480p (854x480)', value: '854x480' },
        { label: '360p (640x360)', value: '640x360' }
    ];

    const bitratePresets = {
        video: ['8M', '5M', '3M', '2M', '1.5M', '1M', '800k', '500k'],
        audio: ['320k', '192k', '128k', '96k', '64k']
    };

    const profilePresets = ['baseline', 'main', 'high'];
    const codecPresets = [
        { value: 'h264', label: 'H.264 / AVC' },
        { value: 'h265', label: 'H.265 / HEVC' },
        { value: 'av1', label: 'AV1' }
    ];
    const audioCodecPresets = ['copy', 'aac', 'mp3', 'opus'];
    const presetSpeeds = ['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow'];
</script>

<div class="track-configuration">
    <div class="section-header">
        <h3>Track Configuration {#if abrEnabled}(ABR Mode){/if}</h3>
        <button type="button" class="btn btn-add" on:click={addRendition}>
            + Add Rendition
        </button>
    </div>

    {#if renditions.length === 0}
        <div class="empty-state">
            <p>No renditions configured. Click "Add Rendition" to create output tracks.</p>
        </div>
    {:else}
        <div class="renditions-list">
            {#each renditions as rendition, index}
                <div class="rendition-card">
                    <div class="rendition-header">
                        <input
                            type="text"
                            class="rendition-name"
                            bind:value={rendition.name}
                            on:input={() => updateRendition(index, 'name', rendition.name)}
                            placeholder="Rendition name"
                        />
                        <button type="button" class="btn-remove" on:click={() => removeRendition(index)} title="Remove rendition">
                            ×
                        </button>
                    </div>

                    {#if outputType !== 'hls'}
                        <div class="output-url-field">
                            <label>Output URL *</label>
                            <input
                                type="text"
                                class="output-url-input"
                                bind:value={rendition.output_url}
                                on:input={() => updateRendition(index, 'output_url', rendition.output_url)}
                                placeholder={outputType === 'udp' ? 'udp://224.1.1.1:5000' : (outputType === 'rtmp' ? 'rtmp://server.com/live/key' : 'srt://server.com:9000')}
                                required
                            />
                            <p class="field-hint">
                                {#if outputType === 'udp'}
                                    Each rendition streams to its own UDP destination. Use multicast (224.x.x.x - 239.x.x.x) or unicast addresses.
                                {:else if outputType === 'rtmp'}
                                    Each rendition streams to its own RTMP destination URL.
                                {:else if outputType === 'srt'}
                                    Each rendition streams to its own SRT destination.
                                {/if}
                            </p>
                        </div>
                    {/if}

                    <div class="rendition-config">
                        <!-- Video Settings -->
                        <div class="config-section">
                            <h4>Video Settings</h4>
                            <div class="form-grid">
                                <div class="form-group">
                                    <label>Resolution</label>
                                    <select bind:value={rendition.video_resolution} on:change={() => updateRendition(index, 'video_resolution', rendition.video_resolution)}>
                                        {#each resolutionPresets as preset}
                                            <option value={preset.value}>{preset.label}</option>
                                        {/each}
                                    </select>
                                </div>

                                <div class="form-group">
                                    <label>Bitrate</label>
                                    <select bind:value={rendition.video_bitrate} on:change={() => updateRendition(index, 'video_bitrate', rendition.video_bitrate)}>
                                        {#each bitratePresets.video as bitrate}
                                            <option value={bitrate}>{bitrate}</option>
                                        {/each}
                                    </select>
                                </div>

                                <div class="form-group">
                                    <label>Frame Rate</label>
                                    <input
                                        type="number"
                                        bind:value={rendition.video_framerate}
                                        on:input={() => updateRendition(index, 'video_framerate', rendition.video_framerate)}
                                        min="1"
                                        max="120"
                                    />
                                </div>

                                <div class="form-group">
                                    <label>Codec</label>
                                    <select bind:value={rendition.video_codec} on:change={() => updateRendition(index, 'video_codec', rendition.video_codec)}>
                                        {#each codecPresets as codec}
                                            <option value={codec.value}>{codec.label}</option>
                                        {/each}
                                    </select>
                                </div>

                                {#if rendition.video_codec && rendition.video_codec !== 'av1'}
                                <div class="form-group">
                                    <label>Profile</label>
                                    <select bind:value={rendition.video_profile} on:change={() => updateRendition(index, 'video_profile', rendition.video_profile)}>
                                        {#each profilePresets as profile}
                                            <option value={profile}>{profile}</option>
                                        {/each}
                                    </select>
                                </div>
                                {/if}

                                <div class="form-group">
                                    <label>Preset Speed</label>
                                    <select bind:value={rendition.preset} on:change={() => updateRendition(index, 'preset', rendition.preset)}>
                                        {#each presetSpeeds as preset}
                                            <option value={preset}>{preset}</option>
                                        {/each}
                                    </select>
                                </div>
                            </div>
                        </div>

                        <!-- Audio Settings -->
                        <div class="config-section">
                            <h4>Audio Settings</h4>
                            <div class="form-grid">
                                <div class="form-group">
                                    <label>Codec</label>
                                    <select bind:value={rendition.audio_codec} on:change={() => updateRendition(index, 'audio_codec', rendition.audio_codec)}>
                                        {#each audioCodecPresets as codec}
                                            <option value={codec}>{codec}</option>
                                        {/each}
                                    </select>
                                </div>

                                <div class="form-group">
                                    <label>Bitrate</label>
                                    <select bind:value={rendition.audio_bitrate} on:change={() => updateRendition(index, 'audio_bitrate', rendition.audio_bitrate)}>
                                        {#each bitratePresets.audio as bitrate}
                                            <option value={bitrate}>{bitrate}</option>
                                        {/each}
                                    </select>
                                </div>

                                <div class="form-group">
                                    <label>Channels</label>
                                    <select bind:value={rendition.audio_channels} on:change={() => updateRendition(index, 'audio_channels', rendition.audio_channels)}>
                                        <option value={1}>Mono</option>
                                        <option value={2}>Stereo</option>
                                        <option value={6}>5.1</option>
                                    </select>
                                </div>

                                <div class="form-group">
                                    <label>Sample Rate</label>
                                    <select bind:value={rendition.audio_sample_rate} on:change={() => updateRendition(index, 'audio_sample_rate', rendition.audio_sample_rate)}>
                                        <option value={44100}>44.1 kHz</option>
                                        <option value={48000}>48 kHz</option>
                                        <option value={96000}>96 kHz</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            {/each}
        </div>
    {/if}
</div>

<style>
    .track-configuration {
        margin: 20px 0;
    }

    .section-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
    }

    .section-header h3 {
        margin: 0;
        font-size: 16px;
        font-weight: 600;
    }

    .btn-add {
        padding: 8px 16px;
        background: #28a745;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
    }

    .btn-add:hover {
        background: #218838;
    }

    .empty-state {
        padding: 40px 20px;
        text-align: center;
        background: #f9f9f9;
        border: 1px dashed #ddd;
        border-radius: 4px;
        color: #666;
    }

    .renditions-list {
        display: flex;
        flex-direction: column;
        gap: 16px;
    }

    .rendition-card {
        border: 1px solid #ddd;
        border-radius: 4px;
        padding: 16px;
        background: #fff;
    }

    .rendition-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid #e0e0e0;
    }

    .rendition-name {
        font-size: 16px;
        font-weight: 600;
        border: 1px solid #ddd;
        padding: 6px 12px;
        border-radius: 4px;
        flex: 1;
        max-width: 300px;
    }

    .btn-remove {
        width: 32px;
        height: 32px;
        background: #dc3545;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 20px;
        line-height: 1;
    }

    .btn-remove:hover {
        background: #c82333;
    }

    .rendition-config {
        display: flex;
        flex-direction: column;
        gap: 16px;
    }

    .config-section h4 {
        margin: 0 0 12px 0;
        font-size: 14px;
        font-weight: 600;
        color: #555;
    }

    .form-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 12px;
    }

    .form-group {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .form-group label {
        font-size: 13px;
        font-weight: 500;
        color: #555;
    }

    .form-group input,
    .form-group select {
        padding: 8px;
        border: 1px solid #ddd;
        border-radius: 4px;
        font-size: 14px;
    }

    .form-group input:focus,
    .form-group select:focus {
        outline: none;
        border-color: #007bff;
    }

    .output-url-field {
        padding: 12px;
        background: #f0f8ff;
        border-left: 3px solid #007bff;
        border-radius: 4px;
        margin-bottom: 12px;
    }

    .output-url-field label {
        display: block;
        margin-bottom: 6px;
        font-size: 13px;
        font-weight: 500;
        color: #333;
    }

    .output-url-input {
        width: 100%;
        padding: 8px 12px;
        border: 1px solid #ddd;
        border-radius: 4px;
        font-size: 14px;
        font-family: monospace;
    }

    .output-url-input:focus {
        outline: none;
        border-color: #007bff;
    }

    .field-hint {
        margin: 6px 0 0 0;
        font-size: 12px;
        color: #666;
        font-style: italic;
    }
</style>

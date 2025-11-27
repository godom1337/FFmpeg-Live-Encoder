<script>
    /**
     * ABR Audio Settings Component
     *
     * Audio encoding settings specifically for ABR mode.
     * Replaces AudioSettings when ABR is enabled.
     *
     * Provides controls for:
     * - Codec selection (applies to all renditions)
     * - Channels
     * - Volume
     * - Audio track selection
     *
     * Note: Audio bitrate is configured per-rendition in the ABR ladder.
     */
    import { formData } from '../../lib/stores/jobFormStore.js';
</script>

<div class="abr-audio-settings">
    <h4>🎵 Audio Settings (ABR Mode)</h4>
    <small class="abr-note">
        Audio codec applies to all ABR renditions. Audio bitrate is configured per-rendition in the ladder.
    </small>

    <div class="settings-grid">
        <!-- Audio Codec -->
        <div class="form-group">
            <label for="abr-audio-codec">Audio Codec (All Renditions)</label>
            <select
                id="abr-audio-codec"
                bind:value={$formData.audioCodec}
                class="form-control"
                disabled={$formData.audioTrackIndex == -1 || $formData.audioTrackIndex === '-1'}
            >
                <option value="copy">Copy (no re-encode)</option>
                <option value="aac">AAC - Most compatible</option>
                <option value="libopus">Opus - Best quality/bitrate</option>
                <option value="libmp3lame">MP3 - Legacy compatibility</option>
            </select>
            <small class="help-text">
                {($formData.audioTrackIndex == -1 || $formData.audioTrackIndex === '-1') ? 'N/A when audio is disabled' : 'Use "Copy" for fastest encoding (no audio re-encoding)'}
            </small>
        </div>

        <!-- Audio Channels -->
        <div class="form-group">
            <label for="abr-audio-channels">Audio Channels</label>
            <select
                id="abr-audio-channels"
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
                {($formData.audioTrackIndex == -1 || $formData.audioTrackIndex === '-1') ? 'N/A when audio is disabled' : $formData.audioCodec === 'copy' ? 'N/A when copying audio' : 'Applies to all renditions'}
            </small>
        </div>

        <!-- Audio Volume -->
        <div class="form-group">
            <label for="abr-audio-volume">Volume Level</label>
            <input
                id="abr-audio-volume"
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

        <!-- Audio Track Selection -->
        <div class="form-group">
            <label for="abr-audio-track">Audio Track</label>
            <select
                id="abr-audio-track"
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
</div>

<style>
    .abr-audio-settings {
        margin-bottom: 1.5rem;
        padding: 1rem;
        background-color: #f8f9fa;
        border-radius: 6px;
        border: 1px solid #e1e4e8;
    }

    h4 {
        margin: 0 0 0.5rem 0;
        color: #2c3e50;
        font-size: 1.05rem;
    }

    .abr-note {
        display: block;
        margin-bottom: 1rem;
        padding: 0.75rem;
        background-color: #fff4e6;
        border-left: 3px solid #f39c12;
        color: #2c3e50;
        font-size: 0.85rem;
        border-radius: 4px;
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
        background-color: #fff;
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

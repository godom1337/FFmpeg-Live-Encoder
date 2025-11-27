<script>
    import { analysisApi } from '../services/api.js';
    import { formData } from '../lib/stores/jobFormStore.js';

    export let inputUrl = '';
    export let inputType = '';
    export let onAnalysisComplete = null;

    let analyzing = false;
    let analysisResult = null;
    let analysisError = null;
    let expanded = true;

    async function analyzeInput() {
        if (!inputUrl) {
            analysisError = 'Please enter an input URL';
            return;
        }

        analyzing = true;
        analysisError = null;
        analysisResult = null;

        try {
            const result = await analysisApi.analyzeInput(inputUrl, inputType || null, 15);

            if (result.error) {
                analysisError = result.error;
            } else {
                analysisResult = result;
                if (onAnalysisComplete) {
                    onAnalysisComplete(result);
                }
            }
        } catch (error) {
            analysisError = error.message || 'Failed to analyze input';
        } finally {
            analyzing = false;
        }
    }

    function formatBitrate(bitrate) {
        if (!bitrate) return 'N/A';
        const num = parseInt(bitrate);
        if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
        if (num >= 1000) return `${(num / 1000).toFixed(0)}k`;
        return `${num}`;
    }

    function formatDuration(seconds) {
        if (!seconds) return 'N/A';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    function formatSize(bytes) {
        if (!bytes) return 'N/A';
        const mb = bytes / (1024 * 1024);
        if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`;
        return `${mb.toFixed(2)} MB`;
    }

    $: canAnalyze = inputUrl && !analyzing;
</script>

<div class="input-analysis-section">
    <div class="section-header" on:click={() => expanded = !expanded} on:keydown={(e) => e.key === 'Enter' && (expanded = !expanded)} role="button" tabindex="0">
        <h3>
            <span class="icon">{expanded ? '▼' : '▶'}</span>
            Input Analysis
        </h3>
        {#if !analysisResult && !analysisError}
            <button
                class="btn btn-analyze"
                on:click|stopPropagation={analyzeInput}
                disabled={!canAnalyze}
            >
                {analyzing ? 'Analyzing...' : 'Analyze Input'}
            </button>
        {/if}
    </div>

    {#if expanded}
        <div class="section-content">
            {#if analyzing}
                <div class="analyzing">
                    <div class="spinner"></div>
                    <p>Analyzing input with ffprobe...</p>
                </div>
            {/if}

            {#if analysisError}
                <div class="error">
                    <strong>Analysis Failed:</strong> {analysisError}
                    <button class="btn-retry" on:click={analyzeInput}>Retry</button>
                </div>
            {/if}

            {#if analysisResult}
                <div class="analysis-results">
                    <!-- Format Information -->
                    <div class="info-section">
                        <h4>Format Information</h4>
                        <div class="info-grid">
                            <div class="info-item">
                                <span class="label">Format:</span>
                                <span class="value">{analysisResult.format_long_name || analysisResult.format_name || 'Unknown'}</span>
                            </div>
                            {#if analysisResult.duration}
                                <div class="info-item">
                                    <span class="label">Duration:</span>
                                    <span class="value">{formatDuration(analysisResult.duration)}</span>
                                </div>
                            {/if}
                            {#if analysisResult.size}
                                <div class="info-item">
                                    <span class="label">Size:</span>
                                    <span class="value">{formatSize(analysisResult.size)}</span>
                                </div>
                            {/if}
                            {#if analysisResult.bit_rate}
                                <div class="info-item">
                                    <span class="label">Bitrate:</span>
                                    <span class="value">{formatBitrate(analysisResult.bit_rate)}</span>
                                </div>
                            {/if}
                        </div>
                    </div>

                    <!-- Video Streams -->
                    {#if analysisResult.video_streams && analysisResult.video_streams.length > 0}
                        <div class="streams-section">
                            <h4>Video Streams ({analysisResult.video_streams.length})</h4>
                            {#each analysisResult.video_streams as stream, idx}
                                <div class="stream-card video-stream">
                                    <div class="stream-header">
                                        <span class="stream-index">Stream #{stream.index} (0:v:{idx})</span>
                                        <span class="stream-codec">{stream.codec_long_name || stream.codec_name}</span>
                                    </div>
                                    <div class="stream-details">
                                        <div class="detail-row">
                                            <span class="label">Resolution:</span>
                                            <span class="value">{stream.resolution}</span>
                                        </div>
                                        <div class="detail-row">
                                            <span class="label">Frame Rate:</span>
                                            <span class="value">{stream.fps ? `${stream.fps} fps` : 'N/A'}</span>
                                        </div>
                                        {#if stream.profile}
                                            <div class="detail-row">
                                                <span class="label">Profile:</span>
                                                <span class="value">{stream.profile}</span>
                                            </div>
                                        {/if}
                                        {#if stream.bit_rate}
                                            <div class="detail-row">
                                                <span class="label">Bitrate:</span>
                                                <span class="value">{formatBitrate(stream.bit_rate)}</span>
                                            </div>
                                        {/if}
                                        {#if stream.pix_fmt}
                                            <div class="detail-row">
                                                <span class="label">Pixel Format:</span>
                                                <span class="value">{stream.pix_fmt}</span>
                                            </div>
                                        {/if}
                                    </div>
                                </div>
                            {/each}
                        </div>
                    {/if}

                    <!-- Audio Streams -->
                    {#if analysisResult.audio_streams && analysisResult.audio_streams.length > 0}
                        <div class="streams-section">
                            <h4>Audio Streams ({analysisResult.audio_streams.length})</h4>
                            {#each analysisResult.audio_streams as stream, idx}
                                <div class="stream-card audio-stream">
                                    <div class="stream-header">
                                        <div class="stream-title">
                                            <span class="stream-index">Stream #{stream.index} (0:a:{stream.audio_index || idx})</span>
                                            {#if stream.language}
                                                <span class="language-badge">{stream.language.toUpperCase()}</span>
                                            {/if}
                                            {#if stream.title}
                                                <span class="title-badge">{stream.title}</span>
                                            {/if}
                                        </div>
                                        <span class="stream-codec">{stream.codec_long_name || stream.codec_name}</span>
                                    </div>
                                    <div class="stream-details">
                                        <div class="detail-row">
                                            <span class="label">Channels:</span>
                                            <span class="value">{stream.channels} ({stream.channel_layout || 'Unknown'})</span>
                                        </div>
                                        <div class="detail-row">
                                            <span class="label">Sample Rate:</span>
                                            <span class="value">{stream.sample_rate} Hz</span>
                                        </div>
                                        {#if stream.bit_rate}
                                            <div class="detail-row">
                                                <span class="label">Bitrate:</span>
                                                <span class="value">{formatBitrate(stream.bit_rate)}</span>
                                            </div>
                                        {/if}
                                    </div>
                                </div>
                            {/each}
                        </div>
                    {/if}

                    <!-- Subtitle Streams -->
                    {#if analysisResult.subtitle_streams && analysisResult.subtitle_streams.length > 0}
                        <div class="streams-section">
                            <h4>Subtitle Streams ({analysisResult.subtitle_streams.length})</h4>
                            {#each analysisResult.subtitle_streams as stream, idx}
                                <div class="stream-card subtitle-stream">
                                    <div class="stream-header">
                                        <span class="stream-index">Stream #{stream.index} (0:s:{idx})</span>
                                        <span class="stream-codec">{stream.codec_name}</span>
                                    </div>
                                    {#if stream.language || stream.title}
                                        <div class="stream-details">
                                            {#if stream.language}
                                                <div class="detail-row">
                                                    <span class="label">Language:</span>
                                                    <span class="value">{stream.language}</span>
                                                </div>
                                            {/if}
                                            {#if stream.title}
                                                <div class="detail-row">
                                                    <span class="label">Title:</span>
                                                    <span class="value">{stream.title}</span>
                                                </div>
                                            {/if}
                                        </div>
                                    {/if}
                                </div>
                            {/each}
                        </div>
                    {/if}

                    <button class="btn btn-reanalyze" on:click={analyzeInput}>
                        Re-analyze
                    </button>
                </div>
            {/if}

            {#if !analyzing && !analysisResult && !analysisError}
                <div class="empty-state">
                    <p>Enter an input URL above and click "Analyze Input" to view stream details.</p>
                </div>
            {/if}
        </div>
    {/if}
</div>

<style>
    .input-analysis-section {
        border: 1px solid #ddd;
        border-radius: 4px;
        margin: 20px 0;
        background: #f9f9f9;
    }

    .section-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 16px;
        background: #fff;
        border-bottom: 1px solid #ddd;
        cursor: pointer;
        user-select: none;
    }

    .section-header h3 {
        margin: 0;
        font-size: 16px;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .icon {
        font-size: 12px;
        color: #666;
    }

    .section-content {
        padding: 16px;
    }

    .btn-analyze {
        padding: 6px 16px;
        background: #007bff;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
    }

    .btn-analyze:hover:not(:disabled) {
        background: #0056b3;
    }

    .btn-analyze:disabled {
        background: #ccc;
        cursor: not-allowed;
    }

    .analyzing {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 20px;
        background: #fff;
        border-radius: 4px;
    }

    .spinner {
        width: 20px;
        height: 20px;
        border: 3px solid #f3f3f3;
        border-top: 3px solid #007bff;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    .error {
        padding: 12px;
        background: #fff3cd;
        border: 1px solid #ffc107;
        border-radius: 4px;
        color: #856404;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .btn-retry {
        padding: 4px 12px;
        background: #ffc107;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 13px;
    }

    .analysis-results {
        background: #fff;
        border-radius: 4px;
        padding: 16px;
    }

    .info-section, .streams-section {
        margin-bottom: 20px;
    }

    .info-section h4, .streams-section h4 {
        margin: 0 0 12px 0;
        font-size: 14px;
        font-weight: 600;
        color: #333;
    }

    .info-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 12px;
    }

    .info-item {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .info-item .label {
        font-size: 12px;
        color: #666;
        font-weight: 500;
    }

    .info-item .value {
        font-size: 14px;
        color: #333;
    }

    .stream-card {
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        padding: 12px;
        margin-bottom: 12px;
    }

    .video-stream {
        border-left: 3px solid #007bff;
    }

    .audio-stream {
        border-left: 3px solid #28a745;
    }

    .subtitle-stream {
        border-left: 3px solid #ffc107;
    }

    .stream-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 8px;
    }

    .stream-title {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        align-items: center;
    }

    .stream-index {
        font-size: 12px;
        font-weight: 600;
        color: #666;
    }

    .language-badge {
        font-size: 10px;
        font-weight: 600;
        padding: 2px 6px;
        background: #007bff;
        color: white;
        border-radius: 3px;
    }

    .title-badge {
        font-size: 10px;
        font-weight: 500;
        padding: 2px 6px;
        background: #6c757d;
        color: white;
        border-radius: 3px;
    }

    .stream-codec {
        font-size: 12px;
        color: #333;
    }

    .stream-details {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 8px;
    }

    .detail-row {
        display: flex;
        gap: 8px;
        font-size: 13px;
    }

    .detail-row .label {
        color: #666;
        font-weight: 500;
        min-width: 100px;
    }

    .detail-row .value {
        color: #333;
    }

    .btn-reanalyze {
        margin-top: 16px;
        padding: 8px 16px;
        background: #6c757d;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
    }

    .btn-reanalyze:hover {
        background: #5a6268;
    }

    .empty-state {
        padding: 40px 20px;
        text-align: center;
        color: #666;
    }

    .empty-state p {
        margin: 0;
        font-size: 14px;
    }
</style>

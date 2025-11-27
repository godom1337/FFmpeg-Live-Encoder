<script>
    /**
     * ABR Preview Panel
     *
     * Shows real-time estimates for ABR configuration:
     * - Total bandwidth (all variants combined)
     * - Storage per hour
     * - Per-variant details on hover
     * - Warnings for non-standard configurations
     *
     * User Story 3: Preview ABR Configuration
     */
    import { formData } from '../../lib/stores/jobFormStore.js';
    import {
        estimateStoragePerHour,
        bitrateToBps,
        isStandardResolution,
        getDeviceProfile,
        formatBitrate
    } from '../../lib/utils/abrCalculations.js';

    // Reactive calculations
    $: estimates = estimateStoragePerHour($formData.abrLadder || []);

    $: variantDetails = ($formData.abrLadder || []).map(r => ({
        name: r.name,
        resolution: r.videoResolution,
        videoBitrate: formatBitrate(r.videoBitrate),
        audioBitrate: formatBitrate(r.audioBitrate || '128k'),
        totalBitrate: formatBitrate(`${bitrateToBps(r.videoBitrate) + bitrateToBps(r.audioBitrate || '128k')}`),
        isStandard: isStandardResolution(r.videoResolution),
        deviceProfile: getDeviceProfile(r.videoResolution),
        profile: r.videoProfile || 'main'
    }));

    let hoveredVariant = null;
</script>

<div class="abr-preview-panel">
    <div class="preview-header">
        <h5>📊 Configuration Preview</h5>
    </div>

    <div class="preview-stats">
        <!-- Total Bandwidth -->
        <div class="stat-card">
            <div class="stat-label">Total Bandwidth</div>
            <div class="stat-value">{estimates.megabitsPerSecond} Mbps</div>
            <div class="stat-hint">Combined all variants</div>
        </div>

        <!-- Storage per Hour -->
        <div class="stat-card">
            <div class="stat-label">Storage / Hour</div>
            <div class="stat-value">{estimates.storagePerHour}</div>
            <div class="stat-hint">Disk space required</div>
        </div>

        <!-- Variant Count -->
        <div class="stat-card">
            <div class="stat-label">Quality Variants</div>
            <div class="stat-value">{$formData.abrLadder?.length || 0}</div>
            <div class="stat-hint">Adaptive levels</div>
        </div>
    </div>

    <!-- Variant Details Table -->
    {#if $formData.abrLadder && $formData.abrLadder.length > 0}
        <div class="variants-table">
            <table>
                <thead>
                    <tr>
                        <th>Variant</th>
                        <th>Resolution</th>
                        <th>Video</th>
                        <th>Audio</th>
                        <th>Total</th>
                        <th>Profile</th>
                    </tr>
                </thead>
                <tbody>
                    {#each variantDetails as variant, index}
                        <tr
                            on:mouseenter={() => hoveredVariant = index}
                            on:mouseleave={() => hoveredVariant = null}
                            class:hovered={hoveredVariant === index}
                        >
                            <td class="variant-name">
                                {variant.name}
                                {#if !variant.isStandard}
                                    <span class="warning-badge" title="Non-standard resolution">⚠️</span>
                                {/if}
                            </td>
                            <td>{variant.resolution}</td>
                            <td>{variant.videoBitrate}</td>
                            <td>{variant.audioBitrate}</td>
                            <td><strong>{variant.totalBitrate}</strong></td>
                            <td>{variant.profile}</td>
                        </tr>

                        <!-- Tooltip on hover -->
                        {#if hoveredVariant === index}
                            <tr class="tooltip-row">
                                <td colspan="6">
                                    <div class="variant-tooltip">
                                        <div><strong>Target Devices:</strong> {variant.deviceProfile}</div>
                                        <div><strong>Codec:</strong> {$formData.videoCodec || 'h264'}
                                            {#if $formData.hardwareAccel && $formData.hardwareAccel !== 'none'}
                                                ({$formData.hardwareAccel})
                                            {/if}
                                        </div>
                                        <div><strong>Encoding Preset:</strong> {$formData.preset || 'medium'}</div>
                                        {#if !variant.isStandard}
                                            <div class="warning-text">
                                                ⚠️ Non-standard resolution may not align with common device capabilities
                                            </div>
                                        {/if}
                                    </div>
                                </td>
                            </tr>
                        {/if}
                    {/each}
                </tbody>
            </table>
        </div>
    {/if}
</div>

<style>
    .abr-preview-panel {
        margin-top: 1rem;
        padding: 1rem;
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 4px;
    }

    .preview-header {
        margin-bottom: 1rem;
    }

    .preview-header h5 {
        margin: 0;
        font-size: 1rem;
        color: #2c3e50;
        font-weight: 600;
    }

    .preview-stats {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 1rem;
        margin-bottom: 1.5rem;
    }

    .stat-card {
        padding: 1rem;
        background-color: white;
        border: 1px solid #dee2e6;
        border-radius: 4px;
        text-align: center;
    }

    .stat-label {
        font-size: 0.75rem;
        color: #6c757d;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 0.5rem;
    }

    .stat-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #3498db;
        margin-bottom: 0.25rem;
    }

    .stat-hint {
        font-size: 0.7rem;
        color: #868e96;
    }

    .variants-table {
        background-color: white;
        border-radius: 4px;
        overflow: hidden;
    }

    table {
        width: 100%;
        border-collapse: collapse;
    }

    thead {
        background-color: #e9ecef;
    }

    th {
        padding: 0.75rem 0.5rem;
        text-align: left;
        font-size: 0.8rem;
        font-weight: 600;
        color: #495057;
        border-bottom: 2px solid #dee2e6;
    }

    tbody tr {
        border-bottom: 1px solid #e9ecef;
        transition: background-color 0.15s;
    }

    tbody tr:hover {
        background-color: #f8f9fa;
    }

    tbody tr.hovered {
        background-color: #e7f3ff;
    }

    td {
        padding: 0.625rem 0.5rem;
        font-size: 0.85rem;
        color: #495057;
    }

    .variant-name {
        font-weight: 600;
        color: #2c3e50;
    }

    .warning-badge {
        margin-left: 0.25rem;
        font-size: 0.75rem;
        cursor: help;
    }

    .tooltip-row {
        background-color: #e7f3ff !important;
        border-bottom: 2px solid #3498db;
    }

    .variant-tooltip {
        padding: 0.75rem;
        font-size: 0.8rem;
        line-height: 1.6;
    }

    .variant-tooltip > div {
        margin: 0.25rem 0;
    }

    .warning-text {
        margin-top: 0.5rem;
        padding: 0.5rem;
        background-color: #fff3cd;
        color: #856404;
        border-radius: 3px;
        font-size: 0.75rem;
    }
</style>

<script>
    /**
     * Validation Warnings Component
     * 
     * Displays validation warnings and errors from the job validation API.
     * Shows hardware acceleration incompatibilities, FFmpeg errors, etc.
     * 
     * User Story 2 & 6: Advanced customization + Command preview and validation
     */
    export let warnings = [];
    export let isValidating = false;

    // Group warnings by severity
    $: errors = warnings.filter(w => w.severity === 'error');
    $: warningMessages = warnings.filter(w => w.severity === 'warning');
    $: infoMessages = warnings.filter(w => w.severity === 'info');

    // Icon for each severity level
    function getIcon(severity) {
        switch (severity) {
            case 'error': return '❌';
            case 'warning': return '⚠️';
            case 'info': return 'ℹ️';
            default: return '';
        }
    }

    // Color class for each severity level
    function getSeverityClass(severity) {
        switch (severity) {
            case 'error': return 'alert-error';
            case 'warning': return 'alert-warning';
            case 'info': return 'alert-info';
            default: return 'alert-info';
        }
    }
</script>

<div class="validation-warnings">
    {#if isValidating}
        <div class="alert alert-info">
            <span class="spinner"></span>
            <span>Validating job configuration...</span>
        </div>
    {:else if warnings.length > 0}
        <div class="warnings-container">
            <!-- Errors -->
            {#each errors as error}
                <div class="alert {getSeverityClass(error.severity)}">
                    <span class="icon">{getIcon(error.severity)}</span>
                    <div class="message-content">
                        <strong class="message-title">Error: {error.code}</strong>
                        <p class="message-text">{error.message}</p>
                    </div>
                </div>
            {/each}

            <!-- Warnings -->
            {#each warningMessages as warning}
                <div class="alert {getSeverityClass(warning.severity)}">
                    <span class="icon">{getIcon(warning.severity)}</span>
                    <div class="message-content">
                        <strong class="message-title">Warning: {warning.code}</strong>
                        <p class="message-text">{warning.message}</p>
                    </div>
                </div>
            {/each}

            <!-- Info messages -->
            {#each infoMessages as info}
                <div class="alert {getSeverityClass(info.severity)}">
                    <span class="icon">{getIcon(info.severity)}</span>
                    <div class="message-content">
                        <strong class="message-title">Info: {info.code}</strong>
                        <p class="message-text">{info.message}</p>
                    </div>
                </div>
            {/each}
        </div>
    {/if}
</div>

<style>
    .validation-warnings {
        margin: 1rem 0;
    }

    .warnings-container {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
    }

    .alert {
        display: flex;
        align-items: flex-start;
        gap: 0.75rem;
        padding: 0.875rem 1rem;
        border-radius: 6px;
        border: 1px solid;
        font-size: 0.9rem;
    }

    .alert-error {
        background-color: #fee;
        border-color: #fcc;
        color: #c33;
    }

    .alert-warning {
        background-color: #fff4e5;
        border-color: #ffe0b2;
        color: #e65100;
    }

    .alert-info {
        background-color: #e3f2fd;
        border-color: #bbdefb;
        color: #1565c0;
    }

    .icon {
        font-size: 1.2rem;
        flex-shrink: 0;
        line-height: 1;
    }

    .message-content {
        flex: 1;
    }

    .message-title {
        display: block;
        font-weight: 600;
        margin-bottom: 0.25rem;
        text-transform: capitalize;
    }

    .message-text {
        margin: 0;
        line-height: 1.5;
    }

    .spinner {
        display: inline-block;
        width: 1rem;
        height: 1rem;
        border: 2px solid rgba(0, 0, 0, 0.1);
        border-top-color: #1565c0;
        border-radius: 50%;
        animation: spin 0.6s linear infinite;
    }

    @keyframes spin {
        to {
            transform: rotate(360deg);
        }
    }

    /* Responsive adjustments */
    @media (max-width: 600px) {
        .alert {
            flex-direction: column;
            gap: 0.5rem;
        }

        .icon {
            font-size: 1rem;
        }
    }
</style>

<script>
    /**
     * Template Selector Component
     *
     * Allows users to quickly apply predefined encoding templates.
     * Templates provide sensible defaults for common encoding scenarios.
     */
    import { onMount } from 'svelte';
    import { jobApi } from '../../services/api.js';

    export let onTemplateSelected = () => {};

    let templates = [];
    let selectedTemplateId = '';
    let isLoading = false;
    let error = null;

    // Fetch templates on mount
    onMount(async () => {
        await loadTemplates();
    });

    async function loadTemplates() {
        isLoading = true;
        error = null;

        try {
            const response = await jobApi.getTemplates();
            templates = response.templates || [];
        } catch (err) {
            console.error('Failed to load templates:', err);
            error = 'Failed to load templates';
        } finally {
            isLoading = false;
        }
    }

    async function handleTemplateChange() {
        if (!selectedTemplateId) {
            // Clear template (user selected "None")
            onTemplateSelected(null);
            return;
        }

        try {
            // Fetch full template details
            const template = await jobApi.getTemplate(selectedTemplateId);
            onTemplateSelected(template);
        } catch (err) {
            console.error('Failed to load template details:', err);
            error = 'Failed to load template details';
        }
    }
</script>

<div class="template-selector">
    <div class="form-group">
        <label for="template">
            📋 Encoding Template
            <span class="optional">(optional)</span>
        </label>

        {#if isLoading}
            <div class="loading">Loading templates...</div>
        {:else if error}
            <div class="error">{error}</div>
        {:else}
            <select
                id="template"
                bind:value={selectedTemplateId}
                on:change={handleTemplateChange}
                class="form-control"
            >
                <option value="">None (Custom Configuration)</option>
                {#each templates as template}
                    <option value={template.id}>
                        {template.name}
                    </option>
                {/each}
            </select>

            {#if selectedTemplateId}
                {@const selected = templates.find(t => t.id === selectedTemplateId)}
                {#if selected}
                    <div class="template-info">
                        <div class="description">{selected.description}</div>
                        <div class="recommended-use">
                            <strong>Best for:</strong> {selected.recommended_use}
                        </div>
                        {#if selected.tags && selected.tags.length > 0}
                            <div class="tags">
                                {#each selected.tags as tag}
                                    <span class="tag">{tag}</span>
                                {/each}
                            </div>
                        {/if}
                    </div>
                {/if}
            {:else}
                <small class="help-text">
                    Select a template to quickly apply common encoding settings.
                    You can still override individual settings after selecting a template.
                </small>
            {/if}
        {/if}
    </div>
</div>

<style>
    .template-selector {
        margin-bottom: 1.5rem;
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
        font-size: 0.95rem;
    }

    .optional {
        color: #7f8c8d;
        font-weight: normal;
        font-size: 0.9rem;
    }

    .form-control {
        padding: 0.75rem;
        border: 1px solid #ddd;
        border-radius: 4px;
        font-size: 0.95rem;
        background-color: white;
        cursor: pointer;
    }

    .form-control:focus {
        outline: none;
        border-color: #3498db;
        box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
    }

    .loading {
        padding: 0.75rem;
        color: #7f8c8d;
        font-style: italic;
    }

    .error {
        padding: 0.75rem;
        color: #e74c3c;
        background: #fadbd8;
        border: 1px solid #e74c3c;
        border-radius: 4px;
    }

    .help-text {
        display: block;
        margin-top: 0.5rem;
        color: #7f8c8d;
        font-size: 0.85rem;
        line-height: 1.4;
    }

    .template-info {
        margin-top: 1rem;
        padding: 1rem;
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 4px;
    }

    .description {
        margin-bottom: 0.75rem;
        color: #495057;
        font-size: 0.9rem;
        line-height: 1.4;
    }

    .recommended-use {
        margin-bottom: 0.75rem;
        color: #6c757d;
        font-size: 0.85rem;
    }

    .recommended-use strong {
        color: #495057;
    }

    .tags {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 0.5rem;
    }

    .tag {
        display: inline-block;
        padding: 0.25rem 0.5rem;
        background: #e9ecef;
        border: 1px solid #dee2e6;
        border-radius: 3px;
        font-size: 0.75rem;
        color: #6c757d;
    }
</style>

<script>
    /**
     * Simple File Browser Component
     * Allows users to browse and select files or directories
     *
     * Props:
     * - isOpen: boolean - controls modal visibility
     * - onSelect: function - callback when file/directory is selected
     * - mode: 'file' | 'directory' - selection mode (default: 'file')
     */
    import { onMount } from 'svelte';

    export let isOpen = false;
    export let onSelect = null;
    export let mode = 'file';  // 'file' or 'directory'

    let files = [];
    let currentDirectory = null;  // Will be set by backend based on environment
    let loading = false;
    let error = null;

    // Get modal title based on mode
    $: modalTitle = mode === 'directory' ? 'Select Directory' : 'Select Input File';

    async function loadFiles() {
        loading = true;
        error = null;
        try {
            // If no directory set yet, let the backend determine the default
            const url = currentDirectory
                ? `/api/v1/jobs/browse/files?directory=${encodeURIComponent(currentDirectory)}`
                : `/api/v1/jobs/browse/files`;
            console.log('Loading files from:', url);

            const response = await fetch(url);
            console.log('Response status:', response.status);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail?.message || `HTTP ${response.status}: Failed to load files`);
            }

            const data = await response.json();
            console.log('Loaded files:', data);
            files = data.files || [];
            // Update currentDirectory from response (backend tells us where we are)
            if (data.directory) {
                currentDirectory = data.directory;
            }
        } catch (err) {
            console.error('Error loading files:', err);
            error = err.message;
            files = [];
        } finally {
            loading = false;
        }
    }

    function selectFile(file) {
        if (file.type === 'directory') {
            if (mode === 'directory') {
                // In directory mode, single click navigates, need explicit select button
                currentDirectory = file.path;
                loadFiles();
            } else {
                // Navigate into directory
                currentDirectory = file.path;
                loadFiles();
            }
        } else {
            // Select file and close modal (only in file mode)
            if (mode === 'file' && onSelect) {
                onSelect(file.path);
                isOpen = false;
            }
        }
    }

    function selectCurrentDirectory() {
        // Select the current directory (for directory mode)
        if (onSelect && currentDirectory) {
            onSelect(currentDirectory);
        }
        isOpen = false;
    }

    function goBack() {
        // Go up one directory
        const parts = currentDirectory.split('/').filter(p => p);
        if (parts.length > 1) {
            parts.pop();
            currentDirectory = '/' + parts.join('/');
            loadFiles();
        } else if (parts.length === 1) {
            // Go to root
            currentDirectory = '/';
            loadFiles();
        }
    }

    function navigateTo(path) {
        currentDirectory = path;
        loadFiles();
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '-';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }

    function getBreadcrumbs() {
        if (!currentDirectory) return [{ name: '/', path: '/' }];

        const parts = currentDirectory.split('/').filter(p => p);
        const breadcrumbs = [{ name: '/', path: '/' }];

        let path = '';
        for (const part of parts) {
            path += '/' + part;
            breadcrumbs.push({ name: part, path });
        }

        return breadcrumbs;
    }

    onMount(() => {
        if (isOpen) {
            loadFiles();
        }
    });

    // Load files when modal opens
    $: if (isOpen) {
        loadFiles();
    }

    function handleClose() {
        isOpen = false;
    }
</script>

{#if isOpen}
    <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
    <div class="modal-overlay" on:click={handleClose}>
        <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
        <div class="modal-content" on:click|stopPropagation>
            <div class="modal-header">
                <h2>{modalTitle}</h2>
                <button class="close-button" on:click={handleClose}>✕</button>
            </div>

            <div class="modal-body">
                <div class="path-bar">
                    <span class="path-label">Location:</span>
                    <div class="breadcrumbs">
                        {#each getBreadcrumbs() as crumb, i}
                            {#if i > 0}
                                <span class="breadcrumb-separator">/</span>
                            {/if}
                            <button
                                class="breadcrumb-button"
                                on:click={() => navigateTo(crumb.path)}
                            >
                                {crumb.name}
                            </button>
                        {/each}
                    </div>
                </div>

                {#if currentDirectory && currentDirectory !== '/'}
                    <div class="parent-dir-item">
                        <button
                            class="file-item directory parent"
                            on:click={goBack}
                        >
                            <span class="file-icon">📁</span>
                            <span class="file-name">..</span>
                            <span class="file-size">(Parent Directory)</span>
                        </button>
                    </div>
                {/if}

                {#if error}
                    <div class="error-message">{error}</div>
                {/if}

                {#if loading}
                    <div class="loading">Loading files...</div>
                {:else if files.length === 0}
                    <div class="empty-message">No files found in this directory</div>
                {:else}
                    <div class="file-list">
                        {#each files as file (file.path)}
                            <div
                                class="file-item {file.type}"
                                on:click={() => selectFile(file)}
                                on:keydown={(e) => e.key === 'Enter' && selectFile(file)}
                                role="button"
                                tabindex="0"
                            >
                                <span class="file-icon">
                                    {#if file.type === 'directory'}
                                        📁
                                    {:else}
                                        📄
                                    {/if}
                                </span>
                                <span class="file-name">{file.name}</span>
                                <span class="file-size">
                                    {#if file.type === 'file'}
                                        {formatFileSize(file.size)}
                                    {/if}
                                </span>
                            </div>
                        {/each}
                    </div>
                {/if}
            </div>

            <div class="modal-footer">
                {#if mode === 'directory'}
                    <button class="select-button" on:click={selectCurrentDirectory}>
                        Select This Directory
                    </button>
                {/if}
                <button class="cancel-button" on:click={handleClose}>Cancel</button>
            </div>
        </div>
    </div>
{/if}

<style>
    .modal-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: rgba(15, 23, 42, 0.6);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
        backdrop-filter: blur(4px);
    }

    .modal-content {
        background-color: white;
        border-radius: 20px;
        box-shadow: 0 25px 50px rgba(0, 0, 0, 0.2);
        width: 90%;
        max-width: 640px;
        max-height: 80vh;
        display: flex;
        flex-direction: column;
        animation: modalSlideIn 0.25s ease;
    }

    @keyframes modalSlideIn {
        from {
            opacity: 0;
            transform: translateY(-20px) scale(0.98);
        }
        to {
            opacity: 1;
            transform: translateY(0) scale(1);
        }
    }

    .modal-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1.25rem 1.5rem;
        border-bottom: 1px solid #e2e8f0;
    }

    .modal-header h2 {
        margin: 0;
        font-size: 1.25rem;
        color: #1e293b;
        font-weight: 600;
    }

    .close-button {
        background: #f1f5f9;
        border: none;
        font-size: 1.25rem;
        cursor: pointer;
        color: #64748b;
        padding: 0;
        width: 36px;
        height: 36px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 10px;
        transition: all 0.2s;
    }

    .close-button:hover {
        background-color: #e2e8f0;
        color: #1e293b;
    }

    .modal-body {
        padding: 1.25rem 1.5rem;
        overflow-y: auto;
        flex: 1;
    }

    .path-bar {
        display: flex;
        align-items: center;
        gap: 0.625rem;
        margin-bottom: 1.125rem;
        padding: 0.875rem 1rem;
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        border-radius: 12px;
        font-size: 0.9rem;
        flex-wrap: wrap;
        border: 1px solid #e2e8f0;
    }

    .path-label {
        font-weight: 600;
        color: #1e293b;
    }

    .breadcrumbs {
        display: flex;
        align-items: center;
        gap: 0.25rem;
        flex: 1;
        flex-wrap: wrap;
    }

    .breadcrumb-button {
        background: none;
        border: none;
        color: #3b82f6;
        cursor: pointer;
        padding: 0.375rem 0.625rem;
        border-radius: 6px;
        font-size: 0.9rem;
        font-weight: 500;
        transition: all 0.15s;
    }

    .breadcrumb-button:hover {
        background-color: rgba(59, 130, 246, 0.1);
        text-decoration: underline;
    }

    .breadcrumb-separator {
        color: #94a3b8;
        margin: 0 0.25rem;
    }

    .parent-dir-item {
        width: 100%;
        margin-bottom: 0.625rem;
    }

    .file-item.parent {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        border: 2px dashed #cbd5e1;
    }

    .file-item.parent:hover {
        background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
        border-color: #3b82f6;
    }

    .error-message {
        padding: 0.875rem 1rem;
        background: linear-gradient(135deg, #ffffff 0%, #fef2f2 100%);
        border: 1px solid #fecaca;
        border-radius: 10px;
        color: #dc2626;
        margin-bottom: 1rem;
        font-weight: 500;
    }

    .loading {
        text-align: center;
        padding: 2.5rem;
        color: #64748b;
    }

    .empty-message {
        text-align: center;
        padding: 2.5rem;
        color: #64748b;
        background: #f8fafc;
        border-radius: 12px;
        border: 2px dashed #e2e8f0;
    }

    .file-list {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .file-item {
        display: flex;
        align-items: center;
        gap: 0.875rem;
        padding: 0.875rem 1rem;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        cursor: pointer;
        transition: all 0.2s;
        user-select: none;
        background: white;
    }

    .file-item:hover {
        background: #f8fafc;
        border-color: #3b82f6;
        transform: translateX(4px);
    }

    .file-item:active {
        background: #f1f5f9;
    }

    .file-item.directory {
        font-weight: 500;
    }

    .file-icon {
        font-size: 1.25rem;
        width: 28px;
        text-align: center;
    }

    .file-name {
        flex: 1;
        color: #1e293b;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .file-size {
        color: #64748b;
        font-size: 0.85rem;
        width: 80px;
        text-align: right;
        font-weight: 500;
    }

    .modal-footer {
        display: flex;
        justify-content: flex-end;
        gap: 0.75rem;
        padding: 1.25rem 1.5rem;
        border-top: 1px solid #e2e8f0;
        background: #f8fafc;
        border-radius: 0 0 20px 20px;
    }

    .cancel-button {
        padding: 0.75rem 1.25rem;
        background-color: #f1f5f9;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        font-size: 0.9rem;
        font-weight: 600;
        color: #475569;
        cursor: pointer;
        transition: all 0.2s;
    }

    .cancel-button:hover {
        background-color: #e2e8f0;
        transform: translateY(-1px);
    }

    .select-button {
        padding: 0.75rem 1.25rem;
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        border: none;
        border-radius: 10px;
        font-size: 0.9rem;
        font-weight: 600;
        color: white;
        cursor: pointer;
        transition: all 0.2s;
        box-shadow: 0 2px 8px rgba(16, 185, 129, 0.4);
    }

    .select-button:hover {
        background: linear-gradient(135deg, #059669 0%, #047857 100%);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.5);
    }

    @media (max-width: 600px) {
        .modal-content {
            width: 95%;
            max-height: 90vh;
            border-radius: 16px;
        }

        .path-bar {
            flex-direction: column;
            align-items: flex-start;
        }

        .path-value {
            width: 100%;
        }
    }
</style>

<script>
  import { onMount, onDestroy } from 'svelte';
  import { logsApi } from '../services/api.js';
  import { showError } from '../components/Notification.svelte';

  let logs = [];
  let isLoading = true;
  let isStreaming = false;
  let autoScroll = true;
  let eventSource = null;
  let logsContainer = null;
  let maxLines = 1000; // Limit displayed lines to prevent memory issues
  let linesCount = 500; // Number of historical lines to fetch

  // Tab state
  let activeTab = 'container'; // 'container' or 'api'
  let apiLogs = [];
  let isLoadingApiLogs = true;
  let isStreamingApiLogs = false;
  let apiEventSource = null;

  // Load initial logs (snapshot)
  async function loadInitialLogs() {
    isLoading = true;
    try {
      const data = await logsApi.getContainerLogsTail(linesCount);
      if (data.success && data.lines) {
        logs = data.lines.map((line, idx) => ({ id: idx, text: line }));
      } else {
        logs = [{ id: 0, text: `[INFO] ${data.message || 'No logs available'}` }];
      }

      // Scroll to bottom after loading (most recent logs)
      setTimeout(() => {
        scrollToBottom();
      }, 100);
    } catch (error) {
      console.error('[Logs] Failed to load initial logs:', error);
      showError('Failed to load container logs');
      logs = [{ id: 0, text: `[ERROR] Failed to load logs: ${error.message}` }];
    } finally {
      isLoading = false;
    }
  }

  // Start streaming logs
  function startStreaming(skipInitialLines = true) {
    if (isStreaming) return;

    isStreaming = true;
    // If we already have logs loaded, we only want to stream NEW logs (lines=0)
    // Otherwise, fetch the last N lines first
    const linesToFetch = skipInitialLines && logs.length > 0 ? 0 : linesCount;
    const streamUrl = logsApi.getContainerLogsStreamUrl(linesToFetch, true);

    try {
      eventSource = new EventSource(streamUrl);

      let isFirstBatch = true;
      let batchLogs = [];
      let batchTimeout = null;

      eventSource.onmessage = (event) => {
        const logLine = event.data;
        if (logLine) {
          // For the first batch of logs (historical), collect them and scroll to bottom
          if (isFirstBatch && batchLogs.length < linesCount) {
            batchLogs.push({ id: Date.now() + Math.random() + batchLogs.length, text: logLine });

            // Clear existing timeout
            if (batchTimeout) clearTimeout(batchTimeout);

            // Wait a bit to see if more logs come in the initial batch
            batchTimeout = setTimeout(() => {
              logs = [...logs, ...batchLogs];
              batchLogs = [];
              isFirstBatch = false;

              // Scroll to bottom to show most recent logs
              setTimeout(() => {
                if (logsContainer) {
                  logsContainer.scrollTop = logsContainer.scrollHeight;
                }
              }, 50);
            }, 100);
          } else {
            // After initial batch, add logs one by one
            isFirstBatch = false;
            logs = [...logs, { id: Date.now() + Math.random(), text: logLine }];

            // Trim logs if exceeding max lines (keep most recent)
            if (logs.length > maxLines) {
              logs = logs.slice(-maxLines);
            }

            // Auto scroll to bottom if enabled (to show most recent logs)
            if (autoScroll && logsContainer) {
              setTimeout(() => {
                logsContainer.scrollTop = logsContainer.scrollHeight;
              }, 10);
            }
          }
        }
      };

      eventSource.onerror = (error) => {
        console.error('[Logs] EventSource error:', error);
        if (eventSource.readyState === EventSource.CLOSED) {
          console.log('[Logs] EventSource closed, attempting to reconnect...');
          stopStreaming();
          // Attempt to reconnect after 5 seconds
          setTimeout(() => {
            if (!isStreaming) {
              startStreaming();
            }
          }, 5000);
        }
      };

      eventSource.onopen = () => {
        console.log('[Logs] EventSource connection established');
      };
    } catch (error) {
      console.error('[Logs] Failed to start streaming:', error);
      showError('Failed to start log streaming');
      isStreaming = false;
    }
  }

  // Stop streaming logs
  function stopStreaming() {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    isStreaming = false;
  }

  // Toggle streaming
  function toggleStreaming() {
    if (isStreaming) {
      stopStreaming();
    } else {
      startStreaming();
    }
  }

  // Clear logs
  function clearLogs() {
    logs = [];
  }

  // Toggle auto-scroll
  function toggleAutoScroll() {
    autoScroll = !autoScroll;
    if (autoScroll && logsContainer) {
      // Both tabs: scroll to bottom (newest logs at bottom)
      logsContainer.scrollTop = logsContainer.scrollHeight;
    }
  }

  // Download logs
  function downloadLogs() {
    const logsText = logs.map(log => log.text).join('\n');
    const blob = new Blob([logsText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `container-logs-${new Date().toISOString()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // Scroll to bottom
  function scrollToBottom() {
    if (logsContainer) {
      logsContainer.scrollTop = logsContainer.scrollHeight;
    }
  }

  // Scroll to top
  function scrollToTop() {
    if (logsContainer) {
      logsContainer.scrollTop = 0;
    }
  }

  // API Logs functions
  function startStreamingApiLogs(skipInitialLines = true) {
    if (isStreamingApiLogs) return;

    isStreamingApiLogs = true;
    const linesToFetch = skipInitialLines && apiLogs.length > 0 ? 0 : linesCount;
    const streamUrl = logsApi.getApiLogsStreamUrl(linesToFetch, true);

    try {
      apiEventSource = new EventSource(streamUrl);

      let isFirstBatch = true;
      let batchLogs = [];
      let batchTimeout = null;

      apiEventSource.onmessage = (event) => {
        const logLine = event.data;
        if (logLine) {
          // Same behavior as container logs - append at bottom
          if (isFirstBatch && batchLogs.length < linesCount) {
            batchLogs.push({ id: Date.now() + Math.random() + batchLogs.length, text: logLine });

            // Clear existing timeout
            if (batchTimeout) clearTimeout(batchTimeout);

            // Wait a bit to see if more logs come in the initial batch
            batchTimeout = setTimeout(() => {
              apiLogs = [...apiLogs, ...batchLogs];
              batchLogs = [];
              isFirstBatch = false;

              // Scroll to bottom to show most recent logs
              setTimeout(() => {
                if (logsContainer) {
                  logsContainer.scrollTop = logsContainer.scrollHeight;
                }
              }, 50);
            }, 100);
          } else {
            // After initial batch, add logs one by one at the bottom
            isFirstBatch = false;
            apiLogs = [...apiLogs, { id: Date.now() + Math.random(), text: logLine }];

            // Trim logs if exceeding max lines (keep most recent)
            if (apiLogs.length > maxLines) {
              apiLogs = apiLogs.slice(-maxLines);
            }

            // Auto scroll to bottom if enabled (to show most recent logs)
            if (autoScroll && logsContainer) {
              setTimeout(() => {
                logsContainer.scrollTop = logsContainer.scrollHeight;
              }, 10);
            }
          }
        }
      };

      apiEventSource.onerror = (error) => {
        console.error('[Logs] API EventSource error:', error);
        stopStreamingApiLogs();
      };
    } catch (error) {
      console.error('[Logs] Failed to start API log streaming:', error);
      isStreamingApiLogs = false;
    }
  }

  function stopStreamingApiLogs() {
    if (apiEventSource) {
      apiEventSource.close();
      apiEventSource = null;
    }
    isStreamingApiLogs = false;
  }

  function toggleStreamingForActiveTab() {
    if (activeTab === 'container') {
      toggleStreaming();
    } else {
      if (isStreamingApiLogs) {
        stopStreamingApiLogs();
      } else {
        startStreamingApiLogs();
      }
    }
  }

  function clearCurrentLogs() {
    if (activeTab === 'container') {
      logs = [];
    } else {
      apiLogs = [];
    }
  }

  function downloadCurrentLogs() {
    const currentLogs = activeTab === 'container' ? logs : apiLogs;
    const logsText = currentLogs.map(log => log.text).join('\n');
    const blob = new Blob([logsText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${activeTab}-logs-${new Date().toISOString()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // Switch tabs
  function switchTab(tab) {
    // Stop current streaming
    if (activeTab === 'container' && isStreaming) {
      stopStreaming();
    } else if (activeTab === 'api' && isStreamingApiLogs) {
      stopStreamingApiLogs();
    }

    activeTab = tab;

    // Start streaming for new tab
    if (tab === 'container' && !isStreaming) {
      startStreaming(false);
    } else if (tab === 'api' && !isStreamingApiLogs) {
      startStreamingApiLogs(false);
    }
  }

  onMount(() => {
    // Don't load initial logs separately - just start streaming
    // The streaming endpoint will provide the tail first, then follow
    isLoading = false;
    isLoadingApiLogs = false;
    startStreaming(false); // false = include initial lines in stream
  });

  onDestroy(() => {
    stopStreaming();
    stopStreamingApiLogs();
  });
</script>

<div class="logs-page">
  <div class="header">
    <h1>Logs</h1>
    <div class="header-info">
      <span class="status-indicator {(activeTab === 'container' && isStreaming) || (activeTab === 'api' && isStreamingApiLogs) ? 'streaming' : 'stopped'}">
        {(activeTab === 'container' && isStreaming) || (activeTab === 'api' && isStreamingApiLogs) ? '● Live' : '○ Stopped'}
      </span>
      <span class="logs-count">{activeTab === 'container' ? logs.length : apiLogs.length} lines</span>
    </div>
  </div>

  <div class="tabs">
    <button
      class="tab {activeTab === 'container' ? 'active' : ''}"
      on:click={() => switchTab('container')}
    >
      🐳 Container Logs
    </button>
    <button
      class="tab {activeTab === 'api' ? 'active' : ''}"
      on:click={() => switchTab('api')}
    >
      🔌 API Logs
    </button>
  </div>

  <div class="controls">
    <div class="control-group">
      <button
        class="btn {(activeTab === 'container' && isStreaming) || (activeTab === 'api' && isStreamingApiLogs) ? 'btn-danger' : 'btn-primary'}"
        on:click={toggleStreamingForActiveTab}
      >
        {(activeTab === 'container' && isStreaming) || (activeTab === 'api' && isStreamingApiLogs) ? '⏸ Stop Streaming' : '▶ Start Streaming'}
      </button>

      <button
        class="btn btn-secondary"
        on:click={toggleAutoScroll}
        title="Toggle auto-scroll to bottom"
      >
        {autoScroll ? '📌 Auto-scroll: ON' : '📌 Auto-scroll: OFF'}
      </button>

      <button
        class="btn btn-secondary"
        on:click={clearCurrentLogs}
        title="Clear displayed logs"
      >
        🗑 Clear
      </button>

      <button
        class="btn btn-secondary"
        on:click={downloadCurrentLogs}
        title="Download logs as text file"
        disabled={(activeTab === 'container' ? logs.length : apiLogs.length) === 0}
      >
        ⬇ Download
      </button>
    </div>

    <div class="control-group">
      <button class="btn btn-sm" on:click={scrollToTop} title="Scroll to top">
        ⬆
      </button>
      <button class="btn btn-sm" on:click={scrollToBottom} title="Scroll to bottom">
        ⬇
      </button>
    </div>
  </div>

  <div class="logs-container" bind:this={logsContainer}>
    {#if activeTab === 'container'}
      {#if isLoading}
        <div class="logs-loading">Loading container logs...</div>
      {:else if logs.length === 0}
        <div class="logs-empty">No logs available. Click "Start Streaming" to begin.</div>
      {:else}
        <div class="logs-content">
          {#each logs as log (log.id)}
            <div class="log-line">{log.text}</div>
          {/each}
        </div>
      {/if}
    {:else}
      {#if isLoadingApiLogs}
        <div class="logs-loading">Loading API logs...</div>
      {:else if apiLogs.length === 0}
        <div class="logs-empty">No API logs available. Click "Start Streaming" to begin.</div>
      {:else}
        <div class="logs-content">
          {#each apiLogs as log (log.id)}
            <div class="log-line">{log.text}</div>
          {/each}
        </div>
      {/if}
    {/if}
  </div>

  <div class="footer-info">
    <p>
      Showing the most recent {linesCount} lines from the tail. New logs appear at the bottom. Maximum {maxLines} lines displayed.
    </p>
  </div>
</div>

<style>
  .logs-page {
    padding: 8px 0;
    display: flex;
    flex-direction: column;
    height: calc(100vh - 100px);
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    flex-wrap: wrap;
    gap: 12px;
  }

  .tabs {
    display: flex;
    gap: 6px;
    margin-bottom: 20px;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 0;
  }

  .tab {
    padding: 14px 24px;
    background: transparent;
    border: none;
    border-bottom: 3px solid transparent;
    font-size: 14px;
    font-weight: 600;
    color: #64748b;
    cursor: pointer;
    transition: all 0.2s;
    border-radius: 8px 8px 0 0;
    margin-bottom: -2px;
  }

  .tab:hover {
    color: #1e293b;
    background: #f8fafc;
  }

  .tab.active {
    color: #3b82f6;
    border-bottom-color: #3b82f6;
    background: white;
  }

  h1 {
    margin: 0;
    color: #1e293b;
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.5px;
  }

  .header-info {
    display: flex;
    gap: 12px;
    align-items: center;
  }

  .status-indicator {
    font-weight: 600;
    font-size: 13px;
    padding: 8px 14px;
    border-radius: 20px;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .status-indicator.streaming {
    background: #ecfdf5;
    color: #059669;
    border: 1px solid #a7f3d0;
  }

  .status-indicator.stopped {
    background: #f8fafc;
    color: #64748b;
    border: 1px solid #e2e8f0;
  }

  .logs-count {
    font-size: 13px;
    color: #64748b;
    font-weight: 600;
    background: #f1f5f9;
    padding: 8px 14px;
    border-radius: 8px;
  }

  .controls {
    display: flex;
    justify-content: space-between;
    margin-bottom: 20px;
    gap: 12px;
    flex-wrap: wrap;
  }

  .control-group {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }

  .btn {
    padding: 12px 20px;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
  }

  .btn-primary {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    color: white;
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.4);
  }

  .btn-primary:hover:not(:disabled) {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.5);
  }

  .btn-danger {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    color: white;
    box-shadow: 0 2px 8px rgba(239, 68, 68, 0.4);
  }

  .btn-danger:hover:not(:disabled) {
    background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(239, 68, 68, 0.5);
  }

  .btn-secondary {
    background: #f1f5f9;
    color: #475569;
    border: 1px solid #e2e8f0;
    box-shadow: none;
  }

  .btn-secondary:hover:not(:disabled) {
    background: #e2e8f0;
    transform: translateY(-1px);
  }

  .btn-sm {
    padding: 10px 14px;
    font-size: 14px;
    background: #f1f5f9;
    color: #475569;
    border-radius: 8px;
    border: 1px solid #e2e8f0;
  }

  .btn-sm:hover {
    background: #e2e8f0;
    transform: translateY(-1px);
  }

  .logs-container {
    flex: 1;
    background: #0f172a;
    border-radius: 16px;
    overflow-y: auto;
    padding: 20px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 13px;
    line-height: 1.6;
    color: #e2e8f0;
    border: 1px solid #1e293b;
  }

  .logs-loading,
  .logs-empty {
    text-align: center;
    padding: 80px 40px;
    color: #64748b;
  }

  .logs-content {
    display: flex;
    flex-direction: column;
  }

  .log-line {
    padding: 4px 8px;
    white-space: pre-wrap;
    word-break: break-all;
    font-family: 'SF Mono', 'Fira Code', monospace;
    border-radius: 4px;
    margin: 1px 0;
  }

  .log-line:hover {
    background: rgba(59, 130, 246, 0.1);
  }

  .footer-info {
    margin-top: 16px;
    text-align: center;
  }

  .footer-info p {
    color: #64748b;
    font-size: 13px;
    margin: 0;
    padding: 12px;
    background: #f8fafc;
    border-radius: 8px;
    font-weight: 500;
  }

  /* Scrollbar styling */
  .logs-container::-webkit-scrollbar {
    width: 10px;
  }

  .logs-container::-webkit-scrollbar-track {
    background: #1e293b;
    border-radius: 5px;
  }

  .logs-container::-webkit-scrollbar-thumb {
    background: #3b82f6;
    border-radius: 5px;
  }

  .logs-container::-webkit-scrollbar-thumb:hover {
    background: #2563eb;
  }

  @media (max-width: 768px) {
    .header {
      flex-direction: column;
      align-items: flex-start;
      gap: 16px;
    }

    .controls {
      flex-direction: column;
    }

    .control-group {
      width: 100%;
      flex-wrap: wrap;
    }

    .btn {
      flex: 1;
      min-width: 100px;
    }

    .tabs {
      width: 100%;
      overflow-x: auto;
    }
  }
</style>

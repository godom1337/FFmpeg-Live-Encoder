<script>
  import { onMount, onDestroy } from "svelte";
  import { jobApi } from "../services/api.js";
  import { showSuccess, showError } from "../components/Notification.svelte";

  export let id;

  // Use the navigate function from AppWithRouter
  const navigate = (path) => {
    if (window.appNavigate) {
      window.appNavigate(path);
    } else {
      window.location.href = path;
    }
  };

  let job = null;
  let isLoading = true;
  let isStarting = false;
  let isStopping = false;
  let isForceKilling = false;
  let logData = null;
  let isLoadingLogs = false;
  let autoRefreshLogs = false;
  let logRefreshInterval = null;
  let logsContainer = null;
  let hlsBaseUrl = "http://localhost/hls"; // Default fallback

  // Command editing state
  let isEditingCommand = false;
  let editableCommand = "";
  let isSavingCommand = false;

  // Fetch HLS base URL from API
  async function fetchHlsConfig() {
    try {
      const response = await fetch("/api/v1/system/config");
      const data = await response.json();
      hlsBaseUrl = data.hls_base_url;
      console.log("[JobDetail] HLS base URL:", hlsBaseUrl);
    } catch (error) {
      console.error("[JobDetail] Failed to fetch HLS config:", error);
      // Keep default fallback
    }
  }

  async function loadJob(silent = false) {
    console.log("[JobDetail] Loading job data for ID:", id);
    if (!silent) {
      isLoading = true;
    }
    try {
      const data = await jobApi.get(id);
      console.log("[JobDetail] Received job data:", data);
      // Force reactivity by creating a new object reference
      job = { ...data };
      console.log("[JobDetail] Job state updated:", job);
    } catch (error) {
      console.error("[JobDetail] Failed to load job:", error);
      if (!silent) {
        showError("Failed to load job details");
      }
    } finally {
      if (!silent) {
        isLoading = false;
      }
    }
  }

  async function loadLogs() {
    if (!id) return;
    isLoadingLogs = true;
    try {
      const data = await jobApi.getLogTail(id, 1000);
      logData = data;
      // Scroll to bottom after DOM updates
      setTimeout(() => {
        if (logsContainer) {
          logsContainer.scrollTop = logsContainer.scrollHeight;
        }
      }, 0);
    } catch (error) {
      console.error("[JobDetail] Failed to load logs:", error);
      // Don't show error to user, logs may not exist yet
    } finally {
      isLoadingLogs = false;
    }
  }

  async function handleStart() {
    console.log("[JobDetail] Starting job:", id);
    isStarting = true;
    try {
      const result = await jobApi.start(id);
      console.log("[JobDetail] Job start result:", result);
      showSuccess("Job started successfully");
      await loadJob();
    } catch (error) {
      console.error("[JobDetail] Failed to start job:", error);
      showError(`Failed to start job: ${error.message}`);
    } finally {
      isStarting = false;
    }
  }

  async function handleStop() {
    console.log("[JobDetail] Stopping job:", id);
    isStopping = true;
    try {
      const result = await jobApi.stop(id);
      console.log("[JobDetail] Job stop result:", result);
      showSuccess("Job stopped successfully");
      await loadJob();
    } catch (error) {
      console.error("[JobDetail] Failed to stop job:", error);
      showError(`Failed to stop job: ${error.message}`);
    } finally {
      isStopping = false;
    }
  }

  async function handleForceKill() {
    if (
      !confirm(
        "Are you sure you want to force kill all FFmpeg processes for this job? This will immediately terminate all processes.",
      )
    ) {
      return;
    }

    console.log("[JobDetail] Force killing job:", id);
    isForceKilling = true;
    try {
      const result = await jobApi.forceKill(id);
      console.log("[JobDetail] Force kill result:", result);
      showSuccess(`Force killed ${result.killed_processes} process(es)`);
      await loadJob();
    } catch (error) {
      console.error("[JobDetail] Failed to force kill job:", error);
      showError(`Failed to force kill job: ${error.message}`);
    } finally {
      isForceKilling = false;
    }
  }

  async function handleResetStatus() {
    if (!confirm(`Reset job "${job.job.name}" status to PENDING?`)) {
      return;
    }

    console.log("[JobDetail] Resetting job status:", id);
    try {
      const result = await jobApi.resetStatus(id);
      console.log("[JobDetail] Reset status result:", result);
      showSuccess(`Job status reset to PENDING`);
      await loadJob();
    } catch (error) {
      console.error("[JobDetail] Failed to reset job status:", error);
      showError(`Failed to reset job status: ${error.message}`);
    }
  }

  function formatCommand(command) {
    if (!command) return "";
    // Format command for better readability by adding line breaks
    return command.replace(/ -/g, " \\\n  -").replace(/^ffmpeg/, "ffmpeg");
  }

  function copyCommand(command) {
    if (!command) return;
    navigator.clipboard
      .writeText(command)
      .then(() => {
        showSuccess("Command copied to clipboard");
      })
      .catch(() => {
        showError("Failed to copy command");
      });
  }

  function formatCommandForEditing(command) {
    if (!command) return "";
    // Split command into lines - each argument on its own line for easier editing
    // Handle: ffmpeg -arg1 value1 -arg2 value2 'quoted value' "double quoted"
    const parts = [];
    let current = "";
    let inSingleQuote = false;
    let inDoubleQuote = false;

    for (let i = 0; i < command.length; i++) {
      const char = command[i];

      if (char === "'" && !inDoubleQuote) {
        inSingleQuote = !inSingleQuote;
        current += char;
      } else if (char === '"' && !inSingleQuote) {
        inDoubleQuote = !inDoubleQuote;
        current += char;
      } else if (char === " " && !inSingleQuote && !inDoubleQuote) {
        if (current.trim()) {
          parts.push(current.trim());
        }
        current = "";
      } else {
        current += char;
      }
    }
    if (current.trim()) {
      parts.push(current.trim());
    }

    // Group into logical lines: ffmpeg on first line, then each -flag with its value(s)
    const lines = [];
    let currentLine = "";

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];

      if (i === 0) {
        // First part is always 'ffmpeg'
        lines.push(part);
      } else if (part.startsWith("-")) {
        // New flag - start a new line
        if (currentLine) {
          lines.push("  " + currentLine);
        }
        currentLine = part;
      } else {
        // Value for current flag
        currentLine += " " + part;
      }
    }
    // Don't forget the last line
    if (currentLine) {
      lines.push("  " + currentLine);
    }

    return lines.join("\n");
  }

  function parseEditedCommand(editedText) {
    // Convert multi-line edited command back to single line
    // Remove line continuations (\), extra whitespace, and join lines
    return editedText
      .split("\n")
      .map((line) => line.replace(/\\$/, "").trim()) // Remove trailing backslashes and trim
      .filter((line) => line.length > 0) // Remove empty lines
      .join(" ")
      .replace(/\s+/g, " ") // Normalize whitespace
      .trim();
  }

  function startEditingCommand() {
    // Format command with line breaks for easier editing
    editableCommand = formatCommandForEditing(job.job.command || "");
    isEditingCommand = true;
  }

  function cancelEditingCommand() {
    isEditingCommand = false;
    editableCommand = "";
  }

  async function saveCommand() {
    // Parse the edited command back to single line
    const finalCommand = parseEditedCommand(editableCommand);

    if (!finalCommand) {
      showError("Command cannot be empty");
      return;
    }

    if (!finalCommand.startsWith("ffmpeg")) {
      showError("Command must start with 'ffmpeg'");
      return;
    }

    isSavingCommand = true;
    try {
      await jobApi.updateCommand(id, finalCommand);
      showSuccess("FFmpeg command updated successfully");
      isEditingCommand = false;
      await loadJob(); // Reload to get the updated command
    } catch (error) {
      console.error("[JobDetail] Failed to save command:", error);
      showError(`Failed to save command: ${error.message}`);
    } finally {
      isSavingCommand = false;
    }
  }

  function copyUrl(url) {
    if (!url) return;
    navigator.clipboard
      .writeText(url)
      .then(() => {
        showSuccess("URL copied to clipboard");
      })
      .catch(() => {
        showError("Failed to copy URL");
      });
  }

  function getStreamUrl(output, jobId, command = null) {
    // If manifest_url is already set, use it
    if (output.manifest_url) {
      return output.manifest_url;
    }

    // Feature 008: HLS output always gets a stream URL with job ID
    // If output type is hls and we have a job ID, construct the URL
    if (output.output_type === "hls" && jobId) {
      // Construct: http://localhost/hls/{job-id}/master.m3u8
      return `${hlsBaseUrl}/${jobId}/master.m3u8`;
    }

    // For file output type, construct download URL
    if (output.output_type === "file" && jobId) {
      let filename = null;

      // Try to extract filename from output_url first
      if (output.output_url) {
        filename = output.output_url.split("/").pop();
      }

      // If no output_url, try to extract from FFmpeg command
      if (!filename && command) {
        // Extract output path from FFmpeg command (last argument that looks like a file path)
        const match = command.match(
          /\/output\/files\/[^\s]+\.(mp4|mkv|webm|avi|mov|flv|ts)/,
        );
        if (match) {
          filename = match[0].split("/").pop();
        }
      }

      // Fall back to default filename
      if (!filename) {
        filename = "output.mp4";
      }

      // Construct: http://localhost/files/{job-id}/{filename}
      return `${hlsBaseUrl.replace("/hls", "/files")}/${jobId}/${filename}`;
    }

    return null;
  }

  function getPlaylistFilename(output) {
    // Always use master.m3u8
    return "master.m3u8";
  }

  function downloadJobConfig() {
    if (!job) return;

    // Export in unified format (compatible with create-unified API)
    const jobConfig = {
      jobName: job.job.name,
      priority: job.job.priority || 5,
      inputFile: job.input.url,
      loopInput: job.input.loop_enabled || false,
      hardwareAccel: job.input.hardware_accel || 'none',
    };

    if (job.output) {
      const out = job.output;

      // Map FFmpeg codec names to API format
      let videoCodec = out.video_codec || 'h264';
      if (videoCodec === 'libx264') videoCodec = 'h264';
      else if (videoCodec === 'libx265' || videoCodec === 'hevc') videoCodec = 'h265';
      else if (videoCodec === 'libsvtav1' || videoCodec === 'libaom-av1') videoCodec = 'av1';

      jobConfig.videoCodec = videoCodec;
      jobConfig.audioCodec = out.audio_codec || 'aac';
      jobConfig.videoBitrate = out.video_bitrate || '2M';
      jobConfig.audioBitrate = out.audio_bitrate || '128k';
      jobConfig.videoResolution = out.video_resolution || '1920x1080';
      jobConfig.videoFrameRate = out.video_framerate || 30;
      jobConfig.outputFormat = out.output_type || 'hls';
      jobConfig.outputDir = out.base_path || '';
      jobConfig.outputUrl = out.output_url || null;

      // HLS specific settings
      if (out.output_type === 'hls') {
        jobConfig.hlsSegmentDuration = out.segment_duration || 6;
        jobConfig.hlsPlaylistSize = out.playlist_size || 5;
      }

      // ABR settings
      jobConfig.abrEnabled = out.abr_enabled || false;
      if (out.abr_enabled && out.renditions && out.renditions.length > 0) {
        jobConfig.abrLadder = out.renditions.map(r => ({
          name: r.name,
          videoBitrate: r.video_bitrate || r.videoBitrate,
          videoResolution: r.video_resolution || r.videoResolution,
          audioBitrate: r.audio_bitrate || r.audioBitrate || '128k'
        }));
      }
    }

    // Create downloadable JSON file
    const jsonString = JSON.stringify(jobConfig, null, 2);
    const blob = new Blob([jsonString], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${job.job.name.replace(/[^a-z0-9]/gi, "_")}_config.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showSuccess("Job configuration downloaded");
  }

  onMount(async () => {
    fetchHlsConfig(); // Fetch HLS config from API
    await loadJob();

    // Load logs initially if job has started
    if (job?.job?.started_at) {
      loadLogs();
      // Auto-enable log refresh for running jobs
      if (job?.job?.status === "running") {
        autoRefreshLogs = true;
        logRefreshInterval = setInterval(() => {
          loadLogs();
        }, 5000);
      }
    }

    // Refresh every 5 seconds if job is running (silent refresh to avoid UI flicker)
    const interval = setInterval(() => {
      if (job?.job?.status === "running") {
        loadJob(true); // Silent refresh
      }
    }, 5000);
    return () => clearInterval(interval);
  });

  function handleDownloadLog() {
    const url = jobApi.getLogDownloadUrl(id);
    window.open(url, "_blank");
  }

  function toggleAutoRefreshLogs() {
    autoRefreshLogs = !autoRefreshLogs;

    if (autoRefreshLogs) {
      // Start auto-refresh
      loadLogs(); // Load immediately
      logRefreshInterval = setInterval(() => {
        loadLogs();
      }, 5000);
    } else {
      // Stop auto-refresh
      if (logRefreshInterval) {
        clearInterval(logRefreshInterval);
        logRefreshInterval = null;
      }
    }
  }

  // Cleanup on component unmount
  onDestroy(() => {
    if (logRefreshInterval) {
      clearInterval(logRefreshInterval);
    }
  });
</script>

<div class="job-detail">
  {#if isLoading}
    <div class="loading">Loading job details...</div>
  {:else if !job}
    <div class="error">Job not found</div>
  {:else}
    <div class="header">
      <h1>{job.job.name}</h1>
      <div class="status status-{job.job.status}">{job.job.status}</div>
    </div>

    <div class="actions">
      {#if job.job.status === "pending" || job.job.status === "stopped"}
        <button
          class="btn btn-primary"
          on:click={handleStart}
          disabled={isStarting}
        >
          {isStarting ? "Starting..." : "Start Job"}
        </button>
      {/if}
      {#if job.job.status === "completed"}
        <button
          class="btn btn-primary"
          on:click={handleStart}
          disabled={isStarting}
        >
          {isStarting ? "Starting..." : "Restart Job"}
        </button>
      {/if}
      {#if job.job.status === "error"}
        <button
          class="btn btn-warning"
          on:click={() => navigate(`/jobs/${id}/edit`)}>Edit Job</button
        >
        <button
          class="btn btn-primary"
          on:click={handleStart}
          disabled={isStarting}
        >
          {isStarting ? "Starting..." : "Restart Job"}
        </button>
      {/if}
      {#if job.job.status === "running"}
        <button
          class="btn btn-danger"
          on:click={handleStop}
          disabled={isStopping}
        >
          {isStopping ? "Stopping..." : "Stop Job"}
        </button>
        <button
          class="btn btn-force-kill"
          on:click={handleForceKill}
          disabled={isForceKilling}
          title="Force kill all FFmpeg processes (SIGKILL)"
        >
          {isForceKilling ? "Force Killing..." : "⚠️ Force Kill"}
        </button>
      {/if}
      {#if job.job.status === "stopped"}
        <button
          class="btn btn-force-kill"
          on:click={handleForceKill}
          disabled={isForceKilling}
          title="Clean up any orphaned FFmpeg processes"
        >
          {isForceKilling ? "Force Killing..." : "🧹 Clean Up Processes"}
        </button>
      {/if}
      {#if job.job.status === "stopped" || job.job.status === "error" || job.job.status === "completed"}
        <button
          class="btn btn-reset"
          on:click={handleResetStatus}
          title="Reset job status to PENDING"
        >
          🔄 Reset Status
        </button>
      {/if}
      {#if job.job.status !== "running" && job.job.status !== "error"}
        <button
          class="btn btn-secondary"
          on:click={() => navigate(`/jobs/${id}/edit`)}>Edit Job</button
        >
      {/if}
      <button
        class="btn btn-download-config"
        on:click={downloadJobConfig}
        title="Download job configuration"
      >
        Download Config
      </button>
    </div>

    <div class="details-grid">
      <!-- Job Information -->
      <div class="detail-card">
        <h3>Job Information</h3>
        <dl>
          <dt>ID</dt>
          <dd>{job.job.id}</dd>
          <dt>Priority</dt>
          <dd>{job.job.priority}</dd>
          <dt>Created</dt>
          <dd>{new Date(job.job.created_at).toLocaleString()}</dd>
          {#if job.job.started_at}
            <dt>Started</dt>
            <dd>{new Date(job.job.started_at).toLocaleString()}</dd>
          {/if}
          {#if job.job.pid}
            <dt>FFmpeg Process ID (PID)</dt>
            <dd class="pid-display">{job.job.pid}</dd>
          {/if}
          {#if job.job.stopped_at}
            <dt>Stopped</dt>
            <dd>{new Date(job.job.stopped_at).toLocaleString()}</dd>
          {/if}
        </dl>
      </div>

      <!-- Input Configuration -->
      {#if job.input}
        <div class="detail-card">
          <h3>Input Configuration</h3>
          <dl>
            <dt>Type</dt>
            <dd>{job.input.type}</dd>
            <dt>URL</dt>
            <dd class="mono">{job.input.url}</dd>
            {#if job.input.loop_enabled}
              <dt>Loop</dt>
              <dd>Enabled</dd>
            {/if}
            {#if job.input.hardware_accel}
              <dt>Hardware Acceleration</dt>
              <dd>{job.input.hardware_accel.type}</dd>
            {/if}
          </dl>
        </div>
      {/if}

      <!-- HLS Streaming Information -->
      {#if job.output && job.output.output_type === "hls"}
        {@const streamUrl = getStreamUrl(
          job.output,
          job.job.id,
          job.job.command,
        )}
        {@const playlistFilename = getPlaylistFilename(job.output)}
        <div class="detail-card hls-card">
          <div class="card-header">
            <h3>🎥 HLS Streaming Information</h3>
          </div>
          <dl>
            {#if streamUrl}
              <dt>Stream URL</dt>
              <dd class="stream-url-container">
                <div class="stream-url">{streamUrl}</div>
                <button
                  class="btn btn-copy-small"
                  on:click={() => copyUrl(streamUrl)}
                  title="Copy URL"
                >
                  📋 Copy
                </button>
              </dd>
            {/if}
            <dt>HLS Directory</dt>
            <dd class="mono">{job.output.base_path}</dd>
            <dt>Playlist File</dt>
            <dd class="mono">{playlistFilename}</dd>
            <dt>Segment Duration</dt>
            <dd>{job.output.segment_duration || 6}s</dd>
            <dt>Playlist Size</dt>
            <dd>{job.output.playlist_size || 10} segments</dd>
            <dt>Nginx Served</dt>
            <dd>{job.output.nginx_served ? "✅ Yes" : "❌ No"}</dd>
            {#if job.output.abr_enabled && job.output.renditions && job.output.renditions.length > 0}
              <dt>ABR Renditions</dt>
              <dd>
                <div class="renditions-list">
                  {#each job.output.renditions as rendition}
                    <div class="rendition-item">
                      {rendition.name} - {rendition.width}x{rendition.height} @ {rendition.video_bitrate}
                    </div>
                  {/each}
                </div>
              </dd>
            {/if}
          </dl>
        </div>
      {/if}

      <!-- Output Configuration (Non-HLS) -->
      {#if job.output && job.output.output_type !== "hls"}
        {@const streamUrl = getStreamUrl(
          job.output,
          job.job.id,
          job.job.command,
        )}
        <div class="detail-card">
          <h3>Output Configuration</h3>
          <dl>
            <dt>Output Type</dt>
            <dd>{job.output.output_type.toUpperCase()}</dd>
            {#if streamUrl}
              <dt>Stream URL</dt>
              <dd class="stream-url-container">
                <div class="stream-url">{streamUrl}</div>
                <button
                  class="btn btn-copy-small"
                  on:click={() => copyUrl(streamUrl)}
                  title="Copy URL"
                >
                  📋 Copy
                </button>
              </dd>
            {/if}
            {#if job.output.output_url}
              <dt>Output Path</dt>
              <dd class="mono">{job.output.output_url}</dd>
            {/if}
            {#if job.output.hardware_accel}
              <dt>Hardware Acceleration</dt>
              <dd>{job.output.hardware_accel.type}</dd>
            {/if}
            {#if job.output.video_codec}
              <dt>Video Codec</dt>
              <dd>{job.output.video_codec}</dd>
            {/if}
            {#if job.output.video_bitrate}
              <dt>Video Bitrate</dt>
              <dd>{job.output.video_bitrate}</dd>
            {/if}
            {#if job.output.video_framerate}
              <dt>Framerate (FPS)</dt>
              <dd>{job.output.video_framerate}</dd>
            {/if}
            {#if job.output.video_profile}
              <dt>Video Profile</dt>
              <dd>{job.output.video_profile}</dd>
            {/if}
            {#if job.output.video_preset}
              <dt>Video Preset</dt>
              <dd>{job.output.video_preset}</dd>
            {/if}
            {#if job.output.video_resolution}
              <dt>Resolution</dt>
              <dd>{job.output.video_resolution}</dd>
            {/if}
          </dl>
        </div>
      {/if}

      <!-- Error Information -->
      {#if job.job.error_message}
        <div class="detail-card error-card">
          <h3>Error Information</h3>
          <p>{job.job.error_message}</p>
        </div>
      {/if}
    </div>

    <!-- Job Logs -->
    {#if job.job.started_at}
      <div class="logs-section">
        <div class="logs-header">
          <h3>Job Logs (Last 1000 Lines)</h3>
          <div class="logs-actions">
            <button
              class="btn {autoRefreshLogs
                ? 'btn-refresh-active'
                : 'btn-refresh'}"
              on:click={toggleAutoRefreshLogs}
            >
              {autoRefreshLogs ? "Auto Refresh: ON" : "Auto Refresh: OFF"}
            </button>
            {#if logData && logData.log_exists}
              <button class="btn btn-download" on:click={handleDownloadLog}>
                Download Full Log
              </button>
            {/if}
          </div>
        </div>
        {#if isLoadingLogs && !logData}
          <div class="logs-loading">Loading logs...</div>
        {:else if logData && logData.log_exists}
          <div class="logs-info">
            Showing {logData.returned_lines} of {logData.total_lines} total lines
          </div>
          <pre class="logs-pre" bind:this={logsContainer}>{logData.lines.join("\n")}</pre>
        {:else if logData && !logData.log_exists}
          <div class="logs-empty">
            {logData.message || "Log file not created yet"}
          </div>
        {:else}
          <div class="logs-empty">Click "Refresh" to load logs</div>
        {/if}
      </div>
    {/if}

    <!-- FFmpeg Command -->
    {#if job.job.command || isEditingCommand}
      <div class="command-section">
        <div class="command-header">
          <h3>FFmpeg Command</h3>
          <div class="command-actions">
            {#if !isEditingCommand}
              <button
                class="btn btn-copy"
                on:click={() => copyCommand(job.job.command)}
              >
                Copy Command
              </button>
              {#if job.job.status !== "running"}
                <button
                  class="btn btn-edit-command"
                  on:click={startEditingCommand}
                >
                  Interactive FFmpeg Command Edit
                </button>
              {/if}
            {:else}
              <button
                class="btn btn-cancel"
                on:click={cancelEditingCommand}
                disabled={isSavingCommand}
              >
                Cancel
              </button>
              <button
                class="btn btn-save-command"
                on:click={saveCommand}
                disabled={isSavingCommand}
              >
                {isSavingCommand ? "Saving..." : "Save"}
              </button>
            {/if}
          </div>
        </div>
        {#if isEditingCommand}
          <div class="command-edit-container">
            <div class="command-edit-header">
              <span class="edit-mode-badge">EDIT MODE</span>
              <span class="edit-mode-info"
                >Each flag (-x) starts a new line for easy editing</span
              >
            </div>
            <div class="command-editor-wrapper">
              <div class="line-numbers" aria-hidden="true">
                {#each editableCommand.split("\n") as _, i}
                  <span>{i + 1}</span>
                {/each}
              </div>
              <textarea
                class="command-textarea"
                bind:value={editableCommand}
                placeholder="ffmpeg&#10;  -i input.mp4&#10;  -c:v libx264&#10;  -c:a aac&#10;  output.mp4"
                spellcheck="false"
                disabled={isSavingCommand}
              ></textarea>
            </div>
            <div class="command-edit-footer">
              <div class="command-edit-hints">
                <span class="hint-item">Add new flags on separate lines</span>
                <span class="hint-item">Delete lines to remove parameters</span>
                <span class="hint-item">Modify values directly</span>
              </div>
              <div class="command-edit-stats">
                {editableCommand.split("\n").length} lines
              </div>
            </div>
          </div>
        {:else}
          <pre class="command-pre">{formatCommand(job.job.command)}</pre>
        {/if}
      </div>
    {/if}
  {/if}
</div>

<style>
  .job-detail {
    padding: 8px 0;
  }

  .loading,
  .error {
    text-align: center;
    padding: 80px 40px;
    color: #64748b;
    background: white;
    border-radius: 16px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  }

  .header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 24px;
    flex-wrap: wrap;
  }

  h1 {
    margin: 0;
    color: #1e293b;
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.5px;
  }

  .status {
    display: inline-flex;
    align-items: center;
    padding: 8px 16px;
    border-radius: 24px;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .status-pending {
    background: #fef3c7;
    color: #92400e;
  }
  .status-running {
    background: #dbeafe;
    color: #1e40af;
  }
  .status-stopped {
    background: #f1f5f9;
    color: #475569;
  }
  .status-error {
    background: #fee2e2;
    color: #991b1b;
  }
  .status-completed {
    background: #d1fae5;
    color: #065f46;
  }

  .actions {
    margin-bottom: 24px;
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }

  .btn {
    padding: 12px 20px;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    font-size: 14px;
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

  .btn-warning {
    background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
    color: white;
    box-shadow: 0 2px 8px rgba(245, 158, 11, 0.4);
  }

  .btn-warning:hover:not(:disabled) {
    background: linear-gradient(135deg, #d97706 0%, #b45309 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(245, 158, 11, 0.5);
  }

  .btn-reset {
    background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
    color: white;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
  }

  .btn-reset:hover:not(:disabled) {
    background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.5);
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

  .btn-force-kill {
    background: linear-gradient(135deg, #a855f7 0%, #9333ea 100%);
    color: white;
    font-weight: 600;
    box-shadow: 0 2px 8px rgba(168, 85, 247, 0.4);
  }

  .btn-force-kill:hover:not(:disabled) {
    background: linear-gradient(135deg, #9333ea 0%, #7e22ce 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(168, 85, 247, 0.5);
  }

  .btn-download-config {
    background: linear-gradient(135deg, #14b8a6 0%, #0d9488 100%);
    color: white;
    font-weight: 600;
    box-shadow: 0 2px 8px rgba(20, 184, 166, 0.4);
  }

  .btn-download-config:hover:not(:disabled) {
    background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(20, 184, 166, 0.5);
  }

  .pid-display {
    font-family: 'SF Mono', 'Fira Code', monospace;
    background: #ecfdf5;
    padding: 8px 14px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 14px;
    color: #065f46;
    border: 2px solid #10b981;
  }

  .details-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 20px;
    margin-bottom: 24px;
  }

  .detail-card {
    background: white;
    padding: 24px;
    border-radius: 16px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
    border: 1px solid rgba(0, 0, 0, 0.04);
    transition: all 0.2s ease;
  }

  .detail-card:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }

  .detail-card h3 {
    margin-top: 0;
    margin-bottom: 20px;
    color: #1e293b;
    font-size: 16px;
    font-weight: 600;
  }

  dl {
    margin: 0;
  }

  dt {
    font-weight: 600;
    color: #64748b;
    margin-bottom: 4px;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  dd {
    margin: 0 0 16px 0;
    color: #1e293b;
    font-size: 14px;
  }

  .mono {
    font-family: 'SF Mono', 'Fira Code', monospace;
    background: #f8fafc;
    padding: 6px 10px;
    border-radius: 6px;
    word-break: break-all;
    font-size: 13px;
    border: 1px solid #e2e8f0;
  }

  .error-card {
    border-left: 4px solid #ef4444;
    background: linear-gradient(135deg, #ffffff 0%, #fef2f2 100%);
  }

  .error-card p {
    color: #dc2626;
    margin: 0;
    font-weight: 500;
  }

  .command-section {
    background: white;
    padding: 24px;
    border-radius: 16px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
    border: 1px solid rgba(0, 0, 0, 0.04);
  }

  .command-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    flex-wrap: wrap;
    gap: 12px;
  }

  .command-header h3 {
    margin: 0;
    color: #1e293b;
    font-size: 16px;
    font-weight: 600;
  }

  .btn-copy {
    padding: 10px 16px;
    background: #f1f5f9;
    color: #475569;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-copy:hover {
    background: #e2e8f0;
    transform: translateY(-1px);
  }

  .command-actions {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }

  .btn-edit-command {
    padding: 10px 18px;
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
  }

  .btn-edit-command:hover {
    background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4);
  }

  .btn-save-command {
    padding: 10px 18px;
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
  }

  .btn-save-command:hover:not(:disabled) {
    background: linear-gradient(135deg, #059669 0%, #047857 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
  }

  .btn-save-command:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }

  .btn-cancel {
    padding: 10px 16px;
    background: #f1f5f9;
    color: #475569;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-cancel:hover:not(:disabled) {
    background: #e2e8f0;
    transform: translateY(-1px);
  }

  .btn-cancel:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .command-edit-container {
    display: flex;
    flex-direction: column;
    gap: 0;
    border: 2px solid #ef4444;
    border-radius: 12px;
    overflow: hidden;
  }

  .command-edit-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 18px;
    background: #1e293b;
    border-bottom: 1px solid #334155;
  }

  .edit-mode-badge {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    color: white;
    padding: 5px 12px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
  }

  .edit-mode-info {
    color: #94a3b8;
    font-size: 12px;
  }

  .command-editor-wrapper {
    display: flex;
    background: #0f172a;
  }

  .line-numbers {
    display: flex;
    flex-direction: column;
    padding: 16px 0;
    background: #1e293b;
    border-right: 1px solid #334155;
    user-select: none;
    min-width: 48px;
  }

  .line-numbers span {
    display: block;
    padding: 0 14px;
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 13px;
    line-height: 1.6;
    color: #64748b;
    text-align: right;
  }

  .command-textarea {
    flex: 1;
    min-height: 400px;
    padding: 16px;
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 13px;
    line-height: 1.6;
    background: #0f172a;
    color: #e2e8f0;
    border: none;
    resize: vertical;
    box-sizing: border-box;
  }

  .command-textarea:focus {
    outline: none;
  }

  .command-textarea:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .command-textarea::placeholder {
    color: #475569;
  }

  .command-edit-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 18px;
    background: #1e293b;
    border-top: 1px solid #334155;
  }

  .command-edit-hints {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
  }

  .hint-item {
    font-size: 11px;
    color: #94a3b8;
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .hint-item::before {
    content: "";
    width: 6px;
    height: 6px;
    background: #3b82f6;
    border-radius: 50%;
  }

  .command-edit-stats {
    font-size: 11px;
    color: #64748b;
    font-family: 'SF Mono', 'Fira Code', monospace;
  }

  .command-pre {
    background: #0f172a;
    color: #22c55e;
    padding: 20px;
    border-radius: 10px;
    overflow-x: auto;
    font-size: 13px;
    line-height: 1.8;
    margin: 0;
    white-space: pre-wrap;
    word-break: break-all;
    font-family: 'SF Mono', 'Fira Code', monospace;
    border: 1px solid #1e293b;
  }

  .logs-section {
    background: white;
    padding: 24px;
    border-radius: 16px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
    border: 1px solid rgba(0, 0, 0, 0.04);
    margin-top: 20px;
  }

  .logs-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    flex-wrap: wrap;
    gap: 12px;
  }

  .logs-header h3 {
    margin: 0;
    color: #1e293b;
    font-size: 16px;
    font-weight: 600;
  }

  .logs-actions {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }

  .btn-refresh {
    padding: 10px 16px;
    background: #f1f5f9;
    color: #475569;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-refresh:hover {
    background: #e2e8f0;
    transform: translateY(-1px);
  }

  .btn-refresh-active {
    padding: 10px 16px;
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
  }

  .btn-refresh-active:hover {
    background: linear-gradient(135deg, #059669 0%, #047857 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
  }

  .btn-download {
    padding: 10px 16px;
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
  }

  .btn-download:hover {
    background: linear-gradient(135deg, #059669 0%, #047857 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
  }

  .logs-info {
    font-size: 12px;
    color: #64748b;
    margin-bottom: 16px;
    font-weight: 500;
  }

  .logs-pre {
    background: #0f172a;
    color: #e2e8f0;
    padding: 18px;
    border-radius: 12px;
    overflow-x: auto;
    font-size: 12px;
    line-height: 1.6;
    margin: 0;
    white-space: pre;
    font-family: 'SF Mono', 'Fira Code', monospace;
    height: 400px;
    overflow-y: scroll;
    border: 1px solid #1e293b;
  }

  .logs-pre::-webkit-scrollbar {
    width: 10px;
  }

  .logs-pre::-webkit-scrollbar-track {
    background: #1e293b;
    border-radius: 5px;
  }

  .logs-pre::-webkit-scrollbar-thumb {
    background: #3b82f6;
    border-radius: 5px;
  }

  .logs-pre::-webkit-scrollbar-thumb:hover {
    background: #2563eb;
  }

  .logs-loading,
  .logs-empty {
    text-align: center;
    padding: 48px;
    color: #64748b;
    background: #f8fafc;
    border-radius: 12px;
    border: 2px dashed #e2e8f0;
  }

  /* HLS Streaming Information Styles */
  .hls-card {
    border-left: 4px solid #8b5cf6;
    background: linear-gradient(135deg, #ffffff 0%, #faf5ff 100%);
  }

  .hls-card .card-header {
    margin-bottom: 20px;
  }

  .hls-card h3 {
    display: flex;
    align-items: center;
    gap: 10px;
    color: #7c3aed;
  }

  .stream-url-container {
    display: flex;
    align-items: center;
    gap: 12px;
    background: linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%);
    padding: 14px 16px;
    border-radius: 10px;
    border: 2px solid #8b5cf6;
  }

  .stream-url {
    flex: 1;
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 14px;
    font-weight: 600;
    color: #6d28d9;
    word-break: break-all;
  }

  .btn-copy-small {
    padding: 8px 14px;
    background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
    flex-shrink: 0;
    box-shadow: 0 2px 6px rgba(139, 92, 246, 0.3);
  }

  .btn-copy-small:hover {
    background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 10px rgba(139, 92, 246, 0.4);
  }

  .renditions-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-top: 12px;
  }

  .rendition-item {
    background: linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%);
    padding: 10px 14px;
    border-radius: 8px;
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 13px;
    color: #6d28d9;
    border-left: 3px solid #8b5cf6;
    transition: all 0.2s;
  }

  .rendition-item:hover {
    background: linear-gradient(135deg, #ede9fe 0%, #ddd6fe 100%);
  }
</style>

<script>
  import { onMount, onDestroy } from "svelte";
  import Hls from "hls.js";
  import { jobApi, systemApi } from "../services/api.js";

  let systemInfo = null;
  let systemMetrics = null;
  let activeJobs = [];
  let isLoading = true;
  let videoPlayers = {};
  let videoElements = {};
  let canvasElements = {};
  let videoLoading = {};
  let snapshotIntervals = {}; // Track snapshot intervals per job
  let snapshotImages = {}; // Store snapshot image URLs for non-HLS jobs
  let hlsBaseUrl = "http://localhost/hls"; // Default fallback

  // Fetch HLS base URL from API
  async function fetchHlsConfig() {
    try {
      const response = await fetch("/api/v1/system/config");
      const data = await response.json();
      hlsBaseUrl = data.hls_base_url;
    } catch (error) {
      console.error("[Dashboard] Failed to fetch HLS config:", error);
      // Keep default fallback
    }
  }

  async function loadData() {
    try {
      // Load system info
      systemInfo = await systemApi.health().catch(() => null);

      // Load system metrics
      systemMetrics = await systemApi.metrics().catch(() => null);

      // Load active jobs with full config
      const jobs = await jobApi.list({ status: "running" }).catch(() => []);

      // Fetch full config for each job to get output paths
      const newJobs = await Promise.all(
        jobs.map(async (job) => {
          try {
            const fullJob = await jobApi.get(job.id);
            return fullJob;
          } catch (error) {
            console.error(`Failed to load config for job ${job.id}:`, error);
            return job;
          }
        }),
      );

      activeJobs = newJobs;

      // Initialize video players for HLS jobs
      // Non-HLS jobs are handled by the setupSnapshot Svelte action
      newJobs.forEach((job) => {
        const jobId = job.job?.id || job.id;

        if (supportsHlsPreview(job)) {
          // HLS job - use video player
          if (videoElements[jobId] && !videoPlayers[jobId]) {
            initVideoPlayer(videoElements[jobId], canvasElements[jobId], job);
          }
        }
      });
    } catch (error) {
      console.error("Failed to load dashboard data:", error);
    } finally {
      isLoading = false;
    }
  }

  // Check if job output supports HLS preview
  function supportsHlsPreview(job) {
    const outputType = job.output?.output_type || "hls";
    return outputType.toLowerCase() === "hls";
  }

  // Get output destination for display
  function getOutputDestination(job) {
    const outputType = job.output?.output_type || "hls";
    if (outputType.toLowerCase() === "hls") {
      return "HLS Stream";
    }
    return job.output?.output_url || `${outputType.toUpperCase()} Stream`;
  }

  // Get snapshot URL for non-HLS jobs
  function getSnapshotUrl(jobId) {
    const baseUrl =
      import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
    // Add timestamp to prevent caching
    return `${baseUrl}/snapshots/${jobId}/thumbnail.jpg?t=${Date.now()}`;
  }

  // Load snapshot for non-HLS job
  async function loadSnapshot(jobId) {
    try {
      // Create a new Image to preload and verify the snapshot loads
      const url = getSnapshotUrl(jobId);
      const img = new Image();

      img.onload = () => {
        // Only update the URL after successful load
        snapshotImages[jobId] = url;
        snapshotImages = { ...snapshotImages };
        console.log(`Snapshot refreshed for job ${jobId}`);
      };

      img.onerror = () => {
        console.error(`Failed to load snapshot for job ${jobId}`);
      };

      // Start loading the image
      img.src = url;
    } catch (error) {
      console.error(`Failed to load snapshot for job ${jobId}:`, error);
    }
  }


  // Generate HLS playlist URL for video preview
  function getPlaylistUrl(job) {
    // Only generate URL for HLS outputs
    if (!supportsHlsPreview(job)) {
      console.log(
        "Output type does not support HLS preview:",
        job.output?.output_type,
      );
      return null;
    }

    // Try to get from manifest_url first
    if (job.output?.manifest_url) {
      // Check if manifest_url is already a full URL
      if (
        job.output.manifest_url.startsWith("http://") ||
        job.output.manifest_url.startsWith("https://")
      ) {
        console.log("Using full manifest_url:", job.output.manifest_url);
        return job.output.manifest_url;
      }
      // Otherwise prepend base URL
      const baseUrl =
        import.meta.env.VITE_API_URL?.replace("/api/v1", "") ||
        "http://localhost:8000";
      const url = `${baseUrl}${job.output.manifest_url}`;
      console.log("Using manifest_url:", url);
      return url;
    }

    // Construct from base_path
    if (job.output?.base_path) {
      // Extract job identifier from base_path
      // Example: /output/hls/323 -> 323
      const match = job.output.base_path.match(/\/output\/hls\/(.+)$/);
      if (match) {
        const jobIdentifier = match[1];
        // Always use master.m3u8
        const playlistName = "master.m3u8";
        const url = `${hlsBaseUrl}/${jobIdentifier}/${playlistName}`;
        console.log("Using base_path to construct URL:", url);
        return url;
      }

      // Fallback: try to extract just the last part
      const pathParts = job.output.base_path.split("/");
      const jobIdentifier = pathParts[pathParts.length - 1];
      const playlistName = "master.m3u8";
      const url = `${hlsBaseUrl}/${jobIdentifier}/${playlistName}`;
      console.log("Using fallback base_path:", url);
      return url;
    }

    // Default to job ID path
    const jobId = job.job?.id || job.id;
    const playlistName = "master.m3u8";
    const url = `${hlsBaseUrl}/${jobId}/${playlistName}`;
    console.log("Using default job ID path:", url);
    return url;
  }

  // Capture a single frame from video to canvas
  function captureFrame(videoElement, canvasElement, jobId, retryCount = 0) {
    const MAX_RETRIES = 3;
    const RETRY_DELAY = 200;

    if (!videoElement || !canvasElement) {
      console.log(`Cannot capture frame for job ${jobId}, elements not available`);
      return false;
    }

    // Check video is ready with actual dimensions
    if (videoElement.readyState < 2 || videoElement.videoWidth === 0 || videoElement.videoHeight === 0) {
      console.log(`Cannot capture frame for job ${jobId}, video not ready (readyState: ${videoElement.readyState}, dimensions: ${videoElement.videoWidth}x${videoElement.videoHeight})`);

      // Retry if we haven't exceeded max retries
      if (retryCount < MAX_RETRIES) {
        console.log(`Retrying frame capture for job ${jobId} (attempt ${retryCount + 1}/${MAX_RETRIES})`);
        setTimeout(() => {
          captureFrame(videoElement, canvasElement, jobId, retryCount + 1);
        }, RETRY_DELAY);
      }
      return false;
    }

    try {
      const ctx = canvasElement.getContext("2d");
      // Use actual video dimensions - never fallback to defaults
      canvasElement.width = videoElement.videoWidth;
      canvasElement.height = videoElement.videoHeight;
      ctx.drawImage(
        videoElement,
        0,
        0,
        canvasElement.width,
        canvasElement.height,
      );

      // Verify the frame isn't completely black by sampling a few pixels
      try {
        const imageData = ctx.getImageData(0, 0, Math.min(10, canvasElement.width), Math.min(10, canvasElement.height));
        const pixels = imageData.data;
        let hasContent = false;
        for (let i = 0; i < pixels.length; i += 4) {
          // Check if any pixel has non-black content (allowing for very dark but valid frames)
          if (pixels[i] > 5 || pixels[i + 1] > 5 || pixels[i + 2] > 5) {
            hasContent = true;
            break;
          }
        }
        if (!hasContent && retryCount < MAX_RETRIES) {
          console.log(`Frame appears black for job ${jobId}, retrying...`);
          setTimeout(() => {
            captureFrame(videoElement, canvasElement, jobId, retryCount + 1);
          }, RETRY_DELAY);
          return false;
        }
      } catch (e) {
        // Canvas tainted or other security error - frame was still captured
        console.log(`Could not verify frame content for job ${jobId}:`, e.message);
      }

      console.log(`Frame captured for job ${jobId} (${canvasElement.width}x${canvasElement.height})`);
      return true;
    } catch (error) {
      console.error(`Error capturing frame for job ${jobId}:`, error);
      return false;
    }
  }

  // Initialize HLS player for snapshot capture
  function initVideoPlayer(videoElement, canvasElement, job) {
    if (!videoElement || !canvasElement) {
      console.warn("Video or canvas element not available");
      return;
    }

    const jobId = job.job?.id || job.id;

    // Check if output type supports HLS preview
    if (!supportsHlsPreview(job)) {
      console.log(
        `Job ${jobId} output type (${job.output?.output_type}) does not support HLS preview`,
      );
      videoLoading[jobId] = false;
      videoLoading = { ...videoLoading };
      return;
    }

    const playlistUrl = getPlaylistUrl(job);
    if (!playlistUrl) {
      console.warn(`No playlist URL available for job ${jobId}`);
      videoLoading[jobId] = false;
      videoLoading = { ...videoLoading };
      return;
    }

    console.log(
      `Initializing snapshot player for job ${jobId} with URL:`,
      playlistUrl,
    );

    // Mark as loading
    videoLoading[jobId] = true;
    videoLoading = { ...videoLoading };

    // Clean up existing player and interval
    if (videoPlayers[jobId]) {
      console.log(`Cleaning up existing player for job ${jobId}`);
      videoPlayers[jobId].destroy();
      delete videoPlayers[jobId];
    }
    if (snapshotIntervals[jobId]) {
      clearInterval(snapshotIntervals[jobId]);
      delete snapshotIntervals[jobId];
    }

    // Hide video element, show canvas
    videoElement.style.display = "none";

    // Check if HLS.js is supported
    if (Hls.isSupported()) {
      console.log("HLS.js is supported, creating snapshot player");
      const hls = new Hls({
        debug: false,
        enableWorker: true,
        lowLatencyMode: false,
        maxBufferLength: 5, // Minimal buffer for snapshots
        maxMaxBufferLength: 10,
        maxBufferSize: 5 * 1000 * 1000,
        liveSyncDurationCount: 1,
      });

      hls.loadSource(playlistUrl);
      hls.attachMedia(videoElement);

      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        console.log(
          `Manifest parsed for job ${jobId}, starting snapshot capture`,
        );
        videoLoading[jobId] = false;
        videoLoading = { ...videoLoading };

        // Start playback muted and hidden
        videoElement.muted = true;

        // Wait for metadata to be loaded (dimensions available)
        const attemptCapture = () => {
          if (videoElement.videoWidth > 0 && videoElement.videoHeight > 0) {
            console.log(`Video dimensions ready for job ${jobId}: ${videoElement.videoWidth}x${videoElement.videoHeight}`);
            // Wait a bit longer for actual frame data to be available
            setTimeout(() => {
              captureFrame(videoElement, canvasElement, jobId);
              videoElement.pause();
            }, 300);
          } else {
            console.log(`Waiting for video dimensions for job ${jobId}...`);
            setTimeout(attemptCapture, 100);
          }
        };

        // Listen for loadedmetadata which fires when dimensions are available
        videoElement.addEventListener("loadedmetadata", () => {
          console.log(`Metadata loaded for job ${jobId}, dimensions: ${videoElement.videoWidth}x${videoElement.videoHeight}`);
          attemptCapture();
        }, { once: true });

        // Also listen for canplay as a fallback
        videoElement.addEventListener("canplay", () => {
          console.log(`Can play event for job ${jobId}`);
          attemptCapture();
        }, { once: true });

        videoElement.play().catch((e) => console.log("Autoplay prevented:", e));

        // Set up interval to refresh snapshot every 10 seconds
        snapshotIntervals[jobId] = setInterval(() => {
          console.log(`Refreshing snapshot for job ${jobId}`);
          // Play for a moment to get fresh frame
          videoElement.play().catch((e) => console.log("Play error:", e));

          // Wait for video to be ready with dimensions before capturing
          const refreshCapture = (attempts = 0) => {
            if (attempts > 10) {
              console.log(`Gave up waiting for video ready for job ${jobId}`);
              videoElement.pause();
              return;
            }
            if (videoElement.readyState >= 2 && videoElement.videoWidth > 0) {
              setTimeout(() => {
                captureFrame(videoElement, canvasElement, jobId);
                videoElement.pause();
              }, 300);
            } else {
              setTimeout(() => refreshCapture(attempts + 1), 100);
            }
          };
          refreshCapture();
        }, 10000);
      });

      hls.on(Hls.Events.ERROR, (event, data) => {
        if (data.fatal) {
          console.error(
            `Fatal HLS error for job ${jobId}:`,
            data.type,
            data.details,
          );
          switch (data.type) {
            case Hls.ErrorTypes.NETWORK_ERROR:
              console.log(
                `Attempting to recover from network error for job ${jobId}`,
              );
              setTimeout(() => hls.startLoad(), 1000);
              break;
            case Hls.ErrorTypes.MEDIA_ERROR:
              console.log(
                `Attempting to recover from media error for job ${jobId}`,
              );
              hls.recoverMediaError();
              break;
          }
        }
      });

      videoPlayers[jobId] = hls;
    } else if (videoElement.canPlayType("application/vnd.apple.mpegurl")) {
      // Native HLS support (Safari)
      console.log("Using native HLS support for snapshots");
      videoElement.src = playlistUrl;
      videoElement.muted = true;

      const attemptNativeCapture = () => {
        if (videoElement.videoWidth > 0 && videoElement.videoHeight > 0 && videoElement.readyState >= 2) {
          console.log(`Native video ready for job ${jobId}: ${videoElement.videoWidth}x${videoElement.videoHeight}`);
          setTimeout(() => {
            captureFrame(videoElement, canvasElement, jobId);
            videoElement.pause();
          }, 300);
        } else {
          console.log(`Waiting for native video dimensions for job ${jobId}...`);
          setTimeout(attemptNativeCapture, 100);
        }
      };

      videoElement.addEventListener("loadedmetadata", () => {
        console.log(`Native metadata loaded for job ${jobId}`);
        videoElement.play().catch((e) => console.log("Autoplay prevented:", e));
        attemptNativeCapture();
      });

      videoElement.addEventListener("canplay", () => {
        console.log(`Native canplay event for job ${jobId}`);
        attemptNativeCapture();
      }, { once: true });

      snapshotIntervals[jobId] = setInterval(() => {
        videoElement.play().catch((e) => console.log("Play error:", e));
        const refreshCapture = (attempts = 0) => {
          if (attempts > 10) {
            videoElement.pause();
            return;
          }
          if (videoElement.readyState >= 2 && videoElement.videoWidth > 0) {
            setTimeout(() => {
              captureFrame(videoElement, canvasElement, jobId);
              videoElement.pause();
            }, 300);
          } else {
            setTimeout(() => refreshCapture(attempts + 1), 100);
          }
        };
        refreshCapture();
      }, 10000);
    } else {
      console.error("HLS not supported in this browser");
    }
  }

  function cleanupAllPlayers() {
    // Clean up HLS players
    Object.values(videoPlayers).forEach((hls) => {
      if (hls) hls.destroy();
    });

    // Clean up all snapshot intervals (both HLS and non-HLS)
    Object.values(snapshotIntervals).forEach((interval) => {
      if (interval) clearInterval(interval);
    });

    videoPlayers = {};
    snapshotIntervals = {};
    snapshotImages = {};
  }

  // Svelte action to setup video player with canvas for snapshots
  function setupVideo(node, job) {
    const jobId = job.job?.id || job.id;
    // Store reference
    videoElements[jobId] = node;

    // Wait for canvas to be available with retry logic
    const waitForCanvas = (attempts = 0) => {
      const canvas = canvasElements[jobId];
      if (canvas) {
        console.log(`Canvas found for job ${jobId}, initializing video player`);
        initVideoPlayer(node, canvas, job);
      } else if (attempts < 20) {
        // Retry up to 20 times (2 seconds total)
        setTimeout(() => waitForCanvas(attempts + 1), 100);
      } else {
        console.error(`Canvas not found for job ${jobId} after 2 seconds`);
      }
    };

    // Use requestAnimationFrame to ensure DOM is ready
    requestAnimationFrame(() => {
      waitForCanvas();
    });

    return {
      destroy() {
        if (videoPlayers[jobId]) {
          videoPlayers[jobId].destroy();
          delete videoPlayers[jobId];
        }
        if (snapshotIntervals[jobId]) {
          clearInterval(snapshotIntervals[jobId]);
          delete snapshotIntervals[jobId];
        }
        delete videoElements[jobId];
      },
    };
  }

  // Svelte action for canvas element
  function setupCanvas(node, job) {
    const jobId = job.job?.id || job.id;
    canvasElements[jobId] = node;

    // If video element is already waiting, trigger initialization
    const videoEl = videoElements[jobId];
    if (videoEl && !videoPlayers[jobId]) {
      console.log(`Video element waiting for canvas ${jobId}, triggering init`);
      initVideoPlayer(videoEl, node, job);
    }

    return {
      destroy() {
        delete canvasElements[jobId];
      },
    };
  }

  // Svelte action for non-HLS snapshot container
  function setupSnapshot(node, job) {
    const jobId = job.job?.id || job.id;
    console.log(`Setting up snapshot refresh for non-HLS job ${jobId}`);

    // Clear any existing interval for this job
    if (snapshotIntervals[jobId]) {
      clearInterval(snapshotIntervals[jobId]);
    }

    // Load initial snapshot
    loadSnapshot(jobId);

    // Setup refresh interval (every 5 seconds)
    snapshotIntervals[jobId] = setInterval(() => {
      console.log(`Refreshing snapshot for non-HLS job ${jobId}`);
      loadSnapshot(jobId);
    }, 5000);

    return {
      destroy() {
        console.log(`Cleaning up snapshot refresh for job ${jobId}`);
        if (snapshotIntervals[jobId]) {
          clearInterval(snapshotIntervals[jobId]);
          delete snapshotIntervals[jobId];
        }
        delete snapshotImages[jobId];
      },
    };
  }

  async function loadMetrics() {
    try {
      systemMetrics = await systemApi.metrics().catch(() => null);
    } catch (error) {
      console.error("Failed to load metrics:", error);
    }
  }

  onMount(() => {
    fetchHlsConfig(); // Fetch HLS config from API
    loadData();

    // Refresh job list every 30 seconds
    const jobInterval = setInterval(loadData, 30000);

    // Refresh metrics every 5 seconds for real-time monitoring
    const metricsInterval = setInterval(loadMetrics, 5000);

    return () => {
      clearInterval(jobInterval);
      clearInterval(metricsInterval);
      cleanupAllPlayers();
    };
  });
</script>

<div class="dashboard">
  <h1>Dashboard</h1>

  {#if isLoading}
    <div class="loading">Loading...</div>
  {:else}
    <div class="stats-grid">
      <!-- Combined Status Card -->
      <div class="stat-card status-overview-card">
        <div class="status-overview">
          <div class="status-item">
            <div class="status-icon status-icon-{systemInfo?.status || 'unknown'}">
              {#if systemInfo?.status === 'healthy'}
                <span>&#10003;</span>
              {:else}
                <span>!</span>
              {/if}
            </div>
            <div class="status-details">
              <div class="status-label">System</div>
              <div class="status-value">{systemInfo?.status || "Unknown"}</div>
            </div>
          </div>
          <div class="status-divider"></div>
          <div class="status-item">
            <div class="status-icon status-icon-jobs">
              <span>{activeJobs.length}</span>
            </div>
            <div class="status-details">
              <div class="status-label">Active Jobs</div>
              <div class="status-value">{activeJobs.length === 1 ? '1 running' : `${activeJobs.length} running`}</div>
            </div>
          </div>
          <div class="status-divider"></div>
          <div class="status-item">
            <div class="status-icon status-icon-api">
              <span>&#9679;</span>
            </div>
            <div class="status-details">
              <div class="status-label">API</div>
              <div class="status-value">Online</div>
            </div>
          </div>
          <div class="status-divider"></div>
          <div class="status-item status-item-metric">
            <div class="status-details">
              <div class="status-label">CPU</div>
              {#if systemMetrics?.cpu}
                <div class="status-value metric-value">{systemMetrics.cpu.percent}%</div>
                <div class="mini-progress">
                  <div
                    class="mini-progress-bar"
                    style="width: {systemMetrics.cpu.percent}%; background-color: {systemMetrics.cpu.percent > 80
                      ? '#ef4444'
                      : systemMetrics.cpu.percent > 60
                        ? '#f59e0b'
                        : '#10b981'}"
                  ></div>
                </div>
                <div class="metric-meta">{systemMetrics.cpu.count} cores</div>
              {:else}
                <div class="status-value metric-value">-</div>
              {/if}
            </div>
          </div>
          <div class="status-divider"></div>
          <div class="status-item status-item-metric">
            <div class="status-details">
              <div class="status-label">Memory</div>
              {#if systemMetrics?.memory}
                <div class="status-value metric-value">{systemMetrics.memory.percent}%</div>
                <div class="mini-progress">
                  <div
                    class="mini-progress-bar"
                    style="width: {systemMetrics.memory.percent}%; background-color: {systemMetrics.memory.percent > 80
                      ? '#ef4444'
                      : systemMetrics.memory.percent > 60
                        ? '#f59e0b'
                        : '#10b981'}"
                  ></div>
                </div>
                <div class="metric-meta">{(systemMetrics.memory.used_mb / 1024).toFixed(1)} / {(systemMetrics.memory.total_mb / 1024).toFixed(1)} GB</div>
              {:else}
                <div class="status-value metric-value">-</div>
              {/if}
            </div>
          </div>
        </div>
      </div>

      {#if systemMetrics?.gpu && systemMetrics.gpu.length > 0}
        {#each systemMetrics.gpu as gpu}
          <div class="stat-card gpu-card-compact" class:apple-gpu={gpu.type === 'apple_silicon'}>
            <div class="gpu-header">
              {#if gpu.type === 'apple_silicon'}
                <span class="gpu-icon apple-icon"></span>
              {:else}
                <span class="gpu-icon nvidia-icon"></span>
              {/if}
              <span class="gpu-name">{gpu.name}</span>
            </div>
            <div class="gpu-stats-compact">
              {#if gpu.type !== 'apple_silicon' || gpu.utilization.gpu !== null}
                <div class="gpu-stat-compact">
                  <span class="gpu-stat-label-compact">GPU</span>
                  <span class="gpu-stat-value-compact">{gpu.utilization.gpu ?? "-"}%</span>
                  <div class="mini-progress">
                    <div class="mini-progress-bar" style="width: {gpu.utilization.gpu ?? 0}%; background-color: {(gpu.utilization.gpu ?? 0) > 80 ? '#ef4444' : (gpu.utilization.gpu ?? 0) > 60 ? '#f59e0b' : '#10b981'}"></div>
                  </div>
                </div>
              {/if}
              {#if gpu.utilization.encoder !== null && gpu.utilization.encoder !== undefined}
                <div class="gpu-stat-compact">
                  <span class="gpu-stat-label-compact">Enc</span>
                  <span class="gpu-stat-value-compact">{gpu.utilization.encoder ?? "-"}%</span>
                  <div class="mini-progress">
                    <div class="mini-progress-bar" style="width: {gpu.utilization.encoder ?? 0}%; background-color: {(gpu.utilization.encoder ?? 0) > 80 ? '#ef4444' : (gpu.utilization.encoder ?? 0) > 60 ? '#f59e0b' : '#10b981'}"></div>
                  </div>
                </div>
              {/if}
              {#if gpu.utilization.decoder !== null && gpu.utilization.decoder !== undefined}
                <div class="gpu-stat-compact">
                  <span class="gpu-stat-label-compact">Dec</span>
                  <span class="gpu-stat-value-compact">{gpu.utilization.decoder ?? "-"}%</span>
                  <div class="mini-progress">
                    <div class="mini-progress-bar" style="width: {gpu.utilization.decoder ?? 0}%; background-color: {(gpu.utilization.decoder ?? 0) > 80 ? '#ef4444' : (gpu.utilization.decoder ?? 0) > 60 ? '#f59e0b' : '#10b981'}"></div>
                  </div>
                </div>
              {/if}
              <div class="gpu-stat-compact">
                <span class="gpu-stat-label-compact">Mem</span>
                <span class="gpu-stat-value-compact">{gpu.memory.percent ?? "-"}%</span>
                <div class="mini-progress">
                  <div class="mini-progress-bar" style="width: {gpu.memory.percent ?? 0}%; background-color: {(gpu.memory.percent ?? 0) > 80 ? '#ef4444' : (gpu.memory.percent ?? 0) > 60 ? '#f59e0b' : '#10b981'}"></div>
                </div>
              </div>
            </div>
            <div class="gpu-meta-compact">
              {#if gpu.temperature !== null}<span class="gpu-meta-tag">{gpu.temperature}°C</span>{/if}
              {#if gpu.power.draw_watts !== null}<span class="gpu-meta-tag">{gpu.power.draw_watts.toFixed(0)}W</span>{/if}
              {#if gpu.encoder.active_sessions > 0}<span class="gpu-meta-tag">{gpu.encoder.active_sessions} enc</span>{/if}
              {#if gpu.type === 'apple_silicon' && gpu.video_toolbox_available}<span class="gpu-meta-tag vt-available">VT</span>{/if}
            </div>
          </div>
        {/each}
      {/if}
    </div>

    <div class="section">
      <h2>Active Encoding Jobs</h2>
      {#if activeJobs.length > 0}
        <div class="jobs-grid">
          {#each activeJobs as job (job.job?.id || job.id)}
            {@const jobId = job.job?.id || job.id}
            {@const playlistUrl = getPlaylistUrl(job)}
            <div class="job-card-grid">
              <div
                class="video-preview"
                class:clickable={playlistUrl}
                on:click={() =>
                  playlistUrl && window.open(playlistUrl, "_blank")}
                role="button"
                tabindex="0"
                on:keypress={(e) => {
                  if ((e.key === "Enter" || e.key === " ") && playlistUrl) {
                    window.open(playlistUrl, "_blank");
                  }
                }}
                title={playlistUrl
                  ? `Click to open HLS stream: ${playlistUrl}`
                  : ""}
              >
                {#if supportsHlsPreview(job)}
                  <!-- Hidden video element for HLS playback -->
                  <video
                    use:setupVideo={job}
                    muted
                    playsinline
                    class="thumbnail-video-hidden"
                  ></video>
                  <!-- Canvas to display static frame -->
                  <canvas use:setupCanvas={job} class="thumbnail-canvas"></canvas>
                  {#if videoLoading[jobId] !== false}
                    <div class="video-placeholder">
                      <span>Loading preview...</span>
                    </div>
                  {/if}
                {:else}
                  <!-- Non-HLS output snapshot -->
                  <div class="snapshot-container" use:setupSnapshot={job}>
                    {#if snapshotImages[jobId]}
                      <img
                        src={snapshotImages[jobId]}
                        alt="Stream preview"
                        class="snapshot-image"
                        on:error={() => {
                          console.log(`Snapshot failed to load for job ${jobId}`);
                        }}
                      />
                    {:else}
                      <div class="video-placeholder non-hls-output">
                        <div class="non-hls-icon">📡</div>
                        <div class="non-hls-text">
                          <strong
                            >{job.output?.output_type?.toUpperCase() || "STREAM"} Output</strong
                          >
                          <span class="non-hls-url"
                            >{getOutputDestination(job)}</span
                          >
                          <span class="non-hls-info">Loading snapshot...</span>
                        </div>
                      </div>
                    {/if}
                  </div>
                {/if}
                <div class="video-overlay">
                  <span class="status-badge"
                    >{job.job?.status || job.status}</span
                  >
                </div>
              </div>
              <div class="job-info">
                <h3 class="job-title">{job.job?.name || job.name}</h3>
                <div class="job-meta">
                  <div class="meta-item">
                    <span class="meta-label">Started:</span>
                    <span class="meta-value">
                      {job.job?.started_at
                        ? new Date(job.job.started_at).toLocaleTimeString()
                        : "N/A"}
                    </span>
                  </div>
                  <div class="meta-item">
                    <span class="meta-label">Job ID:</span>
                    <span class="meta-value job-id"
                      >{(job.job?.id || job.id).substring(0, 8)}...</span
                    >
                  </div>
                </div>
                <div class="job-actions">
                  <a href="/jobs/{job.job?.id || job.id}" class="btn-small"
                    >View</a
                  >
                </div>
              </div>
            </div>
          {/each}
        </div>
      {:else}
        <p class="empty-state">
          No active jobs. <a href="/jobs/create">Create a new job →</a>
        </p>
      {/if}
    </div>
  {/if}
</div>

<style>
  .dashboard {
    padding: 8px 0;
  }

  h1 {
    margin-bottom: 8px;
    color: #1e293b;
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.5px;
  }

  .loading {
    text-align: center;
    padding: 60px 40px;
    color: #64748b;
    background: white;
    border-radius: 16px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  }

  .stat-card {
    background: white;
    padding: 20px;
    border-radius: 16px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.06);
    transition: all 0.2s ease;
    border: 1px solid rgba(0, 0, 0, 0.04);
  }

  .stat-card:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1), 0 2px 4px rgba(0, 0, 0, 0.06);
    transform: translateY(-2px);
  }

  .stats-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    margin-bottom: 24px;
  }

  /* Combined Status Overview Card */
  .status-overview-card {
    flex: 0 0 auto;
    padding: 0;
    overflow: hidden;
  }

  .status-overview {
    display: flex;
    align-items: stretch;
    height: 100%;
  }

  .status-item {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 16px;
  }

  .status-divider {
    width: 1px;
    background: linear-gradient(to bottom, transparent, #e2e8f0, transparent);
    margin: 12px 0;
  }

  .status-icon {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    font-weight: 700;
    flex-shrink: 0;
  }

  .status-icon-healthy {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    color: white;
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
  }

  .status-icon-unknown {
    background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
    color: white;
    box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3);
  }

  .status-icon-jobs {
    background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
    color: white;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
  }

  .status-icon-api {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    color: white;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
  }

  .status-details {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .status-label {
    font-size: 12px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .status-value {
    font-size: 13px;
    font-weight: 700;
    color: #1e293b;
    text-transform: capitalize;
  }

  .status-item-metric {
    min-width: 80px;
  }

  .metric-value {
    font-size: 14px !important;
    line-height: 1.2;
  }

  .mini-progress {
    height: 3px;
    background: #e2e8f0;
    border-radius: 2px;
    overflow: hidden;
    margin-top: 4px;
    width: 100%;
  }

  .mini-progress-bar {
    height: 100%;
    transition: all 0.5s ease;
    border-radius: 2px;
  }

  .metric-meta {
    font-size: 9px;
    color: #94a3b8;
    margin-top: 3px;
    font-weight: 500;
  }

  @media (max-width: 768px) {
    .status-overview-card {
      grid-column: span 1;
    }

    .status-overview {
      flex-direction: column;
    }

    .status-divider {
      width: 100%;
      height: 1px;
      margin: 0 16px;
      background: linear-gradient(to right, transparent, #e2e8f0, transparent);
    }

    .status-item {
      padding: 16px 20px;
    }

    .status-item-metric {
      min-width: auto;
    }
  }

  .stat-label {
    font-size: 12px;
    font-weight: 600;
    color: #64748b;
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .stat-value {
    font-size: 28px;
    font-weight: 700;
    color: #1e293b;
    line-height: 1.2;
  }

  .stat-progress {
    height: 8px;
    background: #e2e8f0;
    border-radius: 4px;
    overflow: hidden;
    margin-top: 12px;
  }

  .progress-bar {
    height: 100%;
    transition: all 0.5s ease;
    border-radius: 4px;
  }

  .stat-meta {
    font-size: 12px;
    color: #94a3b8;
    margin-top: 8px;
    font-weight: 500;
  }

  .status-healthy {
    color: #10b981;
  }

  /* GPU Card */
  .gpu-card-compact {
    flex: 1;
    min-width: 280px;
    padding: 16px 20px;
    background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  }

  .gpu-card-compact.apple-gpu {
    border-left: 3px solid #94a3b8;
  }

  .gpu-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 14px;
  }

  .gpu-name {
    font-size: 13px;
    font-weight: 600;
    color: #1e293b;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .gpu-icon {
    display: inline-block;
    width: 16px;
    height: 16px;
    flex-shrink: 0;
    background-size: contain;
    background-repeat: no-repeat;
    background-position: center;
  }

  .apple-icon {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 384 512'%3E%3Cpath fill='%23555' d='M318.7 268.7c-.2-36.7 16.4-64.4 50-84.8-18.8-26.9-47.2-41.7-84.7-44.6-35.5-2.8-74.3 20.7-88.5 20.7-15 0-49.4-19.7-76.4-19.7C63.3 141.2 4 184.8 4 273.5q0 39.3 14.4 81.2c12.8 36.7 59 126.7 107.2 125.2 25.2-.6 43-17.9 75.8-17.9 31.8 0 48.3 17.9 76.4 17.9 48.6-.7 90.4-82.5 102.6-119.3-65.2-30.7-61.7-90-61.7-91.9zm-56.6-164.2c27.3-32.4 24.8-61.9 24-72.5-24.1 1.4-52 16.4-67.9 34.9-17.5 19.8-27.8 44.3-25.6 71.9 26.1 2 49.9-11.4 69.5-34.3z'/%3E%3C/svg%3E");
  }

  .nvidia-icon {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='%2376b900' d='M8.948 8.798v-1.43a6.7 6.7 0 0 1 .424-.018c3.922-.124 6.493 3.374 6.493 3.374s-2.774 3.851-5.75 3.851c-.44 0-.86-.054-1.167-.171v-4.687c1.256.108 1.513.962 2.267 2.066l1.755-1.479s-1.42-1.566-3.598-1.566c-.152 0-.289.008-.424.02v-.96zm0-4.595v2.037a7.8 7.8 0 0 1 .424-.016c5.025-.17 8.298 4.344 8.298 4.344s-3.787 4.904-7.758 4.904c-.352 0-.68-.03-.964-.09v1.281c.268.03.55.051.845.051 3.434 0 5.932-1.754 8.35-3.817.403.327 2.054 1.117 2.398 1.459-2.058 1.708-6.847 3.582-10.698 3.582-.311 0-.608-.013-.895-.038v1.276h12.444V4.203H8.948z'/%3E%3Cpath fill='%2376b900' d='M3.556 12.632v-1.22a6.13 6.13 0 0 1-.945-.078V5.168s2.645-.323 5.408 1.862V5.59c-2.81-1.87-5.408-1.699-5.408-1.699v8.741h.945z'/%3E%3C/svg%3E");
  }

  .gpu-stats-compact {
    display: flex;
    gap: 16px;
  }

  .gpu-stat-compact {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .gpu-stat-label-compact {
    font-size: 10px;
    color: #64748b;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .gpu-stat-value-compact {
    font-size: 16px;
    font-weight: 700;
    color: #1e293b;
  }

  .gpu-meta-compact {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 12px;
    padding-top: 10px;
    border-top: 1px solid #e2e8f0;
  }

  .gpu-meta-tag {
    font-size: 10px;
    font-weight: 600;
    color: #64748b;
    background: #f1f5f9;
    padding: 3px 8px;
    border-radius: 4px;
  }

  .gpu-meta-tag.vt-available {
    color: #10b981;
    background: rgba(16, 185, 129, 0.1);
  }

  @media (max-width: 768px) {
    .gpu-card-compact {
      min-width: 200px;
      flex: 1;
    }

    .gpu-stats-compact {
      flex-wrap: wrap;
    }

    .gpu-stat-compact {
      flex: 0 0 calc(50% - 8px);
    }
  }

  .status-unknown {
    color: #94a3b8;
  }

  .section {
    background: white;
    padding: 28px;
    border-radius: 16px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.06);
    border: 1px solid rgba(0, 0, 0, 0.04);
  }

  .section h2 {
    margin-top: 0;
    margin-bottom: 20px;
    color: #1e293b;
    font-size: 20px;
    font-weight: 600;
  }

  /* Grid layout for active jobs */
  .jobs-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 16px;
  }

  /* Individual job card with video preview */
  .job-card-grid {
    background: white;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
    transition: all 0.25s ease;
    border: 1px solid rgba(0, 0, 0, 0.04);
  }

  .job-card-grid:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  }

  /* Video preview container */
  .video-preview {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    background: #0f172a;
    overflow: hidden;
  }

  .video-preview.clickable {
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .video-preview.clickable:hover {
    opacity: 0.95;
  }

  .video-preview.clickable:active {
    transform: scale(0.99);
  }

  .video-preview.clickable:focus {
    outline: 3px solid #3b82f6;
    outline-offset: 2px;
  }

  .thumbnail-video-hidden {
    position: absolute;
    opacity: 0;
    pointer-events: none;
    width: 320px;
    height: 180px;
  }

  .thumbnail-canvas {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    position: relative;
    z-index: 1;
    background: #0f172a;
  }

  .snapshot-container {
    width: 100%;
    height: 100%;
    position: relative;
  }

  .snapshot-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    background: #0f172a;
  }

  .video-placeholder {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    color: white;
    font-size: 13px;
    z-index: 0;
    font-weight: 500;
  }

  .non-hls-output {
    background: linear-gradient(135deg, #1e3a5f 0%, #334155 100%);
    flex-direction: column;
    gap: 12px;
    padding: 20px;
  }

  .non-hls-icon {
    font-size: 36px;
    opacity: 0.9;
  }

  .non-hls-text {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    text-align: center;
  }

  .non-hls-text strong {
    font-size: 14px;
    font-weight: 600;
    color: #fff;
  }

  .non-hls-url {
    font-size: 11px;
    color: #93c5fd;
    font-family: 'SF Mono', 'Fira Code', monospace;
    word-break: break-all;
    max-width: 90%;
  }

  .non-hls-info {
    font-size: 11px;
    color: #cbd5e1;
    margin-top: 4px;
  }

  /* Video overlay with status badge */
  .video-overlay {
    position: absolute;
    top: 10px;
    right: 10px;
    z-index: 10;
  }

  .status-badge {
    background: rgba(0, 0, 0, 0.75);
    color: #fff;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    backdrop-filter: blur(8px);
    letter-spacing: 0.3px;
  }

  /* Job information */
  .job-info {
    padding: 14px;
  }

  .job-title {
    margin: 0 0 10px 0;
    font-size: 14px;
    font-weight: 600;
    color: #1e293b;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .job-meta {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 12px;
  }

  .meta-item {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
  }

  .meta-label {
    color: #64748b;
    font-weight: 500;
  }

  .meta-value {
    color: #1e293b;
    font-weight: 600;
  }

  .job-id {
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 11px;
    color: #64748b;
  }

  /* Job actions */
  .job-actions {
    display: flex;
    gap: 6px;
  }

  .btn-small {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 8px 14px;
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    color: white;
    text-decoration: none;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    transition: all 0.2s ease;
    box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
  }

  .btn-small:hover {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(59, 130, 246, 0.4);
  }

  .empty-state {
    text-align: center;
    color: #64748b;
    padding: 60px 40px;
    background: #f8fafc;
    border-radius: 12px;
    border: 2px dashed #e2e8f0;
  }

  .empty-state a {
    color: #3b82f6;
    text-decoration: none;
    font-weight: 600;
    transition: color 0.2s;
  }

  .empty-state a:hover {
    color: #2563eb;
    text-decoration: underline;
  }

  /* Responsive adjustments */
  @media (max-width: 768px) {
    .jobs-grid {
      grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
      gap: 12px;
    }

    .job-info {
      padding: 12px;
    }

    .job-title {
      font-size: 13px;
    }
  }

  @media (min-width: 1400px) {
    .jobs-grid {
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    }
  }
</style>

<script>
  import { onMount } from 'svelte';
  import { jobApi } from '../services/api.js';
  import { showSuccess, showError } from '../components/Notification.svelte';

  // Use simple navigation
  const navigate = (path) => {
    if (window.appNavigate) {
      window.appNavigate(path);
    } else {
      window.location.href = path;
    }
  };

  let jobs = [];
  let isLoading = true;
  let statusFilter = 'all';
  let fileInput;
  let isImporting = false;

  async function loadJobs() {
    isLoading = true;
    try {
      const params = statusFilter !== 'all' ? { status: statusFilter } : {};
      const data = await jobApi.list(params);
      // Force reactivity by creating a new array reference
      jobs = [...data];
    } catch (error) {
      console.error('Failed to load jobs:', error);
      showError('Failed to load jobs');
    } finally {
      isLoading = false;
    }
  }

  async function handleStart(job) {
    try {
      await jobApi.start(job.id);
      showSuccess(`Job "${job.name}" started`);
      await loadJobs();
    } catch (error) {
      showError(`Failed to start job: ${error.message}`);
    }
  }

  async function handleStop(job) {
    try {
      await jobApi.stop(job.id);
      showSuccess(`Job "${job.name}" stopped`);
      await loadJobs();
    } catch (error) {
      showError(`Failed to stop job: ${error.message}`);
    }
  }

  async function handleDelete(job) {
    if (!confirm(`Are you sure you want to delete job "${job.name}"?`)) {
      return;
    }

    try {
      await jobApi.delete(job.id);
      showSuccess(`Job "${job.name}" deleted`);
      await loadJobs();
    } catch (error) {
      showError(`Failed to delete job: ${error.message}`);
    }
  }

  async function handleResetStatus(job) {
    if (!confirm(`Reset job "${job.name}" status to PENDING?`)) {
      return;
    }

    try {
      await jobApi.resetStatus(job.id);
      showSuccess(`Job "${job.name}" status reset to PENDING`);
      await loadJobs();
    } catch (error) {
      showError(`Failed to reset job status: ${error.message}`);
    }
  }

  function handleImportClick() {
    fileInput.click();
  }

  async function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Reset file input so the same file can be selected again
    event.target.value = '';

    if (!file.name.endsWith('.json')) {
      showError('Please select a JSON configuration file');
      return;
    }

    isImporting = true;
    try {
      const text = await file.text();
      const config = JSON.parse(text);

      // Validate the config has required fields (unified format)
      if (!config.jobName || !config.inputFile) {
        throw new Error('Invalid config format. Must contain jobName and inputFile fields.');
      }

      // Create the job using the unified API
      await jobApi.createUnified(config);
      showSuccess(`Job "${config.jobName}" imported successfully`);
      await loadJobs();
    } catch (error) {
      if (error instanceof SyntaxError) {
        showError('Invalid JSON file format');
      } else {
        showError(`Failed to import job: ${error.message}`);
      }
    } finally {
      isImporting = false;
    }
  }

  onMount(() => {
    loadJobs();
  });

  $: if (statusFilter) {
    loadJobs();
  }
</script>

<div class="job-list-page">
  <input
    type="file"
    accept=".json"
    bind:this={fileInput}
    on:change={handleFileSelect}
    style="display: none;"
  />

  <div class="page-header">
    <h1>Encoding Jobs</h1>
    <button
      class="btn-import"
      on:click={handleImportClick}
      disabled={isImporting}
    >
      {isImporting ? 'Importing...' : 'Import Config'}
    </button>
  </div>

  <div class="filters">
    <label>
      Filter by status:
      <select bind:value={statusFilter}>
        <option value="all">All</option>
        <option value="pending">Pending</option>
        <option value="running">Running</option>
        <option value="stopped">Stopped</option>
        <option value="error">Error</option>
        <option value="completed">Completed</option>
      </select>
    </label>
  </div>

  {#if isLoading}
    <div class="loading">Loading jobs...</div>
  {:else if jobs.length === 0}
    <div class="empty-state">
      <p>No jobs found</p>
      <button class="btn-create" on:click={() => navigate('/jobs/create')}>
        Create your first job
      </button>
    </div>
  {:else}
    <div class="jobs-table">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Status</th>
            <th>Priority</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each jobs as job}
            <tr>
              <td>{job.name}</td>
              <td>
                <span class="status status-{job.status}">{job.status}</span>
              </td>
              <td>{job.priority}</td>
              <td>{new Date(job.created_at).toLocaleString()}</td>
              <td>
                <div class="actions">
                  {#if job.status === 'pending' || job.status === 'stopped' || job.status === 'completed' || job.status === 'error'}
                    <button class="btn-small" on:click={() => handleStart(job)}>Start</button>
                  {/if}
                  {#if job.status === 'running'}
                    <button class="btn-small btn-danger" on:click={() => handleStop(job)}>Stop</button>
                  {/if}
                  <button class="btn-small" on:click={() => navigate(`/jobs/${job.id}`)}>View</button>
                  {#if job.status === 'stopped' || job.status === 'error' || job.status === 'completed'}
                    <button class="btn-small btn-warning" on:click={() => handleResetStatus(job)}>Reset</button>
                  {/if}
                  {#if job.status !== 'running'}
                    <button class="btn-small btn-danger" on:click={() => handleDelete(job)}>Delete</button>
                  {/if}
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .job-list-page {
    padding: 8px 0;
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
  }

  h1 {
    margin: 0;
    color: #1e293b;
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.5px;
  }

  .btn-create {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 10px;
    cursor: pointer;
    font-weight: 600;
    font-size: 14px;
    transition: all 0.2s ease;
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.4);
  }

  .btn-create:hover {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.5);
  }

  .btn-import {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 10px;
    cursor: pointer;
    font-weight: 600;
    font-size: 14px;
    transition: all 0.2s ease;
    box-shadow: 0 2px 8px rgba(16, 185, 129, 0.4);
  }

  .btn-import:hover:not(:disabled) {
    background: linear-gradient(135deg, #059669 0%, #047857 100%);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.5);
  }

  .btn-import:disabled {
    background: #94a3b8;
    cursor: not-allowed;
    box-shadow: none;
  }

  .filters {
    background: white;
    padding: 20px 24px;
    border-radius: 12px;
    margin-bottom: 20px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
    border: 1px solid rgba(0, 0, 0, 0.04);
  }

  .filters label {
    display: flex;
    align-items: center;
    gap: 12px;
    color: #64748b;
    font-weight: 500;
    font-size: 14px;
  }

  .filters select {
    padding: 10px 14px;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    font-size: 14px;
    color: #1e293b;
    background: #f8fafc;
    cursor: pointer;
    transition: all 0.2s;
    outline: none;
  }

  .filters select:hover {
    border-color: #cbd5e1;
  }

  .filters select:focus {
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }

  .loading, .empty-state {
    background: white;
    padding: 80px 40px;
    text-align: center;
    border-radius: 16px;
    color: #64748b;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
    border: 1px solid rgba(0, 0, 0, 0.04);
  }

  .jobs-table {
    background: white;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
    border: 1px solid rgba(0, 0, 0, 0.04);
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  th {
    background: #f8fafc;
    padding: 16px 20px;
    text-align: left;
    font-weight: 600;
    color: #64748b;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 1px solid #e2e8f0;
  }

  td {
    padding: 16px 20px;
    border-bottom: 1px solid #f1f5f9;
    color: #1e293b;
    font-size: 14px;
  }

  tr:hover td {
    background: #f8fafc;
  }

  tr:last-child td {
    border-bottom: none;
  }

  .status {
    display: inline-flex;
    align-items: center;
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .status-pending { background: #fef3c7; color: #92400e; }
  .status-running { background: #dbeafe; color: #1e40af; }
  .status-stopped { background: #f1f5f9; color: #475569; }
  .status-error { background: #fee2e2; color: #991b1b; }
  .status-completed { background: #d1fae5; color: #065f46; }

  .actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .btn-small {
    padding: 8px 14px;
    border: 1px solid #e2e8f0;
    background: white;
    border-radius: 8px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
    color: #475569;
    transition: all 0.2s;
  }

  .btn-small:hover {
    background: #f8fafc;
    border-color: #cbd5e1;
    transform: translateY(-1px);
  }

  .btn-danger {
    color: #dc2626;
    border-color: #fecaca;
    background: #fef2f2;
  }

  .btn-danger:hover {
    background: #dc2626;
    color: white;
    border-color: #dc2626;
  }

  .btn-warning {
    color: #d97706;
    border-color: #fde68a;
    background: #fffbeb;
  }

  .btn-warning:hover {
    background: #f59e0b;
    color: white;
    border-color: #f59e0b;
  }
</style>
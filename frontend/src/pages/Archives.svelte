<script>
  import { onMount, onDestroy } from 'svelte';
  import { archivesApi } from '../services/api.js';
  import { showSuccess, showError, showWarning } from '../components/Notification.svelte';

  let archivedJobs = [];
  let isLoading = true;
  let error = null;
  let stats = null;

  // Pagination
  let currentPage = 1;
  let pageSize = 50;
  let totalArchived = 0;
  let hasMore = false;

  // Sorting
  let sortField = 'archived_at';
  let sortDirection = 'DESC';

  // Refresh interval
  let refreshInterval;

  async function loadArchivedJobs() {
    try {
      isLoading = true;
      error = null;

      const offset = (currentPage - 1) * pageSize;
      const orderBy = `${sortField} ${sortDirection}`;

      const response = await archivesApi.list({
        limit: pageSize,
        offset: offset,
        order_by: orderBy
      });

      archivedJobs = response.jobs || [];
      totalArchived = response.total || 0;
      hasMore = response.has_more || false;

    } catch (err) {
      error = err.message || 'Failed to load archived jobs';
      showError(error);
    } finally {
      isLoading = false;
    }
  }

  async function loadStats() {
    try {
      stats = await archivesApi.getStats();
    } catch (err) {
      console.error('Failed to load archives stats:', err);
    }
  }

  async function handleRestore(job) {
    if (!confirm(`Restore job "${job.name}" back to active jobs?`)) {
      return;
    }

    try {
      await archivesApi.restore(job.id);
      showSuccess(`Job "${job.name}" has been restored to active jobs`);
      await loadArchivedJobs();
      await loadStats();
    } catch (err) {
      showError(`Failed to restore job: ${err.message}`);
    }
  }

  async function handleDeletePermanently(job) {
    if (!confirm(
      `⚠️ PERMANENT DELETE\n\nAre you ABSOLUTELY SURE you want to permanently delete job "${job.name}"?\n\nThis action CANNOT be undone!`
    )) {
      return;
    }

    // Double confirmation for permanent deletion
    if (!confirm(
      `This is your last warning!\n\nDelete "${job.name}" permanently?`
    )) {
      return;
    }

    try {
      await archivesApi.deletePermanently(job.id);
      showSuccess(`Job "${job.name}" has been permanently deleted`);
      await loadArchivedJobs();
      await loadStats();
    } catch (err) {
      showError(`Failed to delete job: ${err.message}`);
    }
  }

  function handleSort(field) {
    if (sortField === field) {
      // Toggle direction
      sortDirection = sortDirection === 'ASC' ? 'DESC' : 'ASC';
    } else {
      sortField = field;
      sortDirection = 'DESC';
    }
    currentPage = 1;
    loadArchivedJobs();
  }

  function nextPage() {
    if (hasMore) {
      currentPage++;
      loadArchivedJobs();
    }
  }

  function previousPage() {
    if (currentPage > 1) {
      currentPage--;
      loadArchivedJobs();
    }
  }

  function formatDate(dateString) {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  }

  function getStatusClass(status) {
    const statusMap = {
      'pending': 'status-pending',
      'running': 'status-running',
      'stopped': 'status-stopped',
      'error': 'status-error',
      'completed': 'status-completed'
    };
    return statusMap[status] || 'status-unknown';
  }

  onMount(() => {
    loadArchivedJobs();
    loadStats();

    // Auto-refresh every 30 seconds
    refreshInterval = setInterval(() => {
      loadArchivedJobs();
      loadStats();
    }, 30000);
  });

  onDestroy(() => {
    if (refreshInterval) {
      clearInterval(refreshInterval);
    }
  });
</script>

<div class="archives-page">
  <div class="page-header">
    <div>
      <h1>📦 Archives</h1>
      <p class="subtitle">Deleted jobs that can be restored or permanently deleted</p>
    </div>

    {#if stats}
      <div class="stats-summary">
        <div class="stat-item">
          <span class="stat-label">Total Archived:</span>
          <span class="stat-value">{stats.total_archived}</span>
        </div>
      </div>
    {/if}
  </div>

  {#if error}
    <div class="error-message">
      ⚠️ {error}
      <button class="btn-small" on:click={loadArchivedJobs}>Retry</button>
    </div>
  {/if}

  {#if isLoading}
    <div class="loading">
      <div class="spinner"></div>
      <p>Loading archived jobs...</p>
    </div>
  {:else if archivedJobs.length === 0}
    <div class="empty-state">
      <div class="empty-icon">📦</div>
      <h2>No Archived Jobs</h2>
      <p>Deleted jobs will appear here and can be restored if needed.</p>
    </div>
  {:else}
    <div class="table-container">
      <table class="archives-table">
        <thead>
          <tr>
            <th on:click={() => handleSort('name')} class="sortable">
              Name {sortField === 'name' ? (sortDirection === 'ASC' ? '↑' : '↓') : ''}
            </th>
            <th on:click={() => handleSort('status')} class="sortable">
              Status {sortField === 'status' ? (sortDirection === 'ASC' ? '↑' : '↓') : ''}
            </th>
            <th on:click={() => handleSort('archived_at')} class="sortable">
              Archived At {sortField === 'archived_at' ? (sortDirection === 'ASC' ? '↑' : '↓') : ''}
            </th>
            <th on:click={() => handleSort('created_at')} class="sortable">
              Original Created {sortField === 'created_at' ? (sortDirection === 'ASC' ? '↑' : '↓') : ''}
            </th>
            <th>Input Type</th>
            <th>Output Type</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each archivedJobs as job (job.id)}
            <tr>
              <td class="job-name">{job.name}</td>
              <td>
                <span class="status {getStatusClass(job.status)}">{job.status}</span>
              </td>
              <td class="date-cell">{formatDate(job.archived_at)}</td>
              <td class="date-cell">{formatDate(job.created_at)}</td>
              <td>
                <span class="badge">{job.input_type || 'N/A'}</span>
              </td>
              <td>
                <span class="badge">{job.output_type || 'hls'}</span>
              </td>
              <td>
                <div class="actions">
                  <button
                    class="btn-small btn-primary"
                    on:click={() => handleRestore(job)}
                    title="Restore this job to active jobs"
                  >
                    ↶ Restore
                  </button>
                  <button
                    class="btn-small btn-danger"
                    on:click={() => handleDeletePermanently(job)}
                    title="Permanently delete (cannot be undone)"
                  >
                    🗑️ Delete Forever
                  </button>
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <div class="pagination">
      <div class="pagination-info">
        Showing {(currentPage - 1) * pageSize + 1} - {Math.min(currentPage * pageSize, totalArchived)} of {totalArchived}
      </div>
      <div class="pagination-controls">
        <button
          class="btn-small"
          on:click={previousPage}
          disabled={currentPage === 1}
        >
          ← Previous
        </button>
        <span class="page-number">Page {currentPage}</span>
        <button
          class="btn-small"
          on:click={nextPage}
          disabled={!hasMore}
        >
          Next →
        </button>
      </div>
    </div>
  {/if}
</div>

<style>
  .archives-page {
    padding: 8px 0;
    max-width: 1400px;
    margin: 0 auto;
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 24px;
    flex-wrap: wrap;
    gap: 16px;
  }

  .page-header h1 {
    margin: 0;
    font-size: 28px;
    font-weight: 700;
    color: #1e293b;
    letter-spacing: -0.5px;
  }

  .subtitle {
    margin: 8px 0 0 0;
    color: #64748b;
    font-size: 14px;
  }

  .stats-summary {
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
    padding: 16px 24px;
    border-radius: 12px;
    border: 1px solid rgba(0, 0, 0, 0.04);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  }

  .stat-item {
    display: flex;
    gap: 10px;
    align-items: center;
  }

  .stat-label {
    color: #64748b;
    font-size: 13px;
    font-weight: 500;
  }

  .stat-value {
    font-size: 28px;
    font-weight: 700;
    color: #3b82f6;
    line-height: 1;
  }

  .error-message {
    background: #fef2f2;
    color: #dc2626;
    padding: 16px 20px;
    border-radius: 12px;
    margin-bottom: 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border: 1px solid #fecaca;
    font-weight: 500;
  }

  .loading {
    text-align: center;
    padding: 60px 40px;
    background: white;
    border-radius: 16px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  }

  .spinner {
    border: 3px solid #e2e8f0;
    border-top: 3px solid #3b82f6;
    border-radius: 50%;
    width: 44px;
    height: 44px;
    animation: spin 1s linear infinite;
    margin: 0 auto 16px;
  }

  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }

  .empty-state {
    text-align: center;
    padding: 80px 40px;
    color: #64748b;
    background: white;
    border-radius: 16px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  }

  .empty-icon {
    font-size: 64px;
    margin-bottom: 16px;
    opacity: 0.8;
  }

  .empty-state h2 {
    color: #1e293b;
    margin-bottom: 8px;
    font-weight: 600;
  }

  .table-container {
    background: white;
    border-radius: 16px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
    overflow-x: auto;
    border: 1px solid rgba(0, 0, 0, 0.04);
  }

  .archives-table {
    width: 100%;
    border-collapse: collapse;
  }

  .archives-table thead {
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
  }

  .archives-table th {
    padding: 16px 20px;
    text-align: left;
    font-weight: 600;
    color: #64748b;
    font-size: 12px;
    white-space: nowrap;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .archives-table th.sortable {
    cursor: pointer;
    user-select: none;
    transition: all 0.2s;
  }

  .archives-table th.sortable:hover {
    background: #f1f5f9;
    color: #3b82f6;
  }

  .archives-table td {
    padding: 16px 20px;
    border-bottom: 1px solid #f1f5f9;
    font-size: 14px;
    color: #1e293b;
  }

  .archives-table tbody tr {
    transition: background 0.15s;
  }

  .archives-table tbody tr:hover {
    background: #f8fafc;
  }

  .archives-table tbody tr:last-child td {
    border-bottom: none;
  }

  .job-name {
    font-weight: 600;
    color: #3b82f6;
  }

  .date-cell {
    color: #64748b;
    font-size: 13px;
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
  .status-unknown { background: #f1f5f9; color: #64748b; }

  .badge {
    display: inline-flex;
    align-items: center;
    padding: 5px 10px;
    background: #f1f5f9;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
    color: #475569;
  }

  .actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .btn-small {
    padding: 8px 14px;
    font-size: 12px;
    border: 1px solid #e2e8f0;
    background: white;
    color: #475569;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
    font-weight: 500;
  }

  .btn-small:hover:not(:disabled) {
    background: #f8fafc;
    border-color: #cbd5e1;
    transform: translateY(-1px);
  }

  .btn-small:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-primary {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    color: white;
    border: none;
    font-weight: 600;
    box-shadow: 0 2px 6px rgba(59, 130, 246, 0.3);
  }

  .btn-primary:hover:not(:disabled) {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    box-shadow: 0 4px 10px rgba(59, 130, 246, 0.4);
  }

  .btn-danger {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    color: white;
    border: none;
    font-weight: 600;
    box-shadow: 0 2px 6px rgba(239, 68, 68, 0.3);
  }

  .btn-danger:hover:not(:disabled) {
    background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
    box-shadow: 0 4px 10px rgba(239, 68, 68, 0.4);
  }

  .pagination {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 20px;
    padding: 16px 20px;
    background: white;
    border-radius: 12px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
    border: 1px solid rgba(0, 0, 0, 0.04);
  }

  .pagination-info {
    color: #64748b;
    font-size: 14px;
    font-weight: 500;
  }

  .pagination-controls {
    display: flex;
    gap: 12px;
    align-items: center;
  }

  .page-number {
    font-weight: 600;
    color: #1e293b;
    padding: 8px 14px;
    background: #f1f5f9;
    border-radius: 8px;
    font-size: 14px;
  }
</style>

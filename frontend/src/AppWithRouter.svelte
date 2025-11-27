<script>
  import CreateJob from './pages/CreateJob.svelte';
  import EditJob from './pages/EditJob.svelte';
  import Dashboard from './pages/Dashboard.svelte';
  import JobList from './pages/JobList.svelte';
  import JobDetail from './pages/JobDetail.svelte';
  import Archives from './pages/Archives.svelte';
  import Logs from './pages/Logs.svelte';
  import Notification from './components/Notification.svelte';

  let currentPath = window.location.pathname;
  let currentParams = {};

  // Simple routing logic
  function navigate(path) {
    window.history.pushState({}, '', path);
    currentPath = path;
  }

  // Listen for browser navigation
  window.addEventListener('popstate', () => {
    currentPath = window.location.pathname;
  });

  // Parse route params
  $: {
    // Check for edit route first
    const editMatch = currentPath.match(/^\/jobs\/([^/]+)\/edit$/);
    if (editMatch) {
      currentParams = { id: editMatch[1], edit: true };
    } else {
      // Check for regular job detail
      const match = currentPath.match(/^\/jobs\/([^/]+)$/);
      if (match) {
        currentParams = { id: match[1] };
      } else {
        currentParams = {};
      }
    }
  }

  // Determine current component
  $: currentComponent = (() => {
    if (currentPath === '/') return Dashboard;
    if (currentPath === '/jobs') return JobList;
    if (currentPath === '/jobs/create') return CreateJob;
    if (currentPath === '/archives') return Archives;
    if (currentPath === '/logs') return Logs;
    if (currentPath.startsWith('/jobs/') && currentParams.id && currentParams.edit) return EditJob;
    if (currentPath.startsWith('/jobs/') && currentParams.id) return JobDetail;
    return Dashboard; // Default
  })();

  // Export navigate for child components
  window.appNavigate = navigate;
</script>

<!-- Navigation Bar -->
<nav class="navbar">
  <div class="nav-container">
    <a href="/" class="nav-brand" on:click|preventDefault={() => navigate('/')}>
      🎬 FFmpeg Live Encoder
    </a>
    <div class="nav-menu">
      <a href="/" class="nav-link" on:click|preventDefault={() => navigate('/')}>Dashboard</a>
      <a href="/jobs" class="nav-link" on:click|preventDefault={() => navigate('/jobs')}>Jobs</a>
      <a href="/archives" class="nav-link" on:click|preventDefault={() => navigate('/archives')}>Archives</a>
      <a href="/logs" class="nav-link" on:click|preventDefault={() => navigate('/logs')}>Logs</a>
      <a href="/jobs/create" class="nav-link nav-link-primary" on:click|preventDefault={() => navigate('/jobs/create')}>+ Create Job</a>
    </div>
  </div>
</nav>

<!-- Main Content -->
<main>
  {#key currentPath}
    {#if currentComponent === JobDetail && currentParams.id}
      <svelte:component this={currentComponent} id={currentParams.id} />
    {:else if currentComponent === EditJob && currentParams.id}
      <svelte:component this={currentComponent} id={currentParams.id} />
    {:else}
      <svelte:component this={currentComponent} />
    {/if}
  {/key}
</main>

<!-- Global Notifications -->
<Notification />

<style>
  :global(*) {
    box-sizing: border-box;
  }

  :global(body) {
    margin: 0;
    padding: 0;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background-color: #f0f2f5;
    color: #1a1a2e;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }

  :global(::selection) {
    background-color: #3b82f6;
    color: white;
  }

  .navbar {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
    position: sticky;
    top: 0;
    z-index: 100;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }

  .nav-container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    height: 64px;
  }

  .nav-brand {
    font-size: 18px;
    font-weight: 700;
    color: #ffffff;
    text-decoration: none;
    display: flex;
    align-items: center;
    gap: 10px;
    letter-spacing: -0.5px;
    transition: opacity 0.2s;
  }

  .nav-brand:hover {
    opacity: 0.9;
  }

  .nav-menu {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .nav-link {
    color: rgba(255, 255, 255, 0.7);
    text-decoration: none;
    font-weight: 500;
    font-size: 14px;
    padding: 10px 16px;
    border-radius: 8px;
    transition: all 0.2s ease;
    position: relative;
  }

  .nav-link:hover {
    color: #ffffff;
    background-color: rgba(255, 255, 255, 0.1);
  }

  .nav-link-primary {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    color: white !important;
    font-weight: 600;
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.4);
  }

  .nav-link-primary:hover {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.5);
  }

  main {
    max-width: 1400px;
    margin: 0 auto;
    padding: 24px;
    min-height: calc(100vh - 64px);
  }

  @media (max-width: 768px) {
    .nav-container {
      padding: 0 16px;
    }

    .nav-menu {
      gap: 4px;
    }

    .nav-link {
      padding: 8px 12px;
      font-size: 13px;
    }

    .nav-brand {
      font-size: 16px;
    }

    main {
      padding: 16px;
    }
  }
</style>
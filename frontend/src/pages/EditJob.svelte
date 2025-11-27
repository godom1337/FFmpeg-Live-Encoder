<!-- Edit Job Page - Edit existing job configuration -->
<script>
    import JobCreateForm from '../components/jobs/JobCreateForm.svelte';

    // Get job ID from router parameter
    export let id;
    const jobId = id;

    // Use the navigate function from AppWithRouter
    const navigate = (path) => {
        if (window.appNavigate) {
            window.appNavigate(path);
        } else {
            window.location.href = path;
        }
    };

    // Handle job updated
    function handleJobUpdated(result) {
        console.log('[EditJob] Job updated:', result);
        // Navigate back to job detail
        setTimeout(() => {
            navigate(`/jobs/${jobId}`);
        }, 1000);
    }

    // Handle cancel
    function handleCancel() {
        navigate(`/jobs/${jobId}`);
    }
</script>

<div class="edit-job-page">
    <div class="page-header">
        <h1>Edit Job</h1>
        <p class="subtitle">Update encoding job configuration</p>
    </div>

    <JobCreateForm
        mode="edit"
        jobId={jobId}
        onJobUpdated={handleJobUpdated}
        onCancel={handleCancel}
    />
</div>

<style>
    .edit-job-page {
        padding: 2rem;
        min-height: 100vh;
        background: #f8f9fa;
    }

    .page-header {
        text-align: center;
        margin-bottom: 2rem;
    }

    .page-header h1 {
        color: #2c3e50;
        margin-bottom: 0.5rem;
    }

    .subtitle {
        color: #7f8c8d;
        font-size: 1rem;
        max-width: 600px;
        margin: 0 auto;
    }
</style>

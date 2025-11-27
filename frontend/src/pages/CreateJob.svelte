<script>
    /**
     * Create Job Page
     *
     * Page for creating new encoding jobs using the minimal job creation flow.
     * Uses the new FFmpeg job creation API (rewrite).
     */
    import JobCreateForm from '../components/jobs/JobCreateForm.svelte';
</script>

<div class="create-job-page">
    <div class="page-header">
        <h1>Create Encoding Job</h1>
        <p class="page-description">
            Create a new FFmpeg encoding job with minimal configuration.
            Defaults to H.264 video with audio copy for maximum compatibility.
        </p>
    </div>

    <JobCreateForm />
</div>

<style>
    .create-job-page {
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

    .page-description {
        color: #7f8c8d;
        font-size: 1rem;
        max-width: 600px;
        margin: 0 auto;
    }
</style>

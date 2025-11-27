-- FFmpeg Live Encoder Database Schema
-- Generated from data-model.md

-- Enable WAL mode for concurrent reads
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

-- EncodingProfile table
CREATE TABLE IF NOT EXISTS encoding_profiles (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    codec TEXT CHECK(codec IN ('h264', 'h265', 'av1')) NOT NULL,
    encoder TEXT CHECK(encoder IN ('cpu', 'cuda', 'nvenc', 'vulkan', 'apple')) NOT NULL,
    audio_codec TEXT CHECK(audio_codec IN ('aac', 'ac3', 'copy')) NOT NULL,
    segment_format TEXT CHECK(segment_format IN ('ts', 'm4s')) NOT NULL,
    segment_duration INTEGER DEFAULT 6,
    playlist_size INTEGER DEFAULT 10,
    delete_segments BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_default BOOLEAN DEFAULT 0
);

-- BitrateVariant table
CREATE TABLE IF NOT EXISTS bitrate_variants (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    label TEXT NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    video_bitrate TEXT NOT NULL,
    max_rate TEXT NOT NULL,
    buffer_size TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    FOREIGN KEY (profile_id) REFERENCES encoding_profiles(id) ON DELETE CASCADE
);

-- EncodingJob table
CREATE TABLE IF NOT EXISTS encoding_jobs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    profile_id TEXT,
    status TEXT CHECK(status IN ('pending', 'running', 'stopped', 'error', 'completed')) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    stopped_at TIMESTAMP,
    pid INTEGER,
    error_message TEXT,
    command TEXT,
    priority INTEGER DEFAULT 5 CHECK(priority BETWEEN 1 AND 10),
    archive_on_complete BOOLEAN DEFAULT 0,
    -- New columns for FFmpeg job creation rewrite
    video_codec TEXT,
    audio_codec TEXT,
    video_bitrate TEXT,
    audio_bitrate TEXT,
    audio_volume INTEGER CHECK(audio_volume >= 0 AND audio_volume <= 100),
    hardware_accel TEXT,
    template_id TEXT,
    custom_args TEXT,
    -- Unified configuration cache (Feature: 001-edit-api-simplification)
    full_config TEXT,  -- JSON cache of complete unified job configuration
    FOREIGN KEY (profile_id) REFERENCES encoding_profiles(id) ON DELETE SET NULL
);

-- InputSource table
CREATE TABLE IF NOT EXISTS input_sources (
    job_id TEXT PRIMARY KEY,
    type TEXT CHECK(type IN ('udp', 'http', 'file', 'tcp', 'rtmp', 'srt')) NOT NULL,
    url TEXT NOT NULL,
    loop_enabled BOOLEAN DEFAULT 0,
    hardware_accel TEXT, -- JSON
    FOREIGN KEY (job_id) REFERENCES encoding_jobs(id) ON DELETE CASCADE
);

-- OutputConfiguration table
CREATE TABLE IF NOT EXISTS output_configurations (
    job_id TEXT PRIMARY KEY,
    output_type TEXT DEFAULT 'hls',
    output_url TEXT,

    -- Serialized Pydantic models (Option 2: Pydantic Serialization)
    -- These JSON columns store complete model state, eliminating manual field mapping
    hls_config TEXT, -- JSON: HLSOutput model serialized
    udp_config TEXT, -- JSON: UDPOutput model serialized
    file_config TEXT, -- JSON: FileOutput model serialized

    -- Legacy flat columns (maintained for backward compatibility and simple queries)
    base_path TEXT,
    variant_paths TEXT NOT NULL DEFAULT '{}', -- JSON
    nginx_served BOOLEAN DEFAULT 1,
    manifest_url TEXT,
    segment_duration INTEGER DEFAULT 6,
    playlist_size INTEGER DEFAULT 10,
    playlist_type TEXT DEFAULT 'live' CHECK(playlist_type IN ('vod', 'event', 'live')),
    segment_type TEXT DEFAULT 'mpegts' CHECK(segment_type IN ('mpegts', 'fmp4')),
    segment_pattern TEXT DEFAULT 'segment_%03d.ts',
    video_codec TEXT,
    video_bitrate TEXT,
    video_resolution TEXT,
    video_framerate INTEGER,
    audio_codec TEXT,
    audio_bitrate TEXT,
    audio_channels INTEGER,
    audio_volume INTEGER CHECK(audio_volume >= 0 AND audio_volume <= 100),
    audio_stream_index INTEGER,
    abr_enabled BOOLEAN DEFAULT 0,
    renditions TEXT, -- JSON array of rendition objects
    encoding_preset TEXT,
    crf INTEGER,
    keyframe_interval INTEGER,
    tune TEXT,
    two_pass BOOLEAN DEFAULT 0,
    rate_control_mode TEXT,
    profile TEXT,
    video_profile TEXT,
    level TEXT,
    max_bitrate TEXT,
    buffer_size TEXT,
    look_ahead INTEGER,
    pixel_format TEXT,
    stream_maps TEXT, -- JSON array of stream mapping objects
    FOREIGN KEY (job_id) REFERENCES encoding_jobs(id) ON DELETE CASCADE
);

-- JobStatistics table
CREATE TABLE IF NOT EXISTS job_statistics (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fps REAL,
    bitrate INTEGER,
    dropped_frames INTEGER DEFAULT 0,
    encoding_speed REAL,
    cpu_percent INTEGER,
    memory_mb INTEGER,
    gpu_percent INTEGER,
    total_frames BIGINT,
    current_time TEXT,
    FOREIGN KEY (job_id) REFERENCES encoding_jobs(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_encoding_jobs_status ON encoding_jobs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_encoding_jobs_profile ON encoding_jobs(profile_id);
CREATE INDEX IF NOT EXISTS idx_encoding_jobs_full_config_abr ON encoding_jobs(json_extract(full_config, '$.abrEnabled'));
CREATE INDEX IF NOT EXISTS idx_bitrate_variants_profile ON bitrate_variants(profile_id, order_index);
CREATE INDEX IF NOT EXISTS idx_job_statistics_job ON job_statistics(job_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_job_statistics_cleanup ON job_statistics(timestamp);
CREATE INDEX IF NOT EXISTS idx_input_sources_type ON input_sources(type);
CREATE INDEX IF NOT EXISTS idx_encoding_profiles_default ON encoding_profiles(is_default, created_at DESC);

-- Trigger to update encoding_profiles.updated_at
CREATE TRIGGER IF NOT EXISTS update_profile_timestamp
AFTER UPDATE ON encoding_profiles
BEGIN
    UPDATE encoding_profiles SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Trigger to invalidate full_config cache (Feature: 001-edit-api-simplification)
-- Invalidates cache when output_configurations is updated directly (defensive measure)
CREATE TRIGGER IF NOT EXISTS invalidate_config_cache
AFTER UPDATE ON output_configurations
BEGIN
    UPDATE encoding_jobs SET full_config = NULL WHERE id = NEW.job_id;
END;
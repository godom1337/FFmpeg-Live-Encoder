# Create Job API

Create encoding jobs using the unified configuration API.

## Endpoint

```
POST /api/v1/jobs/create-unified
```

## Request Body

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `jobName` | string | Human-readable job name (max 255 chars) |
| `inputFile` | string | Path to input video file |
| `videoCodec` | string | Video codec (`h264`, `h265`, `vp9`) |
| `audioCodec` | string | Audio codec (`aac`, `mp3`, `opus`) |
| `audioBitrate` | string | Audio bitrate (e.g., `128k`, `192k`) |
| `outputFormat` | string | Output format (`hls`, `dash`, `mp4`, `rtmp`) |

### Optional Fields

**Video Settings**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `videoBitrate` | string | - | Video bitrate (e.g., `5M`, `2500k`) |
| `videoResolution` | string | - | Resolution (e.g., `1920x1080`) |
| `videoFrameRate` | int | - | Frame rate (1-120) |
| `videoPreset` | string | `medium` | Encoding preset (`ultrafast`, `fast`, `medium`, `slow`) |
| `videoProfile` | string | - | H.264/H.265 profile (`baseline`, `main`, `high`) |
| `videoGOP` | int | - | Keyframe interval in frames |

**Audio Settings**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `audioSampleRate` | int | `48000` | Sample rate in Hz |
| `audioChannels` | int | `2` | Number of channels (1-8) |
| `audioVolume` | int | - | Volume percentage (0-100) |

**Input Settings**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `loopInput` | bool | `false` | Loop input continuously |
| `startTime` | string | - | Start offset (`HH:MM:SS`) |
| `duration` | string | - | Duration to encode (`HH:MM:SS`) |

**Output Settings**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `outputDir` | string | - | Output directory (for `hls`, `dash`, `mp4`) |
| `outputUrl` | string | - | Stream URL (for `rtmp`, `udp`, `srt`) |

**HLS Settings**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `hlsSegmentDuration` | int | `6` | Segment duration in seconds |
| `hlsPlaylistType` | string | `vod` | Playlist type (`vod`, `event`) |
| `hlsPlaylistSize` | int | `5` | Number of segments in playlist |
| `hlsSegmentType` | string | `mpegts` | Segment type (`mpegts`, `fmp4`) |

**Hardware Acceleration**

| Field | Type | Description |
|-------|------|-------------|
| `hardwareAccel` | string | Acceleration type (`none`, `nvenc`, `qsv`, `vaapi`) |
| `hardwareDevice` | string | Device index (e.g., `0`) |

**ABR (Adaptive Bitrate)**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `abrEnabled` | bool | `false` | Enable adaptive bitrate |
| `abrLadder` | array | - | Array of rendition configs (required if ABR enabled) |

## Examples

### Simple HLS Job

```bash
curl -X POST http://localhost:8000/api/v1/jobs/create-unified \
  -H "Content-Type: application/json" \
  -d '{
    "jobName": "My Stream",
    "inputFile": "/input/video.mp4",
    "videoCodec": "h264",
    "videoBitrate": "5M",
    "videoResolution": "1920x1080",
    "videoFrameRate": 30,
    "audioCodec": "aac",
    "audioBitrate": "128k",
    "outputFormat": "hls",
    "outputDir": "/output/hls/my-stream",
    "hlsSegmentDuration": 6
  }'
```

### ABR Job (Multiple Quality Levels)

```bash
curl -X POST http://localhost:8000/api/v1/jobs/create-unified \
  -H "Content-Type: application/json" \
  -d '{
    "jobName": "ABR Stream",
    "inputFile": "/input/video.mp4",
    "videoCodec": "h264",
    "videoPreset": "fast",
    "audioCodec": "aac",
    "audioBitrate": "128k",
    "outputFormat": "hls",
    "outputDir": "/output/hls/abr-stream",
    "abrEnabled": true,
    "abrLadder": [
      {
        "name": "1080p",
        "videoBitrate": "5M",
        "videoResolution": "1920x1080"
      },
      {
        "name": "720p",
        "videoBitrate": "3M",
        "videoResolution": "1280x720"
      },
      {
        "name": "480p",
        "videoBitrate": "1.5M",
        "videoResolution": "854x480"
      }
    ]
  }'
```

### RTMP Output

```bash
curl -X POST http://localhost:8000/api/v1/jobs/create-unified \
  -H "Content-Type: application/json" \
  -d '{
    "jobName": "RTMP Stream",
    "inputFile": "/input/video.mp4",
    "loopInput": true,
    "videoCodec": "h264",
    "videoBitrate": "4M",
    "audioCodec": "aac",
    "audioBitrate": "128k",
    "outputFormat": "rtmp",
    "outputUrl": "rtmp://server/live/stream-key"
  }'
```

### With Hardware Acceleration (NVIDIA)

```bash
curl -X POST http://localhost:8000/api/v1/jobs/create-unified \
  -H "Content-Type: application/json" \
  -d '{
    "jobName": "GPU Encoded Stream",
    "inputFile": "/input/video.mp4",
    "videoCodec": "h264",
    "videoBitrate": "5M",
    "hardwareAccel": "nvenc",
    "hardwareDevice": "0",
    "audioCodec": "aac",
    "audioBitrate": "128k",
    "outputFormat": "hls",
    "outputDir": "/output/hls/gpu-stream"
  }'
```

## Response

### Success (201 Created)

```json
{
  "status": "created",
  "jobId": "550e8400-e29b-41d4-a716-446655440000",
  "ffmpegCommand": "ffmpeg -i /input/video.mp4 -c:v libx264 ..."
}
```

### Error (400 Bad Request)

```json
{
  "error": "Validation failed",
  "details": ["jobName is required", "videoCodec must be a valid codec"]
}
```

### Error (409 Conflict)

```json
{
  "error": "Conflict",
  "message": "Job with name 'My Stream' already exists"
}
```

## Start the Job

After creating a job, start it with:

```bash
curl -X POST http://localhost:8000/api/v1/jobs/{jobId}/start
```

## View HLS Stream

Once the job is running, access the stream at:

```
http://localhost/hls/{jobName}/master.m3u8
```

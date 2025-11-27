# OpenLiveEncoder Test Jobs

Complete test suite for the OpenLiveEncoder API with executable bash scripts.

## Configuration

Edit `.env` file to set your API URL and input file:

```bash
apiurl: http://localhost:8000
input: /input/test.mp4
```

## Test Scripts

### HLS Non-ABR (Single Quality) - Live Mode

| Script | Codec | Segment Type | Hardware Accel | Bitrate | Loop |
|--------|-------|--------------|----------------|---------|------|
| `test-job-h264-hls-noabr.sh` | H.264 | MPEG-TS | NVENC | 5M | Yes |
| `test-job-h265-hls-noabr.sh` | H.265 | fMP4 | NVENC | 4M | Yes |
| `test-job-av1-hls-noabr.sh` | AV1 | fMP4 | Software | 3M | Yes |

### HLS ABR (Multi-Quality) - Live Mode

| Script | Codec | Segment Type | Hardware Accel | Qualities | Loop |
|--------|-------|--------------|----------------|-----------|------|
| `test-job-h264-hls-abr.sh` | H.264 | MPEG-TS | NVENC | 1080p/720p/480p | Yes |
| `test-job-h265-hls-abr.sh` | H.265 | fMP4 | NVENC | 1080p/720p/480p | Yes |
| `test-job-av1-hls-abr.sh` | AV1 | fMP4 | Software | 1080p/720p/480p | Yes |

### UDP Streaming (Single Quality)

| Script | Codec | Hardware Accel | Multicast Address | Bitrate | Loop |
|--------|-------|----------------|-------------------|---------|------|
| `test-job-h264-udp.sh` | H.264 | NVENC | udp://239.1.1.1:5001 | 5M | Yes |
| `test-job-h265-udp.sh` | H.265 | NVENC | udp://239.1.1.2:5002 | 4M | Yes |
| `test-job-av1-udp.sh` | AV1 | Software | udp://239.1.1.3:5003 | 3M | Yes |

### UDP Streaming ABR (Multi-Quality)

| Script | Codec | Hardware Accel | Multicast Addresses | Qualities | Loop |
|--------|-------|----------------|---------------------|-----------|------|
| `test-job-h264-udp-abr.sh` | H.264 | NVENC | udp://239.1.2.1-3:5011-5013 | 1080p/720p/480p | Yes |
| `test-job-h265-udp-abr.sh` | H.265 | NVENC | udp://239.1.2.4-6:5014-5016 | 1080p/720p/480p | Yes |
| `test-job-av1-udp-abr.sh` | AV1 | Software | udp://239.1.2.7-9:5017-5019 | 1080p/720p/480p | Yes |

## Usage

Run any test script:

```bash
cd TESTJOBS
./test-job-h264-hls-noabr.sh
```

Each script will:
1. Load API URL and input file from `.env`
2. Validate the job configuration
3. Create the job if validation passes
4. Return the job ID

## Testing UDP Streams

### Single Quality UDP Streams

To receive a single quality UDP stream, use ffplay:

```bash
# H.264 UDP
ffplay udp://239.1.1.1:5001

# H.265 UDP
ffplay udp://239.1.1.2:5002

# AV1 UDP
ffplay udp://239.1.1.3:5003
```

### UDP ABR Streams

To receive ABR UDP streams (each quality on separate port):

```bash
# H.264 UDP ABR
ffplay udp://239.1.2.1:5011  # 1080p
ffplay udp://239.1.2.2:5012  # 720p
ffplay udp://239.1.2.3:5013  # 480p

# H.265 UDP ABR
ffplay udp://239.1.2.4:5014  # 1080p
ffplay udp://239.1.2.5:5015  # 720p
ffplay udp://239.1.2.6:5016  # 480p

# AV1 UDP ABR
ffplay udp://239.1.2.7:5017  # 1080p
ffplay udp://239.1.2.8:5018  # 720p
ffplay udp://239.1.2.9:5019  # 480p
```

## Common Features

All test scripts include:
- **Live Playlist Type**: HLS streams use `live` mode (rolling window)
- **Loop Input**: Input file loops continuously (`loopInput: true`)
- **Hardware Acceleration**: NVENC where supported (H.264, H.265)
- **6-second segments**: HLS segment duration
- **10-segment playlist**: Rolling window size for live streams

## Output Directories

HLS outputs are organized by test type:
- `/output/hls/test-h264-noabr/` - H.264 single quality
- `/output/hls/test-h265-noabr/` - H.265 single quality
- `/output/hls/test-av1-noabr/` - AV1 single quality
- `/output/hls/test-h264-abr/` - H.264 multi-quality
- `/output/hls/test-h265-abr/` - H.265 multi-quality
- `/output/hls/test-av1-abr/` - AV1 multi-quality

## Bitrate Configuration

### Non-ABR Bitrates (HLS & UDP Single Quality)
- **H.264**: 5M video, 128k audio
- **H.265**: 4M video, 128k audio (better compression)
- **AV1**: 3M video, 128k audio (best compression)

### ABR Ladder Bitrates (HLS & UDP Multi-Quality)

**H.264**:
- 1080p: 5M
- 720p: 3M
- 480p: 1.5M

**H.265**:
- 1080p: 4M
- 720p: 2.5M
- 480p: 1.2M

**AV1**:
- 1080p: 3M
- 720p: 2M
- 480p: 1M

All ABR configurations use 128k audio bitrate.

## Notes

- **NVENC**: Hardware acceleration requires NVIDIA GPU. Will fallback to software if unavailable.
- **AV1**: Software-only encoding (no hardware support yet)
- **H.265/AV1 HLS**: Requires fMP4 segment type (not MPEG-TS)
- **Live Mode**: Uses rolling window playlist, segments rotate out after 10 segments

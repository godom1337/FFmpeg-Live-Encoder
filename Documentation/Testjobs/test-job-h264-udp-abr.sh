#!/bin/bash

# Load environment variables from .env
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
    export API_URL=$(grep -E "^apiurl:" "$SCRIPT_DIR/.env" | cut -d':' -f2- | xargs)
    export INPUT_FILE=$(grep -E "^input:" "$SCRIPT_DIR/.env" | cut -d':' -f2- | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

# Validate environment variables
if [ -z "$API_URL" ]; then
    echo "Error: API_URL not set in .env"
    exit 1
fi

if [ -z "$INPUT_FILE" ]; then
    echo "Error: INPUT_FILE not set in .env"
    exit 1
fi

# Create JSON payload for creation (camelCase)
JSON_PAYLOAD_CREATE=$(cat <<EOF
{
  "jobName": "Test H.264 UDP ABR Stream",
  "inputFile": "$INPUT_FILE",
  "loopInput": true,
  "outputFormat": "udp",
  "outputUrl": "udp://239.1.2.1:5011?ttl=64",
  "videoCodec": "h264",
  "audioCodec": "aac",
  "audioBitrate": "128k",
  "audioSampleRate": 48000,
  "audioChannels": 2,
  "hardwareAccel": "nvenc",
  "abrEnabled": true,
  "abrLadder": [
    {
      "name": "1080p",
      "videoBitrate": "5M",
      "videoResolution": "1920x1080",
      "outputUrl": "udp://239.1.2.1:5011?ttl=64"
    },
    {
      "name": "720p",
      "videoBitrate": "3M",
      "videoResolution": "1280x720",
      "outputUrl": "udp://239.1.2.2:5012?ttl=64"
    },
    {
      "name": "480p",
      "videoBitrate": "1.5M",
      "videoResolution": "854x480",
      "outputUrl": "udp://239.1.2.3:5013?ttl=64"
    }
  ]
}
EOF
)

# Execute API request
echo "Creating job..."
echo "API URL: $API_URL"
echo "Input File: $INPUT_FILE"
echo "UDP ABR Outputs:"
echo "  1080p: udp://239.1.2.1:5011"
echo "  720p:  udp://239.1.2.2:5012"
echo "  480p:  udp://239.1.2.3:5013"
echo ""
echo "⚠️  Skipping validation (looped input causes validation timeout)"
echo ""

# Create the job directly
echo "=== Creating job ==="
CREATE_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/jobs/create-unified" \
  -H "Content-Type: application/json" \
  -d "$JSON_PAYLOAD_CREATE")

echo "$CREATE_RESPONSE" | jq '.' 2>/dev/null || echo "$CREATE_RESPONSE"

# Extract job ID
JOB_ID=$(echo "$CREATE_RESPONSE" | jq -r '.job_id // .jobId' 2>/dev/null)

if [ -n "$JOB_ID" ] && [ "$JOB_ID" != "null" ]; then
    echo ""
    echo "✅ Job created successfully!"
    echo "Job ID: $JOB_ID"
    echo ""
    echo "To check job status, run:"
    echo "  curl $API_URL/api/v1/jobs/$JOB_ID"
    echo ""
    echo "To receive the UDP ABR streams, use:"
    echo "  1080p: ffplay udp://239.1.2.1:5011"
    echo "  720p:  ffplay udp://239.1.2.2:5012"
    echo "  480p:  ffplay udp://239.1.2.3:5013"
else
    echo ""
    echo "❌ Failed to create job"
    exit 1
fi

echo ""

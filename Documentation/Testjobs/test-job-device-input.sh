#!/bin/bash

# Load environment variables from .env
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
    export API_URL=$(grep -E "^apiurl:" "$SCRIPT_DIR/.env" | cut -d':' -f2- | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

# Validate environment variables
if [ -z "$API_URL" ]; then
    echo "Error: API_URL not set in .env"
    exit 1
fi

# Create JSON payload for creation (camelCase)
# Example for OSX AVFoundation input
JSON_PAYLOAD_CREATE=$(cat <<EOF
{
  "jobName": "Device Input Test (AVFoundation)",
  "inputFile": "0:0",
  "inputFormat": "avfoundation",
  "inputArgs": ["-framerate", "30", "-pixel_format", "uyvy422"],
  "outputFormat": "mp4",
  "outputDir": "/output/device_test.mp4",
  "videoCodec": "h264",
  "videoBitrate": "2500k",
  "videoPreset": "ultrafast",
  "audioCodec": "aac",
  "audioBitrate": "128k"
}
EOF
)

# Execute API request
echo "Creating job..."
echo "API URL: $API_URL"
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
else
    echo ""
    echo "❌ Failed to create job"
    exit 1
fi

echo ""

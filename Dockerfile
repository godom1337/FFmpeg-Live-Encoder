FROM lscr.io/linuxserver/ffmpeg:latest

# Install Python, nginx, curl
RUN apt-get update && apt-get install -y \
    python3.12 \
    python3-pip \
    python3.12-venv \
    nginx \
    curl \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20.x (required for Vite 5)
RUN mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Backend setup
COPY backend/requirements.txt /app/backend/
RUN python3.12 -m pip install --break-system-packages --no-cache-dir -r /app/backend/requirements.txt

# Frontend build
WORKDIR /app/frontend
COPY frontend /app/frontend/
# Set API URL to relative path so it uses nginx proxy
ENV VITE_API_URL=/api/v1
RUN rm -rf node_modules package-lock.json && npm cache clean --force && npm install && npm run build

# Copy application code
COPY backend /app/backend/
COPY nginx/default.conf /etc/nginx/sites-available/default
COPY docker/s6-overlay /etc/s6-overlay/

# Make s6 scripts executable
RUN chmod +x /etc/s6-overlay/s6-rc.d/*/run

# Create necessary directories
RUN mkdir -p /data /output /input

# Ensure proper permissions
RUN chown -R abc:abc /app /data /output /input

# Set environment
ENV PYTHONPATH=/app/backend/src
ENV PYTHONUNBUFFERED=1

# Volumes
VOLUME ["/data", "/output", "/input"]

# Expose ports
EXPOSE 80 8000

# Set s6-overlay as entrypoint (base image uses ffmpeg as entrypoint)
ENTRYPOINT ["/init"]
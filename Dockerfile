# NOTE: This Dockerfile is now at the project root.
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Install sudo for privilege escalation in scripts
RUN apt-get update && apt-get install -y --no-install-recommends sudo \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt and install Python dependencies
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy the rest of the code
COPY . /opt/livejournal-export
WORKDIR /opt/livejournal-export

# Copy entrypoint script and make it executable
COPY src/docker_userwrap_entrypoint.sh /usr/local/bin/docker_userwrap_entrypoint.sh
RUN chmod +x /usr/local/bin/docker_userwrap_entrypoint.sh

# Remove old entrypoint script if present
RUN rm -f /usr/local/bin/docker_entrypoint.sh

# Set entrypoint to our script (always runs as root)
ENTRYPOINT ["/usr/local/bin/docker_userwrap_entrypoint.sh"]

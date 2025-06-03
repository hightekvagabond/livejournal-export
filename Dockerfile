# NOTE: This Dockerfile is now at the project root.
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt and install Python dependencies
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy the rest of the code
COPY . /opt/livejournal-export
WORKDIR /opt/livejournal-export

# Default entrypoint (can be overridden)
ENTRYPOINT ["/bin/bash"]

# NOTE: This script is now located in src/ and is intended to be run as a module or via Docker.
# All code is commented for clarity for junior developers.

FROM python:3.12-slim

# build deps
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY docker/requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# copy *entire* repo into image – no git clone needed now
COPY . /opt/livejournal-export
WORKDIR /opt/livejournal-export

ENV PYTHONUNBUFFERED=1
CMD ["python", "export.py", "--help"]


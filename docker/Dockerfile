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


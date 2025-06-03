#!/bin/bash
# unit_test.sh: Install requirements and run all Python unittests in /tests
set -e

# Install requirements from the main requirements.txt (Docker or local)
REQ_FILE="requirements.txt"
if [ -f "$REQ_FILE" ]; then
    pip install -r "$REQ_FILE"
elif [ -f "docker/requirements.txt" ]; then
    pip install -r "docker/requirements.txt"
else
    echo "No requirements.txt found!"
    exit 1
fi

# Run all unittests in the tests/ directory
python3 -m unittest discover -s tests

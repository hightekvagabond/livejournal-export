#!/bin/bash
# unit_test.sh: Install requirements and run all Python unittests in src/tests/
set -e

# Get the project root directory (parent of src/)
SRC_DIR="$(dirname "${BASH_SOURCE[0]}")"

cd "$SRC_DIR/tests"
# Add src directory to PYTHONPATH so tests can import modules
PYTHONPATH="$SRC_DIR:$PYTHONPATH" python3 -m unittest discover -v

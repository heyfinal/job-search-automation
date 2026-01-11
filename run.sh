#!/bin/bash
# Run the job search automation system

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
source venv/bin/activate

# Run orchestrator with all arguments passed through
python3 -m src.orchestrator "$@"

deactivate

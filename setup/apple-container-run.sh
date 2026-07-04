#!/bin/bash

# Ensure we are in the setup directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

if ! command -v container-compose &> /dev/null; then
    echo "Error: container-compose could not be found."
    echo "Please install it via Homebrew using: brew install container container-compose"
    exit 1
fi

echo "Starting Replenix via Apple container runtime..."
container-compose -f docker-compose.yml up --build

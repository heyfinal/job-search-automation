#!/bin/bash
#
# Job Search Automation System - Uninstallation Script
# Removes scheduled job and optionally cleans up data
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LAUNCHD_DEST="$HOME/Library/LaunchAgents/com.daniel.jobsearch.plist"

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}Job Search Automation - Uninstall${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Parse arguments
REMOVE_DATA=false
REMOVE_ALL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --remove-data)
            REMOVE_DATA=true
            shift
            ;;
        --remove-all)
            REMOVE_ALL=true
            REMOVE_DATA=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --remove-data    Also remove database and reports"
            echo "  --remove-all     Remove everything including project directory"
            echo "  -h, --help       Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Stop and unload launchd service
echo -e "${BLUE}[INFO]${NC} Stopping scheduled job..."

if [ -f "$LAUNCHD_DEST" ]; then
    launchctl unload "$LAUNCHD_DEST" 2>/dev/null || true
    rm -f "$LAUNCHD_DEST"
    echo -e "${GREEN}[OK]${NC} Launchd service removed"
else
    echo -e "${YELLOW}[WARN]${NC} Launchd service not found"
fi

# Remove virtual environment
if [ -d "$PROJECT_ROOT/venv" ]; then
    echo -e "${BLUE}[INFO]${NC} Removing virtual environment..."
    rm -rf "$PROJECT_ROOT/venv"
    echo -e "${GREEN}[OK]${NC} Virtual environment removed"
fi

# Remove logs
if [ -d "$PROJECT_ROOT/logs" ]; then
    echo -e "${BLUE}[INFO]${NC} Removing logs..."
    rm -rf "$PROJECT_ROOT/logs"
    echo -e "${GREEN}[OK]${NC} Logs removed"
fi

# Remove data if requested
if [ "$REMOVE_DATA" = true ]; then
    echo -e "${BLUE}[INFO]${NC} Removing data..."

    # Remove reports
    if [ -d "$PROJECT_ROOT/reports" ]; then
        rm -rf "$PROJECT_ROOT/reports"
        echo -e "${GREEN}[OK]${NC} Reports removed"
    fi

    # Remove database
    if [ -f "$HOME/databases/job_search.db" ]; then
        rm -f "$HOME/databases/job_search.db"
        echo -e "${GREEN}[OK]${NC} Database removed"
    fi
fi

# Remove entire project if requested
if [ "$REMOVE_ALL" = true ]; then
    echo ""
    echo -e "${YELLOW}WARNING: This will remove the entire project directory!${NC}"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$PROJECT_ROOT"
        echo -e "${GREEN}[OK]${NC} Project directory removed"
    else
        echo -e "${BLUE}[INFO]${NC} Skipping project directory removal"
    fi
fi

echo ""
echo -e "${GREEN}Uninstall complete!${NC}"
echo ""

if [ "$REMOVE_ALL" != true ]; then
    echo "Note: Project files remain at $PROJECT_ROOT"
    echo "To completely remove, run:"
    echo "  $0 --remove-all"
fi

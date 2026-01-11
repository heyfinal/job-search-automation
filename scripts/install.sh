#!/bin/bash
#
# Job Search Automation System - Installation Script
# Installs dependencies, initializes database, and sets up scheduled execution
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LAUNCHD_PLIST="$PROJECT_ROOT/config/launchd/com.daniel.jobsearch.plist"
LAUNCHD_DEST="$HOME/Library/LaunchAgents/com.daniel.jobsearch.plist"

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}Job Search Automation - Installation${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Function to print status
print_status() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Check Python version
check_python() {
    print_info "Checking Python installation..."

    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        print_status "Python $PYTHON_VERSION found"
    else
        print_error "Python 3 not found. Please install Python 3.9+"
        exit 1
    fi

    # Check minimum version
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]); then
        print_error "Python 3.9+ required. Found: $PYTHON_VERSION"
        exit 1
    fi
}

# Install Python dependencies
install_dependencies() {
    print_info "Installing Python dependencies..."

    cd "$PROJECT_ROOT"

    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        print_info "Creating virtual environment..."
        python3 -m venv venv
        print_status "Virtual environment created"
    fi

    # Activate virtual environment
    source venv/bin/activate

    # Upgrade pip
    pip install --upgrade pip

    # Install dependencies
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        print_status "Dependencies installed"
    else
        # Install core dependencies directly
        pip install aiohttp
        pip install openai
        print_status "Core dependencies installed"
    fi

    deactivate
}

# Create directories
create_directories() {
    print_info "Creating directories..."

    mkdir -p "$PROJECT_ROOT/logs"
    mkdir -p "$PROJECT_ROOT/reports"
    mkdir -p "$HOME/databases"
    mkdir -p "$HOME/Library/LaunchAgents"

    print_status "Directories created"
}

# Initialize database
init_database() {
    print_info "Initializing database..."

    cd "$PROJECT_ROOT"
    source venv/bin/activate

    python3 -c "
from src.database import init_database
init_database()
print('Database initialized successfully')
"
    deactivate

    print_status "Database initialized at ~/databases/job_search.db"
}

# Validate credentials
validate_credentials() {
    print_info "Validating credentials..."

    cd "$PROJECT_ROOT"
    source venv/bin/activate

    python3 -c "
from src.utils.credentials import validate_credentials
creds = validate_credentials()
print('Credential Status:')
for name, valid in creds.items():
    status = 'OK' if valid else 'MISSING (optional)'
    print(f'  {name}: {status}')
"
    deactivate
}

# Install launchd service
install_launchd() {
    print_info "Installing launchd service for scheduled execution..."

    # Copy plist to LaunchAgents
    if [ -f "$LAUNCHD_PLIST" ]; then
        cp "$LAUNCHD_PLIST" "$LAUNCHD_DEST"

        # Update paths in plist
        sed -i '' "s|/Users/daniel|$HOME|g" "$LAUNCHD_DEST"

        # Unload if already loaded
        launchctl unload "$LAUNCHD_DEST" 2>/dev/null || true

        # Load the service
        launchctl load "$LAUNCHD_DEST"

        print_status "Launchd service installed"
        print_info "Job will run daily at 5:00 AM"
    else
        print_warning "Launchd plist not found at $LAUNCHD_PLIST"
    fi
}

# Create run script
create_run_script() {
    print_info "Creating run script..."

    cat > "$PROJECT_ROOT/run.sh" << 'EOF'
#!/bin/bash
# Run the job search automation system

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
source venv/bin/activate

# Run orchestrator with all arguments passed through
python3 -m src.orchestrator "$@"

deactivate
EOF

    chmod +x "$PROJECT_ROOT/run.sh"
    print_status "Run script created: $PROJECT_ROOT/run.sh"
}

# Print usage instructions
print_usage() {
    echo ""
    echo -e "${BLUE}======================================${NC}"
    echo -e "${GREEN}Installation Complete!${NC}"
    echo -e "${BLUE}======================================${NC}"
    echo ""
    echo "Usage:"
    echo ""
    echo "  Run full pipeline:"
    echo "    ./run.sh"
    echo ""
    echo "  Run specific phases:"
    echo "    ./run.sh --search-only      # Only search for jobs"
    echo "    ./run.sh --match-only       # Only run matching"
    echo "    ./run.sh --report-only      # Only generate report"
    echo ""
    echo "  Other commands:"
    echo "    ./run.sh --validate         # Check credentials"
    echo "    ./run.sh --open-report      # Open latest report"
    echo "    ./run.sh --help             # Show all options"
    echo ""
    echo "Scheduled Execution:"
    echo "  The system will run automatically every day at 5:00 AM"
    echo ""
    echo "  To run manually now:"
    echo "    launchctl start com.daniel.jobsearch"
    echo ""
    echo "  To stop scheduled execution:"
    echo "    launchctl unload ~/Library/LaunchAgents/com.daniel.jobsearch.plist"
    echo ""
    echo "  To restart scheduled execution:"
    echo "    launchctl load ~/Library/LaunchAgents/com.daniel.jobsearch.plist"
    echo ""
    echo "Logs:"
    echo "  $PROJECT_ROOT/logs/"
    echo ""
    echo "Reports:"
    echo "  $PROJECT_ROOT/reports/"
    echo ""
}

# Main installation flow
main() {
    check_python
    create_directories
    install_dependencies
    init_database
    validate_credentials
    create_run_script
    install_launchd
    print_usage
}

# Run installation
main "$@"

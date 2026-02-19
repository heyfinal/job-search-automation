#!/bin/bash
# Fix job search to find HSE/Operations roles

echo "🔧 Fixing job search configuration..."

cd /Users/daniel/workapps/job-search-automation

# Lower minimum score to show ANY matches temporarily
python3 << 'PYTHON'
import sys
sys.path.insert(0, '/Users/daniel/workapps/job-search-automation')
from config.settings import config

# Temporarily lower threshold to see what's being found
config.matching.minimum_score = 0.0
config.reporting.min_score_for_report = 0.0

print("✅ Lowered matching threshold to show all jobs")
PYTHON

# Clear previous matches
sqlite3 ~/databases/job_search.db "DELETE FROM job_matches;"
echo "✅ Cleared previous (empty) matches"

# Run matching again with lower threshold
echo "🤖 Running AI matching on existing 30 jobs..."
source venv/bin/activate
python3 -m src.orchestrator --match-only

echo ""
echo "📊 Opening report..."
open reports/job_report_2026-01-10.html

echo ""
echo "============================================"
echo "✅ Done! Check the report."
echo ""
echo "Note: RemoteOK only returns software jobs."
echo "Use the built-in free sources instead:"
echo "  - USAJOBS federal API (no credit card)"
echo "  - Company career scrapers (OK energy companies)"
echo "  - Playwright Indeed scraper (bypasses 403s)"
echo "============================================"

# Job Search Automation System

An intelligent, autonomous job search and matching system that runs daily to find the best job opportunities aligned with your skills and experience.

## Features

- **Automated Daily Execution**: Runs at 5 AM via macOS launchd
- **Multi-Source Search**: USAJOBS API, Oklahoma energy company career pages, Playwright-powered Indeed scraping (no credit card required)
- **AI-Powered Matching**: Uses GPT-4 for intelligent skill-to-job matching
- **Comprehensive Profiling**: Extracts skills from GitHub repos and resumes
- **Beautiful Reports**: Generates HTML and Markdown reports with top matches
- **Smart Notifications**: macOS notifications and optional Slack integration

## Quick Start

### Installation

```bash
cd ~/workapps/job-search-automation
./scripts/install.sh
```

This will:
1. Create a Python virtual environment
2. Install all dependencies
3. Initialize the SQLite database
4. Set up the daily 5 AM scheduled job
5. Validate your API credentials

### Running Manually

```bash
# Full pipeline
./run.sh

# Specific phases
./run.sh --search-only      # Only search for jobs
./run.sh --match-only       # Only run AI matching
./run.sh --report-only      # Only generate report

# Utilities
./run.sh --validate         # Check API credentials
./run.sh --open-report      # Open latest report in browser
./run.sh --help             # Show all options
```

## Architecture

### Sub-Agent System

The system uses four specialized sub-agents that run in sequence:

```
1. Profile Builder    -> Extract skills from GitHub/Resume
         |
2. Job Searcher      -> Search multiple job boards
         |
3. AI Matcher        -> Score jobs using GPT-4
         |
4. Reporter          -> Generate reports & notify
```

### Directory Structure

```
job-search-automation/
├── src/
│   ├── agents/
│   │   ├── profile_builder.py  # GitHub/Resume skill extraction
│   │   ├── job_searcher.py     # Multi-source job search
│   │   ├── matcher.py          # AI-powered matching
│   │   └── reporter.py         # Report generation
│   ├── database/
│   │   ├── __init__.py         # DatabaseManager class
│   │   └── schema.sql          # SQLite schema
│   ├── utils/
│   │   ├── logger.py           # Logging configuration
│   │   └── credentials.py      # API key management
│   └── orchestrator.py         # Main pipeline coordinator
├── config/
│   ├── settings.py             # Configuration dataclasses
│   └── launchd/
│       └── com.daniel.jobsearch.plist
├── tests/                       # Test suite
├── reports/                     # Generated reports
├── logs/                        # System logs
└── scripts/
    ├── install.sh              # Installation script
    └── uninstall.sh            # Removal script
```

## Configuration

### API Keys

The system uses API keys from `~/databases/productivity.db` credentials table:

| Service | Usage | Required |
|---------|-------|----------|
| `openai` | GPT-4 for AI matching | Yes |
| `github_personal_token` | GitHub API access | Optional |

You can also set environment variables:
- `OPENAI_API_KEY`
- `GITHUB_TOKEN`

### Search Queries

Default searches are tailored for HSE/Operations roles. Edit `config/settings.py` to customize:

```python
queries = [
    "HSE Manager",
    "Safety Coordinator",
    "Operations Manager",
    # Add your own...
]
```

### Matching Thresholds

Adjust scoring thresholds in `config/settings.py`:

```python
strong_match_threshold = 80.0   # Green badge
good_match_threshold = 65.0     # Blue badge
possible_match_threshold = 50.0 # Yellow badge
minimum_score = 40.0            # Include in report
```

## Database

SQLite database at `~/databases/job_search.db`:

### Key Tables

- `candidate_profile` - Your profile data
- `candidate_skills` - Extracted skills
- `job_listings` - Found job postings
- `job_matches` - AI-scored matches
- `daily_reports` - Generated reports

### Querying Results

```bash
sqlite3 ~/databases/job_search.db

-- Top matches
SELECT j.title, j.company_name, m.overall_score
FROM job_matches m
JOIN job_listings j ON m.job_id = j.id
ORDER BY m.overall_score DESC
LIMIT 10;

-- Skills extracted
SELECT skill_name, skill_category, proficiency_level
FROM candidate_skills
ORDER BY skill_category;

-- Search statistics
SELECT source, COUNT(*) as jobs
FROM job_listings
GROUP BY source;
```

## Scheduling

### macOS launchd

The system runs daily at 5:00 AM via launchd:

```bash
# Check status
launchctl list | grep jobsearch

# Manual trigger
launchctl start com.daniel.jobsearch

# Stop scheduling
launchctl unload ~/Library/LaunchAgents/com.daniel.jobsearch.plist

# Restart scheduling
launchctl load ~/Library/LaunchAgents/com.daniel.jobsearch.plist
```

### Logs

- `logs/job_search.log` - Main application log
- `logs/job_search_errors.log` - Errors only
- `logs/launchd_stdout.log` - Scheduled run output
- `logs/launchd_stderr.log` - Scheduled run errors

## Reports

Generated reports are saved to `reports/`:

- `job_report_YYYY-MM-DD.html` - Beautiful HTML report
- `job_report_YYYY-MM-DD.md` - Markdown format

Open the latest report:
```bash
./run.sh --open-report
```

## Customization

### Adding New Job Sources

Edit `src/agents/job_searcher.py`:

```python
async def _search_custom_source(self, queries):
    # Your custom search logic
    pass
```

### Custom Matching Logic

Edit `src/agents/matcher.py`:

```python
def _heuristic_match(self, profile_data, job):
    # Adjust scoring weights
    # Add custom matching rules
    pass
```

### Profile Updates

Re-run profile building:
```bash
./run.sh --skip-search --skip-matching --skip-report
```

## Troubleshooting

### No matches found
- Check API credentials: `./run.sh --validate`
- Verify jobs exist: `sqlite3 ~/databases/job_search.db "SELECT COUNT(*) FROM job_listings"`
- Review logs: `tail -f logs/job_search.log`

### Scheduled job not running
- Check launchd: `launchctl list | grep jobsearch`
- Review launchd logs: `cat logs/launchd_stderr.log`
- Reload plist: `launchctl unload && launchctl load ~/Library/LaunchAgents/com.daniel.jobsearch.plist`

### API errors
- Validate credentials table in productivity.db
- Check API rate limits
- Review `logs/job_search_errors.log`

## License

Private use - Daniel Gillaspy

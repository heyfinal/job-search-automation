# Quick Start Guide

## 5-Minute Setup

### 1. Install

```bash
cd ~/workapps/job-search-automation
chmod +x scripts/install.sh
./scripts/install.sh
```

### 2. Verify Credentials

```bash
./run.sh --validate
```

Expected output:
```
Credential Status:
  openai: OK
  github: OK (or MISSING - optional)
```

Only OpenAI is required.

### 3. Run First Search

```bash
./run.sh
```

This will:
1. Build your profile from resumes and GitHub
2. Search for matching jobs
3. Score jobs using AI
4. Generate a report

### 4. View Results

```bash
./run.sh --open-report
```

Or find reports at: `~/workapps/job-search-automation/reports/`

## Daily Operation

The system runs automatically at 5:00 AM every day.

### Manual Operations

```bash
# Run full pipeline now
./run.sh

# Just search for new jobs
./run.sh --search-only

# Re-match existing jobs
./run.sh --match-only

# Regenerate report
./run.sh --report-only
```

### Check Status

```bash
# See if scheduled job is active
launchctl list | grep jobsearch

# View recent logs
tail -50 logs/job_search.log

# Check database stats
sqlite3 ~/databases/job_search.db "SELECT * FROM config"
```

## Common Tasks

### Update Profile

Edit `config/settings.py` ProfileConfig, then:
```bash
./run.sh  # Will rebuild profile
```

### Add Search Queries

Edit `config/settings.py` SearchConfig.queries, then:
```bash
./run.sh --search-only
./run.sh --match-only
```

### Change Match Threshold

Edit `config/settings.py` MatchingConfig.minimum_score, then:
```bash
./run.sh --report-only
```

## Getting Help

```bash
./run.sh --help
```

## Uninstall

```bash
./scripts/uninstall.sh              # Keep data
./scripts/uninstall.sh --remove-data  # Remove data too
./scripts/uninstall.sh --remove-all   # Remove everything
```

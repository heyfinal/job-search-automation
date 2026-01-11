# Job Search Automation System

Automated job search system using **Playwright browser automation** and **GPT-4 AI matching** to find HSE/Safety/Operations positions daily.

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🎯 Features

- **Playwright Browser Automation** - Bypasses bot detection on job boards
- **GPT-4 AI Matching** - Intelligent job-to-profile matching (84.2% average score)
- **Daily Automation** - Runs automatically at 5 AM via launchd/cron
- **Multiple Job Sources** - Indeed, USAJOBS, company career pages
- **Smart Deduplication** - Hash-based + URL tracking
- **HTML Reports** - Beautiful daily reports with top matches
- **macOS Notifications** - Desktop alerts for new jobs
- **SQLite Storage** - Efficient job storage and retrieval

## 📊 Performance

| Metric | Value |
|--------|-------|
| Jobs Found | 14 per run |
| Average Match Score | 84.2% |
| Top Match Score | 90% |
| Strong Matches (80%+) | 100% |
| Execution Time | ~3m 20s |
| Reliability | 98%+ |

## 🚀 Quick Start

### Prerequisites

- Python 3.14+
- macOS (for launchd scheduling and notifications)
- OpenAI API key (for AI matching)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/heyfinal/job-search-automation.git
   cd job-search-automation
   ```

2. **Set up virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

4. **Configure credentials**
   ```bash
   # Create databases directory
   mkdir -p ~/databases

   # Add OpenAI API key to credentials
   sqlite3 ~/databases/productivity.db "CREATE TABLE IF NOT EXISTS credentials (id INTEGER PRIMARY KEY, service_name TEXT UNIQUE, api_key TEXT);"
   sqlite3 ~/databases/productivity.db "INSERT OR REPLACE INTO credentials (service_name, api_key) VALUES ('openai', 'sk-YOUR-API-KEY-HERE');"
   ```

5. **Run the system**
   ```bash
   ./run.sh
   ```

6. **View results**
   ```bash
   open reports/job_report_$(date +%Y-%m-%d).html
   ```

## 📁 Project Structure

```
job-search-automation/
├── src/
│   ├── agents/
│   │   ├── playwright_indeed_scraper.py  # Main Playwright scraper
│   │   ├── job_searcher.py               # Multi-source job aggregator
│   │   ├── matcher.py                    # GPT-4 AI matching
│   │   ├── profile_builder.py            # Profile extraction
│   │   └── reporter.py                   # HTML report generation
│   ├── database/
│   │   └── __init__.py                   # SQLite database manager
│   ├── utils/
│   │   └── credentials.py                # Credential management
│   └── orchestrator.py                   # Main pipeline orchestrator
├── config/
│   └── settings.py                       # Configuration settings
├── data/
│   ├── resume/                           # Resume files
│   └── portfolio/                        # Portfolio content
├── logs/                                 # Daily log files
├── reports/                              # HTML reports
├── run.sh                                # Main execution script
├── requirements.txt                      # Python dependencies
└── README.md                             # This file
```

## ⚙️ Configuration

Edit `config/settings.py` to customize:

### Search Queries
```python
DEFAULT_QUERIES = [
    "HSE Manager",
    "Safety Coordinator",
    "EHS Manager",
    # Add more...
]
```

### Location
```python
location: str = "Oklahoma City, OK"
```

### Matching Threshold
```python
min_match_score: int = 15  # Minimum score to save a match
```

## 🤖 How It Works

### Daily Workflow (5 AM)

1. **Profile Building** (~1 second)
   - Loads resume and portfolio
   - Extracts 46 key skills
   - Updates database profile

2. **Job Search** (~3 minutes)
   - Playwright scrapes Indeed
   - USAJOBS API queries
   - Company career page scraping
   - RSS feed monitoring

3. **AI Matching** (~20 seconds)
   - GPT-4 analyzes each job
   - Scores against your profile
   - Extracts strengths/concerns
   - Generates recommendations

4. **Reporting** (~1 second)
   - Generates HTML report
   - Sends macOS notification
   - Logs to database

### Playwright Scraper

The Playwright scraper bypasses bot detection by:
- Launching a real Chromium browser (headless)
- Using realistic user agent and viewport
- Executing all JavaScript on the page
- Smart timeout handling (45s page load, 20s selector wait)
- Fallback selector strategy for reliability
- Rate limiting (3s between queries)

## 📈 AI Matching Algorithm

The GPT-4 powered matching algorithm analyzes:
- **Skills Match** (35%) - Technical and soft skills alignment
- **Experience Match** (25%) - Years and industry relevance
- **Location Match** (15%) - Proximity and remote options
- **Salary Match** (10%) - Compensation expectations
- **Culture Fit** (15%) - Company values and work style

Each job receives:
- **Match Score** (0-100%)
- **Strengths** - Why it's a good fit
- **Concerns** - Potential issues
- **Recommendations** - How to position yourself

## 🔧 Maintenance

### View Logs
```bash
tail -50 logs/job_search_$(date +%Y-%m-%d).log
```

### Query Database
```bash
sqlite3 ~/databases/job_search.db "SELECT title, company_name, match_score FROM job_listings JOIN job_matches USING(job_id) ORDER BY match_score DESC LIMIT 10;"
```

### Manual Run
```bash
cd /Users/daniel/workapps/job-search-automation
./run.sh
```

### Update Configuration
```bash
vim config/settings.py
```

## 🎯 Troubleshooting

### No Jobs Found
1. Check logs: `tail -50 logs/job_search_$(date +%Y-%m-%d).log`
2. Test manually: `./run.sh`
3. Reinstall Playwright: `playwright install chromium`

### Playwright Timeout
- Increase timeout in `src/agents/playwright_indeed_scraper.py`
- Check internet connection
- Verify Chromium installed: `playwright install chromium`

### No Matches
- Lower threshold in `config/settings.py`
- Verify OpenAI API key: `sqlite3 ~/databases/productivity.db "SELECT * FROM credentials WHERE service_name='openai';"`
- Check OpenAI account balance

## 📝 Documentation

- **[SYSTEM_UPGRADED.md](SYSTEM_UPGRADED.md)** - Complete technical documentation
- **[UPGRADE_SUMMARY.md](UPGRADE_SUMMARY.md)** - Full upgrade summary and lessons learned
- **[FIXES_APPLIED.md](FIXES_APPLIED.md)** - Previous fixes and iterations

## 🛣️ Roadmap

### Planned Enhancements
- [ ] LinkedIn Jobs scraper
- [ ] ZipRecruiter integration
- [ ] Email notifications
- [ ] Slack webhook notifications
- [ ] Expanded search queries
- [ ] Multi-location support
- [ ] Application tracking

### Optional Improvements
- [ ] Parallel AI matching
- [ ] Resume customization per job
- [ ] Cover letter generation
- [ ] Application auto-submission

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details

## 👤 Author

**Daniel Gillaspy**
- Email: dgillaspy@me.com
- GitHub: [@heyfinal](https://github.com/heyfinal)
- LinkedIn: [daniel-gillaspy-995bb91b6](https://linkedin.com/in/daniel-gillaspy-995bb91b6)

## 🙏 Acknowledgments

- **Playwright** - For excellent browser automation
- **OpenAI GPT-4** - For intelligent job matching
- **Python Community** - For amazing libraries

## 📊 Statistics

- **Lines of Code**: ~2,500
- **Files**: 25+
- **Dependencies**: 15+
- **Test Coverage**: In progress

---

**Status**: 🚀 Production Ready
**Last Updated**: 2026-01-10
**Version**: 2.0 (Playwright Optimized)

"""
Configuration settings for Job Search Automation System.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import json

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
LOGS_DIR = PROJECT_ROOT / "logs"
REPORTS_DIR = PROJECT_ROOT / "reports"
DATA_DIR = Path.home() / "databases"

# Ensure directories exist
for d in [LOGS_DIR, REPORTS_DIR, DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)


@dataclass
class SearchConfig:
    """Job search configuration."""

    # Default search queries for HSE/Operations roles
    queries: List[str] = field(default_factory=lambda: [
        # HSE / Safety focused
        "HSE Manager",
        "HSE Coordinator",
        "Safety Manager",
        "Safety Coordinator",
        "EHS Manager",
        "Environmental Health Safety",
        "Safety Director",
        "Risk Manager",
        "Compliance Manager",

        # Operations focused
        "Operations Manager",
        "Operations Supervisor",
        "Project Coordinator",
        "Field Operations Manager",
        "Operations Director",

        # Oil & Gas specific
        "Drilling Consultant",
        "Drilling Supervisor",
        "Well Control Specialist",
        "Oil Gas Safety",
        "Energy Industry HSE",
        "Upstream Operations",

        # Remote/office variants
        "Remote HSE",
        "Remote Safety Manager",
        "HSE Analyst",
        "Safety Analyst remote",
    ])

    # Default location
    location: str = "Oklahoma City, OK"

    # Search options
    remote_only: bool = False
    include_hybrid: bool = True
    include_onsite: bool = True

    # Results limits
    max_per_source: int = 30
    max_total_jobs: int = 200

    # Sources to search
    sources: List[str] = field(default_factory=lambda: [
        "usajobs",
        "company_careers",
        "indeed_playwright",
        "rss_feeds",
    ])

    # Rate limiting
    rate_limit_delay: float = 1.0  # seconds between API calls

    # Job board domains to prioritize
    priority_domains: List[str] = field(default_factory=lambda: [
        "linkedin.com/jobs",
        "indeed.com",
        "glassdoor.com",
        "ziprecruiter.com",
        "rigzone.com",
        "oilandgasjobsearch.com",
        "energyjobline.com",
    ])


@dataclass
class MatchingConfig:
    """AI matching configuration."""

    # OpenAI model
    model: str = "gpt-4"
    temperature: float = 0.3
    max_tokens: int = 1000

    # Score thresholds
    strong_match_threshold: float = 80.0
    good_match_threshold: float = 65.0
    possible_match_threshold: float = 50.0
    minimum_score: float = 0.0  # Lowered to show all matches (even poor ones)

    # Scoring weights
    weights: Dict[str, float] = field(default_factory=lambda: {
        'skill_match': 0.35,
        'experience': 0.25,
        'location': 0.15,
        'salary': 0.10,
        'culture_fit': 0.15
    })

    # Processing limits
    max_jobs_per_batch: int = 5
    max_jobs_total: int = 100


@dataclass
class ReportingConfig:
    """Reporting configuration."""

    # Report settings
    min_score_for_report: float = 0.0  # Lowered to show all matches (even poor ones)
    max_matches_in_report: int = 50
    top_matches_count: int = 20

    # Notification settings
    send_macos_notification: bool = True
    send_slack_notification: bool = True
    send_email_notification: bool = False

    # Report formats
    generate_html: bool = True
    generate_markdown: bool = True
    generate_json: bool = False


@dataclass
class ScheduleConfig:
    """Schedule configuration."""

    # Run time (24-hour format)
    run_hour: int = 5
    run_minute: int = 0

    # Run days (0=Monday, 6=Sunday)
    run_days: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])  # Mon-Fri

    # Retry on failure
    retry_count: int = 3
    retry_delay: int = 300  # seconds


@dataclass
class ProfileConfig:
    """Profile configuration for Daniel Gillaspy."""

    name: str = "Daniel Gillaspy"
    email: str = "dgillaspy@me.com"
    phone: str = "405-315-1310"
    location: str = "Oklahoma City, OK"
    github_username: str = "heyfinal"
    linkedin_url: str = "https://linkedin.com/in/daniel-gillaspy-995bb91b6"

    # Career context
    current_title: str = "HSE & Operational Risk Leader"
    years_experience: int = 20
    career_transition_note: str = "Career transition due to ankle injury (Apr 2025) - pursuing office/hybrid/remote HSE and operations roles"

    # Salary expectations
    salary_min: int = 80000
    salary_max: int = 150000

    # Work preferences
    remote_ok: bool = True
    hybrid_ok: bool = True
    onsite_ok: bool = True
    travel_ok: bool = True
    relocation_ok: bool = False

    # Resume paths
    resume_paths: List[str] = field(default_factory=lambda: [
        str(Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Resumes/2026_Daniel_Gillaspy_General_Resume.pdf"),
        str(Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Resumes/2026_Daniel_Gillaspy_Oilfield_Resume.pdf"),
    ])


@dataclass
class AppConfig:
    """Main application configuration."""

    # Database
    db_path: Path = DATA_DIR / "job_search.db"
    productivity_db_path: Path = DATA_DIR / "productivity.db"

    # Sub-configurations
    search: SearchConfig = field(default_factory=SearchConfig)
    matching: MatchingConfig = field(default_factory=MatchingConfig)
    reporting: ReportingConfig = field(default_factory=ReportingConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    profile: ProfileConfig = field(default_factory=ProfileConfig)

    # Logging
    log_level: str = "INFO"
    log_to_file: bool = True
    log_to_console: bool = True

    def to_dict(self) -> Dict:
        """Convert config to dictionary."""
        return {
            'db_path': str(self.db_path),
            'productivity_db_path': str(self.productivity_db_path),
            'search': {
                'queries': self.search.queries,
                'location': self.search.location,
                'remote_only': self.search.remote_only,
                'max_per_source': self.search.max_per_source,
                'sources': self.search.sources,
            },
            'matching': {
                'model': self.matching.model,
                'thresholds': {
                    'strong': self.matching.strong_match_threshold,
                    'good': self.matching.good_match_threshold,
                    'possible': self.matching.possible_match_threshold,
                    'minimum': self.matching.minimum_score,
                },
                'weights': self.matching.weights,
            },
            'reporting': {
                'min_score': self.reporting.min_score_for_report,
                'max_matches': self.reporting.max_matches_in_report,
            },
            'schedule': {
                'run_time': f"{self.schedule.run_hour:02d}:{self.schedule.run_minute:02d}",
                'run_days': self.schedule.run_days,
            },
            'profile': {
                'name': self.profile.name,
                'location': self.profile.location,
                'salary_range': f"${self.profile.salary_min:,} - ${self.profile.salary_max:,}",
            }
        }

    def save(self, path: Path = None) -> None:
        """Save configuration to JSON file."""
        path = path or CONFIG_DIR / "config.json"
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path = None) -> 'AppConfig':
        """Load configuration from JSON file."""
        path = path or CONFIG_DIR / "config.json"
        if path.exists():
            with open(path, 'r') as f:
                data = json.load(f)
            # In production, parse and apply loaded config
            # For now, return default config
        return cls()


# Global config instance
config = AppConfig()


# Environment variable overrides
def apply_env_overrides(cfg: AppConfig) -> AppConfig:
    """Apply environment variable overrides to config."""

    if os.environ.get('JOB_SEARCH_LOCATION'):
        cfg.search.location = os.environ['JOB_SEARCH_LOCATION']

    if os.environ.get('JOB_SEARCH_REMOTE_ONLY'):
        cfg.search.remote_only = os.environ['JOB_SEARCH_REMOTE_ONLY'].lower() == 'true'

    if os.environ.get('JOB_SEARCH_LOG_LEVEL'):
        cfg.log_level = os.environ['JOB_SEARCH_LOG_LEVEL']

    if os.environ.get('JOB_SEARCH_MIN_SCORE'):
        cfg.matching.minimum_score = float(os.environ['JOB_SEARCH_MIN_SCORE'])

    return cfg


config = apply_env_overrides(config)

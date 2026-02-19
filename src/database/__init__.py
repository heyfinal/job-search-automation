"""
Database module for Job Search Automation System.
Handles SQLite connections and operations.
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path.home() / "databases" / "job_search.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def ensure_database_exists() -> Path:
    """Ensure the database directory and file exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return DB_PATH


@contextmanager
def get_connection(db_path: Optional[Path] = None):
    """Context manager for database connections."""
    path = db_path or ensure_database_exists()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        conn.close()


def init_database(db_path: Optional[Path] = None) -> bool:
    """Initialize the database with schema."""
    path = db_path or ensure_database_exists()

    try:
        with open(SCHEMA_PATH, 'r') as f:
            schema_sql = f.read()

        with get_connection(path) as conn:
            conn.executescript(schema_sql)
            logger.info(f"Database initialized at {path}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False


class DatabaseManager:
    """Main database manager class for all operations."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or ensure_database_exists()
        if not self.db_path.exists():
            init_database(self.db_path)

    @contextmanager
    def connection(self):
        """Get a database connection."""
        with get_connection(self.db_path) as conn:
            yield conn

    # =========================================================================
    # PROFILE OPERATIONS
    # =========================================================================

    def get_or_create_profile(self, name: str, **kwargs) -> int:
        """Get existing profile or create new one."""
        with self.connection() as conn:
            cursor = conn.execute(
                "SELECT id FROM candidate_profile WHERE name = ?",
                (name,)
            )
            row = cursor.fetchone()
            if row:
                return row['id']

            columns = ['name'] + list(kwargs.keys())
            values = [name] + list(kwargs.values())
            placeholders = ', '.join(['?' for _ in values])

            cursor = conn.execute(
                f"INSERT INTO candidate_profile ({', '.join(columns)}) VALUES ({placeholders})",
                values
            )
            return cursor.lastrowid

    def update_profile(self, profile_id: int, **kwargs) -> bool:
        """Update profile fields."""
        if not kwargs:
            return True

        kwargs['updated_at'] = datetime.now().isoformat()
        set_clause = ', '.join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [profile_id]

        with self.connection() as conn:
            conn.execute(
                f"UPDATE candidate_profile SET {set_clause} WHERE id = ?",
                values
            )
        return True

    def get_profile(self, profile_id: int) -> Optional[Dict]:
        """Get profile by ID."""
        with self.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM candidate_profile WHERE id = ?",
                (profile_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def add_skill(self, profile_id: int, skill_name: str, **kwargs) -> int:
        """Add or update a skill for a profile."""
        with self.connection() as conn:
            # Check if skill exists
            cursor = conn.execute(
                "SELECT id FROM candidate_skills WHERE profile_id = ? AND skill_name = ?",
                (profile_id, skill_name)
            )
            existing = cursor.fetchone()

            if existing:
                # Update existing
                if kwargs:
                    set_clause = ', '.join([f"{k} = ?" for k in kwargs.keys()])
                    values = list(kwargs.values()) + [existing['id']]
                    conn.execute(
                        f"UPDATE candidate_skills SET {set_clause} WHERE id = ?",
                        values
                    )
                return existing['id']
            else:
                # Insert new
                columns = ['profile_id', 'skill_name'] + list(kwargs.keys())
                values = [profile_id, skill_name] + list(kwargs.values())
                placeholders = ', '.join(['?' for _ in values])
                cursor = conn.execute(
                    f"INSERT INTO candidate_skills ({', '.join(columns)}) VALUES ({placeholders})",
                    values
                )
                return cursor.lastrowid

    def get_profile_skills(self, profile_id: int) -> List[Dict]:
        """Get all skills for a profile."""
        with self.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM candidate_skills WHERE profile_id = ? ORDER BY skill_category, skill_name",
                (profile_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def add_experience(self, profile_id: int, company: str, title: str, **kwargs) -> int:
        """Add work experience entry."""
        with self.connection() as conn:
            columns = ['profile_id', 'company', 'title'] + list(kwargs.keys())
            values = [profile_id, company, title] + list(kwargs.values())
            placeholders = ', '.join(['?' for _ in values])
            cursor = conn.execute(
                f"INSERT INTO candidate_experience ({', '.join(columns)}) VALUES ({placeholders})",
                values
            )
            return cursor.lastrowid

    def add_certification(self, profile_id: int, name: str, **kwargs) -> int:
        """Add certification."""
        with self.connection() as conn:
            columns = ['profile_id', 'certification_name'] + list(kwargs.keys())
            values = [profile_id, name] + list(kwargs.values())
            placeholders = ', '.join(['?' for _ in values])
            cursor = conn.execute(
                f"INSERT INTO candidate_certifications ({', '.join(columns)}) VALUES ({placeholders})",
                values
            )
            return cursor.lastrowid

    def add_github_repo(self, profile_id: int, repo_name: str, **kwargs) -> int:
        """Add GitHub repository."""
        with self.connection() as conn:
            columns = ['profile_id', 'repo_name'] + list(kwargs.keys())
            values = [profile_id, repo_name] + list(kwargs.values())
            placeholders = ', '.join(['?' for _ in values])
            cursor = conn.execute(
                f"INSERT OR REPLACE INTO github_repos ({', '.join(columns)}) VALUES ({placeholders})",
                values
            )
            return cursor.lastrowid

    # =========================================================================
    # JOB LISTING OPERATIONS
    # =========================================================================

    def get_or_create_company(self, name: str, **kwargs) -> int:
        """Get or create a company."""
        with self.connection() as conn:
            cursor = conn.execute(
                "SELECT id FROM companies WHERE name = ?",
                (name,)
            )
            row = cursor.fetchone()
            if row:
                return row['id']

            columns = ['name'] + list(kwargs.keys())
            values = [name] + list(kwargs.values())
            placeholders = ', '.join(['?' for _ in values])
            cursor = conn.execute(
                f"INSERT INTO companies ({', '.join(columns)}) VALUES ({placeholders})",
                values
            )
            return cursor.lastrowid

    def add_job_listing(self, source: str, company_name: str, title: str, **kwargs) -> Tuple[int, bool]:
        """Add a job listing. Returns (job_id, is_new)."""
        external_id = kwargs.get('external_id')

        with self.connection() as conn:
            # Check for existing by external_id
            if external_id:
                cursor = conn.execute(
                    "SELECT id FROM job_listings WHERE source = ? AND external_id = ?",
                    (source, external_id)
                )
                existing = cursor.fetchone()
                if existing:
                    return existing['id'], False

            # Check for existing by title+company (case-insensitive dedup)
            cursor = conn.execute(
                "SELECT id FROM job_listings WHERE LOWER(title) = LOWER(?) AND LOWER(company_name) = LOWER(?)",
                (title, company_name)
            )
            existing = cursor.fetchone()
            if existing:
                return existing['id'], False

            # Get or create company
            company_id = self.get_or_create_company(company_name)

            columns = ['source', 'company_name', 'title', 'company_id'] + list(kwargs.keys())
            values = [source, company_name, title, company_id] + list(kwargs.values())
            placeholders = ', '.join(['?' for _ in values])

            cursor = conn.execute(
                f"INSERT INTO job_listings ({', '.join(columns)}) VALUES ({placeholders})",
                values
            )
            return cursor.lastrowid, True

    def get_job_listing(self, job_id: int) -> Optional[Dict]:
        """Get job listing by ID."""
        with self.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM job_listings WHERE id = ?",
                (job_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_active_jobs(self, limit: int = 100) -> List[Dict]:
        """Get active job listings."""
        with self.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM job_listings WHERE is_active = 1 ORDER BY posted_date DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_unmatched_jobs(self, profile_id: int) -> List[Dict]:
        """Get jobs that haven't been matched for a profile."""
        with self.connection() as conn:
            cursor = conn.execute("""
                SELECT j.* FROM job_listings j
                LEFT JOIN job_matches m ON j.id = m.job_id AND m.profile_id = ?
                WHERE j.is_active = 1 AND m.id IS NULL
                ORDER BY j.posted_date DESC
            """, (profile_id,))
            return [dict(row) for row in cursor.fetchall()]

    def add_job_skill(self, job_id: int, skill_name: str, is_required: bool = True, years_required: int = None) -> int:
        """Add a required skill for a job."""
        with self.connection() as conn:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO job_required_skills
                   (job_id, skill_name, is_required, years_required) VALUES (?, ?, ?, ?)""",
                (job_id, skill_name, is_required, years_required)
            )
            return cursor.lastrowid

    # =========================================================================
    # MATCHING OPERATIONS
    # =========================================================================

    def add_job_match(self, profile_id: int, job_id: int, overall_score: float, **kwargs) -> int:
        """Add or update a job match."""
        with self.connection() as conn:
            # Check for existing
            cursor = conn.execute(
                "SELECT id FROM job_matches WHERE profile_id = ? AND job_id = ?",
                (profile_id, job_id)
            )
            existing = cursor.fetchone()

            if existing:
                # Update
                kwargs['overall_score'] = overall_score
                kwargs['updated_at'] = datetime.now().isoformat()
                set_clause = ', '.join([f"{k} = ?" for k in kwargs.keys()])
                values = list(kwargs.values()) + [existing['id']]
                conn.execute(
                    f"UPDATE job_matches SET {set_clause} WHERE id = ?",
                    values
                )
                return existing['id']
            else:
                # Insert
                columns = ['profile_id', 'job_id', 'overall_score'] + list(kwargs.keys())
                values = [profile_id, job_id, overall_score] + list(kwargs.values())
                placeholders = ', '.join(['?' for _ in values])
                cursor = conn.execute(
                    f"INSERT INTO job_matches ({', '.join(columns)}) VALUES ({placeholders})",
                    values
                )
                return cursor.lastrowid

    def get_top_matches(self, profile_id: int, limit: int = 20, min_score: float = 60.0) -> List[Dict]:
        """Get top job matches for a profile."""
        with self.connection() as conn:
            cursor = conn.execute("""
                SELECT m.*, j.title, j.company_name, j.location, j.location_type,
                       j.salary_min, j.salary_max, j.apply_url, j.posted_date, j.source
                FROM job_matches m
                JOIN job_listings j ON m.job_id = j.id
                WHERE m.profile_id = ? AND m.overall_score >= ? AND j.is_active = 1
                ORDER BY m.overall_score DESC
                LIMIT ?
            """, (profile_id, min_score, limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_match_by_id(self, match_id: int) -> Optional[Dict]:
        """Get a specific match with job details."""
        with self.connection() as conn:
            cursor = conn.execute("""
                SELECT m.*, j.title, j.company_name, j.location, j.description,
                       j.apply_url, j.posted_date, j.source
                FROM job_matches m
                JOIN job_listings j ON m.job_id = j.id
                WHERE m.id = ?
            """, (match_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # =========================================================================
    # SEARCH OPERATIONS
    # =========================================================================

    def add_search_query(self, query_name: str, keywords: List[str], **kwargs) -> int:
        """Add a search query configuration."""
        with self.connection() as conn:
            columns = ['query_name', 'keywords'] + list(kwargs.keys())
            values = [query_name, json.dumps(keywords)] + list(kwargs.values())
            placeholders = ', '.join(['?' for _ in values])
            cursor = conn.execute(
                f"INSERT INTO search_queries ({', '.join(columns)}) VALUES ({placeholders})",
                values
            )
            return cursor.lastrowid

    def get_active_search_queries(self) -> List[Dict]:
        """Get all active search queries."""
        with self.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM search_queries WHERE is_active = 1"
            )
            results = []
            for row in cursor.fetchall():
                d = dict(row)
                d['keywords'] = json.loads(d['keywords']) if d['keywords'] else []
                d['sources'] = json.loads(d['sources']) if d.get('sources') else []
                results.append(d)
            return results

    def log_search_run(self, source: str, jobs_found: int, new_jobs: int,
                       query_id: int = None, errors: str = None, duration: float = None) -> int:
        """Log a search run."""
        with self.connection() as conn:
            cursor = conn.execute(
                """INSERT INTO search_runs
                   (query_id, source, jobs_found, new_jobs, errors, duration_seconds)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (query_id, source, jobs_found, new_jobs, errors, duration)
            )
            return cursor.lastrowid

    # =========================================================================
    # REPORTING OPERATIONS
    # =========================================================================

    def create_daily_report(self, report_date: str, **kwargs) -> int:
        """Create a daily report entry."""
        with self.connection() as conn:
            # Check for existing
            cursor = conn.execute(
                "SELECT id FROM daily_reports WHERE report_date = ?",
                (report_date,)
            )
            existing = cursor.fetchone()

            if existing:
                if kwargs:
                    set_clause = ', '.join([f"{k} = ?" for k in kwargs.keys()])
                    values = list(kwargs.values()) + [existing['id']]
                    conn.execute(
                        f"UPDATE daily_reports SET {set_clause} WHERE id = ?",
                        values
                    )
                return existing['id']
            else:
                columns = ['report_date'] + list(kwargs.keys())
                values = [report_date] + list(kwargs.values())
                placeholders = ', '.join(['?' for _ in values])
                cursor = conn.execute(
                    f"INSERT INTO daily_reports ({', '.join(columns)}) VALUES ({placeholders})",
                    values
                )
                return cursor.lastrowid

    def log_notification(self, report_id: int, notification_type: str,
                         recipient: str, subject: str, status: str, **kwargs) -> int:
        """Log a notification."""
        with self.connection() as conn:
            columns = ['report_id', 'notification_type', 'recipient', 'subject', 'status'] + list(kwargs.keys())
            values = [report_id, notification_type, recipient, subject, status] + list(kwargs.values())
            placeholders = ', '.join(['?' for _ in values])
            cursor = conn.execute(
                f"INSERT INTO notifications ({', '.join(columns)}) VALUES ({placeholders})",
                values
            )
            return cursor.lastrowid

    # =========================================================================
    # CONFIGURATION & LOGGING
    # =========================================================================

    def get_config(self, key: str, default: str = None) -> Optional[str]:
        """Get a configuration value."""
        with self.connection() as conn:
            cursor = conn.execute(
                "SELECT value FROM config WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            return row['value'] if row else default

    def set_config(self, key: str, value: str, description: str = None) -> bool:
        """Set a configuration value."""
        with self.connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO config (key, value, description, updated_at)
                   VALUES (?, ?, COALESCE(?, (SELECT description FROM config WHERE key = ?)), ?)""",
                (key, value, description, key, datetime.now().isoformat())
            )
        return True

    def log(self, level: str, component: str, message: str, details: Dict = None) -> int:
        """Add a system log entry."""
        with self.connection() as conn:
            cursor = conn.execute(
                "INSERT INTO system_logs (level, component, message, details) VALUES (?, ?, ?, ?)",
                (level, component, message, json.dumps(details) if details else None)
            )
            return cursor.lastrowid

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_stats(self) -> Dict:
        """Get database statistics."""
        with self.connection() as conn:
            stats = {}

            cursor = conn.execute("SELECT COUNT(*) as count FROM job_listings WHERE is_active = 1")
            stats['active_jobs'] = cursor.fetchone()['count']

            cursor = conn.execute("SELECT COUNT(*) as count FROM job_listings")
            stats['total_jobs'] = cursor.fetchone()['count']

            cursor = conn.execute("SELECT COUNT(*) as count FROM job_matches")
            stats['total_matches'] = cursor.fetchone()['count']

            cursor = conn.execute("SELECT COUNT(*) as count FROM companies")
            stats['companies'] = cursor.fetchone()['count']

            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM job_listings WHERE date(created_at) = date('now')"
            )
            stats['jobs_today'] = cursor.fetchone()['count']

            return stats


# Module-level convenience functions
_db = None

def get_db() -> DatabaseManager:
    """Get the singleton database manager."""
    global _db
    if _db is None:
        _db = DatabaseManager()
    return _db

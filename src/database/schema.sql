-- Job Search Automation Database Schema
-- Created: 2026-01-10
-- Database: ~/databases/job_search.db

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- ============================================================================
-- CANDIDATE PROFILE TABLES
-- ============================================================================

-- Main candidate profile
CREATE TABLE IF NOT EXISTS candidate_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    location TEXT,
    linkedin_url TEXT,
    github_url TEXT,
    current_title TEXT,
    years_experience INTEGER,
    career_summary TEXT,
    work_preferences TEXT, -- JSON: remote, hybrid, onsite, travel
    salary_min INTEGER,
    salary_max INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Skills extracted from resume and GitHub
CREATE TABLE IF NOT EXISTS candidate_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    skill_name TEXT NOT NULL,
    skill_category TEXT, -- technical, soft, domain, certification
    proficiency_level TEXT, -- expert, advanced, intermediate, beginner
    years_experience INTEGER,
    source TEXT, -- resume, github, linkedin, manual
    confidence_score REAL DEFAULT 1.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES candidate_profile(id),
    UNIQUE(profile_id, skill_name)
);

-- Work experience entries
CREATE TABLE IF NOT EXISTS candidate_experience (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    description TEXT,
    achievements TEXT, -- JSON array
    skills_used TEXT, -- JSON array
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES candidate_profile(id)
);

-- Certifications
CREATE TABLE IF NOT EXISTS candidate_certifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    certification_name TEXT NOT NULL,
    issuing_org TEXT,
    issue_date TEXT,
    expiry_date TEXT,
    credential_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES candidate_profile(id)
);

-- GitHub repositories for skill inference
CREATE TABLE IF NOT EXISTS github_repos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    repo_name TEXT NOT NULL,
    repo_url TEXT,
    description TEXT,
    primary_language TEXT,
    languages TEXT, -- JSON: {language: bytes}
    stars INTEGER DEFAULT 0,
    forks INTEGER DEFAULT 0,
    topics TEXT, -- JSON array
    last_updated DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES candidate_profile(id)
);

-- ============================================================================
-- JOB LISTINGS TABLES
-- ============================================================================

-- Companies
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    website TEXT,
    industry TEXT,
    company_size TEXT,
    location TEXT,
    glassdoor_rating REAL,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Job listings
CREATE TABLE IF NOT EXISTS job_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT, -- ID from source platform
    source TEXT NOT NULL, -- linkedin, indeed, remoteok, etc.
    company_id INTEGER,
    company_name TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    requirements TEXT,
    responsibilities TEXT,
    location TEXT,
    location_type TEXT, -- remote, hybrid, onsite
    salary_min INTEGER,
    salary_max INTEGER,
    salary_currency TEXT DEFAULT 'USD',
    employment_type TEXT, -- full-time, contract, part-time
    experience_level TEXT, -- entry, mid, senior, executive
    posted_date DATETIME,
    application_deadline DATETIME,
    apply_url TEXT,
    is_active BOOLEAN DEFAULT 1,
    raw_data TEXT, -- JSON: original response
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    UNIQUE(source, external_id)
);

-- Job required skills (extracted)
CREATE TABLE IF NOT EXISTS job_required_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    skill_name TEXT NOT NULL,
    is_required BOOLEAN DEFAULT 1, -- required vs nice-to-have
    years_required INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES job_listings(id),
    UNIQUE(job_id, skill_name)
);

-- ============================================================================
-- MATCHING & SCORING TABLES
-- ============================================================================

-- Job matches (AI-scored)
CREATE TABLE IF NOT EXISTS job_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    job_id INTEGER NOT NULL,
    overall_score REAL NOT NULL, -- 0-100
    skill_match_score REAL,
    experience_match_score REAL,
    location_match_score REAL,
    salary_match_score REAL,
    culture_fit_score REAL,
    match_reasoning TEXT, -- AI explanation
    matched_skills TEXT, -- JSON array
    missing_skills TEXT, -- JSON array
    strengths TEXT, -- JSON: why good fit
    concerns TEXT, -- JSON: potential issues
    recommendation TEXT, -- strong_match, good_match, possible_match, poor_match
    is_reviewed BOOLEAN DEFAULT 0,
    is_interested BOOLEAN,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES candidate_profile(id),
    FOREIGN KEY (job_id) REFERENCES job_listings(id),
    UNIQUE(profile_id, job_id)
);

-- Application tracking
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    status TEXT DEFAULT 'pending', -- pending, applied, interviewing, offered, rejected, withdrawn
    applied_date DATETIME,
    response_date DATETIME,
    interview_dates TEXT, -- JSON array
    notes TEXT,
    cover_letter TEXT,
    resume_version TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (match_id) REFERENCES job_matches(id)
);

-- ============================================================================
-- SEARCH & CONFIGURATION TABLES
-- ============================================================================

-- Search queries (what to search for)
CREATE TABLE IF NOT EXISTS search_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_name TEXT NOT NULL,
    keywords TEXT NOT NULL, -- JSON array
    location TEXT,
    remote_only BOOLEAN DEFAULT 0,
    salary_min INTEGER,
    experience_level TEXT,
    job_type TEXT,
    sources TEXT, -- JSON array: which job boards to search
    is_active BOOLEAN DEFAULT 1,
    last_run DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Search results log
CREATE TABLE IF NOT EXISTS search_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id INTEGER,
    source TEXT,
    jobs_found INTEGER DEFAULT 0,
    new_jobs INTEGER DEFAULT 0,
    errors TEXT,
    duration_seconds REAL,
    run_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (query_id) REFERENCES search_queries(id)
);

-- ============================================================================
-- REPORTING & NOTIFICATIONS
-- ============================================================================

-- Daily reports
CREATE TABLE IF NOT EXISTS daily_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date DATE UNIQUE NOT NULL,
    total_jobs_searched INTEGER DEFAULT 0,
    new_jobs_found INTEGER DEFAULT 0,
    matches_generated INTEGER DEFAULT 0,
    top_matches_count INTEGER DEFAULT 0,
    report_html TEXT,
    report_markdown TEXT,
    report_path TEXT,
    sent_notification BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Notification log
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER,
    notification_type TEXT, -- email, slack, desktop
    recipient TEXT,
    subject TEXT,
    status TEXT, -- sent, failed, pending
    error_message TEXT,
    sent_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (report_id) REFERENCES daily_reports(id)
);

-- ============================================================================
-- SYSTEM TABLES
-- ============================================================================

-- Configuration
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT,
    description TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- System logs
CREATE TABLE IF NOT EXISTS system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT, -- DEBUG, INFO, WARNING, ERROR, CRITICAL
    component TEXT, -- profile_builder, job_search, matcher, reporter
    message TEXT,
    details TEXT, -- JSON
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_job_listings_source ON job_listings(source);
CREATE INDEX IF NOT EXISTS idx_job_listings_posted ON job_listings(posted_date);
CREATE INDEX IF NOT EXISTS idx_job_listings_active ON job_listings(is_active);
CREATE INDEX IF NOT EXISTS idx_job_matches_score ON job_matches(overall_score DESC);
CREATE INDEX IF NOT EXISTS idx_job_matches_profile ON job_matches(profile_id);
CREATE INDEX IF NOT EXISTS idx_candidate_skills_name ON candidate_skills(skill_name);
CREATE INDEX IF NOT EXISTS idx_system_logs_level ON system_logs(level);
CREATE INDEX IF NOT EXISTS idx_system_logs_component ON system_logs(component);

-- ============================================================================
-- DEFAULT DATA
-- ============================================================================

-- Insert default configuration
INSERT OR IGNORE INTO config (key, value, description) VALUES
    ('openai_model', 'gpt-4', 'OpenAI model for matching'),
    ('match_threshold', '60', 'Minimum score to include in report'),
    ('max_jobs_per_source', '50', 'Max jobs to fetch per source'),
    ('notification_email', '', 'Email for daily reports'),
    ('slack_webhook', '', 'Slack webhook for notifications'),
    ('search_frequency', 'daily', 'How often to run searches'),
    ('report_time', '05:00', 'Time to generate daily report');

"""
Tests for database module.
"""

import pytest
import tempfile
import sqlite3
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import DatabaseManager, init_database


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    init_database(db_path)
    db = DatabaseManager(db_path)
    yield db

    # Cleanup
    db_path.unlink(missing_ok=True)


class TestDatabaseManager:
    """Tests for DatabaseManager class."""

    def test_init_database(self, temp_db):
        """Test database initialization."""
        # Verify tables exist
        with temp_db.connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row['name'] for row in cursor.fetchall()}

        expected_tables = {
            'candidate_profile', 'candidate_skills', 'candidate_experience',
            'candidate_certifications', 'github_repos', 'companies',
            'job_listings', 'job_required_skills', 'job_matches',
            'applications', 'search_queries', 'search_runs',
            'daily_reports', 'notifications', 'config', 'system_logs'
        }

        assert expected_tables.issubset(tables)

    def test_create_profile(self, temp_db):
        """Test profile creation."""
        profile_id = temp_db.get_or_create_profile(
            name="Test User",
            email="test@example.com",
            location="Test City"
        )

        assert profile_id > 0

        # Verify profile was created
        profile = temp_db.get_profile(profile_id)
        assert profile['name'] == "Test User"
        assert profile['email'] == "test@example.com"
        assert profile['location'] == "Test City"

    def test_get_existing_profile(self, temp_db):
        """Test getting existing profile doesn't create duplicate."""
        profile_id1 = temp_db.get_or_create_profile(name="Test User")
        profile_id2 = temp_db.get_or_create_profile(name="Test User")

        assert profile_id1 == profile_id2

    def test_add_skill(self, temp_db):
        """Test adding skills to profile."""
        profile_id = temp_db.get_or_create_profile(name="Test User")

        skill_id = temp_db.add_skill(
            profile_id=profile_id,
            skill_name="Python",
            skill_category="technical",
            proficiency_level="expert"
        )

        assert skill_id > 0

        skills = temp_db.get_profile_skills(profile_id)
        assert len(skills) == 1
        assert skills[0]['skill_name'] == "Python"
        assert skills[0]['skill_category'] == "technical"

    def test_add_duplicate_skill(self, temp_db):
        """Test adding duplicate skill updates existing."""
        profile_id = temp_db.get_or_create_profile(name="Test User")

        temp_db.add_skill(profile_id, "Python", proficiency_level="beginner")
        temp_db.add_skill(profile_id, "Python", proficiency_level="expert")

        skills = temp_db.get_profile_skills(profile_id)
        assert len(skills) == 1
        # Should keep the updated level
        assert skills[0]['proficiency_level'] == "expert"

    def test_add_job_listing(self, temp_db):
        """Test adding job listings."""
        job_id, is_new = temp_db.add_job_listing(
            source="test",
            company_name="Test Corp",
            title="Software Engineer",
            external_id="test123",
            location="Remote",
            description="Test job description"
        )

        assert job_id > 0
        assert is_new is True

        job = temp_db.get_job_listing(job_id)
        assert job['title'] == "Software Engineer"
        assert job['company_name'] == "Test Corp"

    def test_duplicate_job_listing(self, temp_db):
        """Test adding duplicate job returns existing."""
        job_id1, is_new1 = temp_db.add_job_listing(
            source="test",
            company_name="Test Corp",
            title="Software Engineer",
            external_id="test123"
        )

        job_id2, is_new2 = temp_db.add_job_listing(
            source="test",
            company_name="Test Corp",
            title="Software Engineer",
            external_id="test123"
        )

        assert job_id1 == job_id2
        assert is_new1 is True
        assert is_new2 is False

    def test_add_job_match(self, temp_db):
        """Test adding job matches."""
        profile_id = temp_db.get_or_create_profile(name="Test User")
        job_id, _ = temp_db.add_job_listing(
            source="test",
            company_name="Test Corp",
            title="Software Engineer"
        )

        match_id = temp_db.add_job_match(
            profile_id=profile_id,
            job_id=job_id,
            overall_score=85.5,
            skill_match_score=90.0,
            recommendation="strong_match"
        )

        assert match_id > 0

        matches = temp_db.get_top_matches(profile_id, limit=10)
        assert len(matches) == 1
        assert matches[0]['overall_score'] == 85.5

    def test_get_unmatched_jobs(self, temp_db):
        """Test getting unmatched jobs."""
        profile_id = temp_db.get_or_create_profile(name="Test User")

        # Add some jobs
        for i in range(5):
            temp_db.add_job_listing(
                source="test",
                company_name=f"Company {i}",
                title=f"Job {i}",
                external_id=f"job{i}"
            )

        # Initially all should be unmatched
        unmatched = temp_db.get_unmatched_jobs(profile_id)
        assert len(unmatched) == 5

        # Match one job
        temp_db.add_job_match(profile_id, unmatched[0]['id'], 80.0)

        # Now should have 4 unmatched
        unmatched = temp_db.get_unmatched_jobs(profile_id)
        assert len(unmatched) == 4

    def test_config_operations(self, temp_db):
        """Test configuration get/set."""
        # Get default config
        value = temp_db.get_config('openai_model', 'default')
        assert value == 'gpt-4'

        # Set new config
        temp_db.set_config('test_key', 'test_value', 'Test description')
        assert temp_db.get_config('test_key') == 'test_value'

    def test_logging(self, temp_db):
        """Test system logging."""
        log_id = temp_db.log(
            level='INFO',
            component='test',
            message='Test log message',
            details={'key': 'value'}
        )

        assert log_id > 0

    def test_stats(self, temp_db):
        """Test getting statistics."""
        # Add some test data
        temp_db.add_job_listing(source="test", company_name="Test", title="Job 1")
        temp_db.add_job_listing(source="test", company_name="Test", title="Job 2")

        stats = temp_db.get_stats()

        assert stats['active_jobs'] == 2
        assert stats['total_jobs'] == 2
        assert stats['companies'] == 1


class TestDatabaseIntegrity:
    """Tests for database integrity and constraints."""

    def test_foreign_key_constraint(self, temp_db):
        """Test foreign key constraints work."""
        # Try to add skill without profile should work (no FK constraint on this)
        # But match without valid job should fail

        profile_id = temp_db.get_or_create_profile(name="Test User")

        # This should raise an error due to FK constraint
        with pytest.raises(Exception):
            temp_db.add_job_match(profile_id, 99999, 80.0)

    def test_unique_constraints(self, temp_db):
        """Test unique constraints are enforced."""
        # Company names must be unique
        temp_db.get_or_create_company("Test Corp")
        id1 = temp_db.get_or_create_company("Test Corp")
        id2 = temp_db.get_or_create_company("Test Corp")

        assert id1 == id2  # Should return same ID, not create new


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

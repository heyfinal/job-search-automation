"""
Tests for AI Matching Engine sub-agent.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import DatabaseManager, init_database
from src.agents.matcher import JobMatcher


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    init_database(db_path)
    db = DatabaseManager(db_path)
    yield db

    db_path.unlink(missing_ok=True)


@pytest.fixture
def matcher(temp_db):
    """Create JobMatcher with temp database."""
    return JobMatcher(temp_db)


@pytest.fixture
def sample_profile(temp_db):
    """Create a sample profile for testing."""
    profile_id = temp_db.get_or_create_profile(
        name="Test User",
        current_title="HSE Manager",
        years_experience=15,
        location="Oklahoma City, OK"
    )

    # Add skills
    skills = [
        ("HSE Leadership", "domain", "expert"),
        ("Safety Management", "domain", "expert"),
        ("OSHA Compliance", "certification", "expert"),
        ("Project Management", "soft", "advanced"),
        ("Python", "technical", "beginner"),
        ("Excel", "technical", "advanced"),
    ]

    for skill_name, category, level in skills:
        temp_db.add_skill(
            profile_id,
            skill_name,
            skill_category=category,
            proficiency_level=level
        )

    return profile_id


@pytest.fixture
def sample_jobs(temp_db):
    """Create sample job listings for testing."""
    jobs = []

    # Good match - HSE Manager
    job_id1, _ = temp_db.add_job_listing(
        source="test",
        company_name="Energy Corp",
        title="HSE Manager",
        description="Looking for experienced HSE Manager with OSHA expertise. Must have safety management experience.",
        location="Oklahoma City, OK",
        location_type="hybrid",
        external_id="job1"
    )
    jobs.append(job_id1)

    # Medium match - Safety Coordinator
    job_id2, _ = temp_db.add_job_listing(
        source="test",
        company_name="Industrial Co",
        title="Safety Coordinator",
        description="Entry-level safety coordinator position. Excel skills required.",
        location="Remote",
        location_type="remote",
        external_id="job2"
    )
    jobs.append(job_id2)

    # Poor match - Software Developer
    job_id3, _ = temp_db.add_job_listing(
        source="test",
        company_name="Tech Startup",
        title="Python Developer",
        description="Looking for senior Python developer with 5+ years experience in Django and FastAPI.",
        location="San Francisco, CA",
        location_type="onsite",
        external_id="job3"
    )
    jobs.append(job_id3)

    return jobs


class TestJobMatcher:
    """Tests for JobMatcher class."""

    def test_quick_score_good_match(self, matcher, temp_db, sample_profile, sample_jobs):
        """Test quick scoring for a good match."""
        profile_data = matcher._get_profile_data(sample_profile)
        job = temp_db.get_job_listing(sample_jobs[0])  # HSE Manager job

        score = matcher._quick_score(profile_data, job)

        # Should be a high score - HSE Manager with relevant skills
        assert score >= 50

    def test_quick_score_poor_match(self, matcher, temp_db, sample_profile, sample_jobs):
        """Test quick scoring for a poor match."""
        profile_data = matcher._get_profile_data(sample_profile)
        job = temp_db.get_job_listing(sample_jobs[2])  # Python Developer job

        score = matcher._quick_score(profile_data, job)

        # Should be a low score - Python developer doesn't match HSE profile
        assert score < 70

    def test_heuristic_match(self, matcher, temp_db, sample_profile, sample_jobs):
        """Test heuristic matching without AI."""
        profile_data = matcher._get_profile_data(sample_profile)
        job = temp_db.get_job_listing(sample_jobs[0])  # HSE Manager job

        result = matcher._heuristic_match(profile_data, job)

        assert 'overall_score' in result
        assert 'skill_match_score' in result
        assert 'matched_skills' in result
        assert 'recommendation' in result

        # HSE Manager job should be a good match
        assert result['overall_score'] >= 50

    def test_identify_strengths(self, matcher, temp_db, sample_profile, sample_jobs):
        """Test strength identification."""
        profile_data = matcher._get_profile_data(sample_profile)
        job = temp_db.get_job_listing(sample_jobs[0])

        strengths = matcher._identify_strengths(profile_data, job)

        assert isinstance(strengths, list)
        # Should identify experience as a strength
        assert any('experience' in s.lower() or 'years' in s.lower() for s in strengths) or len(strengths) > 0

    def test_identify_concerns(self, matcher, temp_db, sample_profile, sample_jobs):
        """Test concern identification."""
        profile_data = matcher._get_profile_data(sample_profile)
        job = temp_db.get_job_listing(sample_jobs[2])  # Python Developer job

        concerns = matcher._identify_concerns(profile_data, job)

        assert isinstance(concerns, list)
        # Might identify technical skills gap
        # Could be empty if no specific concerns detected

    def test_recommendation_levels(self, matcher):
        """Test recommendation thresholds."""
        assert matcher.STRONG_MATCH == 80
        assert matcher.GOOD_MATCH == 65
        assert matcher.POSSIBLE_MATCH == 50
        assert matcher.MIN_SCORE == 40

    def test_scoring_weights(self, matcher):
        """Test scoring weights sum to 1."""
        total_weight = sum(matcher.WEIGHTS.values())
        assert abs(total_weight - 1.0) < 0.01

    @pytest.mark.asyncio
    async def test_match_jobs_for_profile(self, matcher, temp_db, sample_profile, sample_jobs):
        """Test full matching process."""
        # Run matching (will use heuristic since no OpenAI key)
        matches = await matcher.match_jobs_for_profile(sample_profile, limit=10)

        # Should have some matches
        assert isinstance(matches, list)

        # Each match should have required fields
        for match in matches:
            assert 'overall_score' in match
            assert match['overall_score'] >= matcher.MIN_SCORE

    def test_get_match_summary(self, matcher, temp_db, sample_profile, sample_jobs):
        """Test match summary generation."""
        # First add some matches
        temp_db.add_job_match(sample_profile, sample_jobs[0], 85.0, recommendation='strong_match')
        temp_db.add_job_match(sample_profile, sample_jobs[1], 70.0, recommendation='good_match')

        summary = matcher.get_match_summary(sample_profile)

        assert 'total_matches' in summary
        assert 'strong_matches' in summary
        assert 'good_matches' in summary
        assert summary['total_matches'] == 2
        assert summary['strong_matches'] == 1
        assert summary['good_matches'] == 1


class TestMatchingLogic:
    """Tests for matching logic and algorithms."""

    def test_skill_matching_case_insensitive(self, matcher, temp_db):
        """Test skill matching is case insensitive."""
        profile_id = temp_db.get_or_create_profile(name="Test")
        temp_db.add_skill(profile_id, "Python")
        temp_db.add_skill(profile_id, "HSE Leadership")

        profile_data = matcher._get_profile_data(profile_id)
        profile_skills = set(s['skill_name'].lower() for s in profile_data['skills'])

        job_text = "PYTHON developer with hse leadership skills"

        matches = sum(1 for skill in profile_skills if skill in job_text.lower())
        assert matches >= 2

    def test_experience_year_extraction(self, matcher, temp_db):
        """Test experience year extraction from job description."""
        profile_id = temp_db.get_or_create_profile(
            name="Test",
            years_experience=15
        )
        profile_data = matcher._get_profile_data(profile_id)

        job = {
            'title': 'Manager',
            'description': 'Must have 10+ years of experience'
        }

        # Heuristic match should extract years
        result = matcher._heuristic_match(profile_data, job)

        # Should score well since 15 > 10
        assert result['experience_match_score'] >= 80


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

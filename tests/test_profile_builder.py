"""
Tests for Profile Builder sub-agent.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import DatabaseManager, init_database
from src.agents.profile_builder import ProfileBuilder


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
def profile_builder(temp_db):
    """Create ProfileBuilder with temp database."""
    return ProfileBuilder(temp_db)


class TestProfileBuilder:
    """Tests for ProfileBuilder class."""

    @pytest.mark.asyncio
    async def test_build_basic_profile(self, profile_builder, temp_db):
        """Test building a basic profile."""
        profile_id = await profile_builder.build_profile(
            name="Test User",
            email="test@example.com",
            phone="555-1234"
        )

        assert profile_id > 0

        profile = temp_db.get_profile(profile_id)
        assert profile['name'] == "Test User"
        assert profile['email'] == "test@example.com"

    @pytest.mark.asyncio
    async def test_build_profile_with_manual_data(self, profile_builder, temp_db):
        """Test building profile with manual data."""
        manual_data = {
            'current_title': 'Software Engineer',
            'years_experience': 10,
            'location': 'Test City',
            'skills': [
                {'name': 'Python', 'category': 'technical', 'level': 'expert'},
                {'name': 'Leadership', 'category': 'soft', 'level': 'advanced'}
            ]
        }

        profile_id = await profile_builder.build_profile(
            name="Test User",
            manual_data=manual_data
        )

        profile = temp_db.get_profile(profile_id)
        assert profile['current_title'] == 'Software Engineer'
        assert profile['years_experience'] == 10

        skills = temp_db.get_profile_skills(profile_id)
        assert len(skills) >= 2

        skill_names = [s['skill_name'] for s in skills]
        assert 'Python' in skill_names
        assert 'Leadership' in skill_names

    @pytest.mark.asyncio
    async def test_skill_extraction_from_resume_content(self, profile_builder, temp_db):
        """Test skill extraction from resume text."""
        profile_id = temp_db.get_or_create_profile(name="Test User")

        # Simulate parsing resume content with known skills
        resume_content = """
        Professional with experience in:
        - HSE Leadership & Compliance
        - Project Management
        - Python programming
        - Microsoft Excel
        - OSHA compliance
        """

        await profile_builder._parse_resume_content(profile_id, resume_content, "test.pdf")

        skills = temp_db.get_profile_skills(profile_id)
        skill_names = [s['skill_name'].lower() for s in skills]

        # Should have extracted at least some skills
        assert any('hse' in s or 'safety' in s for s in skill_names) or \
               any('project management' in s for s in skill_names) or \
               any('python' in s for s in skill_names)

    def test_skill_categories(self, profile_builder):
        """Test skill categories are properly defined."""
        categories = profile_builder.SKILL_CATEGORIES

        assert 'technical' in categories
        assert 'domain' in categories
        assert 'certification' in categories
        assert 'soft' in categories

        # Check some expected skills in categories
        assert 'python' in categories['technical']
        assert 'leadership' in categories['soft']
        assert 'iadc rigpass' in categories['certification']

    def test_proficiency_inference(self, profile_builder):
        """Test proficiency level inference from code volume."""
        assert profile_builder._infer_proficiency(150000) == 'expert'
        assert profile_builder._infer_proficiency(75000) == 'advanced'
        assert profile_builder._infer_proficiency(25000) == 'intermediate'
        assert profile_builder._infer_proficiency(5000) == 'beginner'

    @pytest.mark.asyncio
    async def test_get_profile_data(self, profile_builder, temp_db):
        """Test getting complete profile data."""
        profile_id = await profile_builder.build_profile(
            name="Test User",
            manual_data={
                'skills': [
                    {'name': 'Python', 'category': 'technical'},
                    {'name': 'Leadership', 'category': 'soft'}
                ]
            }
        )

        profile_data = profile_builder.get_profile_data(profile_id)

        assert 'profile' in profile_data
        assert 'skills' in profile_data
        assert 'experiences' in profile_data
        assert 'certifications' in profile_data

        assert profile_data['profile']['name'] == "Test User"
        assert len(profile_data['skills']) >= 2


class TestSkillExtraction:
    """Tests for skill extraction logic."""

    def test_technical_skills_detection(self, profile_builder):
        """Test detection of technical skills."""
        text = "Experience with Python, JavaScript, and SQL databases"
        text_lower = text.lower()

        found_skills = []
        for skill in profile_builder.SKILL_CATEGORIES['technical']:
            if skill in text_lower:
                found_skills.append(skill)

        assert 'python' in found_skills
        assert 'javascript' in found_skills
        assert 'sql' in found_skills

    def test_domain_skills_detection(self, profile_builder):
        """Test detection of domain skills."""
        text = "Background in oil and gas, drilling operations, and HSE"
        text_lower = text.lower()

        found_skills = []
        for skill in profile_builder.SKILL_CATEGORIES['domain']:
            if skill in text_lower:
                found_skills.append(skill)

        assert 'oil and gas' in found_skills or 'drilling' in found_skills

    def test_certification_detection(self, profile_builder):
        """Test detection of certifications."""
        text = "Certified in IADC RigPass, HAZWOPER, and CPR/First Aid"
        text_lower = text.lower()

        found_certs = []
        for cert in profile_builder.SKILL_CATEGORIES['certification']:
            if cert.lower() in text_lower:
                found_certs.append(cert)

        assert any('rigpass' in c.lower() or 'hazwoper' in c.lower() for c in found_certs)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Tests for Reporter sub-agent.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import DatabaseManager, init_database
from src.agents.reporter import Reporter


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
def reporter(temp_db):
    """Create Reporter with temp database."""
    return Reporter(temp_db)


@pytest.fixture
def sample_data(temp_db):
    """Create sample profile and matches for testing."""
    # Create profile
    profile_id = temp_db.get_or_create_profile(
        name="Test User",
        email="test@example.com"
    )

    # Create jobs and matches
    for i in range(5):
        job_id, _ = temp_db.add_job_listing(
            source="test",
            company_name=f"Company {i}",
            title=f"Job Title {i}",
            location="Remote",
            location_type="remote",
            apply_url=f"https://example.com/job/{i}",
            external_id=f"job{i}"
        )

        temp_db.add_job_match(
            profile_id=profile_id,
            job_id=job_id,
            overall_score=90 - i * 5,
            skill_match_score=85 - i * 3,
            experience_match_score=88 - i * 2,
            recommendation='strong_match' if i < 2 else 'good_match',
            match_reasoning=f"Good match for position {i}"
        )

    return profile_id


class TestReporter:
    """Tests for Reporter class."""

    @pytest.mark.asyncio
    async def test_generate_daily_report(self, reporter, sample_data):
        """Test generating a daily report."""
        report_data = await reporter.generate_daily_report(sample_data)

        assert 'date' in report_data
        assert 'generated_at' in report_data
        assert 'summary' in report_data
        assert 'top_matches' in report_data
        assert 'html_path' in report_data
        assert 'md_path' in report_data

        # Check summary stats
        summary = report_data['summary']
        assert summary['total_matches'] == 5
        assert summary['strong_matches'] == 2
        assert summary['good_matches'] == 3

    @pytest.mark.asyncio
    async def test_html_report_generated(self, reporter, sample_data, tmp_path):
        """Test HTML report is properly generated."""
        # Temporarily change reports dir
        original_dir = reporter.reporter if hasattr(reporter, 'reporter') else None

        report_data = await reporter.generate_daily_report(sample_data)

        # Verify HTML file exists
        html_path = Path(report_data['html_path'])
        assert html_path.exists()

        # Verify HTML content
        html_content = html_path.read_text()
        assert '<!DOCTYPE html>' in html_content
        assert 'Job Match Report' in html_content
        assert 'Company 0' in html_content  # First company should be in report

    @pytest.mark.asyncio
    async def test_markdown_report_generated(self, reporter, sample_data):
        """Test Markdown report is properly generated."""
        report_data = await reporter.generate_daily_report(sample_data)

        # Verify MD file exists
        md_path = Path(report_data['md_path'])
        assert md_path.exists()

        # Verify MD content
        md_content = md_path.read_text()
        assert '# Job Match Report' in md_content
        assert '## Summary' in md_content
        assert '## Top Matches' in md_content

    def test_format_match(self, reporter):
        """Test match formatting for report."""
        raw_match = {
            'title': 'Test Job',
            'company_name': 'Test Corp',
            'location': 'Remote',
            'location_type': 'remote',
            'overall_score': 85.5,
            'skill_match_score': 90.0,
            'experience_match_score': 80.0,
            'apply_url': 'https://example.com/apply',
            'source': 'test',
            'posted_date': '2024-01-01',
            'match_reasoning': 'Good match',
            'matched_skills': '["Python", "SQL"]',
            'missing_skills': '["Java"]',
            'strengths': '["Experience"]',
            'concerns': '[]',
            'recommendation': 'strong_match',
            'salary_min': 80000,
            'salary_max': 120000
        }

        formatted = reporter._format_match(raw_match)

        assert formatted['job_title'] == 'Test Job'
        assert formatted['company'] == 'Test Corp'
        assert formatted['score'] == 85.5
        assert formatted['matched_skills'] == ['Python', 'SQL']
        assert formatted['missing_skills'] == ['Java']
        assert formatted['strengths'] == ['Experience']

    def test_generate_html_report_structure(self, reporter):
        """Test HTML report has proper structure."""
        data = {
            'date': '2024-01-01',
            'generated_at': '2024-01-01T05:00:00',
            'profile_name': 'Test User',
            'summary': {
                'total_matches': 10,
                'strong_matches': 3,
                'good_matches': 5,
                'average_score': 75.5,
                'jobs_added_today': 15,
                'total_active_jobs': 100
            },
            'top_matches': [
                {
                    'job_title': 'Test Job',
                    'company': 'Test Corp',
                    'location': 'Remote',
                    'location_type': 'remote',
                    'score': 85,
                    'reasoning': 'Good fit',
                    'strengths': ['Experience'],
                    'concerns': [],
                    'apply_url': 'https://example.com',
                    'source': 'test',
                    'salary_min': None,
                    'salary_max': None
                }
            ]
        }

        html = reporter._generate_html_report(data)

        # Check required elements
        assert '<html' in html
        assert '<head>' in html
        assert '<body>' in html
        assert '<style>' in html  # Should have embedded CSS
        assert 'Test Job' in html
        assert 'Test Corp' in html
        assert '85' in html  # Score

    def test_generate_markdown_report_structure(self, reporter):
        """Test Markdown report has proper structure."""
        data = {
            'date': '2024-01-01',
            'generated_at': '2024-01-01T05:00:00',
            'profile_name': 'Test User',
            'summary': {
                'total_matches': 10,
                'strong_matches': 3,
                'good_matches': 5,
                'average_score': 75.5,
                'jobs_added_today': 15,
                'total_active_jobs': 100
            },
            'top_matches': [
                {
                    'job_title': 'Test Job',
                    'company': 'Test Corp',
                    'location': 'Remote',
                    'location_type': 'remote',
                    'score': 85,
                    'reasoning': 'Good fit',
                    'strengths': ['Experience'],
                    'concerns': [],
                    'apply_url': 'https://example.com',
                    'source': 'test',
                    'salary_min': 80000,
                    'salary_max': 120000
                }
            ]
        }

        md = reporter._generate_markdown_report(data)

        # Check structure
        assert '# Job Match Report' in md
        assert '## Summary' in md
        assert '| Metric | Value |' in md
        assert '## Top Matches' in md
        assert 'Test Job' in md
        assert '$80,000 - $120,000' in md


class TestNotifications:
    """Tests for notification functionality."""

    @pytest.mark.asyncio
    async def test_send_notifications_returns_results(self, reporter):
        """Test notification sending returns results dict."""
        report_data = {
            'date': '2024-01-01',
            'summary': {
                'total_matches': 5,
                'strong_matches': 2
            },
            'top_matches': [],
            'html_path': '/tmp/test.html'
        }

        results = await reporter.send_notifications(report_data)

        assert isinstance(results, dict)
        # macOS notification should be attempted
        assert 'macos' in results


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

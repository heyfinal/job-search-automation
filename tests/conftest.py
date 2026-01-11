"""
Pytest configuration and shared fixtures.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )


@pytest.fixture(scope="session")
def project_root():
    """Return project root path."""
    return PROJECT_ROOT


@pytest.fixture
def sample_job_description():
    """Return a sample job description for testing."""
    return """
    HSE Manager - Oil & Gas Industry

    We are seeking an experienced HSE Manager to lead our safety operations.

    Requirements:
    - 10+ years of HSE experience in oil & gas or related industry
    - Strong knowledge of OSHA regulations
    - Experience with incident investigation and root cause analysis
    - Excellent communication and leadership skills
    - Certifications: IADC RigPass, HAZWOPER preferred

    Responsibilities:
    - Develop and implement HSE policies and procedures
    - Lead safety training programs
    - Conduct audits and inspections
    - Manage incident investigations
    - Interface with regulatory agencies

    Location: Oklahoma City, OK (Hybrid)
    Salary: $100,000 - $130,000

    Apply now!
    """


@pytest.fixture
def sample_profile_data():
    """Return sample profile data for testing."""
    return {
        'profile': {
            'id': 1,
            'name': 'Test User',
            'email': 'test@example.com',
            'phone': '555-1234',
            'location': 'Oklahoma City, OK',
            'current_title': 'HSE Manager',
            'years_experience': 15,
            'career_summary': 'Experienced HSE professional'
        },
        'skills': [
            {'skill_name': 'HSE Leadership', 'skill_category': 'domain', 'proficiency_level': 'expert'},
            {'skill_name': 'OSHA Compliance', 'skill_category': 'certification', 'proficiency_level': 'expert'},
            {'skill_name': 'Incident Investigation', 'skill_category': 'domain', 'proficiency_level': 'expert'},
            {'skill_name': 'Python', 'skill_category': 'technical', 'proficiency_level': 'beginner'},
            {'skill_name': 'Excel', 'skill_category': 'technical', 'proficiency_level': 'advanced'},
        ],
        'experiences': [
            {
                'company': 'Energy Corp',
                'title': 'HSE Manager',
                'start_date': '2020',
                'end_date': '2024'
            }
        ],
        'certifications': [
            {'certification_name': 'IADC RigPass'},
            {'certification_name': 'HAZWOPER'}
        ]
    }

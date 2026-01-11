"""
AI Matching Engine Sub-Agent
Uses OpenAI GPT-4 for intelligent job-candidate matching and scoring.
"""

import json
import asyncio
import aiohttp
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging
import re

from src.database import DatabaseManager, get_db
from src.utils.credentials import get_openai_key

logger = logging.getLogger(__name__)


class JobMatcher:
    """
    AI-powered job matching engine that:
    - Scores jobs based on skill alignment
    - Identifies realistic opportunities
    - Filters out poor matches
    - Provides detailed reasoning
    """

    # Matching thresholds
    STRONG_MATCH = 80
    GOOD_MATCH = 65
    POSSIBLE_MATCH = 50
    MIN_SCORE = 40

    # Scoring weights
    WEIGHTS = {
        'skill_match': 0.35,
        'experience': 0.25,
        'location': 0.15,
        'salary': 0.10,
        'culture_fit': 0.15
    }

    def __init__(self, db: DatabaseManager = None):
        self.db = db or get_db()
        self.openai_key = get_openai_key()
        self.model = "gpt-4"

    async def match_jobs_for_profile(
        self,
        profile_id: int,
        limit: int = 100
    ) -> List[Dict]:
        """
        Match all unmatched jobs for a profile.

        Args:
            profile_id: Candidate profile ID
            limit: Maximum jobs to process

        Returns:
            List of match results
        """
        logger.info(f"Starting job matching for profile {profile_id}")

        # Get profile data
        profile_data = self._get_profile_data(profile_id)
        if not profile_data:
            logger.error(f"Profile {profile_id} not found")
            return []

        # Get unmatched jobs
        unmatched_jobs = self.db.get_unmatched_jobs(profile_id)[:limit]
        logger.info(f"Processing {len(unmatched_jobs)} unmatched jobs")

        # Process in batches for efficiency
        matches = []
        batch_size = 5

        for i in range(0, len(unmatched_jobs), batch_size):
            batch = unmatched_jobs[i:i+batch_size]
            batch_results = await asyncio.gather(
                *[self._match_single_job(profile_data, job) for job in batch]
            )

            for job, result in zip(batch, batch_results):
                if result and result['overall_score'] >= self.MIN_SCORE:
                    # Save match to database
                    match_id = self.db.add_job_match(
                        profile_id=profile_id,
                        job_id=job['id'],
                        overall_score=result['overall_score'],
                        skill_match_score=result.get('skill_match_score'),
                        experience_match_score=result.get('experience_match_score'),
                        location_match_score=result.get('location_match_score'),
                        salary_match_score=result.get('salary_match_score'),
                        culture_fit_score=result.get('culture_fit_score'),
                        match_reasoning=result.get('reasoning'),
                        matched_skills=json.dumps(result.get('matched_skills', [])),
                        missing_skills=json.dumps(result.get('missing_skills', [])),
                        strengths=json.dumps(result.get('strengths', [])),
                        concerns=json.dumps(result.get('concerns', [])),
                        recommendation=result.get('recommendation')
                    )
                    result['match_id'] = match_id
                    result['job'] = job
                    matches.append(result)

        # Sort by score
        matches.sort(key=lambda x: x['overall_score'], reverse=True)

        logger.info(f"Matching complete: {len(matches)} matches above threshold")
        return matches

    async def _match_single_job(
        self,
        profile_data: Dict,
        job: Dict
    ) -> Optional[Dict]:
        """Match a single job against profile."""
        try:
            # First, do quick heuristic scoring
            quick_score = self._quick_score(profile_data, job)

            # If quick score is very low, skip AI analysis (lowered threshold for HSE jobs)
            if quick_score < 15:
                return {
                    'overall_score': quick_score,
                    'recommendation': 'poor_match',
                    'reasoning': 'Very low skill alignment based on keyword matching'
                }

            # Use AI for detailed analysis
            if self.openai_key:
                return await self._ai_match(profile_data, job)
            else:
                # Fall back to heuristic matching
                return self._heuristic_match(profile_data, job)

        except Exception as e:
            logger.error(f"Error matching job {job.get('id')}: {e}")
            return None

    def _quick_score(self, profile_data: Dict, job: Dict) -> float:
        """Quick heuristic score based on keyword matching."""
        profile_skills = set(
            s['skill_name'].lower()
            for s in profile_data.get('skills', [])
        )

        job_text = f"{job.get('title', '')} {job.get('description', '')}".lower()

        # Count skill matches
        matches = sum(1 for skill in profile_skills if skill in job_text)

        # Base score on match ratio
        if not profile_skills:
            return 50

        match_ratio = matches / len(profile_skills)
        base_score = match_ratio * 100

        # Bonus for title relevance
        title_lower = job.get('title', '').lower()
        title_keywords = ['hse', 'safety', 'operations', 'manager', 'supervisor',
                         'coordinator', 'drilling', 'consultant', 'risk', 'compliance']
        title_bonus = sum(5 for kw in title_keywords if kw in title_lower)

        # Location bonus
        location_bonus = 0
        job_location = job.get('location', '').lower()
        if 'remote' in job_location or 'oklahoma' in job_location:
            location_bonus = 10

        return min(100, base_score + title_bonus + location_bonus)

    def _heuristic_match(self, profile_data: Dict, job: Dict) -> Dict:
        """Heuristic-based matching when AI is unavailable."""
        profile = profile_data.get('profile', {})
        skills = profile_data.get('skills', [])

        job_text = f"{job.get('title', '')} {job.get('description', '')}".lower()

        # Skill matching
        skill_names = [s['skill_name'].lower() for s in skills]
        matched_skills = [s for s in skill_names if s in job_text]
        missing_skills = [s for s in skill_names if s not in job_text][:5]

        skill_score = (len(matched_skills) / max(len(skill_names), 1)) * 100

        # Experience matching
        years_exp = profile.get('years_experience', 0)
        exp_match = re.search(r'(\d+)\+?\s*years?', job_text)
        required_years = int(exp_match.group(1)) if exp_match else 5
        exp_score = 100 if years_exp >= required_years else (years_exp / required_years) * 100

        # Location matching
        job_location = job.get('location_type', job.get('location', '')).lower()
        location_score = 100 if 'remote' in job_location else 70

        # Overall score
        overall = (
            skill_score * self.WEIGHTS['skill_match'] +
            exp_score * self.WEIGHTS['experience'] +
            location_score * self.WEIGHTS['location'] +
            70 * self.WEIGHTS['salary'] +  # Default salary assumption
            70 * self.WEIGHTS['culture_fit']  # Default culture fit
        )

        # Determine recommendation
        if overall >= self.STRONG_MATCH:
            recommendation = 'strong_match'
        elif overall >= self.GOOD_MATCH:
            recommendation = 'good_match'
        elif overall >= self.POSSIBLE_MATCH:
            recommendation = 'possible_match'
        else:
            recommendation = 'poor_match'

        return {
            'overall_score': round(overall, 1),
            'skill_match_score': round(skill_score, 1),
            'experience_match_score': round(exp_score, 1),
            'location_match_score': round(location_score, 1),
            'salary_match_score': 70,
            'culture_fit_score': 70,
            'matched_skills': matched_skills[:10],
            'missing_skills': missing_skills,
            'strengths': self._identify_strengths(profile_data, job),
            'concerns': self._identify_concerns(profile_data, job),
            'reasoning': f"Skill match: {len(matched_skills)}/{len(skill_names)}. Experience: {years_exp} years vs {required_years} required.",
            'recommendation': recommendation
        }

    async def _ai_match(self, profile_data: Dict, job: Dict) -> Dict:
        """Use OpenAI GPT-4 for intelligent matching."""
        profile = profile_data.get('profile', {})
        skills = profile_data.get('skills', [])
        experiences = profile_data.get('experiences', [])
        certifications = profile_data.get('certifications', [])

        # Build prompt
        prompt = f"""Analyze this job-candidate match and provide a detailed scoring.

## CANDIDATE PROFILE

Name: {profile.get('name')}
Current Title: {profile.get('current_title')}
Years of Experience: {profile.get('years_experience')}
Location: {profile.get('location')}
Work Preferences: {profile.get('work_preferences')}
Salary Range: ${profile.get('salary_min', 'N/A')} - ${profile.get('salary_max', 'N/A')}

### Skills:
{chr(10).join(f"- {s['skill_name']} ({s.get('skill_category', 'general')}, {s.get('proficiency_level', 'unspecified')})" for s in skills[:20])}

### Recent Experience:
{chr(10).join(f"- {e['title']} at {e['company']} ({e.get('start_date', '?')}-{e.get('end_date', '?')})" for e in experiences[:5])}

### Certifications:
{chr(10).join(f"- {c['certification_name']}" for c in certifications[:10])}

### Career Context:
{profile.get('career_summary', 'N/A')}

---

## JOB POSTING

Title: {job.get('title')}
Company: {job.get('company_name')}
Location: {job.get('location')} ({job.get('location_type', 'unknown')})
Salary: ${job.get('salary_min', 'N/A')} - ${job.get('salary_max', 'N/A')}

### Description:
{job.get('description', 'No description available')[:2000]}

---

## ANALYSIS REQUIRED

Provide a JSON response with:
1. overall_score (0-100): Weighted match score
2. skill_match_score (0-100): How well skills align
3. experience_match_score (0-100): Experience relevance
4. location_match_score (0-100): Location compatibility
5. salary_match_score (0-100): Salary alignment (assume market rate if not specified)
6. culture_fit_score (0-100): Likely culture/industry fit
7. matched_skills: Array of matching skills
8. missing_skills: Array of missing required skills
9. strengths: Array of candidate strengths for this role
10. concerns: Array of potential concerns or gaps
11. reasoning: 2-3 sentence explanation
12. recommendation: "strong_match", "good_match", "possible_match", or "poor_match"

Consider:
- The candidate is transitioning to office/hybrid/remote roles due to an ankle injury
- 20+ years of HSE and operations experience is highly valuable
- Oil & gas industry experience transfers well to other high-risk industries
- Leadership and compliance experience is transferable

Respond ONLY with valid JSON, no markdown formatting."""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.openai_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": "You are an expert job matching analyst. Analyze candidate-job fit and provide detailed, actionable scoring. Always respond with valid JSON only."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 1000
                    }
                ) as response:
                    if response.status != 200:
                        error = await response.text()
                        logger.error(f"OpenAI API error: {response.status} - {error}")
                        return self._heuristic_match(profile_data, job)

                    data = await response.json()
                    content = data['choices'][0]['message']['content']

                    # Parse JSON response
                    # Clean up potential markdown formatting
                    content = content.strip()
                    if content.startswith('```'):
                        content = re.sub(r'^```(?:json)?\n?', '', content)
                        content = re.sub(r'\n?```$', '', content)

                    result = json.loads(content)
                    return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {e}")
            return self._heuristic_match(profile_data, job)
        except Exception as e:
            logger.error(f"AI matching error: {e}")
            return self._heuristic_match(profile_data, job)

    def _get_profile_data(self, profile_id: int) -> Optional[Dict]:
        """Get complete profile data."""
        profile = self.db.get_profile(profile_id)
        if not profile:
            return None

        skills = self.db.get_profile_skills(profile_id)

        with self.db.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM candidate_experience WHERE profile_id = ? ORDER BY start_date DESC",
                (profile_id,)
            )
            experiences = [dict(row) for row in cursor.fetchall()]

            cursor = conn.execute(
                "SELECT * FROM candidate_certifications WHERE profile_id = ?",
                (profile_id,)
            )
            certifications = [dict(row) for row in cursor.fetchall()]

        return {
            'profile': profile,
            'skills': skills,
            'experiences': experiences,
            'certifications': certifications
        }

    def _identify_strengths(self, profile_data: Dict, job: Dict) -> List[str]:
        """Identify candidate strengths for this job."""
        strengths = []
        profile = profile_data.get('profile', {})
        skills = profile_data.get('skills', [])

        job_text = f"{job.get('title', '')} {job.get('description', '')}".lower()

        # Check for experience advantage
        years = profile.get('years_experience', 0)
        if years >= 15:
            strengths.append(f"Extensive {years}+ years of industry experience")

        # Check for relevant skills
        hse_skills = [s for s in skills if 'hse' in s['skill_name'].lower() or 'safety' in s['skill_name'].lower()]
        if hse_skills and ('hse' in job_text or 'safety' in job_text):
            strengths.append("Strong HSE/Safety background directly relevant to role")

        # Check for leadership
        leadership_skills = [s for s in skills if 'leadership' in s['skill_name'].lower() or 'management' in s['skill_name'].lower()]
        if leadership_skills and ('manager' in job_text or 'supervisor' in job_text or 'leader' in job_text):
            strengths.append("Proven leadership and management experience")

        # Check certifications
        certs = profile_data.get('certifications', [])
        if certs:
            strengths.append(f"Holds {len(certs)} relevant industry certifications")

        return strengths[:5]

    def _identify_concerns(self, profile_data: Dict, job: Dict) -> List[str]:
        """Identify potential concerns or gaps."""
        concerns = []
        profile = profile_data.get('profile', {})

        job_text = f"{job.get('title', '')} {job.get('description', '')}".lower()

        # Check for technical skills gaps
        if 'software' in job_text or 'developer' in job_text or 'engineer' in job_text:
            concerns.append("Role may require more technical/software skills")

        # Check salary expectations
        job_min = job.get('salary_min')
        profile_min = profile.get('salary_min')
        if job_min and profile_min and job_min < profile_min * 0.8:
            concerns.append("Listed salary may be below candidate expectations")

        # Check for physical requirements
        if 'field' in job_text and 'travel' not in profile.get('work_preferences', ''):
            concerns.append("Role may have field requirements conflicting with mobility limitations")

        return concerns[:5]

    def get_match_summary(self, profile_id: int, min_score: float = 60) -> Dict:
        """Get a summary of matches for a profile."""
        matches = self.db.get_top_matches(profile_id, limit=50, min_score=min_score)

        summary = {
            'total_matches': len(matches),
            'strong_matches': len([m for m in matches if m['overall_score'] >= self.STRONG_MATCH]),
            'good_matches': len([m for m in matches if self.GOOD_MATCH <= m['overall_score'] < self.STRONG_MATCH]),
            'possible_matches': len([m for m in matches if self.POSSIBLE_MATCH <= m['overall_score'] < self.GOOD_MATCH]),
            'by_location_type': {},
            'by_source': {},
            'top_companies': [],
            'average_score': 0
        }

        if matches:
            summary['average_score'] = sum(m['overall_score'] for m in matches) / len(matches)

            # Group by location type
            for m in matches:
                loc_type = m.get('location_type', 'unknown')
                summary['by_location_type'][loc_type] = summary['by_location_type'].get(loc_type, 0) + 1

            # Group by source
            for m in matches:
                source = m.get('source', 'unknown')
                summary['by_source'][source] = summary['by_source'].get(source, 0) + 1

            # Top companies
            companies = {}
            for m in matches:
                company = m.get('company_name', 'Unknown')
                companies[company] = companies.get(company, 0) + 1
            summary['top_companies'] = sorted(companies.items(), key=lambda x: x[1], reverse=True)[:10]

        return summary


async def run_matching(profile_id: int = 1) -> List[Dict]:
    """Run job matching for a profile."""
    matcher = JobMatcher()
    return await matcher.match_jobs_for_profile(profile_id)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    matches = asyncio.run(run_matching(1))
    print(f"Found {len(matches)} matches")
    for m in matches[:5]:
        print(f"  - {m.get('job', {}).get('title')}: {m['overall_score']}")

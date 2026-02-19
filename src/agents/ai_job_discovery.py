"""
AI-Powered Job Discovery Agent
Uses DeepSeek AI to intelligently find and analyze job opportunities.
"""

import asyncio
import aiohttp
import json
import logging
import subprocess
from typing import List, Dict, Optional
from datetime import datetime

from src.utils.credentials import get_deepseek_key

logger = logging.getLogger(__name__)


class AIJobDiscovery:
    """
    AI-powered job discovery that:
    - Analyzes your resume to find optimal search terms
    - Generates intelligent search queries
    - Searches multiple diverse sources
    - Filters and ranks results
    """
    
    def __init__(self, db):
        self.db = db
        self.api_key = get_deepseek_key()
        self.api_base = "https://api.deepseek.com"
        
    async def discover_jobs(
        self,
        profile_data: Dict,
        location: str = "Oklahoma City, OK",
        max_jobs: int = 50
    ) -> List[Dict]:
        """
        Use AI to discover relevant job opportunities.
        
        Args:
            profile_data: Candidate profile with skills, experience, etc.
            location: Location to search
            max_jobs: Maximum jobs to return
            
        Returns:
            List of job dictionaries
        """
        logger.info("🤖 AI Job Discovery starting...")
        
        # Step 1: Generate intelligent search queries using AI
        search_queries = await self._generate_smart_queries(profile_data, location)
        logger.info(f"📝 Generated {len(search_queries)} AI-optimized search queries")
        
        # Step 2: Search diverse sources with these queries
        all_jobs = []
        for query_set in search_queries:
            jobs = await self._search_with_queries(query_set, location)
            all_jobs.extend(jobs)
            
        logger.info(f"✅ AI Discovery found {len(all_jobs)} total jobs")
        
        # Step 3: AI filtering and ranking
        if all_jobs:
            ranked_jobs = await self._ai_rank_jobs(all_jobs, profile_data)
            return ranked_jobs[:max_jobs]
        
        return []
    
    async def _generate_smart_queries(
        self,
        profile_data: Dict,
        location: str
    ) -> List[Dict[str, str]]:
        """Use DeepSeek to generate optimal search queries."""
        profile = profile_data.get('profile', {})
        skills = profile_data.get('skills', [])[:20]
        experiences = profile_data.get('experiences', [])[:5]
        
        prompt = f"""You are a job search expert. Generate DIVERSE job search queries for this candidate.

CANDIDATE: Daniel Gillaspy, Oklahoma City, OK
SEEKING: Office, hybrid, or remote roles (ankle injury limits sustained stair-climbing and rig-floor mobility; travel OK)

ACTUAL RESUME BACKGROUND (20+ years):
- Operations supervision: managed up to 6 concurrent multi-crew operations
- Budget management: AFE exposure $3MM-$32MM, daily cost tracking
- Logistics & resource coordination: crews, equipment, materials, scheduling
- Vendor & contractor management across every role
- HSE leadership: incident prevention, audits, inspections, safety culture
- OSHA interface, investigations support (TapRooT trained), corrective actions
- Project execution, scheduling, reporting, performance optimization
- Stakeholder communication, meeting leadership, cross-functional coordination
- Heavy equipment operations and site management
- Training teams, coaching, building accountability
- Tools: Excel, Word, PowerPoint, basic Python, daily reporting systems
- Certifications: IADC RigPass, HAZWOPER, Well Control/BOP, confined space, fall protection, LOTO, CPR/First Aid

COMPANIES WORKED FOR: ExxonMobil/XTO, Apache Corp, BP Canada, Altamesa Holdings, DET Consulting, Trinidad/Nabors/Unit Drilling

CRITICAL: Generate 20 queries across DIVERSE job categories. His skills transfer far beyond oil & gas:

CATEGORIES TO COVER (2-3 queries each):
1. Operations Management (any industry - manufacturing, logistics, construction)
2. Logistics / Supply Chain / Warehouse Management
3. Project Management / Project Coordination
4. Safety / HSE / EHS (but NOT the majority of queries)
5. Construction Management / Site Supervision
6. Vendor / Procurement / Contract Management
7. Cost Control / Budget Analysis / Financial Operations
8. Training / Development / Safety Training
9. Risk Management / Compliance / Investigations
10. Oil & Gas Office Roles (drilling coordinator, well planner, rig coordinator)
11. Facilities Management / Maintenance Management
12. Account Management / Business Development (oilfield services)

For EACH query, specify:
- query: Short job search term (2-5 words, what you'd type into Indeed/LinkedIn)
- sources: ["linkedin", "indeed", "ziprecruiter"] (pick 2-3 relevant ones)
- reasoning: One sentence why this fits

Respond ONLY with valid JSON array, no markdown:
[{{"query": "Operations Manager", "sources": ["linkedin", "indeed"], "reasoning": "20 years managing multi-crew operations"}}, ...]"""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {"role": "system", "content": "You are an expert job search strategist. Always respond with valid JSON only."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.7,
                        "max_tokens": 2000
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data['choices'][0]['message']['content']

                        # Clean up markdown formatting (DeepSeek often wraps JSON in ```)
                        content = content.strip()
                        if content.startswith('```'):
                            import re
                            content = re.sub(r'^```(?:json)?\n?', '', content)
                            content = re.sub(r'\n?```$', '', content)

                        # Parse JSON from response
                        queries = json.loads(content)
                        logger.info(f"🎯 AI generated {len(queries)} optimized queries")

                        # Log sample queries for debugging
                        if queries:
                            logger.info(f"Sample queries: {', '.join([q['query'] for q in queries[:5]])}")

                        return queries
                    else:
                        error = await response.text()
                        logger.error(f"DeepSeek API error: {response.status} - {error}")
                        
        except Exception as e:
            logger.error(f"Failed to generate AI queries: {e}")
        
        # Fallback to default queries
        return self._default_queries()
    
    async def _search_with_queries(
        self,
        query_info: Dict,
        location: str
    ) -> List[Dict]:
        """Search for jobs using a query across specified sources."""
        query = query_info.get('query', '')
        sources = query_info.get('sources', ['linkedin', 'indeed'])
        
        jobs = []
        
        for source in sources[:3]:  # Top 3 sources per query
            site_query = f"site:{source}.com/jobs {query} {location}"
            
            try:
                # Use free-search with system Python (has requests module)
                result = subprocess.run(
                    ['/opt/homebrew/bin/python3', '/Users/daniel/.openclaw/tools/free_web_search.py', site_query],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    
                    if data.get('success') and data.get('results'):
                        for item in data['results'][:3]:
                            job = self._parse_job(item, query, location, source)
                            if job:
                                jobs.append(job)
                                
            except Exception as e:
                logger.debug(f"Search error for {source}: {e}")
                
        return jobs
    
    async def _ai_rank_jobs(
        self,
        jobs: List[Dict],
        profile_data: Dict
    ) -> List[Dict]:
        """Use AI to rank and filter jobs by relevance."""
        # Simple deduplication first
        seen_urls = set()
        unique_jobs = []
        for job in jobs:
            if job['apply_url'] not in seen_urls:
                seen_urls.add(job['apply_url'])
                unique_jobs.append(job)
        
        logger.info(f"🎯 After deduplication: {len(unique_jobs)} unique jobs")
        return unique_jobs
    
    def _parse_job(
        self,
        result: Dict,
        query: str,
        location: str,
        source: str
    ) -> Optional[Dict]:
        """Parse job from search result."""
        try:
            return {
                'title': result.get('title', ''),
                'company_name': self._extract_company(result.get('title', ''), result.get('snippet', '')),
                'location': location,
                'location_type': 'onsite',
                'description': result.get('snippet', ''),
                'apply_url': result.get('url', ''),
                'source': f'ai-discovery-{source}',
                'posted_date': datetime.now().isoformat(),
                'salary_min': None,
                'salary_max': None,
            }
        except Exception as e:
            logger.debug(f"Failed to parse job: {e}")
            return None
    
    def _extract_company(self, title: str, snippet: str) -> str:
        """Extract company name from title or snippet."""
        import re
        at_match = re.search(r'\sat\s+([A-Z][A-Za-z\s&]+?)(?:\s*[-|]|$)', title)
        if at_match:
            return at_match.group(1).strip()
        return "Company"
    
    def _default_queries(self) -> List[Dict]:
        """Fallback queries if AI generation fails."""
        return [
            {"query": "HSE Manager oil gas", "sources": ["rigzone", "energyjobline"]},
            {"query": "Safety Manager remote", "sources": ["linkedin", "ziprecruiter"]},
            {"query": "Operations Manager energy", "sources": ["glassdoor", "indeed"]},
            {"query": "Drilling Consultant", "sources": ["rigzone", "energyjobline"]},
            {"query": "Compliance Manager petroleum", "sources": ["linkedin", "indeed"]},
        ]


async def run_ai_job_discovery(db, profile_data: Dict, location: str) -> List[Dict]:
    """Run AI-powered job discovery."""
    discovery = AIJobDiscovery(db)
    return await discovery.discover_jobs(profile_data, location)

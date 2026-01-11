"""
Job Searcher Sub-Agent
Searches multiple job boards and APIs for relevant listings.
"""

import json
import asyncio
import aiohttp
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urljoin
import logging
import hashlib
import time

from src.database import DatabaseManager, get_db
from src.utils.credentials import get_brave_api_key, get_tavily_api_key
from src.agents.rss_scraper import run_rss_scraping
from src.agents.usajobs_scraper import run_usajobs_search
from src.agents.company_scraper import run_company_scraping
from src.agents.playwright_indeed_scraper import run_playwright_indeed_scraping

logger = logging.getLogger(__name__)


class JobSearcher:
    """
    Multi-source job searcher that aggregates listings from:
    - Brave Search API
    - Tavily Search API
    - Direct job board scraping (Indeed, LinkedIn, RemoteOK, etc.)
    """

    # Job board search URLs
    JOB_BOARDS = {
        'linkedin': 'https://www.linkedin.com/jobs/search/?keywords={query}&location={location}&f_WT={remote}',
        'indeed': 'https://www.indeed.com/jobs?q={query}&l={location}&remotejob={remote}',
        'remoteok': 'https://remoteok.com/remote-{query}-jobs',
        'glassdoor': 'https://www.glassdoor.com/Job/jobs.htm?sc.keyword={query}&locT=&locId=&locKeyword={location}',
        'ziprecruiter': 'https://www.ziprecruiter.com/jobs-search?search={query}&location={location}',
    }

    # Search queries tailored for the candidate
    DEFAULT_QUERIES = [
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
    ]

    def __init__(self, db: DatabaseManager = None):
        self.db = db or get_db()
        self.brave_key = get_brave_api_key()
        self.tavily_key = get_tavily_api_key()
        self._rate_limit_delay = 1.0  # seconds between API calls

    async def search_all_sources(
        self,
        queries: List[str] = None,
        location: str = "Oklahoma City, OK",
        remote_only: bool = False,
        max_per_source: int = 20
    ) -> Dict[str, int]:
        """
        Search all available sources for job listings.

        Args:
            queries: Search queries (uses defaults if None)
            location: Location to search
            remote_only: Only search for remote positions
            max_per_source: Maximum results per source

        Returns:
            Dict with source names and job counts
        """
        queries = queries or self.DEFAULT_QUERIES
        results = {}
        total_new = 0

        logger.info(f"Starting job search with {len(queries)} queries")

        # Search with Brave API
        if self.brave_key:
            count, new = await self._search_brave(queries, location, remote_only, max_per_source)
            results['brave'] = {'total': count, 'new': new}
            total_new += new

        # Search with Tavily API
        if self.tavily_key:
            count, new = await self._search_tavily(queries, location, remote_only, max_per_source)
            results['tavily'] = {'total': count, 'new': new}
            total_new += new

        # Search job boards directly
        count, new = await self._search_job_boards(queries, location, remote_only, max_per_source)
        results['job_boards'] = {'total': count, 'new': new}
        total_new += new

        # Log search run
        self.db.log_search_run(
            source='all',
            jobs_found=sum(r['total'] for r in results.values()),
            new_jobs=total_new
        )

        logger.info(f"Search complete: {total_new} new jobs found")
        return results

    async def _search_brave(
        self,
        queries: List[str],
        location: str,
        remote_only: bool,
        max_results: int
    ) -> Tuple[int, int]:
        """Search using Brave Search API."""
        logger.info("Searching with Brave API...")

        total_found = 0
        new_jobs = 0

        async with aiohttp.ClientSession() as session:
            for query in queries[:10]:  # Limit queries to avoid rate limits
                search_query = f"{query} jobs {location}"
                if remote_only:
                    search_query += " remote"

                try:
                    async with session.get(
                        "https://api.search.brave.com/res/v1/web/search",
                        headers={"X-Subscription-Token": self.brave_key},
                        params={
                            "q": search_query,
                            "count": max_results,
                            "search_lang": "en",
                            "result_filter": "web"
                        }
                    ) as response:
                        if response.status != 200:
                            logger.warning(f"Brave API error: {response.status}")
                            continue

                        data = await response.json()
                        results = data.get('web', {}).get('results', [])

                        for result in results:
                            job_data = self._parse_brave_result(result, query)
                            if job_data:
                                job_id, is_new = self.db.add_job_listing(**job_data)
                                total_found += 1
                                if is_new:
                                    new_jobs += 1

                except Exception as e:
                    logger.error(f"Brave search error for '{query}': {e}")

                await asyncio.sleep(self._rate_limit_delay)

        self.db.log_search_run('brave', total_found, new_jobs)
        logger.info(f"Brave search: {total_found} found, {new_jobs} new")
        return total_found, new_jobs

    async def _search_tavily(
        self,
        queries: List[str],
        location: str,
        remote_only: bool,
        max_results: int
    ) -> Tuple[int, int]:
        """Search using Tavily API."""
        logger.info("Searching with Tavily API...")

        total_found = 0
        new_jobs = 0

        async with aiohttp.ClientSession() as session:
            for query in queries[:10]:
                search_query = f"{query} job openings {location}"
                if remote_only:
                    search_query += " remote work"

                try:
                    async with session.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": self.tavily_key,
                            "query": search_query,
                            "search_depth": "advanced",
                            "max_results": max_results,
                            "include_domains": [
                                "linkedin.com/jobs",
                                "indeed.com",
                                "glassdoor.com",
                                "ziprecruiter.com",
                                "monster.com",
                                "careerbuilder.com",
                                "simplyhired.com",
                                "oilandgasjobsearch.com",
                                "rigzone.com"
                            ]
                        }
                    ) as response:
                        if response.status != 200:
                            logger.warning(f"Tavily API error: {response.status}")
                            continue

                        data = await response.json()
                        results = data.get('results', [])

                        for result in results:
                            job_data = self._parse_tavily_result(result, query)
                            if job_data:
                                job_id, is_new = self.db.add_job_listing(**job_data)
                                total_found += 1
                                if is_new:
                                    new_jobs += 1

                except Exception as e:
                    logger.error(f"Tavily search error for '{query}': {e}")

                await asyncio.sleep(self._rate_limit_delay)

        self.db.log_search_run('tavily', total_found, new_jobs)
        logger.info(f"Tavily search: {total_found} found, {new_jobs} new")
        return total_found, new_jobs

    async def _search_job_boards(
        self,
        queries: List[str],
        location: str,
        remote_only: bool,
        max_results: int
    ) -> Tuple[int, int]:
        """Search job boards directly."""
        logger.info("Searching job boards directly...")

        total_found = 0
        new_jobs = 0

        # USAJOBS - Free federal job API (NO API KEY REQUIRED)
        logger.info("Running USAJOBS federal job search...")
        try:
            usajobs = await run_usajobs_search(self.db, queries[:10], location)
            logger.info(f"USAJOBS found {len(usajobs)} federal positions")
            for job in usajobs[:max_results]:
                try:
                    job_id, is_new = self.db.add_job_listing(**job)
                    total_found += 1
                    if is_new:
                        new_jobs += 1
                except Exception as e:
                    logger.warning(f"Failed to add USAJOBS listing: {e}")
        except Exception as e:
            logger.error(f"USAJOBS search failed: {e}")

        # Company career pages (Devon, Continental, Chesapeake, Marathon) - NO API KEY REQUIRED
        logger.info("Running company career page scraper (Oklahoma energy companies)...")
        try:
            company_jobs = await run_company_scraping(self.db, queries[:10], location)
            logger.info(f"Company scraper found {len(company_jobs)} jobs")
            for job in company_jobs[:max_results]:
                try:
                    job_id, is_new = self.db.add_job_listing(**job)
                    total_found += 1
                    if is_new:
                        new_jobs += 1
                except Exception as e:
                    logger.warning(f"Failed to add company job: {e}")
        except Exception as e:
            logger.error(f"Company scraping failed: {e}")

        # RSS Feed scraping (Indeed, SimplyHired) - NO API KEY REQUIRED
        # NOTE: Often blocked by 403 Forbidden - use Playwright below instead
        logger.info("Running RSS feed scraper (Indeed, SimplyHired)...")
        try:
            scraped_jobs = await run_rss_scraping(self.db, queries[:5], location)
            logger.info(f"RSS scraper found {len(scraped_jobs)} jobs")
            for job in scraped_jobs[:max_results]:
                try:
                    job_id, is_new = self.db.add_job_listing(**job)
                    total_found += 1
                    if is_new:
                        new_jobs += 1
                except Exception as e:
                    logger.warning(f"Failed to add scraped job: {e}")
        except Exception as e:
            logger.error(f"RSS scraping failed: {e}")

        # Playwright Indeed scraping - RECOMMENDED: Bypasses 403 blocks
        logger.info("🎭 Running Playwright Indeed scraper (bypasses bot detection)...")
        try:
            playwright_jobs = await run_playwright_indeed_scraping(self.db, queries[:5], location)
            logger.info(f"✅ Playwright found {len(playwright_jobs)} jobs from Indeed")
            for job in playwright_jobs[:max_results]:
                try:
                    job_id, is_new = self.db.add_job_listing(**job)
                    total_found += 1
                    if is_new:
                        new_jobs += 1
                except Exception as e:
                    logger.warning(f"Failed to add Playwright job: {e}")
        except Exception as e:
            logger.error(f"❌ Playwright scraping failed: {e}")

        # RemoteOK API - DISABLED: Only has tech/software jobs, not HSE/Operations
        # remoteok_jobs = await self._search_remoteok(queries)
        # for job in remoteok_jobs[:max_results]:
        #     job_id, is_new = self.db.add_job_listing(**job)
        #     total_found += 1
        #     if is_new:
        #         new_jobs += 1

        self.db.log_search_run('job_boards', total_found, new_jobs)
        logger.info(f"Job boards: {total_found} found, {new_jobs} new")
        return total_found, new_jobs

    async def _search_remoteok(self, queries: List[str]) -> List[Dict]:
        """Search RemoteOK API."""
        jobs = []

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://remoteok.com/api",
                    headers={"User-Agent": "JobSearchAutomation/1.0"}
                ) as response:
                    if response.status != 200:
                        return jobs

                    data = await response.json()

                    # Filter by relevant tags
                    relevant_tags = {'management', 'operations', 'safety', 'health',
                                   'compliance', 'risk', 'executive', 'leadership'}

                    for item in data:
                        if not isinstance(item, dict) or 'id' not in item:
                            continue

                        # Check if job matches any query
                        position = item.get('position', '').lower()
                        tags = set(t.lower() for t in item.get('tags', []))

                        matches = any(
                            q.lower() in position or
                            any(tag in relevant_tags for tag in tags)
                            for q in queries
                        )

                        if matches:
                            jobs.append({
                                'source': 'remoteok',
                                'external_id': str(item.get('id')),
                                'company_name': item.get('company', 'Unknown'),
                                'title': item.get('position', 'Unknown'),
                                'description': item.get('description', ''),
                                'location': item.get('location', 'Remote'),
                                'location_type': 'remote',
                                'salary_min': self._parse_salary(item.get('salary_min')),
                                'salary_max': self._parse_salary(item.get('salary_max')),
                                'posted_date': item.get('date'),
                                'apply_url': item.get('url'),
                                'raw_data': json.dumps(item)
                            })

        except Exception as e:
            logger.error(f"RemoteOK search error: {e}")

        return jobs

    def _parse_brave_result(self, result: Dict, query: str) -> Optional[Dict]:
        """Parse a Brave search result into job data."""
        url = result.get('url', '')
        title = result.get('title', '')
        description = result.get('description', '')

        # Skip non-job results
        if not any(site in url.lower() for site in ['linkedin.com/jobs', 'indeed.com', 'glassdoor.com',
                                                      'ziprecruiter.com', 'monster.com', 'careers']):
            return None

        # Skip if title doesn't look like a job posting
        if not any(word in title.lower() for word in ['job', 'hiring', 'position', 'career', 'opportunity']):
            return None

        # Extract company from title or URL
        company = self._extract_company(title, url)

        # Generate external ID from URL hash
        external_id = hashlib.md5(url.encode()).hexdigest()[:16]

        return {
            'source': 'brave',
            'external_id': external_id,
            'company_name': company,
            'title': self._clean_title(title),
            'description': description,
            'apply_url': url,
            'location': self._extract_location(description),
            'location_type': 'remote' if 'remote' in description.lower() else None,
            'raw_data': json.dumps(result)
        }

    def _parse_tavily_result(self, result: Dict, query: str) -> Optional[Dict]:
        """Parse a Tavily search result into job data."""
        url = result.get('url', '')
        title = result.get('title', '')
        content = result.get('content', '')

        # Skip non-job results
        if not any(site in url.lower() for site in ['linkedin.com/jobs', 'indeed.com', 'glassdoor.com',
                                                      'ziprecruiter.com', 'monster.com', 'careers', 'rigzone']):
            return None

        company = self._extract_company(title, url)
        external_id = hashlib.md5(url.encode()).hexdigest()[:16]

        return {
            'source': 'tavily',
            'external_id': external_id,
            'company_name': company,
            'title': self._clean_title(title),
            'description': content,
            'apply_url': url,
            'location': self._extract_location(content),
            'location_type': 'remote' if 'remote' in content.lower() else None,
            'raw_data': json.dumps(result)
        }

    def _extract_company(self, title: str, url: str) -> str:
        """Extract company name from title or URL."""
        # Common patterns: "Job Title at Company" or "Job Title - Company"
        patterns = [
            r'(?:at|@)\s+([A-Za-z0-9\s&]+?)(?:\s*[-|]|$)',
            r'[-|]\s*([A-Za-z0-9\s&]+?)(?:\s*[-|]|$)',
            r'^([A-Za-z0-9\s&]+?)\s+(?:is hiring|jobs)',
        ]

        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return "Unknown Company"

    def _clean_title(self, title: str) -> str:
        """Clean up job title."""
        # Remove common suffixes
        title = re.sub(r'\s*[-|]\s*(?:LinkedIn|Indeed|Glassdoor|ZipRecruiter).*$', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*\(.*?\)\s*$', '', title)
        return title.strip()

    def _extract_location(self, text: str) -> str:
        """Extract location from text."""
        # Look for city, state patterns
        patterns = [
            r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?,\s*[A-Z]{2})',  # City, ST
            r'(Oklahoma City|Houston|Dallas|Denver|Tulsa|Midland|Odessa)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)

        if 'remote' in text.lower():
            return 'Remote'

        return 'Not specified'

    def _parse_salary(self, salary_str) -> Optional[int]:
        """Parse salary string to integer."""
        if not salary_str:
            return None
        try:
            # Remove non-numeric characters
            cleaned = re.sub(r'[^\d]', '', str(salary_str))
            return int(cleaned) if cleaned else None
        except:
            return None

    def get_search_stats(self) -> Dict:
        """Get search statistics."""
        with self.db.connection() as conn:
            # Jobs by source
            cursor = conn.execute("""
                SELECT source, COUNT(*) as count
                FROM job_listings
                GROUP BY source
            """)
            by_source = {row['source']: row['count'] for row in cursor.fetchall()}

            # Recent searches
            cursor = conn.execute("""
                SELECT source, jobs_found, new_jobs, run_at
                FROM search_runs
                ORDER BY run_at DESC
                LIMIT 10
            """)
            recent_runs = [dict(row) for row in cursor.fetchall()]

            # Jobs by day
            cursor = conn.execute("""
                SELECT date(created_at) as date, COUNT(*) as count
                FROM job_listings
                GROUP BY date(created_at)
                ORDER BY date DESC
                LIMIT 7
            """)
            by_day = {row['date']: row['count'] for row in cursor.fetchall()}

        return {
            'by_source': by_source,
            'recent_runs': recent_runs,
            'by_day': by_day
        }


async def run_job_search(
    queries: List[str] = None,
    location: str = "Oklahoma City, OK",
    remote_only: bool = False
) -> Dict:
    """Run a complete job search."""
    searcher = JobSearcher()
    return await searcher.search_all_sources(
        queries=queries,
        location=location,
        remote_only=remote_only
    )


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    results = asyncio.run(run_job_search())
    print(json.dumps(results, indent=2))

"""
USAJOBS API Scraper - Completely Free, No Credit Card
Official US Government API for federal job postings
"""

import asyncio
import aiohttp
from typing import Dict, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class USAJobsScraper:
    """
    USAJOBS scraper using official government API.
    100% free, no credit card required.
    Requires free API key from: https://developer.usajobs.gov/APIRequest/Index
    """

    BASE_URL = "https://data.usajobs.gov/api/search"

    def __init__(self, db):
        self.db = db
        # Use shared credential manager (reads from productivity.db)
        from src.utils.credentials import get_credential_manager
        manager = get_credential_manager()
        self.api_key = manager.get('usajobs', 'USAJOBS_API_KEY')

    async def search_federal_jobs(
        self,
        queries: List[str],
        location: str = "Oklahoma"
    ) -> List[Dict]:
        """Search USAJOBS federal positions."""

        # Check if API key is available
        if not self.api_key:
            logger.warning("USAJOBS API key not found. Register for free (no credit card) at: https://developer.usajobs.gov/APIRequest/Index")
            logger.warning("Add key to database: sqlite3 ~/databases/productivity.db \"INSERT INTO credentials (service_name, api_key, is_active) VALUES ('usajobs', 'YOUR_API_KEY', 1);\"")
            return []

        logger.info(f"Searching USAJOBS for {len(queries)} queries")

        all_jobs = []

        # USAJOBS requires API key but is completely free (no credit card)
        for query in queries[:3]:  # Limit queries
            logger.info(f"USAJOBS Search: {query}")

            try:
                async with aiohttp.ClientSession() as session:
                    # USAJOBS API endpoint
                    url = "https://data.usajobs.gov/api/search"
                    params = {
                        'Keyword': query,
                        'LocationName': location,
                        'ResultsPerPage': 10
                    }

                    headers = {
                        'Host': 'data.usajobs.gov',
                        'User-Agent': 'dgillaspy@me.com',
                        'Authorization-Key': self.api_key
                    }

                    async with session.get(url, params=params, headers=headers, timeout=15) as response:
                        if response.status == 200:
                            data = await response.json()

                            search_result = data.get('SearchResult', {})
                            search_result_items = search_result.get('SearchResultItems', [])

                            for item in search_result_items:
                                try:
                                    match_data = item.get('MatchedObjectDescriptor', {})

                                    title = match_data.get('PositionTitle', query)
                                    org = match_data.get('OrganizationName', 'Federal Agency')
                                    locations = match_data.get('PositionLocationDisplay', location)
                                    url_text = match_data.get('PositionURI', '')
                                    salary_min = match_data.get('PositionRemuneration', [{}])[0].get('MinimumRange', 0) if match_data.get('PositionRemuneration') else 0
                                    salary_max = match_data.get('PositionRemuneration', [{}])[0].get('MaximumRange', 0) if match_data.get('PositionRemuneration') else 0

                                    job = {
                                        'title': title,
                                        'company_name': org,
                                        'location': locations,
                                        'source': 'usajobs',
                                        'apply_url': url_text,
                                        'description': f"Federal position: {title} at {org}",
                                        'posted_date': datetime.now().isoformat(),
                                        'location_type': 'onsite',
                                        'employment_type': 'full-time',
                                        'salary_min': int(salary_min) if salary_min else None,
                                        'salary_max': int(salary_max) if salary_max else None
                                    }
                                    all_jobs.append(job)

                                except Exception as e:
                                    logger.warning(f"Failed to parse USAJOBS item: {e}")

                            logger.info(f"USAJOBS: Found {len(search_result_items)} jobs for '{query}'")
                        else:
                            logger.warning(f"USAJOBS returned status {response.status}")

            except Exception as e:
                logger.error(f"USAJOBS search failed for '{query}': {e}")

            await asyncio.sleep(2)  # Rate limit

        logger.info(f"USAJOBS complete: {len(all_jobs)} federal jobs")
        return all_jobs


# Async wrapper
async def run_usajobs_search(db, queries: List[str], location: str) -> List[Dict]:
    """Run USAJOBS search and return jobs."""
    scraper = USAJobsScraper(db)
    return await scraper.search_federal_jobs(queries, location)

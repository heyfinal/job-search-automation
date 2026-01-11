"""
Production Playwright Indeed Scraper
Uses Playwright library directly for automated job scraping.
Works in cron/launchd without MCP server.
"""

import asyncio
import hashlib
import re
from typing import Dict, List, Set
from datetime import datetime
import logging
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)


class PlaywrightIndeedScraper:
    """
    Production-ready Indeed scraper using Playwright.
    Bypasses bot detection, extracts full job data, handles errors gracefully.
    """

    def __init__(self, db):
        self.db = db
        self.seen_urls: Set[str] = set()
        self.browser = None
        self.context = None

    def _make_job_hash(self, title: str, company: str) -> str:
        """Create hash for deduplication."""
        key = f"{title.lower().strip()}|{company.lower().strip()}"
        return hashlib.md5(key.encode()).hexdigest()

    def _parse_salary(self, salary_text: str) -> tuple:
        """Parse salary text and extract min/max values."""
        if not salary_text:
            return None, None

        salary_text = salary_text.replace('a year', '').replace('an hour', '').strip()
        numbers = re.findall(r'\$?([\d,]+(?:\.\d{2})?)', salary_text)

        if not numbers:
            return None, None

        try:
            nums = [int(n.replace(',', '').split('.')[0]) for n in numbers]

            # Convert hourly to annual
            if 'hour' in salary_text.lower():
                nums = [n * 2080 for n in nums]

            if len(nums) >= 2:
                return min(nums), max(nums)
            elif len(nums) == 1:
                return nums[0], nums[0]

        except ValueError:
            pass

        return None, None

    async def search_jobs(
        self,
        queries: List[str],
        location: str = "Oklahoma",
        max_per_query: int = 15
    ) -> List[Dict]:
        """
        Search Indeed for jobs using Playwright.
        Returns list of unique job dictionaries.
        """
        all_jobs = []
        seen_hashes = set()

        logger.info(f"🚀 Starting Playwright job scraping for {len(queries)} queries")

        try:
            async with async_playwright() as p:
                # Launch browser in headless mode
                self.browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )

                # Create context with realistic user agent
                self.context = await self.browser.new_context(
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1280, 'height': 720}
                )

                # Process each query
                for query in queries[:5]:  # Limit to top 5 queries
                    logger.info(f"🔍 Searching Indeed: '{query}' in {location}")

                    try:
                        jobs = await self._scrape_indeed_page(query, location, max_per_query)

                        # Deduplicate
                        for job in jobs:
                            job_hash = self._make_job_hash(job['title'], job['company_name'])
                            if job_hash not in seen_hashes and job['apply_url'] not in self.seen_urls:
                                all_jobs.append(job)
                                seen_hashes.add(job_hash)
                                self.seen_urls.add(job['apply_url'])

                        logger.info(f"✅ Found {len(jobs)} jobs for '{query}' ({len(all_jobs)} total unique)")
                        await asyncio.sleep(3)  # Rate limiting - 3s between queries

                    except Exception as e:
                        logger.error(f"❌ Failed to scrape '{query}': {e}")

                await self.browser.close()

        except Exception as e:
            logger.error(f"❌ Browser error: {e}")

        logger.info(f"🎉 Playwright scraping complete: {len(all_jobs)} unique jobs")
        return all_jobs

    async def _scrape_indeed_page(self, query: str, location: str, max_jobs: int) -> List[Dict]:
        """Scrape a single Indeed search results page."""
        jobs = []

        try:
            page = await self.context.new_page()

            # Build URL
            url = f"https://www.indeed.com/jobs?q={query.replace(' ', '+')}&l={location}"

            # Navigate - use 'load' instead of 'networkidle' (more reliable)
            logger.info(f"📄 Loading: {url}")
            try:
                await page.goto(url, wait_until='load', timeout=45000)
                # Give page extra time to render jobs
                await asyncio.sleep(3)
            except PlaywrightTimeout:
                logger.warning(f"Page load timeout for {url}")
                await page.close()
                return jobs

            # Wait for job listings to load - try multiple selectors
            job_cards = []
            try:
                await page.wait_for_selector('.job_seen_beacon', timeout=20000)
                job_cards = await page.query_selector_all('.job_seen_beacon')
            except PlaywrightTimeout:
                # Fallback: try alternative selector
                logger.debug("Primary selector timed out, trying alternative...")
                try:
                    await page.wait_for_selector('.jobCard', timeout=10000)
                    job_cards = await page.query_selector_all('.jobCard')
                except PlaywrightTimeout:
                    logger.warning(f"No job listings found for '{query}' in {location} (tried .job_seen_beacon and .jobCard)")
                    await page.close()
                    return jobs

            if not job_cards:
                logger.warning("No job cards found on page")
                await page.close()
                return jobs
            logger.info(f"📊 Found {len(job_cards)} job cards on page")

            for card in job_cards[:max_jobs]:
                try:
                    job_data = await self._extract_job_from_card(card, query, location)
                    if job_data:
                        jobs.append(job_data)

                except Exception as e:
                    logger.debug(f"Failed to extract job card: {e}")

            await page.close()

        except Exception as e:
            logger.error(f"Page scraping error: {e}")

        return jobs

    async def _extract_job_from_card(self, card, query: str, location: str) -> dict:
        """Extract job data from a single job card element."""
        try:
            # Extract title
            title_el = await card.query_selector('.jobTitle span')
            title = await title_el.inner_text() if title_el else None

            if not title or len(title) < 10:
                return None

            # Filter out navigation links
            skip_keywords = ['apply now', 'post jobs', 'salary estimator', 'contact us',
                           'all jobs', 'sign up', 'login', 'register', 'search']
            if any(kw in title.lower() for kw in skip_keywords):
                return None

            # Extract company
            company_el = await card.query_selector('[data-testid="company-name"]')
            company = await company_el.inner_text() if company_el else 'Company Not Listed'

            # Extract location
            location_el = await card.query_selector('[data-testid="text-location"]')
            job_location = await location_el.inner_text() if location_el else location

            # Extract URL
            link_el = await card.query_selector('.jobTitle a')
            href = await link_el.get_attribute('href') if link_el else ''
            apply_url = f"https://www.indeed.com{href}" if href else ''

            if not apply_url:
                return None

            # Extract description snippet
            snippet_el = await card.query_selector('.job-snippet')
            description = await snippet_el.inner_text() if snippet_el else f"{title} at {company} in {job_location}"

            # Extract salary if available
            salary_el = await card.query_selector('.salary-snippet, [class*="salary"]')
            salary_text = await salary_el.inner_text() if salary_el else None
            salary_min, salary_max = self._parse_salary(salary_text)

            # Determine location type
            desc_lower = description.lower()
            loc_lower = job_location.lower()
            if 'remote' in desc_lower or 'remote' in loc_lower:
                location_type = 'remote'
            elif 'hybrid' in desc_lower or 'hybrid' in loc_lower:
                location_type = 'hybrid'
            else:
                location_type = 'onsite'

            # Build job dictionary
            job = {
                'title': title.strip(),
                'company_name': company.strip(),
                'location': job_location.strip(),
                'source': 'indeed_playwright',
                'apply_url': apply_url,
                'description': description.strip()[:500],
                'posted_date': datetime.now().isoformat(),
                'location_type': location_type,
                'employment_type': 'full-time',
                'salary_min': salary_min,
                'salary_max': salary_max
            }

            return job

        except Exception as e:
            logger.debug(f"Card extraction error: {e}")
            return None


# Async wrapper
async def run_playwright_indeed_scraping(db, queries: List[str], location: str) -> List[Dict]:
    """
    Main entry point for Playwright Indeed scraping.
    Called by job_searcher.py
    """
    scraper = PlaywrightIndeedScraper(db)
    return await scraper.search_jobs(queries, location, max_per_query=15)

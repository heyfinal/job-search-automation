"""
Company Career Page Scraper - Oklahoma Energy Companies
Scrapes directly from company career pages for HSE/Operations positions.
"""

import asyncio
import re
import json
from typing import Dict, List
from datetime import datetime
import logging
import urllib.request
import urllib.parse
from html.parser import HTMLParser

logger = logging.getLogger(__name__)


class JobHTMLParser(HTMLParser):
    """Simple HTML parser to extract job listings."""

    def __init__(self):
        super().__init__()
        self.jobs = []
        self.current_job = {}
        self.capturing = False
        self.capture_tag = None

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        # Look for job listing containers
        if 'class' in attrs_dict:
            classes = attrs_dict['class'].lower()
            if any(kw in classes for kw in ['job', 'career', 'position', 'listing', 'opening']):
                self.current_job = {}

    def handle_data(self, data):
        data = data.strip()
        if data and len(data) > 3:
            # Try to categorize the data
            if not self.current_job.get('title') and len(data) < 100:
                self.current_job['title'] = data
            elif not self.current_job.get('location') and any(kw in data.lower() for kw in ['oklahoma', 'ok', 'remote', 'city']):
                self.current_job['location'] = data


class CompanyCareerScraper:
    """
    Scrapes job listings from Oklahoma energy company career pages.
    Direct scraping from company websites - usually less restrictive.
    """

    # Oklahoma energy companies with career pages
    COMPANIES = {
        'devon': {
            'name': 'Devon Energy',
            'url': 'https://www.devonenergy.com/careers',
            'search_url': 'https://wd5.myworkdaysite.com/en-US/recruiting/devonenergy/Careers',
            'type': 'workday'
        },
        'continental': {
            'name': 'Continental Resources',
            'url': 'https://www.clr.com/careers',
            'search_url': 'https://clr.wd1.myworkdayjobs.com/en-US/CLR_External_Career_Site',
            'type': 'workday'
        },
        'chesapeake': {
            'name': 'Chesapeake Energy',
            'url': 'https://www.chk.com/careers',
            'search_url': 'https://www.chk.com/careers',
            'type': 'html'
        },
        'ovintiv': {
            'name': 'Ovintiv',
            'url': 'https://ovintiv.com/careers/',
            'search_url': 'https://ovintiv.wd1.myworkdayjobs.com/en-US/Careers',
            'type': 'workday'
        }
    }

    def __init__(self, db):
        self.db = db
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }

    async def search_all_companies(
        self,
        queries: List[str],
        location: str = "Oklahoma"
    ) -> List[Dict]:
        """Search all company career pages."""
        logger.info(f"Searching company career pages for {len(queries)} queries")

        all_jobs = []

        # Search each company
        for company_key, company_info in self.COMPANIES.items():
            logger.info(f"Searching {company_info['name']}...")

            try:
                jobs = await self._scrape_company(company_key, company_info, queries, location)
                all_jobs.extend(jobs)
                logger.info(f"{company_info['name']}: Found {len(jobs)} jobs")
                await asyncio.sleep(2)  # Be respectful with rate limiting
            except Exception as e:
                logger.error(f"Failed to scrape {company_info['name']}: {e}")

        logger.info(f"Company career pages: {len(all_jobs)} total jobs found")
        return all_jobs

    async def _scrape_company(
        self,
        company_key: str,
        company_info: Dict,
        queries: List[str],
        location: str
    ) -> List[Dict]:
        """Scrape a specific company's career page."""

        scraper_type = company_info.get('type', 'html')

        if scraper_type == 'json_api':
            return await self._scrape_json_api(company_key, company_info, queries, location)
        elif scraper_type == 'workday':
            return await self._scrape_workday(company_key, company_info, queries, location)
        else:
            return await self._scrape_html(company_key, company_info, queries, location)

    async def _scrape_json_api(
        self,
        company_key: str,
        company_info: Dict,
        queries: List[str],
        location: str
    ) -> List[Dict]:
        """Scrape company with JSON API."""
        jobs = []

        try:
            # Devon Energy has a JSON API
            url = company_info.get('api', company_info['url'])

            req = urllib.request.Request(url, headers=self.headers)

            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode('utf-8'))

                # Parse job listings
                job_list = data.get('jobs', data.get('data', []))

                for job_data in job_list[:20]:  # Limit to 20 jobs per company
                    # Filter for HSE/Operations related jobs
                    title = job_data.get('title', '').lower()

                    # Check if relevant to queries
                    is_relevant = any(
                        q.lower().split()[0] in title  # First word of query
                        for q in queries
                    )

                    if is_relevant or any(kw in title for kw in ['hse', 'safety', 'health', 'environmental', 'operations', 'compliance']):
                        job = {
                            'title': job_data.get('title', 'Unknown Position'),
                            'company_name': company_info['name'],
                            'location': job_data.get('location', location),
                            'source': f'company_{company_key}',
                            'apply_url': job_data.get('url', company_info['url']),
                            'description': job_data.get('description', f"Position at {company_info['name']}")[:500],
                            'posted_date': job_data.get('posted_date', datetime.now().isoformat()),
                            'location_type': 'onsite',
                            'employment_type': 'full-time'
                        }
                        jobs.append(job)

        except Exception as e:
            logger.warning(f"JSON API scraping failed for {company_info['name']}: {e}")

        return jobs

    async def _scrape_workday(
        self,
        company_key: str,
        company_info: Dict,
        queries: List[str],
        location: str
    ) -> List[Dict]:
        """Scrape Workday-based career sites."""
        jobs = []

        try:
            # Workday sites usually have predictable URL patterns
            url = company_info.get('search_url', company_info['url'])

            req = urllib.request.Request(url, headers=self.headers)

            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8', errors='ignore')

                # Look for job data in script tags (Workday embeds JSON)
                json_pattern = r'<script[^>]*>.*?window\.__appData\s*=\s*({.*?});.*?</script>'
                matches = re.findall(json_pattern, html, re.DOTALL)

                if matches:
                    try:
                        data = json.loads(matches[0])
                        job_list = data.get('jobPostings', [])

                        for job_data in job_list[:20]:
                            title = job_data.get('title', '').lower()

                            if any(kw in title for kw in ['hse', 'safety', 'health', 'environmental', 'operations']):
                                job = {
                                    'title': job_data.get('title', 'Unknown'),
                                    'company_name': company_info['name'],
                                    'location': job_data.get('location', location),
                                    'source': f'company_{company_key}',
                                    'apply_url': job_data.get('externalPath', url),
                                    'description': job_data.get('description', '')[:500],
                                    'posted_date': datetime.now().isoformat(),
                                    'location_type': 'onsite',
                                    'employment_type': 'full-time'
                                }
                                jobs.append(job)
                    except json.JSONDecodeError:
                        pass

        except Exception as e:
            logger.warning(f"Workday scraping failed for {company_info['name']}: {e}")

        return jobs

    async def _scrape_html(
        self,
        company_key: str,
        company_info: Dict,
        queries: List[str],
        location: str
    ) -> List[Dict]:
        """Scrape standard HTML career pages."""
        jobs = []

        try:
            url = company_info.get('search_url', company_info['url'])

            req = urllib.request.Request(url, headers=self.headers)

            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8', errors='ignore')

                # Look for job listings using common patterns
                # Pattern 1: Job title in <a> tags with "job" class
                title_pattern = r'<a[^>]*class[^>]*job[^>]*>([^<]+)</a>'
                titles = re.findall(title_pattern, html, re.IGNORECASE)

                # Pattern 2: Job location
                location_pattern = r'<[^>]*class[^>]*location[^>]*>([^<]+)</[^>]*>'
                locations = re.findall(location_pattern, html, re.IGNORECASE)

                # Pattern 3: Job URLs
                url_pattern = r'<a[^>]*href="([^"]*job[^"]*)"'
                urls = re.findall(url_pattern, html, re.IGNORECASE)

                # Combine results
                for i, title in enumerate(titles[:20]):
                    title_lower = title.lower()

                    # Filter for HSE/Operations
                    if any(kw in title_lower for kw in ['hse', 'safety', 'health', 'environmental', 'operations', 'drilling', 'compliance']):
                        job_location = locations[i] if i < len(locations) else location
                        job_url = urls[i] if i < len(urls) else url

                        # Make URL absolute if relative
                        if job_url.startswith('/'):
                            base_url = f"{urllib.parse.urlparse(url).scheme}://{urllib.parse.urlparse(url).netloc}"
                            job_url = base_url + job_url

                        job = {
                            'title': self._clean_text(title),
                            'company_name': company_info['name'],
                            'location': self._clean_text(job_location),
                            'source': f'company_{company_key}',
                            'apply_url': job_url,
                            'description': f"Position at {company_info['name']} - {title}",
                            'posted_date': datetime.now().isoformat(),
                            'location_type': 'onsite',
                            'employment_type': 'full-time'
                        }
                        jobs.append(job)

        except Exception as e:
            logger.warning(f"HTML scraping failed for {company_info['name']}: {e}")

        return jobs

    def _clean_text(self, text: str) -> str:
        """Clean HTML entities and whitespace."""
        if not text:
            return ""

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)

        # Decode HTML entities
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")
        text = text.replace('&nbsp;', ' ')

        # Clean whitespace
        text = ' '.join(text.split())

        return text.strip()


# Async wrapper
async def run_company_scraping(db, queries: List[str], location: str) -> List[Dict]:
    """Run company career page scraping and return jobs."""
    scraper = CompanyCareerScraper(db)
    return await scraper.search_all_companies(queries, location)

"""
RSS Feed Job Scraper - No API Keys Required
Uses public RSS feeds from job boards
"""

import asyncio
import re
import xml.etree.ElementTree as ET
from typing import Dict, List
from datetime import datetime
import logging
import urllib.request
import urllib.parse

logger = logging.getLogger(__name__)


class RSSJobScraper:
    """
    Scrapes job boards via their public RSS feeds.
    No API keys, no credit cards, no authentication required.
    """

    # RSS feed URLs (publicly accessible)
    RSS_FEEDS = {
        'indeed': 'https://www.indeed.com/rss?q={query}&l={location}',
        'simplyhired': 'https://www.simplyhired.com/search?q={query}&l={location}&frs=rss',
        'careerjet': 'http://rss.careerjet.com/rss?s={query}&l={location}',
    }

    def __init__(self, db):
        self.db = db
        self.jobs_found = []

    async def search_all_feeds(
        self,
        queries: List[str],
        location: str = "Oklahoma"
    ) -> List[Dict]:
        """Search all RSS feeds for jobs."""
        logger.info(f"Starting RSS feed search for {len(queries)} queries")

        all_jobs = []

        # Search top queries only (to avoid overwhelming)
        for query in queries[:5]:
            logger.info(f"RSS Search: {query}")

            # Indeed RSS
            indeed_jobs = await self._fetch_indeed_rss(query, location)
            all_jobs.extend(indeed_jobs)
            await asyncio.sleep(1)

            # SimplyHired RSS
            simplyhired_jobs = await self._fetch_simplyhired_rss(query, location)
            all_jobs.extend(simplyhired_jobs)
            await asyncio.sleep(1)

            # CareerJet RSS - DISABLED: DNS errors, domain may no longer exist
            # careerjet_jobs = await self._fetch_careerjet_rss(query, location)
            # all_jobs.extend(careerjet_jobs)
            # await asyncio.sleep(1)

        # Deduplicate
        seen = set()
        unique_jobs = []
        for job in all_jobs:
            key = f"{job['title']}|{job['company_name']}"
            if key not in seen:
                seen.add(key)
                unique_jobs.append(job)

        logger.info(f"RSS feeds complete: {len(unique_jobs)} unique jobs")
        return unique_jobs

    async def _fetch_indeed_rss(self, query: str, location: str) -> List[Dict]:
        """Fetch jobs from Indeed RSS feed."""
        jobs = []

        try:
            url = f"https://www.indeed.com/rss?q={urllib.parse.quote(query)}&l={urllib.parse.quote(location)}"
            logger.info(f"Fetching Indeed RSS: {url}")

            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/rss+xml, application/xml, text/xml, */*',
                    'Accept-Language': 'en-US,en;q=0.9',
                }
            )

            with urllib.request.urlopen(req, timeout=15) as response:
                xml_data = response.read().decode('utf-8', errors='ignore')

                # Parse XML
                root = ET.fromstring(xml_data)

                # Find all job items
                for item in root.findall('.//item')[:10]:  # Max 10 per query
                    try:
                        title = item.find('title').text if item.find('title') is not None else query
                        link = item.find('link').text if item.find('link') is not None else url
                        description = item.find('description').text if item.find('description') is not None else ""
                        pub_date = item.find('pubDate').text if item.find('pubDate') is not None else None

                        # Extract company from title or description
                        company = self._extract_company(title, description)

                        # Extract location from description
                        job_location = self._extract_location(description) or location

                        job = {
                            'title': self._clean_text(title),
                            'company_name': company,
                            'location': job_location,
                            'source': 'indeed_rss',
                            'apply_url': link,
                            'description': self._clean_html(description)[:500],
                            'posted_date': self._parse_date(pub_date),
                            'location_type': 'hybrid',
                            'employment_type': 'full-time'
                        }
                        jobs.append(job)

                    except Exception as e:
                        logger.warning(f"Failed to parse Indeed RSS item: {e}")

            logger.info(f"Indeed RSS: Found {len(jobs)} jobs for '{query}'")

        except Exception as e:
            logger.error(f"Indeed RSS fetch failed: {e}")

        return jobs

    async def _fetch_simplyhired_rss(self, query: str, location: str) -> List[Dict]:
        """Fetch jobs from SimplyHired RSS feed."""
        jobs = []

        try:
            # SimplyHired has a working RSS feed
            url = f"https://www.simplyhired.com/search?q={urllib.parse.quote(query)}&l={urllib.parse.quote(location)}&frs=1"
            logger.info(f"Fetching SimplyHired: {url}")

            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/rss+xml, application/xml, text/xml, */*',
                    'Accept-Language': 'en-US,en;q=0.9',
                }
            )

            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8', errors='ignore')

                # SimplyHired returns HTML, extract job data
                title_pattern = r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>'
                titles = re.findall(title_pattern, html, re.DOTALL)[:5]

                company_pattern = r'<span[^>]*data-testid="companyName"[^>]*>(.*?)</span>'
                companies = re.findall(company_pattern, html, re.DOTALL)

                for i, title in enumerate(titles):
                    # Filter out navigation links and junk
                    title_lower = title.lower()
                    skip_keywords = ['apply now', 'post jobs', 'salary estimator', 'contact us',
                                    'all jobs', 'sign up', 'login', 'register', 'search']

                    if any(skip in title_lower for skip in skip_keywords):
                        continue  # Skip navigation links

                    if len(title) < 10:  # Skip very short titles
                        continue

                    company = companies[i] if i < len(companies) else "Company"
                    job = {
                        'title': self._clean_text(title),
                        'company_name': self._clean_text(company),
                        'location': location,
                        'source': 'simplyhired',
                        'apply_url': url,
                        'description': f"Position: {query} in {location}",
                        'posted_date': datetime.now().isoformat(),
                        'location_type': 'hybrid',
                        'employment_type': 'full-time'
                    }
                    jobs.append(job)

            logger.info(f"SimplyHired: Found {len(jobs)} jobs for '{query}'")

        except Exception as e:
            logger.error(f"SimplyHired fetch failed: {e}")

        return jobs

    async def _fetch_careerjet_rss(self, query: str, location: str) -> List[Dict]:
        """Fetch jobs from CareerJet RSS feed."""
        jobs = []

        try:
            # CareerJet has RSS feeds
            query_encoded = urllib.parse.quote(query)
            location_encoded = urllib.parse.quote(location)
            url = f"http://rss.careerjet.com/rss?s={query_encoded}&l={location_encoded}&sort=date"

            logger.info(f"Fetching CareerJet RSS: {url}")

            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/rss+xml, application/xml, text/xml, */*',
                    'Accept-Language': 'en-US,en;q=0.9',
                }
            )

            with urllib.request.urlopen(req, timeout=15) as response:
                xml_data = response.read().decode('utf-8', errors='ignore')

                # Parse XML
                root = ET.fromstring(xml_data)

                # Find all job items
                for item in root.findall('.//item')[:5]:
                    try:
                        title = item.find('title').text if item.find('title') is not None else query
                        link = item.find('link').text if item.find('link') is not None else url
                        description = item.find('description').text if item.find('description') is not None else ""

                        company = self._extract_company(title, description)
                        job_location = self._extract_location(description) or location

                        job = {
                            'title': self._clean_text(title),
                            'company_name': company,
                            'location': job_location,
                            'source': 'careerjet',
                            'apply_url': link,
                            'description': self._clean_html(description)[:500],
                            'posted_date': datetime.now().isoformat(),
                            'location_type': 'hybrid',
                            'employment_type': 'full-time'
                        }
                        jobs.append(job)

                    except Exception as e:
                        logger.warning(f"Failed to parse CareerJet RSS item: {e}")

            logger.info(f"CareerJet RSS: Found {len(jobs)} jobs for '{query}'")

        except Exception as e:
            logger.error(f"CareerJet RSS fetch failed: {e}")

        return jobs

    def _extract_company(self, title: str, description: str) -> str:
        """Extract company name from title or description."""
        # Look for common patterns: "Job Title at Company"
        at_match = re.search(r' at ([^-|\n]+)', title)
        if at_match:
            return self._clean_text(at_match.group(1))

        # Look for "Company" in description
        company_match = re.search(r'<b>([^<]+)</b>', description)
        if company_match:
            return self._clean_text(company_match.group(1))

        return "Company"

    def _extract_location(self, text: str) -> str:
        """Extract location from text."""
        # Look for city, state patterns
        location_match = re.search(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)*,?\s[A-Z]{2})', text)
        if location_match:
            return location_match.group(1)

        return None

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags and entities."""
        if not text:
            return ""

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)

        # Decode entities
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")
        text = text.replace('&nbsp;', ' ')

        # Clean whitespace
        text = ' '.join(text.split())

        return text.strip()

    def _clean_text(self, text: str) -> str:
        """Clean text."""
        return self._clean_html(text)

    def _parse_date(self, date_str: str) -> str:
        """Parse RSS date to ISO format."""
        if not date_str:
            return datetime.now().isoformat()

        try:
            # Try common RSS date formats
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            return dt.isoformat()
        except:
            return datetime.now().isoformat()


# Async wrapper
async def run_rss_scraping(db, queries: List[str], location: str) -> List[Dict]:
    """Run RSS scraping and return jobs."""
    scraper = RSSJobScraper(db)
    return await scraper.search_all_feeds(queries, location)

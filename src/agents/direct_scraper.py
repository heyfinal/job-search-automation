"""
Direct Job Board Scraper - No API Keys Required
Uses Playwright MCP server to scrape public job listings directly
"""

import asyncio
import json
import re
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DirectJobScraper:
    """
    Scrapes job boards directly using Playwright MCP.
    No API keys or credit cards required.
    """

    def __init__(self, db):
        self.db = db
        self.jobs_found = []

    async def search_all_sources(
        self,
        queries: List[str],
        location: str = "Oklahoma"
    ) -> List[Dict]:
        """Search multiple job boards in parallel."""

        logger.info(f"Starting direct scraping for {len(queries)} queries")

        all_jobs = []

        # Search each source
        for query in queries[:3]:  # Limit to avoid overwhelming
            logger.info(f"Scraping: {query}")

            # Indeed
            indeed_jobs = await self._scrape_indeed(query, location)
            all_jobs.extend(indeed_jobs)
            await asyncio.sleep(2)  # Rate limit

            # Rigzone
            rigzone_jobs = await self._scrape_rigzone(query)
            all_jobs.extend(rigzone_jobs)
            await asyncio.sleep(2)

            # LinkedIn (public listings)
            linkedin_jobs = await self._scrape_linkedin(query, location)
            all_jobs.extend(linkedin_jobs)
            await asyncio.sleep(2)

        # Deduplicate
        seen = set()
        unique_jobs = []
        for job in all_jobs:
            key = f"{job['title']}|{job['company_name']}"
            if key not in seen:
                seen.add(key)
                unique_jobs.append(job)

        logger.info(f"Direct scraping complete: {len(unique_jobs)} unique jobs")
        return unique_jobs

    async def _scrape_indeed(self, query: str, location: str) -> List[Dict]:
        """Scrape Indeed.com public listings."""
        jobs = []

        try:
            url = f"https://www.indeed.com/jobs?q={query.replace(' ', '+')}&l={location.replace(' ', '+')}"

            # Use simple HTTP fetch since Indeed has public data
            import urllib.request
            from urllib.parse import quote

            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }

            req = urllib.request.Request(url, headers=headers)

            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    html = response.read().decode('utf-8', errors='ignore')

                    # Parse job cards (simple regex - Indeed has consistent structure)
                    # Look for job titles
                    title_pattern = r'<h2[^>]*class="jobTitle"[^>]*>.*?<span[^>]*>([^<]+)</span>'
                    titles = re.findall(title_pattern, html, re.DOTALL)

                    # Look for company names
                    company_pattern = r'<span[^>]*class="companyName"[^>]*>([^<]+)</span>'
                    companies = re.findall(company_pattern, html)

                    # Look for locations
                    location_pattern = r'<div[^>]*class="companyLocation"[^>]*>([^<]+)</div>'
                    locations = re.findall(location_pattern, html)

                    # Look for job links
                    link_pattern = r'<a[^>]*class="jcs-JobTitle"[^>]*href="/rc/clk\?jk=([^"&]+)'
                    job_ids = re.findall(link_pattern, html)

                    # Combine results
                    for i in range(min(len(titles), len(companies), 10)):  # Max 10 per query
                        if i < len(titles) and i < len(companies):
                            job = {
                                'title': self._clean_text(titles[i]),
                                'company_name': self._clean_text(companies[i]),
                                'location': self._clean_text(locations[i]) if i < len(locations) else location,
                                'source': 'indeed',
                                'apply_url': f"https://www.indeed.com/viewjob?jk={job_ids[i]}" if i < len(job_ids) else url,
                                'description': f"HSE, Safety, and Operations role: {query}",
                                'posted_date': datetime.now().isoformat(),
                                'location_type': 'hybrid',
                                'employment_type': 'full-time'
                            }
                            jobs.append(job)

                    logger.info(f"Indeed: Found {len(jobs)} jobs for '{query}'")

            except Exception as e:
                logger.warning(f"Indeed fetch failed: {e}")

        except Exception as e:
            logger.error(f"Indeed scraping error: {e}")

        return jobs

    async def _scrape_rigzone(self, query: str) -> List[Dict]:
        """Scrape Rigzone.com oil & gas jobs."""
        jobs = []

        try:
            # Rigzone has a simple search URL structure
            url = f"https://www.rigzone.com/jobs/search/?keyword={query.replace(' ', '+')}"

            import urllib.request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }

            req = urllib.request.Request(url, headers=headers)

            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    html = response.read().decode('utf-8', errors='ignore')

                    # Rigzone job card patterns
                    title_pattern = r'<h3[^>]*class="job-title"[^>]*>.*?<a[^>]*>([^<]+)</a>'
                    titles = re.findall(title_pattern, html, re.DOTALL)

                    company_pattern = r'<div[^>]*class="company-name"[^>]*>([^<]+)</div>'
                    companies = re.findall(company_pattern, html)

                    location_pattern = r'<div[^>]*class="location"[^>]*>([^<]+)</div>'
                    locations = re.findall(location_pattern, html)

                    for i in range(min(len(titles), len(companies), 5)):
                        job = {
                            'title': self._clean_text(titles[i]),
                            'company_name': self._clean_text(companies[i]) if i < len(companies) else 'Oil & Gas Company',
                            'location': self._clean_text(locations[i]) if i < len(locations) else 'Various',
                            'source': 'rigzone',
                            'apply_url': url,
                            'description': f"Oil & Gas position: {query}",
                            'posted_date': datetime.now().isoformat(),
                            'location_type': 'onsite',
                            'employment_type': 'full-time'
                        }
                        jobs.append(job)

                    logger.info(f"Rigzone: Found {len(jobs)} jobs for '{query}'")

            except Exception as e:
                logger.warning(f"Rigzone fetch failed: {e}")

        except Exception as e:
            logger.error(f"Rigzone scraping error: {e}")

        return jobs

    async def _scrape_linkedin(self, query: str, location: str) -> List[Dict]:
        """Scrape LinkedIn public job listings."""
        jobs = []

        try:
            # LinkedIn has public job listings that don't require login
            url = f"https://www.linkedin.com/jobs/search/?keywords={query.replace(' ', '%20')}&location={location.replace(' ', '%20')}"

            import urllib.request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }

            req = urllib.request.Request(url, headers=headers)

            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    html = response.read().decode('utf-8', errors='ignore')

                    # LinkedIn job data (often in JSON-LD)
                    json_ld_pattern = r'<script type="application/ld\+json">(\{[^<]+JobPosting[^<]+\})</script>'
                    json_data = re.findall(json_ld_pattern, html, re.DOTALL)

                    for data_str in json_data[:5]:
                        try:
                            data = json.loads(data_str)
                            if isinstance(data, dict) and data.get('@type') == 'JobPosting':
                                job = {
                                    'title': data.get('title', query),
                                    'company_name': data.get('hiringOrganization', {}).get('name', 'Company'),
                                    'location': data.get('jobLocation', {}).get('address', {}).get('addressLocality', location),
                                    'source': 'linkedin',
                                    'apply_url': data.get('url', url),
                                    'description': data.get('description', '')[:500],
                                    'posted_date': data.get('datePosted', datetime.now().isoformat()),
                                    'location_type': 'hybrid',
                                    'employment_type': data.get('employmentType', 'full-time').lower()
                                }
                                jobs.append(job)
                        except:
                            pass

                    logger.info(f"LinkedIn: Found {len(jobs)} jobs for '{query}'")

            except Exception as e:
                logger.warning(f"LinkedIn fetch failed: {e}")

        except Exception as e:
            logger.error(f"LinkedIn scraping error: {e}")

        return jobs

    def _clean_text(self, text: str) -> str:
        """Clean HTML entities and extra whitespace."""
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

        # Clean whitespace
        text = ' '.join(text.split())

        return text.strip()


# Async wrapper for main orchestrator
async def run_direct_scraping(db, queries: List[str], location: str) -> List[Dict]:
    """Run direct scraping and return jobs."""
    scraper = DirectJobScraper(db)
    return await scraper.search_all_sources(queries, location)

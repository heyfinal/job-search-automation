"""
Puppeteer-based Indeed Scraper
Uses MCP Puppeteer server to bypass 403 blocks and scrape real jobs.
"""

import subprocess
import json
import asyncio
from typing import Dict, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PuppeteerIndeedScraper:
    """
    Scrapes Indeed using Puppeteer browser automation via MCP server.
    Bypasses bot detection that blocks regular HTTP requests.
    """

    def __init__(self, db):
        self.db = db

    async def search_jobs(
        self,
        queries: List[str],
        location: str = "Oklahoma"
    ) -> List[Dict]:
        """
        Search Indeed for HSE/Safety/Operations jobs using Puppeteer.
        """
        all_jobs = []

        for query in queries[:5]:  # Top 5 queries
            logger.info(f"Puppeteer scraping Indeed: '{query}' in {location}")

            try:
                jobs = await self._scrape_indeed_page(query, location)
                all_jobs.extend(jobs)
                logger.info(f"Found {len(jobs)} jobs for '{query}'")
                await asyncio.sleep(2)  # Rate limiting

            except Exception as e:
                logger.error(f"Puppeteer Indeed scraping failed for '{query}': {e}")

        logger.info(f"Puppeteer Indeed scraping complete: {len(all_jobs)} total jobs")
        return all_jobs

    async def _scrape_indeed_page(self, query: str, location: str) -> List[Dict]:
        """
        Scrape a single Indeed search page using Puppeteer MCP.
        """
        jobs = []

        try:
            # Use Puppeteer MCP server to navigate and extract jobs
            # This bypasses 403 Forbidden errors

            url = f"https://www.indeed.com/jobs?q={query.replace(' ', '+')}&l={location}"

            # Navigate to page
            nav_result = subprocess.run(
                ['npx', '@modelcontextprotocol/server-puppeteer', 'navigate', url],
                capture_output=True,
                text=True,
                timeout=30
            )

            if nav_result.returncode != 0:
                logger.warning(f"Navigation failed: {nav_result.stderr}")
                return jobs

            # Extract job data
            extract_script = """
(function() {
  const jobList = [];
  const jobCards = document.querySelectorAll('.job_seen_beacon');

  jobCards.forEach((card) => {
    try {
      const titleEl = card.querySelector('.jobTitle span');
      const companyEl = card.querySelector('[data-testid="company-name"]');
      const locationEl = card.querySelector('[data-testid="text-location"]');
      const linkEl = card.querySelector('.jobTitle a');
      const snippetEl = card.querySelector('.job-snippet');

      const title = titleEl ? titleEl.textContent.trim() : null;
      const company = companyEl ? companyEl.textContent.trim() : 'Company Not Listed';
      const location = locationEl ? locationEl.textContent.trim() : 'Oklahoma';
      const href = linkEl ? linkEl.getAttribute('href') : '';
      const url = href ? `https://www.indeed.com${href}` : '';
      const description = snippetEl ? snippetEl.textContent.trim().substring(0, 500) : '';

      if (title && url && !title.toLowerCase().includes('apply now') && !title.toLowerCase().includes('post jobs')) {
        jobList.push({ title, company, location, url, description });
      }
    } catch (e) {
      // Skip errors
    }
  });

  return JSON.stringify(jobList);
})();
            """

            eval_result = subprocess.run(
                ['npx', '@modelcontextprotocol/server-puppeteer', 'evaluate', extract_script],
                capture_output=True,
                text=True,
                timeout=30
            )

            if eval_result.returncode == 0 and eval_result.stdout:
                raw_jobs = json.loads(eval_result.stdout)

                # Convert to job format
                for job_data in raw_jobs[:15]:  # Limit 15 per query
                    job = {
                        'title': job_data['title'],
                        'company_name': job_data['company'],
                        'location': job_data['location'],
                        'source': 'indeed_puppeteer',
                        'apply_url': job_data['url'],
                        'description': job_data.get('description', f"Position: {job_data['title']} at {job_data['company']}"),
                        'posted_date': datetime.now().isoformat(),
                        'location_type': 'onsite',
                        'employment_type': 'full-time'
                    }
                    jobs.append(job)

        except subprocess.TimeoutExpired:
            logger.error(f"Puppeteer timeout for '{query}'")
        except Exception as e:
            logger.error(f"Puppeteer extraction error: {e}")

        return jobs


# Async wrapper
async def run_puppeteer_indeed_scraping(db, queries: List[str], location: str) -> List[Dict]:
    """
    Run Puppeteer-based Indeed scraping and return jobs.
    """
    scraper = PuppeteerIndeedScraper(db)
    return await scraper.search_jobs(queries, location)

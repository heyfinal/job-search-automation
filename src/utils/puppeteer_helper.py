"""
Puppeteer MCP Helper
Provides Python interface to Puppeteer MCP server for job scraping.
"""

import json
import subprocess
import asyncio
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class PuppeteerHelper:
    """
    Helper class to interact with Puppeteer MCP server.
    Handles navigation, evaluation, and data extraction.
    """

    def __init__(self):
        self.browser_ready = False

    async def navigate(self, url: str, wait_time: int = 2) -> bool:
        """
        Navigate to a URL using Puppeteer.
        Returns True if successful.
        """
        try:
            # Call Puppeteer MCP server via npx
            result = subprocess.run(
                ['npx', '@modelcontextprotocol/server-puppeteer', 'navigate', url],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                await asyncio.sleep(wait_time)  # Wait for page load
                self.browser_ready = True
                return True
            else:
                logger.warning(f"Navigation failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error(f"Navigation timeout for {url}")
            return False
        except Exception as e:
            logger.error(f"Navigation error: {e}")
            return False

    async def evaluate(self, script: str) -> Optional[str]:
        """
        Execute JavaScript in the browser and return result.
        Returns None if execution fails.
        """
        if not self.browser_ready:
            logger.warning("Browser not ready, call navigate() first")
            return None

        try:
            result = subprocess.run(
                ['npx', '@modelcontextprotocol/server-puppeteer', 'evaluate', script],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.warning(f"Evaluation failed: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            logger.error("Evaluation timeout")
            return None
        except Exception as e:
            logger.error(f"Evaluation error: {e}")
            return None

    async def scrape_indeed_jobs(self, query: str, location: str) -> List[Dict]:
        """
        High-level method to scrape jobs from Indeed.
        Returns list of job dictionaries.
        """
        jobs = []

        try:
            # Build URL
            url = f"https://www.indeed.com/jobs?q={query.replace(' ', '+')}&l={location}"

            # Navigate to page
            logger.info(f"🌐 Navigating to Indeed: {query}")
            if not await self.navigate(url, wait_time=3):
                return jobs

            # Extraction script
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
      const salaryEl = card.querySelector('.salary-snippet, [class*="salary"]');

      const title = titleEl ? titleEl.textContent.trim() : null;
      const company = companyEl ? companyEl.textContent.trim() : 'Company Not Listed';
      const location = locationEl ? locationEl.textContent.trim() : 'Oklahoma';
      const href = linkEl ? linkEl.getAttribute('href') : '';
      const url = href ? 'https://www.indeed.com' + href : '';
      const description = snippetEl ? snippetEl.textContent.trim().substring(0, 500) : '';
      const salary = salaryEl ? salaryEl.textContent.trim() : null;

      // Filter out navigation links
      const skipKeywords = ['apply now', 'post jobs', 'salary estimator', 'contact us',
                           'all jobs', 'sign up', 'login', 'register', 'search'];
      const titleLower = title ? title.toLowerCase() : '';

      if (title && url && !skipKeywords.some(kw => titleLower.includes(kw)) && title.length >= 10) {
        jobList.push({ title, company, location, url, description, salary });
      }
    } catch (e) {
      // Skip errors
    }
  });

  return JSON.stringify(jobList.slice(0, 20));
})();
            """

            # Execute extraction
            logger.info("📊 Extracting job data...")
            result = await self.evaluate(extract_script)

            if result:
                try:
                    jobs = json.loads(result)
                    logger.info(f"✅ Extracted {len(jobs)} jobs")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse job data: {e}")

        except Exception as e:
            logger.error(f"Scraping error: {e}")

        return jobs

    async def close(self):
        """Close the browser."""
        self.browser_ready = False


# Singleton instance
_helper = None


def get_puppeteer_helper() -> PuppeteerHelper:
    """Get or create Puppeteer helper instance."""
    global _helper
    if _helper is None:
        _helper = PuppeteerHelper()
    return _helper

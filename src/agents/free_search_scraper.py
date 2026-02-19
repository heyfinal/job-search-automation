"""
Free Web Search Job Scraper
Uses DuckDuckGo (ddgs library) directly for fast, free job searching.
"""

import logging
from typing import List, Dict
from datetime import datetime
import re

logger = logging.getLogger(__name__)

try:
    from ddgs import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False
    logger.warning("ddgs not installed. Run: pip3 install --break-system-packages ddgs")


async def run_free_search_scraping(
    db,
    queries: List[str],
    location: str = "Oklahoma City, OK"
) -> List[Dict]:
    """
    Search DuckDuckGo directly for job listings.
    Fast, free, no API key needed.
    """
    if not HAS_DDGS:
        logger.error("ddgs library not available")
        return []

    jobs = []
    seen_urls = set()

    for query in queries[:8]:
        search_term = f"{query} jobs {location}"
        logger.info(f"🔍 DDG search: {search_term}")

        try:
            results = list(DDGS().text(search_term, max_results=10))
            logger.info(f"  ✅ {len(results)} results for '{query}'")

            for r in results:
                url = r.get('href', '')
                title = r.get('title', '')
                snippet = r.get('body', '')

                # Skip duplicates and non-job pages
                if url in seen_urls or not url:
                    continue
                seen_urls.add(url)

                # Skip generic listing pages
                if any(skip in title.lower() for skip in ['search results', 'sign up', 'login', 'post a job']):
                    continue

                # Extract source domain
                domain = url.split('/')[2] if '://' in url else 'unknown'
                source = domain.replace('www.', '').split('.')[0]

                job = {
                    'title': _clean_title(title, query),
                    'company_name': _extract_company(title, snippet),
                    'location': location,
                    'location_type': _detect_location_type(title + ' ' + snippet),
                    'description': snippet[:500],
                    'apply_url': url,
                    'source': f'ddg-{source}',
                    'posted_date': datetime.now().isoformat(),
                    'salary_min': None,
                    'salary_max': None,
                }

                if job['title'] and len(job['title']) > 5:
                    jobs.append(job)

        except Exception as e:
            logger.warning(f"  ❌ DDG search failed for '{query}': {e}")

    logger.info(f"🎯 DDG search complete: {len(jobs)} jobs found")
    return jobs


def _clean_title(title: str, query: str) -> str:
    """Clean up search result title to extract job title."""
    # Remove common suffixes
    for suffix in [' - Indeed', ' - LinkedIn', ' - Glassdoor', ' - ZipRecruiter',
                   ' | Indeed.com', ' | LinkedIn', ' | Glassdoor', ' jobs in']:
        if suffix.lower() in title.lower():
            idx = title.lower().index(suffix.lower())
            title = title[:idx]
    return title.strip()


def _detect_location_type(text: str) -> str:
    """Detect remote/hybrid/onsite from text."""
    t = text.lower()
    if 'remote' in t:
        return 'remote'
    elif 'hybrid' in t:
        return 'hybrid'
    return 'onsite'


def _extract_company(title: str, snippet: str) -> str:
    """Try to extract company name from title or snippet."""
    at_match = re.search(r'\bat\s+([A-Z][A-Za-z\s&]+?)(?:\s*[-|•]|\s*$)', title)
    if at_match:
        return at_match.group(1).strip()

    company_keywords = ['hiring', 'join', 'career', 'opportunity']
    for keyword in company_keywords:
        if keyword in snippet.lower():
            words = snippet.split()
            for i, word in enumerate(words):
                if keyword in word.lower() and i > 0:
                    if words[i-1][0].isupper():
                        return words[i-1]

    return "Unknown Company"


# Backwards compatibility
async def run_web_search_scraping(*args, **kwargs):
    return await run_free_search_scraping(*args, **kwargs)

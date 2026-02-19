"""
Multi-Site Job Scraper using Playwright
Scrapes LinkedIn, Glassdoor, ZipRecruiter, Rigzone directly
"""

import asyncio
import logging
from typing import List, Dict
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
import re

logger = logging.getLogger(__name__)


async def scrape_linkedin_jobs(page, query: str, location: str) -> List[Dict]:
    """Scrape LinkedIn jobs."""
    jobs = []
    try:
        # LinkedIn job search URL
        search_url = f"https://www.linkedin.com/jobs/search/?keywords={query.replace(' ', '%20')}&location={location.replace(' ', '%20')}"
        logger.info(f"  🔵 LinkedIn: {search_url}")
        
        await page.goto(search_url, wait_until='domcontentloaded', timeout=15000)
        await page.wait_for_timeout(2000)
        
        # LinkedIn job cards
        job_cards = await page.query_selector_all('.job-search-card, .base-card')
        
        for card in job_cards[:5]:  # Top 5
            try:
                title = await card.query_selector('.base-search-card__title, h3')
                company = await card.query_selector('.base-search-card__subtitle, h4')
                link = await card.query_selector('a')
                
                if title and company and link:
                    jobs.append({
                        'title': (await title.text_content()).strip(),
                        'company_name': (await company.text_content()).strip(),
                        'location': location,
                        'location_type': 'onsite',
                        'description': f"Found via LinkedIn for {query}",
                        'apply_url': await link.get_attribute('href'),
                        'source': 'linkedin',
                        'posted_date': datetime.now().isoformat(),
                        'salary_min': None,
                        'salary_max': None,
                    })
            except Exception as e:
                logger.debug(f"Failed to parse LinkedIn job: {e}")
                
    except Exception as e:
        logger.warning(f"  ❌ LinkedIn failed: {e}")
    
    return jobs


async def scrape_ziprecruiter_jobs(page, query: str, location: str) -> List[Dict]:
    """Scrape ZipRecruiter jobs."""
    jobs = []
    try:
        search_url = f"https://www.ziprecruiter.com/jobs-search?search={query.replace(' ', '+')}&location={location.replace(' ', '+')}"
        logger.info(f"  🟣 ZipRecruiter: {search_url}")
        
        await page.goto(search_url, wait_until='domcontentloaded', timeout=15000)
        await page.wait_for_timeout(2000)
        
        job_cards = await page.query_selector_all('article.job_result, .job-listing')
        
        for card in job_cards[:5]:
            try:
                title_elem = await card.query_selector('h2 a, .job_title')
                company_elem = await card.query_selector('.company_name, .hiring_company')
                
                if title_elem and company_elem:
                    title = (await title_elem.text_content()).strip()
                    company = (await company_elem.text_content()).strip()
                    link = await title_elem.get_attribute('href') if await title_elem.get_attribute('href') else f"https://www.ziprecruiter.com/jobs-search?search={query}"
                    
                    jobs.append({
                        'title': title,
                        'company_name': company,
                        'location': location,
                        'location_type': 'onsite',
                        'description': f"Found via ZipRecruiter for {query}",
                        'apply_url': link if link.startswith('http') else f"https://www.ziprecruiter.com{link}",
                        'source': 'ziprecruiter',
                        'posted_date': datetime.now().isoformat(),
                        'salary_min': None,
                        'salary_max': None,
                    })
            except Exception as e:
                logger.debug(f"Failed to parse ZipRecruiter job: {e}")
                
    except Exception as e:
        logger.warning(f"  ❌ ZipRecruiter failed: {e}")
    
    return jobs


async def scrape_rigzone_jobs(page, query: str) -> List[Dict]:
    """Scrape Rigzone oil & gas jobs."""
    jobs = []
    try:
        search_url = f"https://www.rigzone.com/jobs/keyword/{query.replace(' ', '_')}"
        logger.info(f"  🟠 Rigzone: {search_url}")
        
        await page.goto(search_url, wait_until='domcontentloaded', timeout=15000)
        await page.wait_for_timeout(2000)
        
        job_cards = await page.query_selector_all('.job-listing, .job-item')
        
        for card in job_cards[:5]:
            try:
                title_elem = await card.query_selector('.job-title a, h3 a')
                company_elem = await card.query_selector('.company-name, .employer')
                
                if title_elem:
                    title = (await title_elem.text_content()).strip()
                    company = (await company_elem.text_content()).strip() if company_elem else "Oil & Gas Company"
                    link = await title_elem.get_attribute('href')
                    
                    jobs.append({
                        'title': title,
                        'company_name': company,
                        'location': 'Oklahoma City, OK',
                        'location_type': 'onsite',
                        'description': f"Oil & Gas job from Rigzone for {query}",
                        'apply_url': link if link.startswith('http') else f"https://www.rigzone.com{link}",
                        'source': 'rigzone',
                        'posted_date': datetime.now().isoformat(),
                        'salary_min': None,
                        'salary_max': None,
                    })
            except Exception as e:
                logger.debug(f"Failed to parse Rigzone job: {e}")
                
    except Exception as e:
        logger.warning(f"  ❌ Rigzone failed: {e}")
    
    return jobs


async def run_multi_site_scraping(db, queries: List[str], location: str) -> List[Dict]:
    """
    Scrape multiple job sites with Playwright.
    
    Args:
        db: Database manager
        queries: Job search queries
        location: Location to search
        
    Returns:
        List of job dictionaries
    """
    all_jobs = []
    
    logger.info("🌐 Multi-Site Scraper starting (LinkedIn, ZipRecruiter, Rigzone)...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        
        for query in queries[:8]:  # Search 8 diverse queries across all categories
            logger.info(f"🔍 Searching for: {query}")
            
            # LinkedIn
            linkedin_jobs = await scrape_linkedin_jobs(page, query, location)
            all_jobs.extend(linkedin_jobs)
            logger.info(f"    ✅ LinkedIn: {len(linkedin_jobs)} jobs")
            
            # ZipRecruiter
            zip_jobs = await scrape_ziprecruiter_jobs(page, query, location)
            all_jobs.extend(zip_jobs)
            logger.info(f"    ✅ ZipRecruiter: {len(zip_jobs)} jobs")
            
            # Rigzone (oil & gas)
            rigzone_jobs = await scrape_rigzone_jobs(page, query)
            all_jobs.extend(rigzone_jobs)
            logger.info(f"    ✅ Rigzone: {len(rigzone_jobs)} jobs")
            
            await page.wait_for_timeout(2000)  # Rate limiting
        
        await browser.close()
    
    logger.info(f"✅ Multi-Site Scraper complete: {len(all_jobs)} total jobs")
    return all_jobs

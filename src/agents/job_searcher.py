"""Job Searcher Sub-Agent: aggregates listings from free, no-CC-required sources."""

import asyncio
import json
from typing import Dict, List, Tuple
import logging

from src.agents.company_scraper import run_company_scraping
from src.agents.playwright_indeed_scraper import run_playwright_indeed_scraping
from src.agents.rss_scraper import run_rss_scraping
from src.agents.usajobs_scraper import run_usajobs_search
from src.agents.free_search_scraper import run_free_search_scraping
from src.agents.ai_job_discovery import run_ai_job_discovery
from src.agents.multi_site_scraper import run_multi_site_scraping
from src.database import DatabaseManager, get_db

logger = logging.getLogger(__name__)


class JobSearcher:
    """
    Multi-source job searcher that aggregates listings from:
    - FREE Web Search (LinkedIn, ZipRecruiter, Glassdoor, Monster, CareerBuilder)
    - Oil & Gas Specific (Rigzone, EnergyJobline, OilAndGasJobSearch)
    - Company Direct (ConocoPhillips, Oxy, Marathon, ExxonMobil, Chevron)
    - USAJOBS federal API (free)
    - Company career pages (Oklahoma energy companies)
    - Playwright-powered Indeed scraping (bypasses bot detection)
    """

    # INTERLEAVED queries - each position covers a DIFFERENT category so queries[:5]
    # or queries[:10] always hits diverse job types.
    # Based on Daniel's ACTUAL resume: 20+ years ops, logistics, vendors, budgets, safety.
    DEFAULT_QUERIES = [
        # --- ROUND 1 (queries[:5] hits 5 different categories) ---
        "Operations Manager",           # 0: Operations
        "Logistics Manager",            # 1: Logistics/Supply Chain
        "Project Manager construction", # 2: Project Management
        "Safety Manager",               # 3: Safety (but just 1 of 5)
        "Construction Superintendent",  # 4: Construction

        # --- ROUND 2 (queries[:10] hits 10 different categories) ---
        "Vendor Manager",               # 5: Vendor/Procurement
        "Cost Controller",              # 6: Cost/Budget
        "Training Manager",             # 7: Training
        "Risk Manager",                 # 8: Risk/Investigations
        "Drilling Coordinator",         # 9: Oil & Gas Office

        # --- ROUND 3 (more depth per category) ---
        "Operations Supervisor",        # 10: Operations
        "Supply Chain Coordinator",     # 11: Logistics
        "Project Coordinator",          # 12: Project Management
        "Facilities Manager",           # 13: Facilities
        "Contract Manager",             # 14: Vendor/Procurement

        # --- ROUND 4 ---
        "Warehouse Operations Manager", # 15: Logistics
        "EHS Manager",                  # 16: Safety
        "Site Manager",                 # 17: Construction
        "Budget Analyst",               # 18: Cost/Budget
        "Compliance Manager",           # 19: Risk/Compliance

        # --- ROUND 5 ---
        "Fleet Manager",               # 20: Logistics
        "Director of Operations",      # 21: Operations
        "Well Planner",                # 22: Oil & Gas Office
        "OSHA Compliance Specialist",  # 23: Safety
        "Account Manager energy",      # 24: Account/Biz Dev

        # --- ROUND 6 ---
        "Procurement Coordinator",     # 25: Vendor
        "Construction Manager",        # 26: Construction
        "Safety Coordinator",          # 27: Safety
        "Rig Coordinator",            # 28: Oil & Gas Office
        "Training Coordinator",        # 29: Training
    ]

    def __init__(self, db: DatabaseManager = None):
        self.db = db or get_db()

    async def search_all_sources(
        self,
        queries: List[str] = None,
        location: str = "Oklahoma City, OK",
        remote_only: bool = False,
        max_per_source: int = 20,
        use_ai_discovery: bool = True
    ) -> Dict[str, int]:
        """
        Search all available sources for job listings.

        Args:
            queries: Search queries (uses AI discovery or defaults if None)
            location: Location to search
            remote_only: Only search for remote positions
            max_per_source: Maximum results per source
            use_ai_discovery: Use AI to generate intelligent search queries

        Returns:
            Dict with source names and job counts
        """
        # AI-POWERED QUERY GENERATION
        if queries is None and use_ai_discovery:
            logger.info("🤖 Using AI to generate intelligent search queries based on full skill set...")
            try:
                # Get complete profile data
                profile = self.db.get_profile(1)
                skills = self.db.get_profile_skills(1)

                with self.db.connection() as conn:
                    cursor = conn.execute(
                        "SELECT * FROM candidate_experience WHERE profile_id = ? ORDER BY start_date DESC",
                        (1,)
                    )
                    experiences = [dict(row) for row in cursor.fetchall()]

                profile_data = {
                    'profile': profile,
                    'skills': skills,
                    'experiences': experiences
                }

                from src.agents.ai_job_discovery import AIJobDiscovery
                ai_discovery = AIJobDiscovery(self.db)
                ai_queries = await ai_discovery._generate_smart_queries(profile_data, location)
                queries = [q['query'] for q in ai_queries] if ai_queries else self.DEFAULT_QUERIES
                logger.info(f"✅ AI generated {len(queries)} diverse queries across all skill areas")
            except Exception as e:
                logger.warning(f"⚠️ AI query generation failed, using defaults: {e}")
                queries = self.DEFAULT_QUERIES
        else:
            queries = queries or self.DEFAULT_QUERIES

        results = {}
        total_new = 0

        # Distribute queries across scrapers using ROUND-ROBIN
        # so each scraper gets a diverse mix of categories
        multi_queries = queries[0::3]   # Every 3rd starting at 0
        free_queries = queries[1::3]    # Every 3rd starting at 1
        indeed_queries = queries[2::3]  # Every 3rd starting at 2

        logger.info(f"Starting diverse job search: {len(queries)} queries total")
        logger.info(f"  Multi-site: {len(multi_queries)} queries ({', '.join(multi_queries[:3])}...)")
        logger.info(f"  Free search: {len(free_queries)} queries ({', '.join(free_queries[:3])}...)")
        logger.info(f"  Indeed: {len(indeed_queries)} queries ({', '.join(indeed_queries[:3])}...)")

        # MULTI-SITE SCRAPING - Playwright scrapes LinkedIn, ZipRecruiter, Rigzone
        logger.info("🌐 Running Multi-Site Scraper (LinkedIn, ZipRecruiter, Rigzone)...")
        try:
            multi_jobs = await run_multi_site_scraping(self.db, multi_queries[:8], location)
            logger.info(f"✅ Multi-Site found {len(multi_jobs)} jobs from diverse sources")

            multi_count = 0
            multi_new = 0
            for job in multi_jobs:
                try:
                    job_id, is_new = self.db.add_job_listing(**job)
                    multi_count += 1
                    if is_new:
                        multi_new += 1
                except Exception as e:
                    logger.warning(f"Failed to add multi-site job: {e}")

            results['multi_site'] = {'total': multi_count, 'new': multi_new}
            total_new += multi_new
        except Exception as e:
            logger.error(f"❌ Multi-Site scraping failed: {e}")
            results['multi_site'] = {'total': 0, 'new': 0}

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

        # Distribute queries using round-robin for diversity
        free_queries = queries[1::3]    # Every 3rd starting at 1
        indeed_queries = queries[2::3]  # Every 3rd starting at 2

        # FREE WEB SEARCH - Searches LinkedIn, ZipRecruiter, Glassdoor, Rigzone, etc.
        logger.info("🌐 Running FREE web search (LinkedIn, ZipRecruiter, Glassdoor, Oil & Gas sites)...")
        try:
            free_search_jobs = await run_free_search_scraping(self.db, free_queries[:6], location)
            logger.info(f"✅ Free search found {len(free_search_jobs)} jobs from diverse sources")
            for job in free_search_jobs[:max_results]:
                try:
                    job_id, is_new = self.db.add_job_listing(**job)
                    total_found += 1
                    if is_new:
                        new_jobs += 1
                except Exception as e:
                    logger.warning(f"Failed to add free search job: {e}")
        except Exception as e:
            logger.error(f"❌ Free search failed: {e}")

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
            playwright_jobs = await run_playwright_indeed_scraping(self.db, indeed_queries[:8], location)
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

        self.db.log_search_run('job_boards', total_found, new_jobs)
        logger.info(f"Job boards: {total_found} found, {new_jobs} new")
        return total_found, new_jobs

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

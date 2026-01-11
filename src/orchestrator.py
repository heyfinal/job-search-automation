#!/usr/bin/env python3
"""
Job Search Automation - Main Orchestrator
Coordinates all sub-agents to run the complete job search pipeline.
"""

import asyncio
import argparse
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import logging

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import DatabaseManager, get_db, init_database
from src.utils.logger import setup_logging, get_logger
from src.utils.credentials import validate_credentials, get_openai_key
from src.agents.profile_builder import ProfileBuilder, build_daniel_profile
from src.agents.job_searcher import JobSearcher
from src.agents.matcher import JobMatcher
from src.agents.reporter import Reporter, generate_and_notify

logger = get_logger("orchestrator")


class JobSearchOrchestrator:
    """
    Main orchestrator that coordinates all sub-agents:
    1. Profile Builder - Build/update candidate profile
    2. Job Searcher - Search multiple sources for jobs
    3. Matcher - AI-powered job matching
    4. Reporter - Generate reports and notifications
    """

    def __init__(
        self,
        db: DatabaseManager = None,
        profile_id: int = None,
        skip_profile: bool = False,
        skip_search: bool = False,
        skip_matching: bool = False,
        skip_report: bool = False
    ):
        self.db = db or get_db()
        self.profile_id = profile_id
        self.skip_profile = skip_profile
        self.skip_search = skip_search
        self.skip_matching = skip_matching
        self.skip_report = skip_report

        # Initialize sub-agents
        self.profile_builder = ProfileBuilder(self.db)
        self.job_searcher = JobSearcher(self.db)
        self.matcher = JobMatcher(self.db)
        self.reporter = Reporter(self.db)

        # Results tracking
        self.results = {
            'started_at': None,
            'completed_at': None,
            'profile_id': None,
            'jobs_found': 0,
            'new_jobs': 0,
            'matches_created': 0,
            'report_path': None,
            'errors': []
        }

    async def run(self) -> Dict:
        """
        Run the complete job search pipeline.

        Returns:
            Results dictionary with statistics
        """
        self.results['started_at'] = datetime.now().isoformat()
        logger.info("=" * 60)
        logger.info("JOB SEARCH AUTOMATION - STARTING PIPELINE")
        logger.info("=" * 60)

        try:
            # Phase 1: Profile Building
            if not self.skip_profile:
                await self._run_profile_phase()
            elif self.profile_id:
                self.results['profile_id'] = self.profile_id
            else:
                # Try to get existing profile
                with self.db.connection() as conn:
                    cursor = conn.execute("SELECT id FROM candidate_profile LIMIT 1")
                    row = cursor.fetchone()
                    if row:
                        self.results['profile_id'] = row['id']
                    else:
                        logger.warning("No profile found, building default profile")
                        await self._run_profile_phase()

            # Phase 2: Job Search
            if not self.skip_search:
                await self._run_search_phase()

            # Phase 3: AI Matching
            if not self.skip_matching and self.results['profile_id']:
                await self._run_matching_phase()

            # Phase 4: Reporting
            if not self.skip_report and self.results['profile_id']:
                await self._run_reporting_phase()

        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            self.results['errors'].append(str(e))

        self.results['completed_at'] = datetime.now().isoformat()

        # Log results
        self._log_results()

        return self.results

    async def _run_profile_phase(self) -> None:
        """Run the profile building phase."""
        logger.info("-" * 40)
        logger.info("PHASE 1: PROFILE BUILDING")
        logger.info("-" * 40)

        try:
            # Build Daniel's profile with all available data
            profile_id = await build_daniel_profile()
            self.results['profile_id'] = profile_id
            logger.info(f"Profile built/updated: ID={profile_id}")

            # Get profile summary
            profile = self.db.get_profile(profile_id)
            skills = self.db.get_profile_skills(profile_id)

            logger.info(f"Profile: {profile.get('name')}")
            logger.info(f"Skills extracted: {len(skills)}")

            self.db.log('INFO', 'orchestrator', 'Profile phase complete', {
                'profile_id': profile_id,
                'skills_count': len(skills)
            })

        except Exception as e:
            logger.error(f"Profile phase error: {e}")
            self.results['errors'].append(f"Profile: {e}")

    async def _run_search_phase(self) -> None:
        """Run the job search phase."""
        logger.info("-" * 40)
        logger.info("PHASE 2: JOB SEARCH")
        logger.info("-" * 40)

        try:
            # Run searches across all sources
            search_results = await self.job_searcher.search_all_sources(
                location="Oklahoma City, OK",
                remote_only=False,
                max_per_source=30
            )

            # Aggregate results
            total_found = sum(r.get('total', 0) for r in search_results.values())
            total_new = sum(r.get('new', 0) for r in search_results.values())

            self.results['jobs_found'] = total_found
            self.results['new_jobs'] = total_new

            logger.info(f"Jobs found: {total_found}")
            logger.info(f"New jobs: {total_new}")
            for source, stats in search_results.items():
                logger.info(f"  - {source}: {stats.get('total', 0)} found, {stats.get('new', 0)} new")

            self.db.log('INFO', 'orchestrator', 'Search phase complete', {
                'total_found': total_found,
                'new_jobs': total_new,
                'by_source': search_results
            })

        except Exception as e:
            logger.error(f"Search phase error: {e}")
            self.results['errors'].append(f"Search: {e}")

    async def _run_matching_phase(self) -> None:
        """Run the AI matching phase."""
        logger.info("-" * 40)
        logger.info("PHASE 3: AI MATCHING")
        logger.info("-" * 40)

        profile_id = self.results['profile_id']

        try:
            # Run matching
            matches = await self.matcher.match_jobs_for_profile(profile_id)
            self.results['matches_created'] = len(matches)

            # Get summary
            summary = self.matcher.get_match_summary(profile_id)

            logger.info(f"Matches created: {len(matches)}")
            logger.info(f"Strong matches (80%+): {summary.get('strong_matches', 0)}")
            logger.info(f"Good matches (65-79%): {summary.get('good_matches', 0)}")
            logger.info(f"Average score: {summary.get('average_score', 0):.1f}%")

            # Show top matches
            if matches:
                logger.info("Top 5 matches:")
                for m in matches[:5]:
                    job = m.get('job', {})
                    logger.info(f"  - {job.get('title')} @ {job.get('company_name')}: {m['overall_score']:.0f}%")

            self.db.log('INFO', 'orchestrator', 'Matching phase complete', {
                'matches_created': len(matches),
                'summary': summary
            })

        except Exception as e:
            logger.error(f"Matching phase error: {e}")
            self.results['errors'].append(f"Matching: {e}")

    async def _run_reporting_phase(self) -> None:
        """Run the reporting and notification phase."""
        logger.info("-" * 40)
        logger.info("PHASE 4: REPORTING & NOTIFICATIONS")
        logger.info("-" * 40)

        profile_id = self.results['profile_id']

        try:
            # Generate report and send notifications
            report_result = await generate_and_notify(profile_id)

            self.results['report_path'] = report_result['report'].get('html_path')

            logger.info(f"Report generated: {self.results['report_path']}")
            logger.info(f"Notifications: {report_result['notifications']}")

            self.db.log('INFO', 'orchestrator', 'Reporting phase complete', {
                'report_path': self.results['report_path'],
                'notifications': report_result['notifications']
            })

        except Exception as e:
            logger.error(f"Reporting phase error: {e}")
            self.results['errors'].append(f"Reporting: {e}")

    def _log_results(self) -> None:
        """Log final results."""
        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Duration: {self._calculate_duration()}")
        logger.info(f"Profile ID: {self.results['profile_id']}")
        logger.info(f"Jobs found: {self.results['jobs_found']}")
        logger.info(f"New jobs: {self.results['new_jobs']}")
        logger.info(f"Matches created: {self.results['matches_created']}")
        logger.info(f"Report: {self.results['report_path']}")

        if self.results['errors']:
            logger.warning(f"Errors: {len(self.results['errors'])}")
            for err in self.results['errors']:
                logger.warning(f"  - {err}")

        self.db.log('INFO', 'orchestrator', 'Pipeline complete', self.results)

    def _calculate_duration(self) -> str:
        """Calculate pipeline duration."""
        if not self.results['started_at'] or not self.results['completed_at']:
            return "unknown"

        start = datetime.fromisoformat(self.results['started_at'])
        end = datetime.fromisoformat(self.results['completed_at'])
        duration = end - start

        minutes = int(duration.total_seconds() // 60)
        seconds = int(duration.total_seconds() % 60)
        return f"{minutes}m {seconds}s"


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Job Search Automation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.orchestrator                    # Run full pipeline
  python -m src.orchestrator --skip-profile     # Skip profile building
  python -m src.orchestrator --search-only      # Only run job search
  python -m src.orchestrator --report-only      # Only generate report
  python -m src.orchestrator --validate         # Validate credentials
        """
    )

    parser.add_argument('--skip-profile', action='store_true',
                       help='Skip profile building phase')
    parser.add_argument('--skip-search', action='store_true',
                       help='Skip job search phase')
    parser.add_argument('--skip-matching', action='store_true',
                       help='Skip AI matching phase')
    parser.add_argument('--skip-report', action='store_true',
                       help='Skip reporting phase')
    parser.add_argument('--search-only', action='store_true',
                       help='Only run job search')
    parser.add_argument('--match-only', action='store_true',
                       help='Only run matching')
    parser.add_argument('--report-only', action='store_true',
                       help='Only generate report')
    parser.add_argument('--profile-id', type=int,
                       help='Use specific profile ID')
    parser.add_argument('--validate', action='store_true',
                       help='Validate credentials and exit')
    parser.add_argument('--init-db', action='store_true',
                       help='Initialize database and exit')
    parser.add_argument('--open-report', action='store_true',
                       help='Open latest report in browser')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose logging')

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(level=log_level)

    # Handle special commands
    if args.validate:
        creds = validate_credentials()
        print("\nCredential Status:")
        for name, valid in creds.items():
            status = "OK" if valid else "MISSING"
            print(f"  {name}: {status}")
        return

    if args.init_db:
        init_database()
        print("Database initialized successfully")
        return

    if args.open_report:
        reporter = Reporter()
        reporter.open_report()
        return

    # Determine which phases to run
    skip_profile = args.skip_profile or args.search_only or args.match_only or args.report_only
    skip_search = args.skip_search or args.match_only or args.report_only
    skip_matching = args.skip_matching or args.search_only or args.report_only
    skip_report = args.skip_report or args.search_only or args.match_only

    # Initialize database
    init_database()

    # Run orchestrator
    orchestrator = JobSearchOrchestrator(
        profile_id=args.profile_id,
        skip_profile=skip_profile,
        skip_search=skip_search,
        skip_matching=skip_matching,
        skip_report=skip_report
    )

    results = await orchestrator.run()

    # Exit with error code if there were errors
    if results.get('errors'):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

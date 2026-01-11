#!/usr/bin/env python3
"""
Debug script to test job matching manually
"""

import asyncio
import sys
sys.path.insert(0, '/Users/daniel/workapps/job-search-automation')

from src.database import get_db
from src.agents.matcher import JobMatcher

async def main():
    db = get_db()
    matcher = JobMatcher(db)

    print("=" * 60)
    print("DEBUG: Job Matching Test")
    print("=" * 60)

    # Check profile
    profile_data = matcher._get_profile_data(1)
    if profile_data:
        print(f"\n✅ Profile found: {profile_data.get('name')}")
        print(f"   Skills: {len(profile_data.get('skills', []))}")
    else:
        print("\n❌ Profile not found!")
        return

    # Check unmatched jobs
    unmatched = db.get_unmatched_jobs(1)
    print(f"\n✅ Unmatched jobs: {len(unmatched)}")

    if len(unmatched) > 0:
        print(f"\nSample jobs:")
        for i, job in enumerate(unmatched[:5]):
            print(f"  {i+1}. {job.get('title')} @ {job.get('company_name')}")

    # Try matching first job
    if len(unmatched) > 0:
        print(f"\n🤖 Testing match for first job...")
        job = unmatched[0]
        print(f"   Job: {job.get('title')}")
        print(f"   Company: {job.get('company_name')}")

        # Test quick score
        quick_score = matcher._quick_score(profile_data, job)
        print(f"   Quick score: {quick_score:.1f}%")

        if quick_score >= 30:
            print(f"   → Will use AI matching (score >= 30)")
            result = await matcher._match_single_job(profile_data, job)
            if result:
                print(f"   ✅ Match result:")
                print(f"      Overall score: {result.get('overall_score'):.1f}%")
                print(f"      Recommendation: {result.get('recommendation')}")
                print(f"      Reasoning: {result.get('reasoning', '')[:100]}...")
            else:
                print(f"   ❌ Matching failed (returned None)")
        else:
            print(f"   → Skipped AI matching (score < 30)")

    # Run full matching
    print(f"\n🚀 Running full matching pipeline...")
    matches = await matcher.match_jobs_for_profile(1)
    print(f"✅ Matches created: {len(matches)}")

    if matches:
        print(f"\nTop matches:")
        for i, match in enumerate(matches[:5]):
            job = match.get('job', {})
            print(f"  {i+1}. {job.get('title')} - {match.get('overall_score'):.1f}%")

if __name__ == '__main__':
    asyncio.run(main())

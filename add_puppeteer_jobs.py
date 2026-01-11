"""Quick script to add the 14 jobs extracted via Puppeteer"""

import sys
sys.path.insert(0, '/Users/daniel/workapps/job-search-automation')

from src.database import DatabaseManager
from datetime import datetime

# The 14 real jobs we extracted via Puppeteer
jobs = [
    {
        "title": "Site Safety Coordinator",
        "company_name": "Blue Sage Services",
        "location": "Beaver, OK 73932",
        "source": "indeed_puppeteer",
        "apply_url": "https://www.indeed.com/rc/clk?jk=2dfebc4aa18a5b23",
        "description": "Site Safety Coordinator position at Blue Sage Services in Beaver, OK",
        "posted_date": datetime.now().isoformat(),
        "location_type": "onsite",
        "employment_type": "full-time"
    },
    {
        "title": "SR SAFETY COORDINATOR",
        "company_name": "FORCE ELECTRICAL SERVICES",
        "location": "Oklahoma City, OK 73103",
        "source": "indeed_puppeteer",
        "apply_url": "https://www.indeed.com/rc/clk?jk=ace79eb21033c68a",
        "description": "Senior Safety Coordinator position at FORCE ELECTRICAL SERVICES in Oklahoma City",
        "posted_date": datetime.now().isoformat(),
        "location_type": "onsite",
        "employment_type": "full-time"
    },
    {
        "title": "Safety Coordinator",
        "company_name": "Duit Construction",
        "location": "Oklahoma City, OK",
        "source": "indeed_puppeteer",
        "apply_url": "https://www.indeed.com/rc/clk?jk=1725ee2c1335c0e5",
        "description": "Safety Coordinator position at Duit Construction in Oklahoma City",
        "posted_date": datetime.now().isoformat(),
        "location_type": "onsite",
        "employment_type": "full-time"
    },
    {
        "title": "Safety & Training Coordinator",
        "company_name": "Highridge Corrosion Services",
        "location": "Prague, OK 74864",
        "source": "indeed_puppeteer",
        "apply_url": "https://www.indeed.com/rc/clk?jk=40a99db456d67c2e",
        "description": "Safety & Training Coordinator at Highridge Corrosion Services in Prague, OK",
        "posted_date": datetime.now().isoformat(),
        "location_type": "onsite",
        "employment_type": "full-time"
    },
    {
        "title": "Safety Specialist",
        "company_name": "Cavco Manufacturing LLC",
        "location": "Duncan, OK 73533",
        "source": "indeed_puppeteer",
        "apply_url": "https://www.indeed.com/rc/clk?jk=eda20503fe971539",
        "description": "Safety Specialist position at Cavco Manufacturing LLC in Duncan, OK",
        "posted_date": datetime.now().isoformat(),
        "location_type": "onsite",
        "employment_type": "full-time"
    },
    {
        "title": "Safety Support Specialist",
        "company_name": "The Davey Tree Expert Company",
        "location": "Oklahoma",
        "source": "indeed_puppeteer",
        "apply_url": "https://www.indeed.com/pagead/clk?mo=r&ad=-6NYlbfkN0DcS-P5NUBDu4xoTfy8nct7",
        "description": "Safety Support Specialist for Utility Asset Management at The Davey Tree Expert Company",
        "posted_date": datetime.now().isoformat(),
        "location_type": "onsite",
        "employment_type": "full-time"
    },
    {
        "title": "Commercial Construction Safety Director",
        "company_name": "Lambert Construction Company",
        "location": "Stillwater, OK 74074",
        "source": "indeed_puppeteer",
        "apply_url": "https://www.indeed.com/rc/clk?jk=8a2d58588e2e45f9",
        "description": "Commercial Construction Safety Director at Lambert Construction Company in Stillwater, OK",
        "posted_date": datetime.now().isoformat(),
        "location_type": "onsite",
        "employment_type": "full-time"
    },
    {
        "title": "Construction Safety Manager",
        "company_name": "Primary Holdings, Inc.",
        "location": "Duke, OK",
        "source": "indeed_puppeteer",
        "apply_url": "https://www.indeed.com/rc/clk?jk=ea344856f18c6baf",
        "description": "Construction Safety Manager at Primary Holdings, Inc. in Duke, OK",
        "posted_date": datetime.now().isoformat(),
        "location_type": "onsite",
        "employment_type": "full-time"
    },
    {
        "title": "Environmental Health and Safety (EHS) Specialist",
        "company_name": "Axel U.S.",
        "location": "Tulsa, OK 74127",
        "source": "indeed_puppeteer",
        "apply_url": "https://www.indeed.com/rc/clk?jk=d3ce68eeb85ee286",
        "description": "Environmental Health and Safety (EHS) Specialist at Axel U.S. in Tulsa, OK",
        "posted_date": datetime.now().isoformat(),
        "location_type": "onsite",
        "employment_type": "full-time"
    },
    {
        "title": "Advisor - Health & Safety",
        "company_name": "Boralex",
        "location": "Oklahoma",
        "source": "indeed_puppeteer",
        "apply_url": "https://www.indeed.com/rc/clk?jk=4b17d28f857e64fd",
        "description": "Advisor - Health & Safety position at Boralex in Oklahoma",
        "posted_date": datetime.now().isoformat(),
        "location_type": "onsite",
        "employment_type": "full-time"
    },
    {
        "title": "Occupational Safety and Health Specialist",
        "company_name": "Manhattan Road and Bridge",
        "location": "Tulsa, OK 74146",
        "source": "indeed_puppeteer",
        "apply_url": "https://www.indeed.com/rc/clk?jk=138272b3c34fc43c",
        "description": "Occupational Safety and Health Specialist at Manhattan Road and Bridge in Tulsa, OK",
        "posted_date": datetime.now().isoformat(),
        "location_type": "onsite",
        "employment_type": "full-time"
    },
    {
        "title": "Site Safety Health Officer",
        "company_name": "Ross Group",
        "location": "McAlester, OK 74501",
        "source": "indeed_puppeteer",
        "apply_url": "https://www.indeed.com/rc/clk?jk=426019f16afd108e",
        "description": "Site Safety Health Officer at Ross Group in McAlester, OK",
        "posted_date": datetime.now().isoformat(),
        "location_type": "onsite",
        "employment_type": "full-time"
    },
    {
        "title": "Safety Specialist",
        "company_name": "USA Compression",
        "location": "El Reno, OK",
        "source": "indeed_puppeteer",
        "apply_url": "https://www.indeed.com/rc/clk?jk=2ba31dcd5f2ccb11",
        "description": "Safety Specialist position at USA Compression in El Reno, OK",
        "posted_date": datetime.now().isoformat(),
        "location_type": "onsite",
        "employment_type": "full-time"
    },
    {
        "title": "Health, Safety, & Quality Rep Staff",
        "company_name": "OG&E",
        "location": "Fort Gibson, OK 74434",
        "source": "indeed_puppeteer",
        "apply_url": "https://www.indeed.com/rc/clk?jk=d30b3d134a2013bf",
        "description": "Health, Safety, & Quality Rep Staff at OG&E in Fort Gibson, OK",
        "posted_date": datetime.now().isoformat(),
        "location_type": "onsite",
        "employment_type": "full-time"
    }
]

# Initialize database
db = DatabaseManager()

# Add jobs
print("Adding 14 real HSE/Safety jobs from Indeed (via Puppeteer)...")
for job in jobs:
    try:
        job_id, is_new = db.add_job_listing(**job)
        status = "NEW" if is_new else "EXISTS"
        print(f"  {status}: {job['title']} - {job['company_name']}")
    except Exception as e:
        print(f"  ERROR: {job['title']} - {e}")

print("\nDone! Run ./run.sh to match these jobs to your profile.")

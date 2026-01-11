# Job Search Automation - Comprehensive Bug Audit Report
**Date**: 2026-01-10
**Audited By**: Claude Code
**Codebase**: /Users/daniel/workapps/job-search-automation/

---

## Executive Summary

The job search automation system has **5 critical/high severity bugs** preventing it from working as intended. The system is technically sound in architecture but has:
- Missing database table causing credential lookup failures
- Incorrect User-Agent strings causing 403 blocks
- Missing API keys for USAJOBS
- Wrong job sources (software jobs vs HSE jobs)
- Aggressive filtering threshold skipping valid matches

---

## Bug Report: Critical & High Priority Issues

### 🔴 BUG #1: USAJOBS Scraper Queries Non-Existent Database Table
**Severity**: CRITICAL
**File**: `src/agents/usajobs_scraper.py:30-42`
**Impact**: USAJOBS scraper crashes on initialization

**Problem**:
```python
# usajobs_scraper.py line 31-37
with self.db.connection() as conn:
    cursor = conn.execute(
        "SELECT credential_value FROM credentials WHERE service_name = ?",
        ('usajobs',)
    )
```

The code tries to query a `credentials` table in `job_search.db`, but this table **does not exist**. The database schema only includes:
- applications, candidate_*, companies, config, daily_reports, github_repos, job_*, notifications, search_*, system_logs

**Error Message**:
```
Database error: no such table: credentials
Could not retrieve USAJOBS API key: no such table: credentials
```

**Root Cause**:
- `src/database/schema.sql` never creates a `credentials` table
- The credential system uses `~/databases/productivity.db` (different database)
- USAJOBS scraper incorrectly assumes credentials are in `job_search.db`

**Fix**:
```python
# Option 1: Use existing credential system
from src.utils.credentials import get_credential_manager

def __init__(self, db):
    self.db = db
    # Use the shared credential manager instead
    manager = get_credential_manager()
    self.api_key = manager.get('usajobs', 'USAJOBS_API_KEY')
```

OR

```python
# Option 2: Add credentials table to job_search.db schema
# In src/database/schema.sql, add:
CREATE TABLE IF NOT EXISTS credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name TEXT UNIQUE NOT NULL,
    credential_value TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

### 🔴 BUG #2: USAJOBS API Key Missing
**Severity**: CRITICAL
**File**: N/A (configuration issue)
**Impact**: USAJOBS returns 401 Unauthorized errors

**Problem**:
USAJOBS API requires an API key in the `Authorization-Key` header, but no key is configured.

**Error Message**:
```
USAJOBS returned status 401
USAJOBS returned status 401
```

**Verification**:
```bash
$ sqlite3 ~/databases/productivity.db "SELECT service_name FROM credentials WHERE service_name='usajobs';"
# Returns nothing - no usajobs credential
```

**Fix**:
1. Register for free USAJOBS API key at: https://developer.usajobs.gov/APIRequest/Index
2. Add to database:
```bash
sqlite3 ~/databases/productivity.db "INSERT INTO credentials (service_name, api_key, is_active) VALUES ('usajobs', 'YOUR_API_KEY_HERE', 1);"
```

**Note**: USAJOBS is 100% free, no credit card required. Just needs email signup.

---

### 🔴 BUG #3: RSS Scrapers Use Bot-Like User-Agent
**Severity**: HIGH
**File**: `src/agents/rss_scraper.py:86, 143, 192`
**Impact**: All RSS feeds blocked with 403 Forbidden

**Problem**:
```python
headers={'User-Agent': 'Mozilla/5.0 Job Search RSS Reader/1.0'}
```

This User-Agent string **immediately identifies the request as a bot**. Modern websites block non-browser User-Agents to prevent scraping. Indeed, SimplyHired, and CareerJet all return 403 Forbidden.

**Error Messages**:
```
Indeed RSS fetch failed: HTTP Error 403: Forbidden
SimplyHired fetch failed: HTTP Error 403: Forbidden
CareerJet RSS fetch failed: <urlopen error [Errno 8] nodename nor servname provided, or not known>
```

**Fix**:
Use a realistic browser User-Agent:
```python
headers={
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
```

**Updated Code** (lines 84-87, 141-144, 190-193):
```python
req = urllib.request.Request(
    url,
    headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/rss+xml, application/xml, text/xml, */*',
        'Accept-Language': 'en-US,en;q=0.9',
    }
)
```

---

### 🟠 BUG #4: Wrong Job Source (RemoteOK = Software Jobs Only)
**Severity**: HIGH
**File**: `src/agents/job_searcher.py:293-345`
**Impact**: Only finding software engineering jobs, 0 HSE matches

**Problem**:
RemoteOK API (`https://remoteok.com/api`) is a **tech-only job board**. It only has software engineering, DevOps, and IT positions. User's profile is HSE/Safety/Operations in oil & gas industry.

**Current Results**:
```
Senior Software Engineer Solutions @ Ada
Principal Software Engineer @ Recorded Future
Software Engineer Identity Access Management @ Zip
AEP Enterprise Architect @ Jobgether
```

**Match Scores**: 12-45% (correctly low, but jobs are irrelevant)

**Root Cause**:
The system needs HSE/Safety/Operations job sources, not tech job boards.

**Fix**:
Replace or supplement RemoteOK with relevant sources:

1. **USAJOBS** (already implemented, needs API key):
   - Federal HSE, Safety, Environmental, Compliance roles
   - Free API, no credit card

2. **State/Local Government Jobs**:
   ```python
   # Oklahoma state jobs
   'https://www.ok.gov/opm/joblist.php'
   # City of Oklahoma City
   'https://www.okc.gov/government/city-jobs'
   ```

3. **Industry-Specific Boards**:
   ```python
   'https://www.rigzone.com/jobs/' # Oil & gas specific
   'https://www.oilandgasjobsearch.com/' # Energy industry
   'https://jobs.spe.org/' # Society of Petroleum Engineers
   ```

4. **Company Career Pages**:
   - Devon Energy
   - Continental Resources
   - Chesapeake Energy
   - Other Oklahoma energy companies

---

### 🟠 BUG #5: Aggressive Quick Score Threshold Skips Valid Jobs
**Severity**: MEDIUM
**File**: `src/agents/matcher.py:126-131`
**Impact**: Jobs scoring 12-29% skip AI analysis entirely

**Problem**:
```python
if quick_score < 30:
    return {
        'overall_score': quick_score,
        'recommendation': 'poor_match',
        'reasoning': 'Low skill alignment based on keyword matching'
    }
```

The quick_score is based on **exact keyword matching**. For HSE jobs, terms like "Safety Manager" or "HSE Coordinator" might not contain specific skill keywords like "OSHA" or "Risk Management". This causes them to score < 30% and skip AI analysis.

**Example**:
- Job title: "ERP Systems Manager @ DISHER"
- Quick score: ~20% (few keyword matches)
- Never sent to GPT-4 for deeper analysis
- Might actually be 65% match with AI analysis

**Impact on Current Run**:
```
Matches created: 1
Average score: 0.0%
Top 5 matches:
  - ERP Systems Manager @ DISHER: 45%
```

Only 1 match created because all others scored < 30% and were skipped.

**Fix Option 1** (Lower Threshold):
```python
if quick_score < 15:  # More lenient threshold
    return {
        'overall_score': quick_score,
        'recommendation': 'poor_match',
        'reasoning': 'Very low skill alignment'
    }
```

**Fix Option 2** (HSE-Specific Keywords):
```python
def _quick_score(self, profile_data: Dict, job: Dict) -> float:
    """Quick heuristic score with HSE-specific boosting."""
    # ... existing code ...

    # Boost for HSE-relevant titles
    hse_keywords = {'hse', 'safety', 'health', 'environmental', 'compliance',
                    'risk', 'ehs', 'operations manager', 'drilling', 'well control'}
    job_title_lower = job.get('title', '').lower()

    if any(keyword in job_title_lower for keyword in hse_keywords):
        match_ratio += 0.2  # 20% boost for HSE titles
```

**Fix Option 3** (Remove Threshold Entirely for Debug):
```python
# Comment out the early return for testing
# if quick_score < 30:
#     return {...}

# Always run AI analysis for now
return await self._ai_match(profile_data, job, quick_score)
```

---

## Additional Findings (Low Priority)

### ⚪ BUG #6: osascript Notification Crashes (FIXED)
**Severity**: LOW (Already Fixed)
**File**: `src/agents/reporter.py:487-514`
**Impact**: Segmentation faults on macOS notifications

**Status**: ✅ FIXED in latest code
- Added timeout and error handling
- Fixed script formatting
- No longer crashes the pipeline

---

### ⚪ BUG #7: CareerJet DNS Errors
**Severity**: LOW
**File**: `src/agents/rss_scraper.py:178-232`
**Impact**: CareerJet RSS always fails

**Problem**:
```
CareerJet RSS fetch failed: <urlopen error [Errno 8] nodename nor servname provided, or not known>
```

DNS resolution failing for `rss.careerjet.com`. May be:
- Domain no longer exists
- Requires API key
- Geographic restrictions

**Fix**:
Remove CareerJet from RSS feeds (it's not working anyway):
```python
# Remove or comment out CareerJet scraping
# careerjet_jobs = await self._fetch_careerjet_rss(query, location)
```

---

## Architecture Review

### ✅ Good Practices Found:
1. **Async/await properly used** - No race conditions detected
2. **Database transactions** - Proper commit/rollback
3. **Error handling** - Try/except blocks in place
4. **Logging** - Comprehensive logging throughout
5. **Modular design** - Clean separation of concerns

### ⚠️ Areas for Improvement:
1. **Database schema** - Missing credentials table
2. **Job sources** - Need industry-specific boards
3. **Matching threshold** - Too aggressive for non-tech jobs
4. **User-Agent strings** - Need realistic browser headers
5. **API key management** - Inconsistent between scrapers

---

## Priority Fix List

### Immediate (Do Now):
1. **Fix USAJOBS credential lookup** - Use shared credential manager
2. **Get USAJOBS API key** - Register at developer.usajobs.gov
3. **Fix RSS User-Agent strings** - Use realistic browser headers

### Short Term (This Week):
4. **Add Oklahoma state job scraper** - No API key needed
5. **Lower matching threshold to 15%** - Allow more AI analysis
6. **Remove CareerJet** - It doesn't work

### Medium Term (Future Enhancement):
7. **Add Rigzone scraper** - Oil & gas specific
8. **Add company career page scrapers** - Devon, Continental, etc.
9. **Disable RemoteOK** - Wrong industry entirely
10. **Create credentials table in job_search.db** - Proper schema

---

## Testing Recommendations

After fixes, test with:
```bash
# 1. Clear database
sqlite3 ~/databases/job_search.db "DELETE FROM job_listings; DELETE FROM job_matches;"

# 2. Add USAJOBS key
sqlite3 ~/databases/productivity.db "INSERT INTO credentials (service_name, api_key, is_active) VALUES ('usajobs', 'YOUR_KEY', 1);"

# 3. Run pipeline
cd ~/workapps/job-search-automation
./run.sh

# 4. Verify results
# - USAJOBS should work (no 401 errors)
# - RSS feeds might work (no 403 if User-Agent fixed)
# - More matches created (lower threshold)
# - HSE/Safety jobs found (right sources)
```

---

## Summary of Issues

| Bug # | Severity | Issue | Status | ETA to Fix |
|-------|----------|-------|--------|------------|
| 1 | CRITICAL | credentials table missing | Open | 10 min |
| 2 | CRITICAL | USAJOBS API key missing | Open | 5 min |
| 3 | HIGH | RSS User-Agent blocks | Open | 5 min |
| 4 | HIGH | Wrong job sources (tech vs HSE) | Open | 30 min |
| 5 | MEDIUM | Matching threshold too high | Open | 5 min |
| 6 | LOW | osascript crashes | **Fixed** | ✅ Done |
| 7 | LOW | CareerJet DNS errors | Open | 2 min |

**Total Time to Fix All**: ~60 minutes

---

## Conclusion

The job search system is **architecturally sound** but has configuration and integration issues preventing it from working:

1. **Database mismatch** - USAJOBS scraper queries wrong database
2. **Missing API keys** - USAJOBS needs free registration
3. **Bot detection** - RSS scrapers use obvious bot User-Agent
4. **Wrong data sources** - Tech job boards for HSE professional
5. **Aggressive filtering** - Skips jobs that might match

**Recommendation**: Fix bugs 1-3 immediately (20 minutes total). This will get USAJOBS working and RSS feeds potentially unblocked. Then add Oklahoma state jobs (no API needed) for immediate HSE results.

---

**Report End**

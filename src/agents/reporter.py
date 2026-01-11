"""
Reporter & Notification Sub-Agent
Generates daily reports and sends notifications.
"""

import json
import os
import smtplib
import ssl
import asyncio
import aiohttp
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import logging
import subprocess

from src.database import DatabaseManager, get_db
from src.utils.credentials import get_slack_webhook, get_notification_email

logger = logging.getLogger(__name__)

# Report output directory
REPORTS_DIR = Path.home() / "workapps" / "job-search-automation" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


class Reporter:
    """
    Generates daily job match reports and sends notifications via:
    - Email
    - Slack
    - macOS notifications
    - HTML/Markdown files
    """

    def __init__(self, db: DatabaseManager = None):
        self.db = db or get_db()
        self.slack_webhook = get_slack_webhook()
        self.notification_email = get_notification_email()

    async def generate_daily_report(self, profile_id: int = 1, min_score: float = 60) -> Dict:
        """
        Generate a comprehensive daily report.

        Args:
            profile_id: Candidate profile ID
            min_score: Minimum match score to include

        Returns:
            Report data and file paths
        """
        report_date = datetime.now().strftime("%Y-%m-%d")
        logger.info(f"Generating daily report for {report_date}")

        # Get matches
        matches = self.db.get_top_matches(profile_id, limit=50, min_score=min_score)

        # Get stats
        stats = self.db.get_stats()

        # Get profile
        profile = self.db.get_profile(profile_id)

        # Build report data
        report_data = {
            'date': report_date,
            'generated_at': datetime.now().isoformat(),
            'profile_name': profile.get('name', 'Unknown') if profile else 'Unknown',
            'summary': {
                'total_active_jobs': stats.get('active_jobs', 0),
                'jobs_added_today': stats.get('jobs_today', 0),
                'total_matches': len(matches),
                'strong_matches': len([m for m in matches if m['overall_score'] >= 80]),
                'good_matches': len([m for m in matches if 65 <= m['overall_score'] < 80]),
                'average_score': round(sum(m['overall_score'] for m in matches) / len(matches), 1) if matches else 0
            },
            'top_matches': [self._format_match(m) for m in matches[:20]],
            'all_matches': [self._format_match(m) for m in matches]
        }

        # Generate HTML report
        html_content = self._generate_html_report(report_data)
        html_path = REPORTS_DIR / f"job_report_{report_date}.html"
        html_path.write_text(html_content)

        # Generate Markdown report
        md_content = self._generate_markdown_report(report_data)
        md_path = REPORTS_DIR / f"job_report_{report_date}.md"
        md_path.write_text(md_content)

        # Save to database
        report_id = self.db.create_daily_report(
            report_date=report_date,
            total_jobs_searched=stats.get('active_jobs', 0),
            new_jobs_found=stats.get('jobs_today', 0),
            matches_generated=len(matches),
            top_matches_count=report_data['summary']['strong_matches'],
            report_html=html_content,
            report_markdown=md_content,
            report_path=str(html_path)
        )

        report_data['report_id'] = report_id
        report_data['html_path'] = str(html_path)
        report_data['md_path'] = str(md_path)

        logger.info(f"Report generated: {html_path}")
        return report_data

    def _format_match(self, match: Dict) -> Dict:
        """Format a match for the report."""
        return {
            'job_title': match.get('title', 'Unknown'),
            'company': match.get('company_name', 'Unknown'),
            'location': match.get('location', 'Not specified'),
            'location_type': match.get('location_type', 'unknown'),
            'score': match.get('overall_score', 0),
            'skill_score': match.get('skill_match_score', 0),
            'experience_score': match.get('experience_match_score', 0),
            'apply_url': match.get('apply_url', ''),
            'source': match.get('source', 'unknown'),
            'posted_date': match.get('posted_date', ''),
            'reasoning': match.get('match_reasoning', ''),
            'matched_skills': json.loads(match.get('matched_skills', '[]')) if match.get('matched_skills') else [],
            'missing_skills': json.loads(match.get('missing_skills', '[]')) if match.get('missing_skills') else [],
            'strengths': json.loads(match.get('strengths', '[]')) if match.get('strengths') else [],
            'concerns': json.loads(match.get('concerns', '[]')) if match.get('concerns') else [],
            'recommendation': match.get('recommendation', 'unknown'),
            'salary_min': match.get('salary_min'),
            'salary_max': match.get('salary_max')
        }

    def _generate_html_report(self, data: Dict) -> str:
        """Generate HTML report."""
        summary = data['summary']
        matches = data['top_matches']

        # Score badge color
        def score_color(score):
            if score >= 80:
                return '#22c55e'  # Green
            elif score >= 65:
                return '#3b82f6'  # Blue
            elif score >= 50:
                return '#f59e0b'  # Yellow
            return '#ef4444'  # Red

        # Generate match cards
        match_cards = ""
        for i, m in enumerate(matches, 1):
            salary_str = ""
            if m['salary_min'] or m['salary_max']:
                if m['salary_min'] and m['salary_max']:
                    salary_str = f"${m['salary_min']:,} - ${m['salary_max']:,}"
                elif m['salary_min']:
                    salary_str = f"From ${m['salary_min']:,}"
                else:
                    salary_str = f"Up to ${m['salary_max']:,}"

            strengths_html = "".join(f"<li>{s}</li>" for s in m.get('strengths', [])[:3])
            concerns_html = "".join(f"<li>{s}</li>" for s in m.get('concerns', [])[:2])

            match_cards += f"""
            <div class="match-card">
                <div class="match-header">
                    <div class="match-rank">#{i}</div>
                    <div class="match-score" style="background-color: {score_color(m['score'])}">
                        {m['score']:.0f}%
                    </div>
                </div>
                <h3 class="job-title">{m['job_title']}</h3>
                <p class="company">{m['company']}</p>
                <div class="job-meta">
                    <span class="location">{m['location']}</span>
                    <span class="location-type">{m['location_type'].upper()}</span>
                    {f'<span class="salary">{salary_str}</span>' if salary_str else ''}
                </div>
                <div class="reasoning">{m.get('reasoning', '')}</div>
                {f'<div class="strengths"><strong>Strengths:</strong><ul>{strengths_html}</ul></div>' if strengths_html else ''}
                {f'<div class="concerns"><strong>Considerations:</strong><ul>{concerns_html}</ul></div>' if concerns_html else ''}
                <div class="actions">
                    <a href="{m['apply_url']}" target="_blank" class="apply-btn">Apply Now</a>
                    <span class="source">via {m['source']}</span>
                </div>
            </div>
            """

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Job Match Report - {data['date']}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f8fafc;
            color: #1e293b;
            line-height: 1.6;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        header {{
            background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
            color: white;
            padding: 40px 20px;
            margin-bottom: 30px;
            border-radius: 12px;
        }}
        h1 {{ font-size: 2rem; margin-bottom: 10px; }}
        .date {{ opacity: 0.9; font-size: 1.1rem; }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .stat-card {{
            background: white;
            padding: 24px;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .stat-value {{
            font-size: 2.5rem;
            font-weight: 700;
            color: #1e40af;
        }}
        .stat-label {{ color: #64748b; margin-top: 5px; }}
        .matches-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }}
        .match-card {{
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .match-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        .match-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        .match-rank {{
            font-size: 1.2rem;
            font-weight: 700;
            color: #64748b;
        }}
        .match-score {{
            color: white;
            padding: 6px 14px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 1rem;
        }}
        .job-title {{
            font-size: 1.25rem;
            margin-bottom: 5px;
            color: #1e293b;
        }}
        .company {{
            color: #3b82f6;
            font-weight: 500;
            margin-bottom: 10px;
        }}
        .job-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 15px;
        }}
        .job-meta span {{
            background: #f1f5f9;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.85rem;
        }}
        .location-type {{
            background: #dbeafe !important;
            color: #1e40af;
        }}
        .salary {{ color: #059669; font-weight: 500; }}
        .reasoning {{
            color: #475569;
            font-size: 0.95rem;
            margin-bottom: 15px;
            padding: 12px;
            background: #f8fafc;
            border-radius: 8px;
        }}
        .strengths, .concerns {{ margin-bottom: 10px; font-size: 0.9rem; }}
        .strengths ul, .concerns ul {{ margin-left: 20px; margin-top: 5px; }}
        .strengths {{ color: #059669; }}
        .concerns {{ color: #d97706; }}
        .actions {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #e2e8f0;
        }}
        .apply-btn {{
            background: #3b82f6;
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 500;
            transition: background 0.2s;
        }}
        .apply-btn:hover {{ background: #2563eb; }}
        .source {{ color: #94a3b8; font-size: 0.85rem; }}
        footer {{
            text-align: center;
            padding: 40px 20px;
            color: #64748b;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Job Match Report</h1>
            <p class="date">{data['date']} | {data['profile_name']}</p>
        </header>

        <section class="summary">
            <div class="stat-card">
                <div class="stat-value">{summary['total_matches']}</div>
                <div class="stat-label">Total Matches</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #22c55e">{summary['strong_matches']}</div>
                <div class="stat-label">Strong Matches (80%+)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #3b82f6">{summary['good_matches']}</div>
                <div class="stat-label">Good Matches (65-79%)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{summary['average_score']:.0f}%</div>
                <div class="stat-label">Average Score</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{summary['jobs_added_today']}</div>
                <div class="stat-label">New Jobs Today</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{summary['total_active_jobs']}</div>
                <div class="stat-label">Active Listings</div>
            </div>
        </section>

        <h2 style="margin-bottom: 20px; font-size: 1.5rem;">Top Matches</h2>
        <section class="matches-grid">
            {match_cards}
        </section>

        <footer>
            <p>Generated by Job Search Automation System</p>
            <p>Report generated at {data['generated_at']}</p>
        </footer>
    </div>
</body>
</html>"""
        return html

    def _generate_markdown_report(self, data: Dict) -> str:
        """Generate Markdown report."""
        summary = data['summary']
        matches = data['top_matches']

        md = f"""# Job Match Report - {data['date']}

Generated: {data['generated_at']}
Profile: {data['profile_name']}

## Summary

| Metric | Value |
|--------|-------|
| Total Matches | {summary['total_matches']} |
| Strong Matches (80%+) | {summary['strong_matches']} |
| Good Matches (65-79%) | {summary['good_matches']} |
| Average Score | {summary['average_score']:.1f}% |
| New Jobs Today | {summary['jobs_added_today']} |
| Active Listings | {summary['total_active_jobs']} |

---

## Top Matches

"""
        for i, m in enumerate(matches, 1):
            score_badge = "+++" if m['score'] >= 80 else ("++" if m['score'] >= 65 else "+")

            salary_str = ""
            if m['salary_min'] or m['salary_max']:
                if m['salary_min'] and m['salary_max']:
                    salary_str = f"${m['salary_min']:,} - ${m['salary_max']:,}"
                elif m['salary_min']:
                    salary_str = f"From ${m['salary_min']:,}"
                else:
                    salary_str = f"Up to ${m['salary_max']:,}"

            md += f"""### {i}. {m['job_title']} [{score_badge} {m['score']:.0f}%]

**Company:** {m['company']}
**Location:** {m['location']} ({m['location_type']})
{f"**Salary:** {salary_str}" if salary_str else ""}
**Source:** {m['source']}

{m.get('reasoning', '')}

"""
            if m.get('strengths'):
                md += "**Strengths:**\n"
                for s in m['strengths'][:3]:
                    md += f"- {s}\n"
                md += "\n"

            if m.get('concerns'):
                md += "**Considerations:**\n"
                for c in m['concerns'][:2]:
                    md += f"- {c}\n"
                md += "\n"

            md += f"[Apply Now]({m['apply_url']})\n\n---\n\n"

        md += """
---

*Generated by Job Search Automation System*
"""
        return md

    async def send_notifications(self, report_data: Dict) -> Dict:
        """Send notifications about the report."""
        results = {}

        # macOS notification (always attempt)
        try:
            self._send_macos_notification(report_data)
            results['macos'] = 'sent'
        except Exception as e:
            logger.error(f"macOS notification error: {e}")
            results['macos'] = f'error: {e}'

        # Slack notification
        if self.slack_webhook:
            try:
                await self._send_slack_notification(report_data)
                results['slack'] = 'sent'
            except Exception as e:
                logger.error(f"Slack notification error: {e}")
                results['slack'] = f'error: {e}'

        # Log notifications
        report_id = report_data.get('report_id')
        if report_id:
            for notif_type, status in results.items():
                self.db.log_notification(
                    report_id=report_id,
                    notification_type=notif_type,
                    recipient=notif_type,
                    subject=f"Job Match Report - {report_data['date']}",
                    status='sent' if status == 'sent' else 'failed',
                    error_message=None if status == 'sent' else status,
                    sent_at=datetime.now().isoformat() if status == 'sent' else None
                )

        return results

    def _send_macos_notification(self, report_data: Dict) -> None:
        """Send macOS notification."""
        try:
            summary = report_data['summary']

            title = "Job Match Report Ready"
            message = f"{summary['total_matches']} matches found ({summary['strong_matches']} strong)"

            # Use osascript for macOS notification (fixed formatting to prevent crashes)
            script = f'display notification "{message}" with title "{title}"'

            # Use subprocess with timeout and proper error handling
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                logger.info("macOS notification sent")
            else:
                logger.warning(f"macOS notification failed: {result.stderr}")

        except subprocess.TimeoutExpired:
            logger.warning("macOS notification timed out")
        except Exception as e:
            logger.warning(f"macOS notification error: {e}")

    async def _send_slack_notification(self, report_data: Dict) -> None:
        """Send Slack notification."""
        summary = report_data['summary']

        # Build Slack message
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Job Match Report - {report_data['date']}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Total Matches:* {summary['total_matches']}"},
                    {"type": "mrkdwn", "text": f"*Strong Matches:* {summary['strong_matches']}"},
                    {"type": "mrkdwn", "text": f"*Good Matches:* {summary['good_matches']}"},
                    {"type": "mrkdwn", "text": f"*Avg Score:* {summary['average_score']:.1f}%"}
                ]
            }
        ]

        # Add top matches
        if report_data['top_matches']:
            top_3 = report_data['top_matches'][:3]
            matches_text = "\n".join([
                f"*{i+1}. {m['job_title']}* at {m['company']} ({m['score']:.0f}%)"
                for i, m in enumerate(top_3)
            ])
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Top Matches:*\n{matches_text}"}
            })

        # Add link to full report
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"<file://{report_data.get('html_path', '')}|View Full Report>"
            }
        })

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.slack_webhook,
                json={"blocks": blocks}
            ) as response:
                if response.status != 200:
                    raise Exception(f"Slack API error: {response.status}")

        logger.info("Slack notification sent")

    def open_report(self, report_path: str = None) -> None:
        """Open the report in the default browser."""
        if not report_path:
            # Find most recent report
            reports = sorted(REPORTS_DIR.glob("job_report_*.html"), reverse=True)
            if reports:
                report_path = str(reports[0])
            else:
                logger.warning("No reports found")
                return

        subprocess.run(['open', report_path])
        logger.info(f"Opened report: {report_path}")


async def generate_and_notify(profile_id: int = 1) -> Dict:
    """Generate report and send notifications."""
    reporter = Reporter()

    # Generate report
    report_data = await reporter.generate_daily_report(profile_id)

    # Send notifications
    notification_results = await reporter.send_notifications(report_data)

    return {
        'report': report_data,
        'notifications': notification_results
    }


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(generate_and_notify(1))
    print(f"Report generated: {result['report']['html_path']}")
    print(f"Notifications: {result['notifications']}")

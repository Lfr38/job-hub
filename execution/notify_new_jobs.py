#!/usr/bin/env python3
"""
Check for new AI-passed jobs and send Telegram notification.
Run via cron to get alerts for promising job matches.
"""

import sys
import os
import sqlite3
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from config_loader import load_config

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.tmp', 'jobs.db')

# Thresholds
MIN_SCORE = 40  # Min score to notify
LOOKBACK_HOURS = 8  # Check jobs from last N hours


def get_new_passed_jobs():
    """Get AI-passed jobs from the last N hours."""
    if not os.path.exists(DB_PATH):
        return []
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Jobs with ai_pass status in the last N hours
    lookback = (datetime.now() - timedelta(hours=LOOKBACK_HOURS)).isoformat()
    
    rows = cursor.execute('''
        SELECT title, company, location, url, llm_score, llm_evaluation,
               description, source, ingested_at
        FROM jobs
        WHERE status = 'ai_pass'
          AND llm_score >= ?
          AND ingested_at >= ?
        ORDER BY llm_score DESC
    ''', (MIN_SCORE, lookback)).fetchall()
    
    conn.close()
    return rows


def format_notification(jobs):
    """Format jobs as a Telegram message."""
    if not jobs:
        return None
    
    lines = [f"🎯 *Nuovi job promettenti!* ({len(jobs)} trovati)", ""]
    
    for j in jobs[:5]:  # Top 5
        score = j['llm_score']
        stars = '🔥' if score >= 70 else '⭐'
        
        # Parse evaluation for summary
        summary = ""
        if j['llm_evaluation']:
            try:
                ev = json.loads(j['llm_evaluation'])
                if ev.get('summary'):
                    summary = f"\n   _{ev['summary'][:120]}_"
            except:
                pass
        
        line = (
            f"{stars} *{j['title']}*\n"
            f"   📍 {j['company']} · {j['location'] or 'N/A'}\n"
            f"   🏆 Score: {score}/100"
            f"{summary}"
        )
        lines.append(line)
    
    if len(jobs) > 5:
        lines.append(f"\n… e altri {len(jobs) - 5} job. Vedi la dashboard per tutti.")
    
    lines.append(f"\n📊 Dashboard: http://192.168.2.102:8080")
    
    return '\n'.join(lines)


def check_and_notify():
    """Main check function."""
    jobs = get_new_passed_jobs()
    msg = format_notification(jobs)
    
    if msg:
        print(msg)
        return True
    
    return False


if __name__ == '__main__':
    check_and_notify()

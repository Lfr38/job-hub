#!/usr/bin/env python3
"""
Custom Job Scraper — multiple free sources without anti-bot.
Designed to be called by run_pipeline.py as an additional source.
"""
import re
import json
import time
import logging
import urllib.request
import urllib.error
from datetime import datetime
from typing import List, Dict, Any, Optional

from db_client import initialize_db, is_job_processed, save_job, JobData
from config_loader import get_config

logger = logging.getLogger(__name__)

# ── Trabajo.org (Italian job aggregation board) ──

TRABAJO_BASE = "https://it.trabajo.org"

# Search queries — add more as needed
SEARCH_QUERIES = [
    "python-remoto",
    "cybersecurity-remoto",
    "help-desk-remoto",
    "it-support-remoto",
    "sicurezza-informatica-remoto",
    "sviluppatore-python-remoto",
    "programmatore-remoto",
    "backend-remoto",
]


def fetch_trabajo(query: str, max_pages: int = 5) -> List[Dict[str, Any]]:
    """Scrape it.trabajo.org for job listings."""
    jobs = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    }

    for page in range(1, max_pages + 1):
        url = f"{TRABAJO_BASE}/lavoro-{query}/{page}/"
        logger.info(f"Fetching {url}")

        # Rate limiting: wait between requests
        if page > 1:
            time.sleep(3)

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
        except urllib.error.HTTPError as e:
            if e.code == 429:
                logger.warning(f"  Rate limited on page {page}. Waiting 10s before retry...")
                time.sleep(10)
                try:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        html = resp.read().decode('utf-8', errors='ignore')
                except Exception as e2:
                    logger.warning(f"  Retry failed: {e2}")
                    break
            else:
                logger.warning(f"  Page {page} HTTP {e.code}: {e}")
                break
        except Exception as e:
            logger.warning(f"  Page {page} failed: {e}")
            break

        # Extract job items
        pattern = re.compile(
            r'<li[^>]*class="nf-job[^"]*job-item"[^>]*'
            r'title="([^"]+)"[^>]*'
            r'data-id="([^"]+)"[^>]*'
            r'data-url="([^"]+)"[^>]*'
            r'data-fuente="([^"]*)"'
        )
        found = pattern.findall(html)

        if not found:
            logger.info(f"  No more jobs on page {page}")
            break

        for title, data_id, url, fuente in found:
            jobs.append({
                "title": title.strip(),
                "data_id": data_id,
                "url": url if url.startswith("http") else TRABAJO_BASE + url,
                "source_id": f"trabajo_{data_id}",
                "fuente": fuente,
            })

        logger.info(f"  Page {page}: {len(found)} jobs")

    return jobs


def fetch_trabajo_details(job_url: str) -> Dict[str, str]:
    """Fetch additional details from a job page."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        req = urllib.request.Request(job_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')

        # Extract description
        desc_match = re.search(
            r'<div[^>]*class="nf-offer-desc[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
            html, re.DOTALL
        )
        description = ""
        if desc_match:
            description = re.sub(r'<[^>]+>', ' ', desc_match.group(1))
            description = re.sub(r'\s+', ' ', description).strip()

        # Extract location
        location = ""
        loc_match = re.search(r'<span[^>]*class="[^"]*location[^"]*"[^>]*>(.*?)</span>', html, re.DOTALL)
        if loc_match:
            location = re.sub(r'<[^>]+>', ' ', loc_match.group(1)).strip()

        # Extract company
        company = ""
        comp_match = re.search(r'<span[^>]*class="[^"]*company[^"]*"[^>]*>(.*?)</span>', html, re.DOTALL)
        if comp_match:
            company = re.sub(r'<[^>]+>', ' ', comp_match.group(1)).strip()

        return {
            "description": description,
            "location": location,
            "company": company,
        }
    except Exception as e:
        logger.debug(f"Detail fetch failed for {job_url}: {e}")
        return {}


def process_trabajo_job(job: Dict[str, Any], details: Dict[str, str]) -> Optional[JobData]:
    """Convert raw job data to normalized JobData."""
    title = job["title"]
    description = details.get("description", "")
    location = details.get("location", "")
    company = details.get("company", "Unknown")

    # Detect remote from title/location
    title_lower = title.lower()
    is_remote = any(kw in title_lower for kw in ["remoto", "remote", "da casa", "work from home", "anywhere"])
    is_part_time = any(kw in title_lower for kw in ["part-time", "part time", "parttime", "mezza giornata"])

    job_data: JobData = {
        "system_id": job["source_id"],
        "source": "trabajo",
        "source_id": job["source_id"],
        "title": title,
        "company": company,
        "url": job["url"],
        "description": description[:5000],  # truncate to avoid huge DB
        "publication_date": datetime.now().isoformat(),
        "salary_min": None,
        "salary_max": None,
        "currency": None,
        "location": location or None,
        "remote_type": "remote" if is_remote else None,
        "job_type": None,
        "is_remote": is_remote,
        "is_part_time": is_part_time,
        "candidate_url": job["url"],
        "source_raw": json.dumps(job),
    }
    return job_data


def run() -> None:
    """Main execution: scrape all sources."""
    initialize_db()
    config = get_config()

    logger.info("╔══════════════════════════════════╗")
    logger.info("║   Custom Scraper — Avvio         ║")
    logger.info("╚══════════════════════════════════╝")

    total_new = 0

    # ── Trabajo.org (free, no anti-bot) ──
    logger.info("\n─── Source: Trabajo.org ───")
    for query in SEARCH_QUERIES:
        logger.info(f"  Search: {query}")
        try:
            jobs = fetch_trabajo(query, max_pages=3)
            logger.info(f"  Found {len(jobs)} raw jobs for '{query}'")

            for job in jobs:
                if is_job_processed(job["source_id"]):
                    continue

                # Fetch details for new jobs (limit to keep speed reasonable)
                details = fetch_trabajo_details(job["url"])
                time.sleep(0.3)  # rate limit

                job_data = process_trabajo_job(job, details)
                if job_data:
                    save_job(job_data)
                    total_new += 1

        except Exception as e:
            logger.error(f"  Trabajo '{query}' failed: {e}")

    logger.info(f"\n══════════════════════════════════")
    logger.info(f"  Custom scraper: {total_new} nuovi job salvati")
    logger.info(f"══════════════════════════════════")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    run()

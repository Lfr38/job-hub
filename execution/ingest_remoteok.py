#!/usr/bin/env python3
"""
RemoteOK Job Scraper — API-based (no browser needed).
Free JSON API at remoteok.com/api. Attribution required: link back to RemoteOK.
"""
import sys
import os
import json
import time
import hashlib
import logging
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    import subprocess
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "requests", "-q"],
            timeout=30
        )
        import requests  # noqa: F811
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        logging.error(f"Failed to install requests: {e}")
        raise SystemExit(1) from e

sys.path.insert(0, os.path.dirname(__file__))
from config_loader import load_config
import db_client

logger = logging.getLogger("RemoteOK")

API_URL = "https://remoteok.com/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"
}
REQUEST_DELAY = 2  # seconds between API calls (be gentle)


def _default_tags():
    """Read RemoteOK tags from config, fallback to reasonable defaults."""
    config = load_config()
    return config.get("sources", {}).get("remoteok", {}).get("tags", [
        "python", "ai", "machine-learning", "cybersecurity",
        "devops", "security",
    ])


def fetch_jobs(tag: str) -> list[dict]:
    """Fetch jobs for a single tag from RemoteOK API."""
    params = {"tag": tag, "action": "get_jobs"}
    try:
        resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        # First element is metadata/legal, skip it
        jobs = data[1:] if isinstance(data, list) and len(data) > 1 else []
        logger.info(f"   {tag:20s} → {len(jobs)} job")
        return jobs
    except requests.RequestException as e:
        logger.warning(f"   {tag:20s} → errore: {e}")
        return []
    except (json.JSONDecodeError, IndexError) as e:
        logger.warning(f"   {tag:20s} → parsing error: {e}")
        return []


def run():
    """Main entry point: fetch all tags and save new jobs to DB."""
    logger.info("🌍 RemoteOK Scraper (API)")
    tags = _default_tags()
    logger.info(f"   Tag da cercare: {', '.join(tags)}")

    all_jobs = []
    for tag in tags:
        jobs = fetch_jobs(tag)
        for j in jobs:
            j["_remoteok_tag"] = tag
        all_jobs.extend(jobs)
        if tag != tags[-1]:
            time.sleep(REQUEST_DELAY)

    if not all_jobs:
        logger.info("   ❌ Nessun job trovato")
        return

    # Deduplicate by ID
    seen = set()
    unique = []
    for j in all_jobs:
        jid = str(j.get("id", ""))
        if jid in seen:
            continue
        seen.add(jid)
        unique.append(j)

    logger.info(f"   🎯 {len(unique)} job unici (da {len(all_jobs)} raw)")

    # Save to DB
    db_client.initialize_db()
    inserted = 0
    for j in unique:
        job_id = str(j.get("id", ""))
        system_id = hashlib.md5(f"remoteok_{job_id}".encode()).hexdigest()
        if db_client.is_job_processed(system_id):
            continue

        source_raw = json.dumps({
            "tag": j.get("_remoteok_tag", ""),
            "slug": j.get("slug", ""),
            "salary_min": j.get("salary_min"),
            "salary_max": j.get("salary_max"),
            "epoch": j.get("epoch"),
        })

        db_client.save_job({
            "system_id": system_id,
            "source": "remoteok",
            "source_id": job_id,
            "title": j.get("position", ""),
            "company": j.get("company", ""),
            "url": j.get("url", j.get("apply_url", "")),
            "description": j.get("description", "")[:5000],
            "publication_date": j.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
            "location": j.get("location", "Remote"),
            "candidate_url": j.get("apply_url", ""),
            "source_raw": source_raw,
            "remote_type": "remote",
        })
        inserted += 1

    logger.info(f"   💾 DB: {inserted} nuovi inseriti")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    run()

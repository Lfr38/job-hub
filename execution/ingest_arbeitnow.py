import urllib.request
import urllib.error
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from db_client import initialize_db, is_job_processed, save_job, JobData
from config_loader import get_config

logger = logging.getLogger(__name__)

ARBEITNOW_API_URL = "https://www.arbeitnow.com/api/job-board-api"


def fetch_jobs() -> List[Dict[str, Any]]:
    """Fetches jobs from the Arbeitnow API (free, no key needed)."""
    config = get_config()
    sources = config.get("sources", {})
    api_url = sources.get("arbeitnow", {}).get("api_url", ARBEITNOW_API_URL)

    # Fetch multiple pages to get more jobs
    all_jobs = []
    for page in range(1, 4):  # First 3 pages
        url = f"{api_url}?page={page}&per_page=50"
        logger.info(f"Fetching page {page} from {url}")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    jobs = data.get("data", [])
                    all_jobs.extend(jobs)
                    logger.info(f"  Page {page}: got {len(jobs)} jobs")
                else:
                    logger.warning(f"Page {page}: HTTP {response.status}")
                    break
        except Exception as e:
            logger.warning(f"Page {page} failed: {e}")
            break

    return all_jobs


def process_jobs(jobs: List[Dict[str, Any]]) -> int:
    """Processes jobs, normalizing to our schema and saving."""
    new_jobs_count = 0
    skipped_jobs_count = 0

    for job in jobs:
        slug = str(job.get("slug", ""))
        system_id = f"arbeitnow_{slug}"

        if is_job_processed(system_id):
            skipped_jobs_count += 1
            continue

        title = job.get("title", "")
        description = job.get("description", "") or ""
        # Strip HTML tags from description
        import re
        description_clean = re.sub(r'<[^>]+>', ' ', description)
        description_clean = re.sub(r'\s+', ' ', description_clean).strip()

        # Parse tags into a searchable string
        tags = job.get("tags", [])
        tags_text = " ".join(tags) if tags else ""

        # Detect remote from API field
        is_remote = job.get("remote", False) or False

        # Detect job types
        job_types = job.get("job_types", [])
        job_type_str = ", ".join(job_types) if job_types else None
        is_part_time = any("part" in jt.lower() for jt in job_types) if job_types else False

        # Location
        location = job.get("location", "") or None

        # Publication date - filter only recent jobs (last 7 days)
        created_at = job.get("created_at", "")
        url = job.get("url", "")

        # Company name
        company = job.get("company_name", "") or "Unknown"

        # Arbeitnow doesn't provide salary info in the free API
        # Combine title, description, tags for full-text search
        full_description = f"{description_clean}\nTags: {tags_text}"

        job_data: JobData = {
            "system_id": system_id,
            "source": "arbeitnow",
            "source_id": slug,
            "title": title,
            "company": company,
            "url": url,
            "description": full_description,
            "publication_date": created_at,
            "salary_min": None,
            "salary_max": None,
            "currency": None,
            "location": location,
            "remote_type": "remote" if is_remote else None,
            "job_type": job_type_str,
            "is_remote": is_remote,
            "is_part_time": is_part_time,
            "candidate_url": url,
            "source_raw": json.dumps(job),
        }

        save_job(job_data)
        new_jobs_count += 1

    logger.info(
        f"Arbeitnow ingestion complete. Added {new_jobs_count} new. "
        f"Skipped {skipped_jobs_count} existing."
    )
    return new_jobs_count


def run() -> None:
    """Main execution block"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logger.info("Starting Arbeitnow ingestion...")
    initialize_db()
    jobs = fetch_jobs()

    if jobs:
        logger.info(f"Fetched {len(jobs)} total jobs from Arbeitnow.")
        process_jobs(jobs)
    else:
        logger.warning("No jobs fetched from Arbeitnow.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    run()

import urllib.request
import urllib.error
import json
import logging
from datetime import datetime
from typing import List, Dict, Any
from db_client import initialize_db, is_job_processed, save_job, JobData

logger = logging.getLogger(__name__)

REMOTIVE_API_URL = "https://remotive.com/api/remote-jobs?category=software-dev"


def fetch_jobs() -> List[Dict[str, Any]]:
    """Fetches jobs from the Remotive API."""
    logger.info(f"Fetching jobs from {REMOTIVE_API_URL}")
    req = urllib.request.Request(REMOTIVE_API_URL, headers={'User-Agent': 'Mozilla/5.0'})

    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                return data.get("jobs", [])
            else:
                logger.error(f"Failed to fetch jobs. HTTP Status: {response.status}")
                return []
    except urllib.error.URLError as e:
        logger.error(f"Network error fetching from Remotive API: {e}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"JSON decoding error from Remotive API: {e}")
        return []


def process_jobs(jobs: List[Dict[str, Any]]) -> int:
    """Processes jobs, checking the database for duplicates before saving."""
    new_jobs_count = 0
    skipped_jobs_count = 0

    for job in jobs:
        source_id = str(job.get("id"))
        system_id = f"remotive_{source_id}"

        if is_job_processed(system_id):
            skipped_jobs_count += 1
            continue

        # Remotive returns these extra fields directly in the API response:
        #   salary, candidate_required_location, job_type
        salary_raw = job.get("salary", "")
        location_raw = job.get("candidate_required_location", "")
        job_type_raw = job.get("job_type", "")
        title = job.get("title", "")
        description = job.get("description", "")

        # Parse salary range from string like "$80K - $120K", "$50/hr", etc.
        salary_min, salary_max, currency = parse_salary(salary_raw)

        # Detect remote/part-time from available fields + description
        is_remote = is_remote_job(location_raw, title, description)
        is_part_time = is_part_time_job(job_type_raw, title, description)

        job_data: JobData = {
            "system_id": system_id,
            "source": "remotive",
            "source_id": source_id,
            "title": title,
            "company": job.get("company_name", ""),
            "url": job.get("url", ""),
            "description": description,
            "publication_date": job.get("publication_date", ""),
            "salary_min": salary_min,
            "salary_max": salary_max,
            "currency": currency,
            "location": location_raw or None,
            "remote_type": "remote" if is_remote else None,
            "job_type": job_type_raw or None,
            "is_remote": is_remote,
            "is_part_time": is_part_time,
            "candidate_url": job.get("url", ""),
            "source_raw": json.dumps(job),
        }

        save_job(job_data)
        new_jobs_count += 1

    logger.info(f"Ingestion complete. Added {new_jobs_count} new jobs. Skipped {skipped_jobs_count} existing jobs.")
    return new_jobs_count


def parse_salary(salary_str: str):
    """Extract salary_min, salary_max, currency from a salary string."""
    if not salary_str or salary_str.strip() == "":
        return None, None, None

    salary_str = salary_str.strip()

    # Detect currency
    currency = None
    for sym in ["$", "€", "£", "USD", "EUR", "GBP"]:
        if sym in salary_str:
            currency = sym if len(sym) == 1 else sym
            break

    # Try to find number ranges: "80K - 120K", "$80,000 - $120,000"
    import re
    numbers = re.findall(r'([\d,.]+)(?:\s*[KkMm]?)?', salary_str.replace(",", ""))
    if len(numbers) >= 2:
        try:
            salary_min = int(float(numbers[0]))
            salary_max = int(float(numbers[1]))
            # Normalize if K/M suffixes were already applied vs not
            if "k" in salary_str.lower() and salary_min < 1000:
                salary_min *= 1000
                salary_max *= 1000
            return salary_min, salary_max, currency
        except ValueError:
            pass
    elif len(numbers) == 1:
        try:
            val = int(float(numbers[0]))
            if "k" in salary_str.lower() and val < 1000:
                val *= 1000
            return val, val, currency
        except ValueError:
            pass

    return None, None, currency


def is_remote_job(location: str, title: str, description: str) -> bool:
    """Detect if a job is remote from available fields."""
    text = f"{location} {title} {description}".lower()
    remote_indicators = [
        "remote", "work from home", "wfh", "anywhere", "worldwide",
        "100% remote", "fully remote", "virtual", "telecommute",
        "da remoto", "remoto",
    ]
    return any(kw in text for kw in remote_indicators)


def is_part_time_job(job_type: str, title: str, description: str) -> bool:
    """Detect if a job is part-time."""
    text = f"{job_type} {title} {description}".lower()
    pt_indicators = [
        "part-time", "part time", "parttime", "mezza giornata",
        "20 hours", "25 hours", "30 hours", "4 hour", "4-hour",
        "half day", "half-day",
    ]
    return any(kw in text for kw in pt_indicators)


def run() -> None:
    """Main execution block"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logger.info("Starting Remotive ingestion...")
    initialize_db()
    jobs = fetch_jobs()

    if jobs:
        logger.info(f"Fetched {len(jobs)} total jobs from currently active feed.")
        process_jobs(jobs)
    else:
        logger.warning("No jobs fetched or feed failed.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    run()

import logging
import re
from typing import List, Dict, Any
from db_client import _get_connection
from config_loader import get_config

logger = logging.getLogger(__name__)


def get_unscored_jobs() -> List[Dict[str, Any]]:
    """Retrieves jobs that have not been scored yet (heuristic_score = 0)."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT system_id, title, description, source, location,
               remote_type, job_type, is_remote, is_part_time
        FROM jobs
        WHERE status = 'new' AND heuristic_score = 0
    ''')
    rows = cursor.fetchall()
    conn.close()

    jobs = []
    for row in rows:
        jobs.append({
            "system_id": row["system_id"],
            "title": row["title"] or "",
            "description": row["description"] or "",
            "source": row["source"] or "",
            "location": row["location"] or "",
            "remote_type": row["remote_type"] or "",
            "job_type": row["job_type"] or "",
            "is_remote": bool(row["is_remote"]),
            "is_part_time": bool(row["is_part_time"]),
        })
    return jobs


def calculate_heuristic_score(
    title: str,
    description: str,
    is_remote: bool = False,
    is_part_time: bool = False,
    location: str = "",
) -> tuple:
    """
    Calculates a score based on the YAML config rules.
    Returns: (score, status, details_dict)
    """
    config = get_config()
    search = config.get("search", {})
    scoring = config.get("scoring", {})

    title_lower = title.lower()
    desc_lower = description.lower()
    text_to_search = f"{title_lower} {desc_lower}"

    # ── Negative keywords check (word-boundary match, non substring) ──
    negative_kws = search.get("negative_keywords", [])
    for kw in negative_kws:
        # \b word boundary previene match parziali:
        #   "principal" non matcha "principali"
        #   "lead" non matcha "leading"
        #   "senior" non matcha "seniority"
        #   "director" non matcha "directory"
        #   "+" escaped via re.escape; "5+ years" matcha "5+ years" ma non "5 years"
        pattern = r'\b' + re.escape(kw.lower()) + r'\b'
        if re.search(pattern, text_to_search):
            return -1, "filtered_reject", {"reason": f"negative keyword: {kw}"}

    # ── Part-time check ──
    pt_config = search.get("part_time", {})
    pt_required = pt_config.get("required", False)
    pt_kw = pt_config.get("keywords", [])
    found_pt = any(kw.lower() in text_to_search for kw in pt_kw) or is_part_time

    if pt_required and not found_pt:
        return -1, "filtered_reject", {"reason": "not part-time"}

    # ── Remote check ──
    remote_config = search.get("remote", {})
    remote_required = remote_config.get("required", False)
    remote_kw = remote_config.get("keywords", [])
    found_remote = any(kw.lower() in text_to_search for kw in remote_kw) or is_remote

    if remote_required and not found_remote:
        return -1, "filtered_reject", {"reason": "not remote"}

    # ── Positive scoring ──
    score = 0
    details = {}

    # Title match (biggest signal)
    target_roles = search.get("target_roles", [])
    title_match_found = any(role.lower() in title_lower for role in target_roles)
    if title_match_found:
        matched_titles = [r for r in target_roles if r.lower() in title_lower]
        score += scoring.get("title_match", 30)
        details["title_match"] = matched_titles
    else:
        # If title doesn't match ANY target role, it's probably not relevant
        # but let's not auto-reject - keywords in description might save it
        details["title_match"] = []

    # Keyword match (in title + description)
    required_kws = search.get("required_keywords", [])
    keyword_matches = []
    for kw in required_kws:
        if kw.lower() in text_to_search:
            keyword_matches.append(kw)
            score += scoring.get("keyword_match", 10)
    details["keyword_matches"] = keyword_matches

    # Local jobs check (Brescia area)
    local_config = search.get("local", {})
    if local_config.get("enabled", False):
        local_roles = local_config.get("roles", [])
        local_kws = local_config.get("keywords", [])
        location_lower = (title + " " + description + " " + location).lower()

        is_local_role = any(role.lower() in location_lower for role in local_roles)
        is_local_area = any(kw.lower() in location_lower for kw in local_kws)

        if is_local_role and is_local_area:
            score += scoring.get("local_bonus", 15)
            details["local_match"] = True
            # Local jobs don't need remote/part-time rules
            # Override the reject above if this is a local match
            if remote_required and not found_remote:
                score += 50  # Compensate for "not remote"
                details["local_override"] = True

    # Bonuses
    if found_remote:
        score += scoring.get("remote_bonus", 20)
        details["remote_bonus"] = True
    if found_pt:
        score += scoring.get("part_time_bonus", 25)
        details["part_time_bonus"] = True

    # ── Determine status based on score ──
    threshold = scoring.get("ai_pass_threshold", 40)
    if score <= 0:
        status = "filtered_reject"
    elif score >= threshold:
        status = "filtered_pass"
    else:
        # Low score but positive → still pass, AI will decide
        status = "filtered_pass"

    logger.debug(f"Score: {score}, Status: {status}, Details: {details}")
    return score, status, details


def update_job_score(system_id: str, new_score: int, new_status: str) -> None:
    """Updates the heuristic score and status of a specific job."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE jobs
            SET heuristic_score = ?, status = ?
            WHERE system_id = ?
        ''', (new_score, new_status, system_id))
        conn.commit()
    except Exception as e:
        logger.error(f"Error updating score for {system_id}: {e}")
    finally:
        conn.close()


def run_filters() -> None:
    """Main execution block for heuristic filtering."""
    logger.info("Starting heuristic filtering phase...")
    jobs = get_unscored_jobs()

    if not jobs:
        logger.info("No new jobs to filter.")
        return

    logger.info(f"Found {len(jobs)} jobs to filter.")
    rejected_count = 0
    approved_count = 0
    local_count = 0

    for job in jobs:
        score, status, details = calculate_heuristic_score(
            title=job["title"],
            description=job["description"],
            is_remote=job["is_remote"],
            is_part_time=job["is_part_time"],
            location=job["location"],
        )

        if score < 0:
            rejected_count += 1
        else:
            approved_count += 1
            if details.get("local_match"):
                local_count += 1

        update_job_score(job["system_id"], score, status)

    logger.info(
        f"Filtering complete. Processed: {len(jobs)}. "
        f"Passed: {approved_count}. Rejected: {rejected_count}. "
        f"Local matches: {local_count}."
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    run_filters()

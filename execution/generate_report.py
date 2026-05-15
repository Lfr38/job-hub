import os
import json
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv
from db_client import _get_connection, update_job

import sqlite3  # ← FIX: needed for row_factory in get_jobs_to_report()

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

SPREADSHEET_ID = os.getenv('GOOGLE_SHEET_ID')
RANGE_NAME = 'Sheet1!A:H'


def get_google_sheets_service():
    """Authenticates and returns the Google Sheets API service object."""
    creds = None
    token_path = os.path.join(os.path.dirname(__file__), "..", "token.json")
    creds_path = os.path.join(os.path.dirname(__file__), "..", "credentials.json")

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.warning(f"Failed to refresh token: {e}. Re-authenticating...")
                os.remove(token_path)
                creds = None

        if not creds:
            if not os.path.exists(creds_path):
                logger.error(f"Missing {creds_path}. Download OAuth 2.0 credentials from Google Cloud Console.")
                return None

            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    return build('sheets', 'v4', credentials=creds)


def get_jobs_to_report() -> List[Dict[str, Any]]:
    """Retrieves all jobs that passed the AI filter and haven't been reported."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT system_id, title, company, url, llm_score, llm_evaluation,
               location, salary_min, salary_max, currency, source
        FROM jobs
        WHERE status = 'ai_pass'
    ''')
    rows = cursor.fetchall()

    jobs = []
    for row in rows:
        eval_data = json.loads(row["llm_evaluation"]) if row["llm_evaluation"] else {}
        pros = ", ".join(eval_data.get('pros', []))
        cons = ", ".join(eval_data.get('cons', []))
        summary = eval_data.get('summary', '')
        fit_reason = eval_data.get('fit_reason', '')

        # Format salary
        salary_str = ""
        if row["salary_min"] and row["salary_max"]:
            cur = row["currency"] or "€"
            salary_str = f"{cur}{row['salary_min']} - {cur}{row['salary_max']}"
        elif row["salary_min"]:
            cur = row["currency"] or "€"
            salary_str = f"{cur}{row['salary_min']}"

        jobs.append({
            "system_id": row["system_id"],
            "title": row["title"],
            "company": row["company"],
            "url": row["url"],
            "score": row["llm_score"],
            "pros": pros,
            "cons": cons,
            "summary": summary,
            "fit_reason": fit_reason,
            "location": row["location"] or "",
            "salary": salary_str,
            "source": row["source"] or "",
        })
    conn.close()
    return jobs


def mark_jobs_as_reported(system_ids: List[str]) -> None:
    """Updates the status in the local DB so we don't report them twice."""
    if not system_ids:
        return
    for sid in system_ids:
        update_job(sid, status="reported")


def append_to_sheet(service, jobs: List[Dict[str, Any]]) -> bool:
    """Appends jobs to the Google Sheet, one row at a time for safety."""
    if not SPREADSHEET_ID:
        logger.error("GOOGLE_SHEET_ID is missing from environment variables.")
        return False

    success_count = 0
    for job in jobs:
        row = [
            job['title'],
            job['company'],
            str(job['score']),
            job['summary'],
            job['pros'],
            job['cons'],
            job['url'],
            f"{job['source']} | {job['location']} | {job['salary']}",
        ]

        body = {'values': [row]}
        try:
            service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID,
                range=RANGE_NAME,
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to append job {job['system_id']}: {e}")
            # Don't mark as reported - it will be retried next run

    logger.info(f"Sheet update: {success_count}/{len(jobs)} jobs appended successfully.")
    return success_count > 0


def run_reporting() -> None:
    """Main execution block for generating the report."""
    logger.info("Starting Reporting Phase...")

    jobs = get_jobs_to_report()
    if not jobs:
        logger.info("No new AI-approved jobs to report.")
        return

    logger.info(f"Found {len(jobs)} jobs to send to Google Sheets.")

    service = get_google_sheets_service()
    if not service:
        logger.error("Could not authenticate with Google Sheets.")
        return

    # Append rows individually so partial failures don't lose data
    if append_to_sheet(service, jobs):
        mark_jobs_as_reported([job['system_id'] for job in jobs])
        logger.info("Reporting complete. DB updated.")
    else:
        logger.error("Reporting failed. Jobs remain queued in local DB.")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    run_reporting()

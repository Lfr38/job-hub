import sqlite3
import os
import json
import logging
from datetime import datetime
from typing import TypedDict, Optional, List

logger = logging.getLogger(__name__)


class JobData(TypedDict, total=False):
    system_id: str
    source: str
    source_id: str
    title: str
    company: str
    url: str
    description: str
    publication_date: str
    salary_min: Optional[int]
    salary_max: Optional[int]
    currency: Optional[str]
    location: Optional[str]
    remote_type: Optional[str]
    job_type: Optional[str]           # full-time, part-time, contract, etc.
    is_remote: bool
    is_part_time: bool


DB_PATH = os.path.join(os.path.dirname(__file__), "..", ".tmp", "jobs.db")


def _get_connection() -> sqlite3.Connection:
    """Returns a connection to the SQLite database, creating the directory if needed."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db() -> None:
    """Creates/upgrades the jobs table with migrations."""
    conn = _get_connection()
    cursor = conn.cursor()

    # Base table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            system_id TEXT PRIMARY KEY,
            source TEXT,
            source_id TEXT,
            title TEXT,
            company TEXT,
            url TEXT,
            description TEXT,
            publication_date TEXT,
            ingested_at TEXT,
            status TEXT DEFAULT 'new',
            heuristic_score INTEGER DEFAULT 0,
            llm_score INTEGER DEFAULT 0,
            llm_evaluation TEXT
        )
    ''')

    # ── Migration: add new columns if they don't exist ──
    existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(jobs)")}

    new_columns = {
        "salary_min": "INTEGER",
        "salary_max": "INTEGER",
        "currency": "TEXT",
        "location": "TEXT",
        "remote_type": "TEXT",
        "job_type": "TEXT",
        "is_remote": "INTEGER DEFAULT 0",
        "is_part_time": "INTEGER DEFAULT 0",
        "candidate_url": "TEXT",
        "source_raw": "TEXT",    # raw JSON from the source (for debugging)
    }

    for col_name, col_type in new_columns.items():
        if col_name not in existing_cols:
            logger.info(f"Migrating DB: adding column {col_name}")
            cursor.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type}")

    conn.commit()
    conn.close()
    logger.info(f"Database ready at: {DB_PATH}")


def is_job_processed(system_id: str) -> bool:
    """Checks if a job with the given system_id already exists."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM jobs WHERE system_id = ?', (system_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def save_job(job_data: JobData) -> None:
    """Saves a job to the database with all available fields."""
    conn = _get_connection()
    cursor = conn.cursor()

    ingested_at = datetime.now().isoformat()

    try:
        cursor.execute('''
            INSERT INTO jobs
            (system_id, source, source_id, title, company, url, description,
             publication_date, ingested_at, salary_min, salary_max, currency,
             location, remote_type, job_type, is_remote, is_part_time,
             candidate_url, source_raw)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            job_data['system_id'],
            job_data['source'],
            job_data['source_id'],
            job_data['title'],
            job_data['company'],
            job_data['url'],
            job_data['description'],
            job_data.get('publication_date', ''),
            ingested_at,
            job_data.get('salary_min'),
            job_data.get('salary_max'),
            job_data.get('currency'),
            job_data.get('location'),
            job_data.get('remote_type'),
            job_data.get('job_type'),
            1 if job_data.get('is_remote') else 0,
            1 if job_data.get('is_part_time') else 0,
            job_data.get('candidate_url'),
            job_data.get('source_raw'),
        ))
        conn.commit()
    except sqlite3.IntegrityError:
        logger.debug(f"Job already exists, ignoring: {job_data.get('system_id')}")
        pass
    finally:
        conn.close()


def get_jobs_by_status(status: str) -> List[sqlite3.Row]:
    """Returns jobs with a specific status."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM jobs WHERE status = ?', (status,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_jobs_by_conditions(where_clause: str, params: tuple = ()) -> List[sqlite3.Row]:
    """Flexible query: pass a WHERE clause and params."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(f'SELECT * FROM jobs WHERE {where_clause}', params)
    rows = cursor.fetchall()
    conn.close()
    return rows


def update_job(system_id: str, **kwargs) -> None:
    """Generic update: pass column=value pairs."""
    if not kwargs:
        return
    conn = _get_connection()
    cursor = conn.cursor()
    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [system_id]
    try:
        cursor.execute(f'UPDATE jobs SET {set_clause} WHERE system_id = ?', values)
        conn.commit()
    except Exception as e:
        logger.error(f"Error updating {system_id}: {e}")
    finally:
        conn.close()


def get_stats() -> dict:
    """Returns summary stats about the jobs database."""
    conn = _get_connection()
    cursor = conn.cursor()
    stats = {}
    for row in cursor.execute('SELECT status, COUNT(*) as cnt FROM jobs GROUP BY status'):
        stats[row['status']] = row['cnt']
    stats['total'] = sum(stats.values()) if stats else 0
    conn.close()
    return stats


# Quick test when run directly
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    initialize_db()
    logger.info(f"Database initialized at: {DB_PATH}")

    # Show current stats
    print("Stats:", get_stats())

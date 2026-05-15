import logging
import sys
import time
import subprocess
import os

# Ensure execution/ is on path for imports
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "execution"))

from execution.ingest_remotive import run as ingest_remotive
from execution.ingest_arbeitnow import run as ingest_arbeitnow
from execution.scraper_custom import run as scraper_custom
from execution.heuristic_filter import run_filters as filter_run
from execution.llm_evaluator import run_evaluation as evaluator_run
from execution.generate_report import run_reporting as report_run
from execution.db_client import get_stats, initialize_db
from config_loader import get_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("PipelineOrchestrator")


def run_pipeline():
    """Executes the multi-source job hunting pipeline top-to-bottom."""
    logger.info("═══════════════════════════════════════════")
    logger.info("        STARTING JOB HUNT PIPELINE")
    logger.info("═══════════════════════════════════════════")

    config = get_config()
    sources = config.get("sources", {})

    try:
        # ── Phase 1: Ingestion (multiple sources) ──
        logger.info("\n─── STEP 1: INGESTION ───")

        if sources.get("remotive", {}).get("enabled", True):
            t0 = time.time()
            logger.info(">>> Source: Remotive API")
            ingest_remotive()
            logger.info(f"<<< Remotive done in {time.time() - t0:.1f}s")
        else:
            logger.info(">>> Remotive: disabled in config")

        if sources.get("arbeitnow", {}).get("enabled", True):
            t0 = time.time()
            logger.info(">>> Source: Arbeitnow API")
            ingest_arbeitnow()
            logger.info(f"<<< Arbeitnow done in {time.time() - t0:.1f}s")
        else:
            logger.info(">>> Arbeitnow: disabled in config")

        if sources.get("custom_scraper", {}).get("enabled", True):
            t0 = time.time()
            logger.info(">>> Source: Custom Scraper (Trabajo.org)")
            scraper_custom()
            logger.info(f"<<< Custom scraper done in {time.time() - t0:.1f}s")
        else:
            logger.info(">>> Custom scraper: disabled in config")

        if sources.get("linkedin", {}).get("enabled", True):
            t0 = time.time()
            logger.info(">>> Source: LinkedIn (Playwright)")
            lk_cfg = sources["linkedin"]
            keywords = ",".join(lk_cfg.get("keywords", ["cybersecurity"]))
            max_pages = lk_cfg.get("max_pages", 2)
            script_path = os.path.join(os.path.dirname(__file__), "execution", "ingest_linkedin.py")
            timeout_sec = min(30 * len(keywords.split(",")) * max_pages, 600)
            result = subprocess.run(
                [sys.executable, script_path, "--keywords", keywords, "--max-pages", str(max_pages)],
                capture_output=True, text=True, timeout=timeout_sec
            )
            if result.returncode == 0 or "Traceback" not in result.stderr:
                logger.info(f"LinkedIn OK: {result.stdout.strip().split(chr(10))[-1]}")
            else:
                logger.warning(f"LinkedIn stderr: {result.stderr[:300]}")
            logger.info(f"<<< LinkedIn done in {time.time() - t0:.1f}s")
        else:
            logger.info(">>> LinkedIn: disabled in config")

        # ── Phase 2: Heuristic Deterministic Filter ──
        logger.info("\n─── STEP 2: HEURISTIC FILTERING ───")
        t0 = time.time()
        filter_run()
        logger.info(f"<<< Filtering done in {time.time() - t0:.1f}s")

        # ── Phase 3: AI Probabilistic Evaluator ──
        logger.info(f"\n─── STEP 3: AI EVALUATION ({config.get('ai', {}).get('provider', 'gemini')}) ───")
        t0 = time.time()
        evaluator_run()
        logger.info(f"<<< AI eval done in {time.time() - t0:.1f}s")

        # ── Phase 4: Reporting ──
        logger.info("\n─── STEP 4: REPORTING ───")
        t0 = time.time()
        report_run()
        logger.info(f"<<< Reporting done in {time.time() - t0:.1f}s")

        # ── Summary ──
        stats = get_stats()
        logger.info("\n═══════════════════════════════════════════")
        logger.info("        PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("═══════════════════════════════════════════")
        logger.info(f"Database stats: {stats}")

        return stats

    except Exception as e:
        logger.error(f"Pipeline failed critically: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def run_ingestion_only():
    """Run only the ingestion phase (for faster daily runs)."""
    config = get_config()
    sources = config.get("sources", {})

    initialize_db()

    if sources.get("remotive", {}).get("enabled", True):
        ingest_remotive()
    if sources.get("arbeitnow", {}).get("enabled", True):
        ingest_arbeitnow()


if __name__ == "__main__":
    run_pipeline()

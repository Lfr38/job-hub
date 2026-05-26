#!/bin/bash
# Full job pipeline: all sources → filter → AI eval → email
set -e
cd /mnt/code/WorkResearch
source venv/bin/activate

echo "🤖 Job Pipeline — $(date '+%d/%m/%Y %H:%M')"
echo ""

# ── Load secrets from .env (non in git — password email, API keys) ──
if [ -f .env ]; then
    set -a; source .env; set +a
fi

# ── Step 1: Remotive API ──
echo "─── Step 1: Remotive API ───"
python -c "
import sys; sys.path.insert(0, 'execution')
from ingest_remotive import run as r; r()
" 2>&1 | grep -v "Starting\|Database ready\|^$" || true

echo ""

# ── Step 2: Arbeitnow API ──
echo "─── Step 2: Arbeitnow API ───"
python -c "
import sys; sys.path.insert(0, 'execution')
from ingest_arbeitnow import run as a; a()
" 2>&1 | grep -v "Starting\|Database ready\|^$" || true

echo ""

# ── Step 3: LinkedIn scrape (keyword e location dal config YAML) ──
echo "─── Step 3: LinkedIn Scrape ───"
timeout 300 python execution/ingest_linkedin.py \
  --max-jobs 8 --max-total 30 2>&1 || echo "⚠️ LinkedIn scrape non completato (timeout 300s)"

echo ""

# ── Step 4: Heuristic filter (su TUTTI i job nuovi) ──
echo "─── Step 4: Heuristic Filter ───"
python -c "
import sys; sys.path.insert(0, 'execution')
from heuristic_filter import run_filters; run_filters()
" 2>&1

echo ""

# ── Step 5: AI evaluation (su TUTTI i filtered_pass) ──
echo "─── Step 5: AI Evaluation ───"
python -c "
import sys; sys.path.insert(0, 'execution')
from llm_evaluator import run_evaluation; run_evaluation()
" 2>&1

echo ""

# ── Step 6: Email notification (password da .env) ──
echo "─── Step 6: Email Notification ───"
python execution/email_notifier.py 2>&1

echo ""
echo "✅ Pipeline completata — $(date '+%d/%m/%Y %H:%M')"

# Stats finali
python -c "
import sys; sys.path.insert(0, 'execution')
import sqlite3
conn = sqlite3.connect('.tmp/jobs.db')
aipass = conn.execute('SELECT COUNT(*) FROM jobs WHERE status=\"ai_pass\"').fetchone()[0]
total = conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
conn.close()
print(f'📊 DB: {total} job — ✅ AI Pass: {aipass}')
"

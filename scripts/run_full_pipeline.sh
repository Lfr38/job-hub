#!/bin/bash
# Full job pipeline: LinkedIn scrape → heuristic filter → AI evaluation
# Runs as no_agent cron job — output is sent to user verbatim.
# Silent when nothing new (watchdog pattern).

set -e
cd /mnt/code/WorkResearch
source venv/bin/activate

echo "🤖 Job Pipeline — $(date '+%d/%m/%Y %H:%M')"
echo ""

# ── Step 1: LinkedIn scrape ──
echo "─── Step 1: LinkedIn Scrape ───"
python execution/ingest_linkedin.py \
  --keywords "guardia giurata,cybersecurity,sicurezza informatica,vigilanza,portierato,soc analyst,junior security,IT security,penetration testing" \
  --locations "Brescia,Italy" \
  --max-jobs 12 2>&1

echo ""

# ── Step 2: Heuristic filter ──
echo "─── Step 2: Heuristic Filter ───"
python -c "
import sys; sys.path.insert(0, 'execution')
from heuristic_filter import run_filters; run_filters()
" 2>&1

echo ""

# ── Step 3: AI evaluation ──
echo "─── Step 3: AI Evaluation ───"
python -c "
import sys; sys.path.insert(0, 'execution')
from llm_evaluator import run_evaluation; run_evaluation()
" 2>&1

echo ""

# ── Summary ──
python -c "
import sys; sys.path.insert(0, 'execution')
import sqlite3
conn = sqlite3.connect('.tmp/jobs.db')
aipass = conn.execute('SELECT COUNT(*) FROM jobs WHERE status=\"ai_pass\"').fetchone()[0]
aireject = conn.execute('SELECT COUNT(*) FROM jobs WHERE status=\"ai_reject\"').fetchone()[0]
total = conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
print(f'📊 Totale DB: {total} — ✅ Pass: {aipass} — ❌ Reject: {aireject}')
conn.close()
"

echo ""
echo "✅ Pipeline completata"

# Job Search Pipeline (WorkResearch 🧠)

**Goal:** Automate discovery and evaluation of part-time, remote jobs matching Simone's profile (IT support → Cybersecurity, Python/AI development). Filter noise with heuristics + AI, deliver clean reports to Google Sheets and email.

## Architecture

```
run_pipeline.py  (orchestratore)
    │
    ├── Phase 1: INGESTION (multi-fonte)
    │   ├── Remotive API  → software-dev remote jobs
    │   └── Arbeitnow API → tech jobs (free, no key needed)
    │   (Future: TinyFish Agent → LinkedIn, Indeed)
    │
    ├── Phase 2: HEURISTIC FILTER (config-driven)
    │   ├── YAML config: job_search_config.yaml
    │   ├── Title matching (target_roles)
    │   ├── Part-time required check
    │   ├── Remote/WFH required check
    │   ├── Negative keywords (senior, lead, etc.)
    │   ├── Local Brescia jobs bonus
    │   └── Scoring → filtered_pass or filtered_reject
    │
    ├── Phase 3: AI EVALUATION (multi-provider)
    │   ├── Configurable: gemini | deepseek | openai | claude
    │   ├── Prompt tailored to Simone's profile
    │   ├── Score 0-100 + pros/cons/summary
    │   └── Threshold: >= 60 → ai_pass
    │
    └── Phase 4: REPORTING
        ├── Google Sheets (rich schema with salary, location, source)
        ├── Per-row append (no data loss on partial failure)
        └── DB status: new → filtered_pass → ai_pass → reported

```

## Key Files

| File | Description |
|------|-------------|
| `job_search_config.yaml` | All filters, keywords, AI provider, thresholds |
| `run_pipeline.py` | Orchestrator (ingest → filter → evaluate → report) |
| `execution/db_client.py` | SQLite DB with migration support + full schema |
| `execution/config_loader.py` | YAML config loader (shared by all scripts) |
| `execution/ingest_remotive.py` | Remotive API ingestion |
| `execution/ingest_arbeitnow.py` | Arbeitnow API ingestion |
| `execution/heuristic_filter.py` | Config-driven keyword/title/remote/PT filter |
| `execution/llm_evaluator.py` | Multi-provider AI evaluation (Gemini/DS/OAI/Claude) |
| `execution/generate_report.py` | Google Sheets reporting |

## Simone's Profile (for AI evaluation)

- Background: 3 years Help Desk IT support, Python automation, MySQL, networking
- Certs: Google Cybersecurity Professional, Google IT Support
- Skills: Python, Django, Node.js, Linux, AD, pfSense, networking
- Languages: Italian (native), English (B2)
- Seeking: Part-time, remote, entry-level/junior positions
- Areas: Cybersecurity, Python/AI development, IT support

## How to Run

```bash
# Full pipeline
python run_pipeline.py

# Ingestion only (faster daily runs)
python -c "from run_pipeline import run_ingestion_only; run_ingestion_only()"

# Single steps
python execution/ingest_remotive.py
python execution/ingest_arbeitnow.py
python execution/heuristic_filter.py
python execution/llm_evaluator.py
python execution/generate_report.py
```

## Configuration

Edit `job_search_config.yaml` to:
- Change AI provider (gemini → deepseek → claude → openai)
- Add/remove target roles and keywords
- Adjust scoring thresholds
- Enable/disable data sources
- Configure local Brescia job search

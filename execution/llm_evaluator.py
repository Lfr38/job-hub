import os
import json
import logging
import time
import re
from typing import List, Dict, Any, Optional, Tuple, Callable
from dotenv import load_dotenv
from db_client import _get_connection, update_job
from config_loader import get_config

import sqlite3  # ← FIX: needed for row_factory in get_jobs_to_evaluate()

load_dotenv()

logger = logging.getLogger(__name__)

# ── Rate Limit Handling ──

# Default token budgets per provider per minute (free tiers)
PROVIDER_LIMITS = {
    "groq": {"tpm": 6000, "model": "llama-3.1-8b-instant"},
    "gemini": {"tpm": 1_000_000},  # effectively unlimited
    "deepseek": {"tpm": 500_000},
    "openai": {"tpm": 200_000},
    "claude": {"tpm": 200_000},
}


def parse_retry_after(error_msg: str) -> Optional[float]:
    """Extract retry-after seconds from Groq 429 error messages."""
    # "Please try again in 160ms."
    m = re.search(r'try again in ([\d.]+)\s*(ms|s|milliseconds|seconds)', error_msg, re.IGNORECASE)
    if m:
        value = float(m.group(1))
        unit = m.group(2).lower()
        if unit in ("ms", "milliseconds"):
            return value / 1000.0
        return value
    return None


def call_with_retry(
    fn: Callable, job_title: str, max_retries: int = 5, base_delay: float = 5.0
) -> Optional[Dict[str, Any]]:
    """Call an evaluation function with exponential backoff on 429 errors."""
    import openai

    for attempt in range(max_retries + 1):
        try:
            return fn()
        except openai.RateLimitError as e:
            error_text = str(e)
            retry_in = parse_retry_after(error_text)

            if retry_in:
                wait = retry_in + 2.0  # add a small buffer
                logger.warning(
                    f"   ⏳ Rate limit per '{job_title}'. Attendo {wait:.1f}s "
                    f"(tentativo {attempt + 1}/{max_retries + 1})"
                )
                time.sleep(wait)
            else:
                # Exponential backoff
                wait = base_delay * (2 ** attempt)
                logger.warning(
                    f"   ⏳ Rate limit per '{job_title}'. Backoff {wait:.0f}s "
                    f"(tentativo {attempt + 1}/{max_retries + 1})"
                )
                time.sleep(wait)

        except Exception as e:
            # Non-rate-limit error — log and give up
            logger.error(f"   ❌ Errore per '{job_title}': {e}")
            return None

    logger.error(f"   ❌ Troppi tentativi per '{job_title}'. Salto.")
    return None

# ── AI Provider Registry ──


def get_jobs_to_evaluate() -> List[Dict[str, Any]]:
    """Retrieves jobs that passed the heuristic filter and haven't been evaluated."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT system_id, title, company, description, location,
               remote_type, job_type, is_remote, is_part_time,
               salary_min, salary_max, currency
        FROM jobs
        WHERE status = 'filtered_pass' AND llm_score = 0
    ''')
    rows = cursor.fetchall()
    conn.close()

    jobs = []
    for row in rows:
        jobs.append({
            "system_id": row["system_id"],
            "title": row["title"],
            "company": row["company"],
            "description": row["description"],
            "location": row["location"],
            "remote_type": row["remote_type"],
            "job_type": row["job_type"],
            "is_remote": bool(row["is_remote"]),
            "is_part_time": bool(row["is_part_time"]),
            "salary_min": row["salary_min"],
            "salary_max": row["salary_max"],
            "currency": row["currency"],
        })
    return jobs


def build_evaluation_prompt(job: Dict[str, Any]) -> str:
    """Builds the evaluation prompt based on Simone's profile."""
    salary_info = ""
    if job.get("salary_min") and job.get("salary_max"):
        sal_curr = job.get("currency", "$")
        salary_info = f"- Salary: {sal_curr}{job['salary_min']} - {sal_curr}{job['salary_max']}\n"
    elif job.get("salary_min"):
        sal_curr = job.get("currency", "$")
        salary_info = f"- Salary: {sal_curr}{job['salary_min']}\n"

    location_info = f"- Location: {job.get('location', 'Not specified')}\n"
    remote_info = f"- Remote: {'Yes' if job.get('is_remote') else 'Not specified'}\n"
    pt_info = f"- Part-time: {'Yes' if job.get('is_part_time') else 'Not specified'}\n"

    prompt = f"""You are a career coach evaluating job listings for Simone, an Italian IT professional.

**Simone's Profile:**
- Background: 3 years Help Desk IT support, Python automation, MySQL, networking
- Certifications: Google Cybersecurity & IT Support Professional
- Skills: Python, Django, Node.js, Linux, AD, pfSense
- Languages: Italian (native), English (B2)
- Seeking: Entry-level / junior — IT, Cybersecurity, AI/Python
- Open to: part-time (ideal) or full-time

**Job to evaluate:**
Title: {job['title']}
Company: {job['company']}
{salary_info}{location_info}{remote_info}{pt_info}
Description (truncated):
{job['description'][:1200]}

**CRITICAL RULES — Location & Role Type:**

Rule A — Portierato/Vigilanza (local security/porter roles):
If the title contains "portierato", "vigilanza", "guardia", "portiere", "custode", "sorveglianza":
  → The location MUST be Brescia or nearby (provincia di Brescia, BS area).
  → If NOT Brescia province, set score=0 with fit_reason="Ruolo locale non IT — fuori area Brescia".

Rule B — IT / Cybersecurity / Technical roles (everything else):
  → Remote across all Italy or abroad is IDEAL.
  → On-site in Italy is acceptable but scores lower on remote criterion.
  → On-site abroad is penalized unless exceptional.

**Scoring (0-100 total):**

1. Career match (0-20): Cybersecurity/AI/Python dev → 15-20, IT Support → 8-14, other → 0-7
2. Entry-level friendly (0-15): truly junior/trainee? Score accordingly.
3. Remote work (0-15): full remote → 12-15, hybrid Italy → 8-11, on-site Italy → 4-7, on-site abroad → 0-3
4. Part-time factor — SETS THE CEILING:
   Clearly part-time (+30 to +35) → can reach 90-100
   Not specified (+15 to +20) → realistic max 70-75
   Clearly full-time (+5 to +10) → realistic max 55-65
5. Language bonus (0-10): Italian or English → bonus
6. Red flags: subtract 0-10 if ambiguous/scammy/unrealistic

**REALISTIC MAXIMUMS:**
- Part-time, strong criteria → 90-100
- Part-time not specified, strong → 65-75
- Full-time, strong → 55-65
- Poor match → 0-40

Return ONLY a valid JSON object:
{{
  "score": <integer 0-100>,
  "pros": ["list of 1-3 specific pros for Simone"],
  "cons": ["list of 1-3 specific cons for Simone"],
  "summary": "<1-sentence summary>",
  "fit_reason": "<why this fits Simone or doesn't>"
}}
"""

    return prompt


def evaluate_with_gemini(client: Any, job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Evaluate using Google Gemini."""
    from google import genai
    from google.genai import types

    prompt = build_evaluation_prompt(job)
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        if response.text:
            return json.loads(response.text)
        return None
    except Exception as e:
        logger.error(f"Gemini evaluation failed for {job['system_id']}: {e}")
        return None


def evaluate_with_deepseek(client: Any, job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Evaluate using DeepSeek."""
    import openai
    prompt = build_evaluation_prompt(job)
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a career coach evaluating job listings. Return ONLY valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        if response.choices:
            return json.loads(response.choices[0].message.content)
        return None
    except Exception as e:
        logger.error(f"DeepSeek evaluation failed for {job['system_id']}: {e}")
        return None


def evaluate_with_openai(client: Any, job: Dict[str, Any], model: str = "gpt-4o-mini") -> Optional[Dict[str, Any]]:
    """Evaluate using OpenAI-compatible API with rate limit retry."""
    prompt = build_evaluation_prompt(job)
    
    def _call():
        return client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a career coach evaluating job listings. Return ONLY valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
    
    result = call_with_retry(_call, job['title'])
    if result and result.choices:
        try:
            return json.loads(result.choices[0].message.content)
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"   ❌ JSON parse error per '{job['title']}': {e}")
            return None
    return None


def evaluate_with_groq(client: Any, job: Dict[str, Any], model: str = "llama-3.1-8b-instant") -> Optional[Dict[str, Any]]:
    """Evaluate using Groq with rate limit handling and pacing between jobs."""
    prompt = build_evaluation_prompt(job)
    
    # Stima token per pacing: ~4 chars = 1 token
    estimated_tokens = len(prompt) // 4
    provider_limit = PROVIDER_LIMITS.get("groq", {}).get("tpm", 6000)
    min_pause = max(15.0, (estimated_tokens / provider_limit) * 60)
    
    logger.info(f"   Groq: ~{estimated_tokens} token stimati, pausa {min_pause:.0f}s tra job")
    
    def _call():
        return client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a career coach evaluating job listings. Return ONLY valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
    
    result = call_with_retry(_call, job['title'])
    if result and result.choices:
        try:
            parsed = json.loads(result.choices[0].message.content)
            # Pacing prima di tornare — il prossimo job aspetterà
            logger.info(f"   ⏱ Pacing {min_pause:.0f}s prima del prossimo job Groq...")
            time.sleep(min_pause)
            return parsed
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"   ❌ JSON parse error per '{job['title']}': {e}")
            return None
    return None


def evaluate_with_claude(client: Any, job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Evaluate using Anthropic Claude."""
    prompt = build_evaluation_prompt(job)
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system="You are a career coach evaluating job listings. Return ONLY valid JSON without markdown formatting.",
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        # Strip markdown code blocks if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except Exception as e:
        logger.error(f"Claude evaluation failed for {job['system_id']}: {e}")
        return None


def get_evaluator(provider: str):
    """Returns the appropriate evaluation function and client for the chosen provider."""
    provider = provider.lower()

    if provider == "gemini":
        from google import genai
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("GOOGLE_API_KEY not set in .env")
            return None, None
        client = genai.Client(api_key=api_key)
        return evaluate_with_gemini, client

    elif provider == "deepseek":
        import openai
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            logger.error("DEEPSEEK_API_KEY not set in .env")
            return None, None
        client = openai.OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        return evaluate_with_deepseek, client

    elif provider == "groq":
        import openai
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            logger.error("GROQ_API_KEY not set in .env")
            return None, None
        client = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        return evaluate_with_groq, client

    elif provider == "openai":
        import openai
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY not set in .env")
            return None, None
        client = openai.OpenAI(api_key=api_key)
        return evaluate_with_openai, client

    elif provider == "claude":
        from anthropic import Anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error("ANTHROPIC_API_KEY not set in .env")
            return None, None
        client = Anthropic(api_key=api_key)
        return evaluate_with_claude, client

    else:
        logger.error(f"Unknown AI provider: {provider}. Falling back to Gemini.")
        return get_evaluator("gemini")


def update_job_evaluation(system_id: str, evaluation: Dict[str, Any]) -> None:
    """Updates the database with the LLM's evaluation."""
    score = evaluation.get('score', 0)
    eval_text = json.dumps(evaluation)
    status = "ai_pass" if score >= 60 else "ai_reject"

    update_job(system_id, llm_score=score, llm_evaluation=eval_text, status=status)


def run_evaluation() -> None:
    """Main execution block for LLM evaluation."""
    config = get_config()
    provider = config.get("ai", {}).get("provider", "gemini")
    logger.info(f"Starting LLM evaluation phase (provider: {provider})...")

    # Get evaluator
    evaluate_fn, client = get_evaluator(provider)
    if not evaluate_fn:
        logger.error(f"Could not initialize AI provider '{provider}'. Check your .env file.")
        return

    jobs = get_jobs_to_evaluate()

    if not jobs:
        logger.info("No jobs waiting for AI evaluation.")
        return

    logger.info(f"Found {len(jobs)} jobs to evaluate with {provider}.")

    processed = 0
    passed = 0

    for job in jobs:
        logger.info(f"Evaluating: {job['title']} at {job['company']}")
        evaluation = evaluate_fn(client, job)

        if evaluation:
            update_job_evaluation(job['system_id'], evaluation)
            processed += 1
            if evaluation.get('score', 0) >= 60:
                passed += 1
            logger.info(f"  → Score: {evaluation.get('score')}/100 - {'PASS' if evaluation.get('score', 0) >= 60 else 'REJECT'}")
        else:
            logger.warning(f"  → Evaluation failed for {job['system_id']}")

    logger.info(f"Evaluation complete. Processed: {processed}. Passed AI filter: {passed}.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    run_evaluation()

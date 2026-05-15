#!/usr/bin/env python3
"""Send email notification with top AI-passed jobs via SMTP."""

import os
import sys
import sqlite3
import smtplib
import ssl
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from config_loader import load_config
from notify_new_jobs import get_new_passed_jobs, MIN_SCORE, LOOKBACK_HOURS

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '.tmp', 'jobs.db')

# Email config
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
EMAIL_FROM = "hermnexus@gmail.com"
EMAIL_TO = "simone.ronchi01@outlook.com"
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "CHANGE_ME")
DASHBOARD_URL = "http://192.168.2.102:8080"


def build_email_body(jobs):
    """Build HTML email body with top 5 jobs and summary."""
    now = datetime.now()
    date_str = now.strftime("%d/%m/%Y")
    time_str = now.strftime("%H:%M")

    # Stats
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    aipass = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='ai_pass'").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='filtered_pass'").fetchone()[0]
    rejected = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='ai_reject'").fetchone()[0]
    conn.close()

    # Build HTML
    html = f"""
    <html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0d1117;color:#e6edf3;padding:20px">
    <div style="max-width:600px;margin:0 auto;background:#161b22;border:1px solid #30363d;border-radius:12px;padding:24px">

    <h2 style="color:#58a6ff;margin:0 0 4px">🧑‍💻 Job Hub — Report</h2>
    <p style="color:#8b949e;font-size:13px;margin:0 0 20px">{date_str} alle {time_str}</p>

    <div style="display:flex;gap:8px;margin-bottom:20px">
      <div style="flex:1;text-align:center;background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:10px">
        <div style="font-size:22px;font-weight:700;color:#58a6ff">{total}</div>
        <div style="font-size:11px;color:#8b949e">Totale DB</div>
      </div>
      <div style="flex:1;text-align:center;background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:10px">
        <div style="font-size:22px;font-weight:700;color:#3fb950">{aipass}</div>
        <div style="font-size:11px;color:#8b949e">AI Pass</div>
      </div>
      <div style="flex:1;text-align:center;background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:10px">
        <div style="font-size:22px;font-weight:700;color:#d29922">{pending}</div>
        <div style="font-size:11px;color:#8b949e">In attesa</div>
      </div>
      <div style="flex:1;text-align:center;background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:10px">
        <div style="font-size:22px;font-weight:700;color:#f85149">{rejected}</div>
        <div style="font-size:11px;color:#8b949e">Rifiutati</div>
      </div>
    </div>
    """

    if jobs:
        html += '<h3 style="color:#e6edf3;margin:0 0 12px">🏆 Top 5 — Nuovi AI Pass</h3>'
        for j in jobs[:5]:
            score = j["llm_score"]
            color = "#3fb950" if score >= 70 else "#d29922"
            ev = {}
            if j["llm_evaluation"]:
                try:
                    ev = json.loads(j["llm_evaluation"])
                except:
                    pass
            summary = (ev.get("summary") or "")[:120]

            html += f"""
            <div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:12px;margin-bottom:8px">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <div>
                  <div style="font-weight:600;font-size:14px">{j['title'][:70]}</div>
                  <div style="color:#8b949e;font-size:12px">{j['company'][:40]} · {j['location'] or 'N/A'}</div>
                </div>
                <div style="font-size:18px;font-weight:700;color:{color}">{score}</div>
              </div>
              {f'<div style="color:#8b949e;font-size:12px;margin-top:4px">{summary}</div>' if summary else ''}
            </div>
            """

    html += f"""
    <div style="margin-top:20px;text-align:center">
      <a href="{DASHBOARD_URL}?status=ai_pass" style="display:inline-block;padding:10px 24px;border-radius:8px;background:#238636;color:#fff;text-decoration:none;font-size:14px;font-weight:600">
        📊 Vedi tutti su Dashboard
      </a>
    </div>

    <p style="color:#8b949e;font-size:11px;margin-top:20px;text-align:center">
      Job Hub · hermnexus@gmail.com · <a href="{DASHBOARD_URL}" style="color:#58a6ff">Dashboard</a>
    </p>
    </div></body></html>
    """
    return html


def send_email(subject, html_body):
    """Send HTML email via SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Job Hub <{EMAIL_FROM}>"
    msg["To"] = EMAIL_TO

    part = MIMEText(html_body, "html")
    msg.attach(part)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context, timeout=15) as server:
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())

    print(f"✅ Email inviata: {subject}")


def main():
    jobs = get_new_passed_jobs()

    now = datetime.now()
    date_str = now.strftime("%d/%m/%Y")
    time_str = now.strftime("%H:%M")

    if not jobs:
        # Empty report — still send a brief one if wanted, or stay silent
        print("Nessun nuovo AI Pass. Nessuna email inviata.")
        return

    subject = f"Lavori trovati {date_str} {time_str}"
    body = build_email_body(jobs)
    send_email(subject, body)


if __name__ == "__main__":
    main()

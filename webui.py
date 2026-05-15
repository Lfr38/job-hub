"""Job Hub Web UI — English, responsive, with hide/cleanup actions."""

import os
import sys
import json
import sqlite3
import subprocess
from datetime import datetime

import yaml
from flask import Flask, render_template_string, request, jsonify, redirect, url_for

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from execution.db_client import DB_PATH, _get_connection, update_job

app = Flask(__name__)

# ── TEMPLATE ──

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Job Hub — Simone</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0d1117;--bg-card:#161b22;--bg-hover:#1c2333;--border:#30363d;
  --text:#e6edf3;--text-dim:#8b949e;--accent:#58a6ff;--green:#3fb950;
  --red:#f85149;--yellow:#d29922;--orange:#f0883e;--purple:#bc8cff
}
body{
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  background:var(--bg);color:var(--text);padding:12px;min-height:100vh
}
.container{max-width:1400px;margin:0 auto}

/* Header */
.header{
  display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;
  gap:8px;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid var(--border)
}
.header h1{font-size:20px;font-weight:700}
.header h1 span{color:var(--accent)}
.header .subtitle{color:var(--text-dim);font-size:12px;width:100%}
.header-actions{display:flex;gap:4px;flex-wrap:wrap}
.action-btn{padding:5px 10px;border-radius:6px;text-decoration:none;font-size:11px;font-weight:600;white-space:nowrap}
.action-btn.green{border:1px solid var(--green);background:rgba(63,185,80,0.1);color:var(--green)}
.action-btn.purple{border:1px solid var(--purple);background:rgba(188,140,255,0.1);color:var(--purple)}
.action-btn.orange{border:1px solid var(--orange);background:rgba(240,136,62,0.1);color:var(--orange)}
.action-btn:hover{opacity:.8}

/* Stats */
.stats{
  display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));
  gap:8px;margin-bottom:16px
}
.stat-card{
  background:var(--bg-card);border:1px solid var(--border);
  border-radius:8px;padding:10px;text-align:center
}
.stat-card .number{font-size:22px;font-weight:700}
.stat-card .label{font-size:10px;color:var(--text-dim);margin-top:2px}
.stat-card.total .number{color:var(--accent)}
.stat-card.green .number{color:var(--green)}
.stat-card.red .number{color:var(--red)}
.stat-card.yellow .number{color:var(--yellow)}
.stat-card.purple .number{color:var(--purple)}
.stat-card.orange .number{color:var(--orange)}

/* Filters */
.filters{display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap}
.filters a{
  padding:5px 12px;border-radius:16px;font-size:12px;
  text-decoration:none;color:var(--text-dim);
  background:var(--bg-card);border:1px solid var(--border);transition:all .2s;
  white-space:nowrap
}
.filters a:hover{background:var(--bg-hover);color:var(--text)}
.filters a.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.filters .count{font-size:10px;opacity:.7;margin-left:3px}

/* Search */
.search-bar{display:flex;gap:6px;margin-bottom:12px}
.search-bar input{
  flex:1;padding:8px 12px;border-radius:6px;border:1px solid var(--border);
  background:var(--bg-card);color:var(--text);font-size:14px;min-width:0
}
.search-bar button{
  padding:8px 14px;border-radius:6px;border:1px solid var(--accent);
  background:var(--accent);color:#fff;cursor:pointer;font-size:13px;white-space:nowrap
}

/* Job cards (mobile) + table (desktop) */
.job-list{display:flex;flex-direction:column;gap:8px}
.job-card{
  background:var(--bg-card);border:1px solid var(--border);
  border-radius:10px;padding:12px;transition:background .2s
}
.job-card:active{background:var(--bg-hover)}
.job-title-wrap{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.job-title{font-weight:600;font-size:14px;color:var(--text);line-height:1.3;flex:1}
.job-company{color:var(--text-dim);font-size:12px;margin-top:2px}
.job-meta{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;align-items:center}
.job-source{display:inline-block;padding:1px 7px;border-radius:8px;font-size:10px;font-weight:600}
.job-source.linkedin{background:#0a66c2;color:#fff}
.job-source.arbeitnow{background:#1a5c3a;color:var(--green)}
.job-source.remotive{background:#1a3a5c;color:var(--accent)}
.badge{
  display:inline-block;padding:2px 8px;border-radius:8px;
  font-size:10px;font-weight:600;white-space:nowrap
}
.badge.pass{background:#1a3a2a;color:var(--green)}
.badge.reject{background:#3a1a1a;color:var(--red)}
.badge.new{background:#2a2a1a;color:var(--yellow)}
.badge.reported{background:#1a1a3a;color:var(--purple)}
.badge.applied{background:#1a3a3a;color:var(--orange)}
.badge.hidden{background:#1a1a1a;color:#555}

.score-high{color:var(--green)}
.score-mid{color:var(--yellow)}
.score-low{color:var(--red)}

.score-bar-wrap{display:inline-flex;align-items:center;gap:4px}
.score-bar{
  display:inline-block;height:5px;border-radius:3px;
  background:var(--border);width:50px
}
.score-bar .fill{height:100%;border-radius:3px;background:linear-gradient(90deg,var(--red),var(--yellow),var(--green))}

.job-actions{display:flex;gap:4px;margin-top:8px}
.job-actions a,.job-actions button{
  text-decoration:none;font-size:13px;padding:4px 8px;
  border-radius:6px;border:none;cursor:pointer;background:transparent;color:var(--text-dim)
}
.job-actions a:hover,.job-actions button:hover{background:var(--bg-hover);color:var(--text)}
.job-actions .btn-apply{color:var(--green)}
.job-actions .btn-dismiss{color:var(--red)}
.job-actions .btn-trash{color:var(--text-dim)}

/* Bulk actions */
.bulk-actions{
  display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap
}
.bulk-btn{
  padding:5px 12px;border-radius:6px;border:1px solid var(--border);
  background:var(--bg-card);color:var(--text-dim);cursor:pointer;
  font-size:11px;transition:all .2s;white-space:nowrap
}
.bulk-btn:hover{background:var(--bg-hover);color:var(--text)}
.bulk-btn.danger{color:var(--red);border-color:var(--red)}

/* Pagination */
.pagination{display:flex;justify-content:center;gap:6px;margin-top:16px;flex-wrap:wrap}
.pagination a{
  padding:5px 10px;border-radius:4px;text-decoration:none;
  font-size:13px;color:var(--text);background:var(--bg-card);
  border:1px solid var(--border)
}
.pagination a.active{background:var(--accent);border-color:var(--accent);color:#fff}

/* Empty state */
.empty{text-align:center;padding:40px 20px;color:var(--text-dim)}
.empty .icon{font-size:40px;margin-bottom:8px}
.empty h3{font-size:16px;margin-bottom:4px}

/* Modal */
.modal-overlay{
  display:none;position:fixed;top:0;left:0;width:100%;height:100%;
  background:rgba(0,0,0,.7);z-index:999;align-items:center;justify-content:center
}
.modal-box{
  background:var(--bg-card);border:1px solid var(--border);border-radius:12px;
  max-width:600px;width:92%;max-height:85vh;overflow-y:auto;padding:20px;margin:0 auto
}
.modal-header{display:flex;justify-content:space-between;margin-bottom:12px}
.modal-header h3{font-size:16px}
.modal-close{background:none;border:none;color:var(--text-dim);font-size:22px;cursor:pointer}
.modal-body{font-size:13px;line-height:1.5}
.modal-body strong{color:var(--text)}

/* Toast */
.toast{
  position:fixed;bottom:16px;left:50%;transform:translateX(-50%);
  padding:10px 20px;border-radius:8px;background:var(--bg-card);
  border:1px solid var(--border);color:var(--text);font-size:13px;
  display:none;z-index:1000;box-shadow:0 4px 12px rgba(0,0,0,.3);
  max-width:90%;text-align:center
}
.toast.show{display:block;animation:fadeIn .3s}
@keyframes fadeIn{from{opacity:0;transform:translateX(-50%) translateY(10px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}

/* Desktop table */
@media(min-width:769px){
  .job-list{display:none}
  .job-table{width:100%;border-collapse:collapse;display:table}
  .job-table th{
    text-align:left;padding:8px 10px;font-size:11px;text-transform:uppercase;
    letter-spacing:.5px;color:var(--text-dim);border-bottom:1px solid var(--border);
    cursor:pointer;user-select:none
  }
  .job-table td{padding:10px;font-size:13px;border-bottom:1px solid var(--border);vertical-align:middle}
  .job-table tr:hover td{background:var(--bg-hover)}
}
@media(max-width:768px){
  .job-table{display:none}
  .stats{grid-template-columns:repeat(3,1fr)}
  .header h1{font-size:18px}
  .header-actions{gap:4px}
  .stat-card .number{font-size:18px}
  body{padding:8px}
}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <h1>🧑‍💻 Job <span>Hub</span></h1>
      <div class="subtitle">Filtered for Simone · Updated {{ now }}</div>
    </div>
    <div class="header-actions">
      <span style="font-size:11px;color:var(--text-dim);margin-right:4px;align-self:center">AI: {{ ai_provider }}</span>
      <a href="{{ url_for('run_pipeline_web') }}" class="action-btn green" onclick="return confirm('Run full pipeline? (LinkedIn scrape → filter → AI eval)')">🔄 Pipeline</a>
      <a href="{{ url_for('run_ai_web') }}" class="action-btn purple" onclick="return confirm('Run AI evaluation on pending jobs?')">🤖 AI Eval</a>
      <a href="{{ url_for('dashboard') }}" style="color:var(--accent);font-size:16px;text-decoration:none;padding:4px">⟳</a>
    </div>
  </div>

  <!-- Stats -->
  <div class="stats">
    {% for s in stats %}
    <div class="stat-card {{ s.class }}">
      <div class="number">{{ s.count }}</div>
      <div class="label">{{ s.label }}</div>
    </div>
    {% endfor %}
  </div>

  <!-- Bulk actions -->
  <div class="bulk-actions">
    <button class="bulk-btn" onclick="hideAll('ai_reject')">🗑️ Hide all AI Rejected</button>
    <button class="bulk-btn" onclick="hideAll('filtered_reject')">🗑️ Hide all Blocked</button>
    <button class="bulk-btn" onclick="hideAll('dismissed')">🗑️ Hide all Dismissed</button>
  </div>

  <!-- Filters -->
  <div class="filters">
    {% for f in filters %}
    <a href="{{ f.url }}" class="{% if f.active %}active{% endif %}">
      {{ f.label }} <span class="count">({{ f.count }})</span>
    </a>
    {% endfor %}
    <a href="{{ url_for('dashboard', status='today') }}" class="{% if current_status == 'today' %}active{% endif %}" style="border-color:var(--yellow)">📅 Today</a>
  </div>

  <!-- Search -->
  <form class="search-bar" method="GET" action="{{ url_for('dashboard') }}">
    <input type="hidden" name="status" value="{{ current_status }}">
    <input type="text" name="search" value="{{ search_query }}" placeholder="Search title, company, keyword…">
    <button type="submit">🔍 Search</button>
  </form>

  <!-- DESKTOP TABLE -->
  {% if jobs %}
  <table class="job-table">
    <thead><tr>
      <th>Title</th><th>Source</th><th>Heur</th><th>AI</th><th>Status</th><th>Actions</th>
    </tr></thead>
    <tbody>
    {% for j in jobs %}
    <tr>
      <td>
        <div class="job-title">{{ j.title[:70] }}</div>
        <div class="job-company">{{ j.company[:40] }}</div>
      </td>
      <td><span class="job-source {{ j.source }}">{{ j.source }}</span></td>
      <td>{% if j.heuristic_score %}<span class="{% if j.heuristic_score>=40 %}score-high{% elif j.heuristic_score>=20 %}score-mid{% else %}score-low{% endif %}">{{ j.heuristic_score }}</span>{% else %}<span class="score-low">—</span>{% endif %}</td>
      <td>
        {% if j.llm_score %}
        <div class="score-bar-wrap">
          <div class="score-bar"><div class="fill" style="width:{{ j.llm_score }}%"></div></div>
          <span class="{% if j.llm_score>=60 %}score-high{% elif j.llm_score>=40 %}score-mid{% else %}score-low{% endif %}">{{ j.llm_score }}</span>
        </div>
        {% else %}<span class="score-low">—</span>{% endif %}
      </td>
      <td>
        <span class="badge {{ j.badge_class }}">{{ j.status_label }}</span>
        {% if j.is_remote %}<span style="font-size:11px;color:var(--accent);margin-left:2px">🌍</span>{% endif %}
        {% if j.is_part_time %}<span style="font-size:11px;color:var(--yellow);margin-left:2px">⏳</span>{% endif %}
      </td>
      <td style="white-space:nowrap">
        <a href="{{ j.url }}" target="_blank" title="Open">🔗</a>
        {% if j.status in ('ai_pass', 'ai_reject', 'filtered_pass', 'new') %}
        <a href="#" onclick="mark('{{ j.system_id }}','applied')" class="btn-apply" title="Applied">📩</a>
        <a href="#" onclick="mark('{{ j.system_id }}','dismissed')" class="btn-dismiss" title="Dismiss">✕</a>
        {% endif %}
        <a href="#" onclick="mark('{{ j.system_id }}','hidden')" title="Hide permanently">🗑️</a>
        {% if j.llm_evaluation %}<a href="#" onclick="showEval('{{ j.system_id }}')" title="AI eval">📊</a>{% endif %}
      </td>
    </tr>
    {% endfor %}
    </tbody>
  </table>

  <!-- MOBILE CARDS -->
  <div class="job-list">
    {% for j in jobs %}
    <div class="job-card">
      <div class="job-title-wrap">
        <div>
          <div class="job-title">{{ j.title[:80] }}</div>
          <div class="job-company">{{ j.company[:50] }}</div>
        </div>
        <span class="badge {{ j.badge_class }}" style="flex-shrink:0">{{ j.status_label }}</span>
      </div>
      <div class="job-meta">
        <span class="job-source {{ j.source }}">{{ j.source }}</span>
        {% if j.heuristic_score %}<span class="{% if j.heuristic_score>=40 %}score-high{% elif j.heuristic_score>=20 %}score-mid{% else %}score-low{% endif %}" style="font-size:11px">H:{{ j.heuristic_score }}</span>{% endif %}
        {% if j.llm_score %}
        <div class="score-bar-wrap">
          <div class="score-bar"><div class="fill" style="width:{{ j.llm_score }}%"></div></div>
          <span class="{% if j.llm_score>=60 %}score-high{% elif j.llm_score>=40 %}score-mid{% else %}score-low{% endif %}" style="font-size:11px">{{ j.llm_score }}</span>
        </div>
        {% endif %}
        {% if j.is_remote %}<span style="font-size:12px">🌍</span>{% endif %}
        {% if j.is_part_time %}<span style="font-size:12px">⏳</span>{% endif %}
      </div>
      <div class="job-actions">
        <a href="{{ j.url }}" target="_blank">🔗 Open</a>
        {% if j.status in ('ai_pass', 'ai_reject', 'filtered_pass', 'new') %}
        <a href="#" onclick="event.stopPropagation();mark('{{ j.system_id }}','applied')" class="btn-apply">📩 Apply</a>
        <a href="#" onclick="event.stopPropagation();mark('{{ j.system_id }}','dismissed')" class="btn-dismiss">✕ Dismiss</a>
        {% endif %}
        <a href="#" onclick="event.stopPropagation();mark('{{ j.system_id }}','hidden')" class="btn-trash">🗑️</a>
        {% if j.llm_evaluation %}<a href="#" onclick="event.stopPropagation();showEval('{{ j.system_id }}')">📊 Eval</a>{% endif %}
      </div>
    </div>
    {% endfor %}
  </div>

  <!-- Pagination -->
  {% if total_pages > 1 %}
  <div class="pagination">
    {% for p in range(1, total_pages + 1) %}
    <a href="{{ url_for('dashboard', status=current_status, search=search_query, page=p) }}" class="{% if p == page %}active{% endif %}">{{ p }}</a>
    {% endfor %}
  </div>
  {% endif %}

  {% else %}
  <div class="empty">
    <div class="icon">🔍</div>
    <h3>No results</h3>
    <p>No jobs match your current filters.</p>
  </div>
  {% endif %}
</div>

<!-- Modal -->
<div class="modal-overlay" id="evalModal">
  <div class="modal-box">
    <div class="modal-header">
      <h3>🤖 AI Evaluation</h3>
      <button class="modal-close" onclick="closeEval()">✕</button>
    </div>
    <div class="modal-body" id="evalContent"></div>
  </div>
</div>

<!-- Toast -->
<div class="toast" id="toast"></div>

<script>
function mark(id, action) {
  fetch('/api/mark', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({system_id: id, status: action})
  })
  .then(r => r.json())
  .then(d => {
    showToast(d.message);
    if(d.success) setTimeout(() => location.reload(), 600);
  });
}

function hideAll(status) {
  const labels = {'ai_reject':'AI Rejected','filtered_reject':'Blocked','dismissed':'Dismissed'};
  if(!confirm(`Hide all "${labels[status] || status}" jobs? They won't appear anymore but stay in DB to avoid duplicates.`)) return;
  fetch('/api/hide-all', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({status: status})
  })
  .then(r => r.json())
  .then(d => {
    showToast(d.message);
    if(d.success) setTimeout(() => location.reload(), 600);
  });
}

function showEval(id) {
  fetch('/api/eval/' + id)
  .then(r => r.json())
  .then(d => {
    if(d.error) { showToast(d.error); return; }
    let html = '';
    if(d.eval) {
      const e = d.eval;
      html = `
        <p><strong>Score:</strong> <span style="color:${e.score >= 60 ? 'var(--green)' : 'var(--red)'}">${e.score}/100</span></p>
        <p><strong>Summary:</strong> ${e.summary || 'N/A'}</p>
        <p><strong>Fit:</strong> ${e.fit_reason || 'N/A'}</p>
        <p><strong>Pros:</strong></p><ul>${(e.pros||[]).map(p => '<li>'+p+'</li>').join('')}</ul>
        <p><strong>Cons:</strong></p><ul>${(e.cons||[]).map(c => '<li>'+c+'</li>').join('')}</ul>
      `;
    } else {
      html = '<p>No AI evaluation available.</p>';
    }
    document.getElementById('evalContent').innerHTML = html;
    document.getElementById('evalModal').style.display = 'flex';
  });
}

function closeEval() {
  document.getElementById('evalModal').style.display = 'none';
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2000);
}

document.getElementById('evalModal').addEventListener('click', function(e) {
  if(e.target === this) closeEval();
});
</script>
</body>
</html>"""


# ── HELPERS ──

STATUS_LABELS = {
    "ai_pass": "✅ Pass",
    "ai_reject": "❌ Reject",
    "filtered_pass": "⏳ Pending AI",
    "filtered_reject": "🚫 Blocked",
    "reported": "📋 Reported",
    "applied": "📩 Applied",
    "dismissed": "✕ Dismissed",
    "new": "🆕 New",
    "hidden": "⬜ Hidden",
}

BADGE_CLASSES = {
    "ai_pass": "pass", "ai_reject": "reject", "filtered_pass": "new",
    "filtered_reject": "reject", "reported": "reported", "applied": "applied",
    "dismissed": "reject", "new": "new", "hidden": "hidden",
}


def get_stats():
    conn = _get_connection()
    cursor = conn.cursor()
    rows = cursor.execute("SELECT status, COUNT(*) as cnt FROM jobs WHERE status != 'hidden' GROUP BY status").fetchall()
    stats = {r["status"]: r["cnt"] for r in rows}
    conn.close()

    items = [
        {"label": "Total", "count": sum(stats.values()), "class": "total", "key": ""},
        {"label": "Passed", "count": stats.get("ai_pass", 0), "class": "green", "key": "ai_pass"},
        {"label": "Pending AI", "count": stats.get("filtered_pass", 0), "class": "yellow", "key": "filtered_pass"},
        {"label": "AI Reject", "count": stats.get("ai_reject", 0), "class": "red", "key": "ai_reject"},
        {"label": "Blocked", "count": stats.get("filtered_reject", 0), "class": "red", "key": "filtered_reject"},
        {"label": "Applied", "count": stats.get("applied", 0), "class": "orange", "key": "applied"},
    ]
    return items, stats


def get_filter_links(current_status, search_query, stats):
    filters = [
        {"label": "All", "key": "", "url": url_for('dashboard')},
        {"label": "AI Pass", "key": "ai_pass", "url": url_for('dashboard', status='ai_pass')},
        {"label": "Pending AI", "key": "filtered_pass", "url": url_for('dashboard', status='filtered_pass')},
        {"label": "AI Reject", "key": "ai_reject", "url": url_for('dashboard', status='ai_reject')},
        {"label": "Blocked", "key": "filtered_reject", "url": url_for('dashboard', status='filtered_reject')},
        {"label": "Dismissed", "key": "dismissed", "url": url_for('dashboard', status='dismissed')},
        {"label": "Applied", "key": "applied", "url": url_for('dashboard', status='applied')},
    ]
    for f in filters:
        f["count"] = stats.get(f["key"], 0) if f["key"] else sum(stats.values())
        f["active"] = f["key"] == current_status
    return filters


# ── ROUTES ──

@app.route('/')
def dashboard():
    status_filter = request.args.get('status', '')
    search_query = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 30
    offset = (page - 1) * per_page

    conn = _get_connection()
    cursor = conn.cursor()

    where = ["status != 'hidden'"]
    params = []
    if status_filter == 'today':
        where.append("date(ingested_at) = date('now')")
    elif status_filter:
        where.append("status = ?")
        params.append(status_filter)
    if search_query:
        where.append("(title LIKE ? OR company LIKE ? OR description LIKE ?)")
        like = f"%{search_query}%"
        params.extend([like, like, like])

    where_clause = " AND ".join(where)

    cursor.execute(f'SELECT COUNT(*) FROM jobs WHERE {where_clause}', params)
    total = cursor.fetchone()[0]
    total_pages = max(1, (total + per_page - 1) // per_page)

    cursor.execute(f'''
        SELECT system_id, title, company, source, url, status,
               heuristic_score, llm_score, llm_evaluation,
               is_remote, is_part_time, ingested_at
        FROM jobs
        WHERE {where_clause}
        ORDER BY
            CASE status
                WHEN 'ai_pass' THEN 0
                WHEN 'filtered_pass' THEN 1
                WHEN 'new' THEN 2
                ELSE 3
            END,
            llm_score DESC,
            heuristic_score DESC
        LIMIT ? OFFSET ?
    ''', params + [per_page, offset])

    jobs = []
    for row in cursor.fetchall():
        ev = None
        if row["llm_evaluation"]:
            try:
                ev = json.loads(row["llm_evaluation"])
            except Exception:
                pass
        status = row["status"] or "new"
        jobs.append({
            "system_id": row["system_id"],
            "title": row["title"] or "",
            "company": row["company"] or "",
            "source": row["source"] or "",
            "url": row["url"] or "",
            "status": status,
            "status_label": STATUS_LABELS.get(status, status),
            "badge_class": BADGE_CLASSES.get(status, "new"),
            "heuristic_score": row["heuristic_score"] or 0,
            "llm_score": row["llm_score"] or 0,
            "llm_evaluation": ev,
            "is_remote": bool(row["is_remote"]),
            "is_part_time": bool(row["is_part_time"]),
        })
    conn.close()

    stats_items, stats_dict = get_stats()
    filter_links = get_filter_links(status_filter, search_query, stats_dict)

    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'job_search_config.yaml')) as f:
            cfg = yaml.safe_load(f)
        ai_provider = cfg.get('ai', {}).get('provider', 'deepseek')
    except Exception:
        ai_provider = 'deepseek'

    return render_template_string(
        TEMPLATE,
        jobs=jobs, stats=stats_items, filters=filter_links,
        current_status=status_filter, search_query=search_query,
        page=page, total_pages=total_pages,
        now=datetime.now().strftime("%d/%m/%Y %H:%M"),
        ai_provider=ai_provider,
    )


@app.route('/api/mark', methods=['POST'])
def mark_job():
    data = request.get_json()
    system_id = data.get('system_id')
    new_status = data.get('status')
    if not system_id or not new_status:
        return jsonify({"success": False, "message": "Missing parameters"})
    update_job(system_id, status=new_status)
    return jsonify({"success": True, "message": f"Marked as '{new_status}'"})


@app.route('/api/hide-all', methods=['POST'])
def hide_all():
    data = request.get_json()
    target_status = data.get('status')
    if not target_status:
        return jsonify({"success": False, "message": "Missing status parameter"})

    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE jobs SET status = 'hidden' WHERE status = ?", (target_status,))
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"Hid {count} jobs"})


@app.route('/api/eval/<system_id>')
def get_eval(system_id):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT llm_evaluation FROM jobs WHERE system_id = ?', (system_id,))
    row = cursor.fetchone()
    conn.close()
    if not row or not row['llm_evaluation']:
        return jsonify({"error": "No evaluation"})
    try:
        return jsonify({"eval": json.loads(row['llm_evaluation'])})
    except Exception:
        return jsonify({"error": "Parse error"})


@app.route('/api/stats')
def api_stats():
    items, _ = get_stats()
    return jsonify(items)


# ── Pipeline / AI routes ──

_RUNNING_PROCESS = {"pid": None, "type": None}


@app.route('/run-pipeline')
def run_pipeline_web():
    global _RUNNING_PROCESS
    if _RUNNING_PROCESS["pid"]:
        return redirect(url_for('dashboard'))
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'run_pipeline.py')
    proc = subprocess.Popen(
        [sys.executable, script],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    _RUNNING_PROCESS = {"pid": proc.pid, "type": "pipeline"}
    return redirect(url_for('dashboard'))


@app.route('/run-ai')
def run_ai_web():
    global _RUNNING_PROCESS
    if _RUNNING_PROCESS["pid"]:
        return redirect(url_for('dashboard'))
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, 'execution'); from llm_evaluator import run_evaluation; run_evaluation()"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    _RUNNING_PROCESS = {"pid": proc.pid, "type": "ai"}
    return redirect(url_for('dashboard'))


@app.route('/api/run-status')
def run_status():
    global _RUNNING_PROCESS
    pid = _RUNNING_PROCESS["pid"]
    if pid is None:
        return jsonify({"running": False, "type": None})
    try:
        os.kill(pid, 0)
        return jsonify({"running": True, "type": _RUNNING_PROCESS["type"]})
    except OSError:
        _RUNNING_PROCESS = {"pid": None, "type": None}
        return jsonify({"running": False, "type": None})


if __name__ == '__main__':
    print("=" * 50)
    print("  Job Hub Web UI")
    print(f"  DB: {DB_PATH}")
    print("=" * 50)
    print("  http://localhost:8080")
    print("=" * 50)
    app.run(host='0.0.0.0', port=8080, debug=True)

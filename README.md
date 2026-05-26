# 🤖 Job Hub — Pipeline di ricerca lavoro automatizzata

> Cerca, filtra e valuta offerte di lavoro su LinkedIn, Remotive e Arbeitnow
> con AI, e ricevi via email solo quelle che fanno per te.

---

## Come funziona

La pipeline esegue 6 step automatici:

```
LinkedIn ──┐
Remotive ──┤──> Filtro euristico ──> AI evaluation ──> Email
Arbeitnow ─┘      (scrematura veloce)    (Groq LLM)       (solo top match)
```

1. **Scraping**: raccoglie annunci da LinkedIn (con autenticazione), Remotive API e Arbeitnow API
2. **Filtro euristico**: assegna un punteggio basato su titolo, keyword, remote, part-time, zona Brescia
3. **AI evaluation**: i migliori candidati vengono valutati da Groq (Llama 3.1 8B) con analisi semantica
4. **Notifica email**: invia i risultati migliori a `simone.ronchi01@outlook.com`

---

## Prerequisiti

- Python 3.10+
- [Playwright](https://playwright.dev/python/) (solo per LinkedIn)
- Un account [Groq](https://console.groq.com) (gratuito, 6000 TPM)
- Un account Gmail per l'invio email

---

## ⚡ Guida rapida

```bash
# 1. Clona
git clone https://github.com/Lfr38/job-hub.git
cd job-hub

# 2. Crea ambiente virtuale
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Installa dipendenze
pip install -r requirements.txt
playwright install chromium

# 4. Configura (vedi sotto)
cp .env.example .env   # non esiste? crealo da zero
```

---

## 🔧 Configurazione

### 1. `.env` — Segreti e API key

**Questo file NON va in git.** Contiene credenziali sensibili.

```bash
# AI Provider — raccomandato: Groq (gratuito, veloce)
GROQ_API_KEY=gsk_tua_chiave_qui

# Invia notifiche email
EMAIL_ADDRESS=tua.email@gmail.com
EMAIL_PASSWORD=password_app_gmail

# Altri provider (opzionali)
# GOOGLE_API_KEY=AIza...
# DEEPSEEK_API_KEY=sk-...
```

> **💡 Per Groq**: registrati su https://console.groq.com, API gratuita con 6000 token/minuto (abbastanza per ~6-7 valutazioni/minuto). Consigliato come provider predefinito perché veloce, stabile e con tier gratuito generoso.

> **💡 Password Gmail**: usa una [password per app](https://support.google.com/accounts/answer/185833) — non la password del tuo account.

### 2. `job_search_config.yaml` — Ricerca e filtri

Tutta la configurazione della ricerca qui:

```yaml
search:
  target_roles:        # Ruoli da cercare (match sul titolo)
    - cybersecurity
    - security analyst
    - python developer
    - ...

  required_keywords:   # Parole chiave che devono apparire
    - python
    - security
    - ai

  negative_keywords:   # Parole da escludere
    - senior
    - lead
    - 5+ years

scoring:
  title_match: 30       # Punteggio per match nel titolo
  keyword_match: 10     # Punteggio per ogni keyword trovata
  ai_pass_threshold: 25 # Soglia per passare all'AI

sources:
  linkedin:
    keywords:           # Parole cercate su LinkedIn
      - cybersecurity
      - sicurezza informatica
      - guardia giurata
      - ...
```

### 3. 🔐 LinkedIn (solo autenticato)

LinkedIN richiede cookie di autenticazione:

1. Installa [Cookie-Editor](https://cookie-editor.com/) (estensione Chrome/Edge)
2. Vai su linkedin.com (loggato)
3. Apri Cookie-Editor → **Export** (formato JSON)
4. Salva come `execution/linkedin_cookies.json`
5. Rinnova ogni ~anno (o quando LinkedIn ti fa sloggiare)

### 4. AI Provider

**Raccomandato: Groq** (tutto gratis):

| Fornitore | API key | Modello | Vantaggi |
|---|---|---|---|
| **Groq** | `GROQ_API_KEY` | llama-3.1-8b-instant | 🆓 Gratuito, velocissimo (fino a 6-7 job/minuto) |
| Google Gemini | `GOOGLE_API_KEY` | gemini-2.0-flash | 🆓 60 chiamate/minuto, ottimo per test |
| DeepSeek | `DEEPSEEK_API_KEY` | deepseek-chat | 💰 Economico, buona qualità |
| OpenAI | `OPENAI_API_KEY` | gpt-4o-mini | 💰 Più costoso, massima qualità |

Per cambiare provider modifica `job_search_config.yaml`:
```yaml
ai:
  provider: groq  # opzioni: gemini | deepseek | claude | openai | groq
```

---

## 🚀 Esecuzione

### Manuale
```bash
source venv/bin/activate
cd /mnt/code/WorkResearch
bash scripts/run_full_pipeline.sh
```

### Con cron (automatico — Hermes Agent)
```bash
hermes cronjob create \
  --name linkedin-jobs-daily \
  --schedule "0 8,14 * * *" \
  --script run_full_pipeline.sh \
  --no-agent \
  --workdir /path/to/job-hub
```

La pipeline esegue: Remotive → Arbeitnow → LinkedIn → filtro → AI → email.

> **⚠️ Nota**: lo script usa `timeout 300` su LinkedIn perché Playwright può impiegare anche 3-4 minuti con 8 keyword. Se il tuo server ha poca RAM (es. 2GB Pentium), il timeout è tuo amico.

---

## 📁 Struttura del progetto

```
job-hub/
├── .env                    # ❌ Segreti (NON in git)
├── .gitignore
├── job_search_config.yaml  # ✅ Config condivisa
├── requirements.txt
├── scripts/
│   └── run_full_pipeline.sh    # Pipeline orchestrata
├── execution/
│   ├── config_loader.py        # Carica il YAML
│   ├── db_client.py            # SQLite wrapper
│   ├── ingest_remotive.py      # Scraper Remotive
│   ├── ingest_arbeitnow.py     # Scraper Arbeitnow
│   ├── ingest_linkedin.py      # Scraper LinkedIn (cookie)
│   ├── heuristic_filter.py     # Filtro veloce
│   ├── llm_evaluator.py        # Valutazione AI (Groq)
│   ├── email_notifier.py       # Notifica email
│   ├── config_loader.py        # Lettura config YAML
│   └── linkedin_cookies.json   # ❌ Cookie LinkedIn (NON in git)
├── directives/
│   └── job_hunt_remotive.md
├── webui.py                # Web UI di consultazione
└── .tmp/
    └── jobs.db             # Database SQLite
```

---

## 📊 Database

I job vengono salvati in SQLite (`.tmp/jobs.db`). Stati possibili:

- `new` — appena inserito
- `filtered_pass` — ha superato il filtro euristico
- `filtered_reject` — scartato dal filtro
- `ai_pass` — valutato positivamente dall'AI
- `ai_reject` — scartato dall'AI

Per statistiche rapide:
```bash
python -c "
import sqlite3
conn = sqlite3.connect('.tmp/jobs.db')
for row in conn.execute('SELECT status, COUNT(*) FROM jobs GROUP BY status'):
    print(f'{row[0]:20s} {row[1]}')
conn.close()
"
```

---

## 🤝 Per il tuo amico (fork personale)

Se qualcuno fork/clona questo repo:

1. Seguire la guida rapida sopra
2. Creare un **proprio** `.env` con le **proprie** API key
3. Eventualmente modificare `job_search_config.yaml` per filtri personalizzati
4. Per LinkedIn, esportare i **propri** cookie

**Niente credenziali del proprietario originale** finiscono nel repo, né nella storia git.

---

## 🧠 Note tecniche

- **Timeout LinkedIn**: Playwright con 8 keyword × 1-2 location può richiedere 2-4 minuti. Lo script ha `timeout 300` esplicito.
- **Rate limit Groq**: 6000 TPM. La pipeline ha pacing automatico di ~15s tra richieste + retry con backoff (5, 10, 20, 40, 80s) su errore 429.
- **Browser restart**: dopo 5 iterazioni keyword×location, il browser Playwright viene riavviato per evitare memory leak.
- **Anti signup**: se LinkedIn restituisce la pagina "Iscriviti a LinkedIn" invece dei risultati, lo scraper salta la keyword.

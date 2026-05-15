#!/usr/bin/env python3
"""
LinkedIn Job Scraper — Authenticated mode (cookies from user's browser).
Extracts full job details including description.
Uses Playwright with saved cookies, navigates directly to each job page.
"""

import sys
import os
import json
import time
import re
import hashlib
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config_loader import load_config
import db_client

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("❌ playwright not installed.")
    sys.exit(1)

logger = logging.getLogger("LinkedInScraper")

COOKIES_FILE = os.path.join(os.path.dirname(__file__), "linkedin_cookies.json")

DEFAULT_KEYWORDS = [
    "cybersecurity", "sicurezza informatica", "guardia giurata",
    "vigilanza", "soc analyst", "junior security", "portierato",
    "penetration testing",
]


def load_cookies(path=COOKIES_FILE):
    if not os.path.exists(path):
        logger.error(f"Cookie file not found: {path}")
        return None
    with open(path) as f:
        raw = json.load(f)
    cookies = []
    for c in raw:
        c2 = {k: v for k, v in c.items() if k in ('name', 'value', 'domain', 'path', 'secure', 'httpOnly')}
        c2['sameSite'] = 'None' if c.get('sameSite') == 'no_restriction' else 'Lax'
        if 'expirationDate' in c and c['expirationDate']:
            c2['expires'] = int(c['expirationDate'])
        cookies.append(c2)
    return cookies


def get_job_urls(page, keyword, location):
    """Extract unique job URLs from LinkedIn search results page."""
    try:
        page.wait_for_selector('a[href*="/jobs/view/"]', timeout=15000)
        time.sleep(2)
        
        urls = page.evaluate('''() => {
            const links = document.querySelectorAll('a[href*="/jobs/view/"]');
            const seen = new Set();
            return Array.from(links)
                .map(a => a.href.split('?')[0])
                .filter(h => { 
                    if (seen.has(h)) return false;
                    seen.add(h);
                    return true;
                });
        }''')
        
        return urls
    except Exception as e:
        logger.warning(f"   Errore estrazione URL: {e}")
        return []


def extract_job_from_page(page, url):
    """Navigate to a single job page and extract all details."""
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=20000)
        time.sleep(1.5)
        
        info = page.evaluate('''() => {
            const g = (sel) => {
                const el = document.querySelector(sel);
                return el ? el.textContent.trim() : '';
            };
            
            // Cerca in vari selettori possibili
            const title = g('h1') || g('.topcard__title') || 
                          g('.job-details-jobs-unified-top-card__job-title') || '';
            
            const company = g('.topcard__org-name-link') || 
                            g('.job-details-jobs-unified-top-card__company-name') ||
                            g('.jobs-unified-top-card__company-name') || '';
            
            const location = g('.topcard__flavor') || 
                             g('.job-details-jobs-unified-top-card__primary-description') ||
                             g('.jobs-unified-top-card__primary-description') || '';
            
            // Descrizione
            const descEl = document.querySelector('.show-more-less-html__markup') || 
                          document.querySelector('.description__text') ||
                          document.querySelector('.jobs-description-content__text');
            const desc = descEl ? descEl.innerText.trim() : '';
            
            // Stipendio
            const salary = g('.job-details-jobs-unified-top-card__salary-info') ||
                          g('.jobs-unified-top-card__salary-info') || '';
            
            return JSON.stringify({ title, company, location, desc: desc.substring(0, 3000), salary });
        }''')
        
        data = json.loads(info)
        return data
        
    except Exception as e:
        logger.debug(f"   Errore su {url.split('/')[-1][:30]}: {e}")
        return None


def scrape_linkedin(cookies, keywords=None, locations=None, max_pages=1, 
                    max_jobs=15, dry_run=False):
    """Main scraper with authentication."""
    if keywords is None:
        keywords = DEFAULT_KEYWORDS
    if locations is None:
        locations = ["Brescia", "Italy"]
    
    all_jobs = []
    seen_urls = set()
    
    logger.info(f"🔍 LinkedIn Auth Scraper — {len(keywords)} keywords")
    logger.info(f"   Keyword: {', '.join(keywords[:5])}{'...' if len(keywords) > 5 else ''}")
    logger.info(f"   Location: {', '.join(locations)}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='it-IT',
        )
        context.add_cookies(cookies)
        
        page = context.new_page()
        
        for keyword in keywords:
            for location in locations:
                # Raccolta URL dalla pagina di ricerca
                search_url = f"https://www.linkedin.com/jobs/search/?keywords={keyword.replace(' ', '%20')}&location={location.replace(' ', '%20')}&position=1&pageNum=0"
                
                logger.info(f"🔎 [{keyword}] @ {location}")
                
                try:
                    page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
                    time.sleep(2)
                    
                    # Rifiuta cookie se compaiono
                    try:
                        reject = page.query_selector('button:has-text("Rifiuta")')
                        if reject and reject.is_visible():
                            reject.click()
                            time.sleep(0.5)
                    except:
                        pass
                    
                    urls = get_job_urls(page, keyword, location)
                    
                    # Filtra già visti
                    new_urls = [u for u in urls if u not in seen_urls]
                    for u in new_urls:
                        seen_urls.add(u)
                    
                    logger.info(f"   {len(urls)} job trovati, {len(new_urls)} nuovi")
                    
                    # Estrai dettagli dai primi N job
                    to_extract = new_urls[:max_jobs]
                    for idx, job_url in enumerate(to_extract):
                        data = extract_job_from_page(page, job_url)
                        if not data:
                            continue
                        
                        # Pulisci località (formato LinkedIn: "Brescia, Lombardia · 2 settimane fa")
                        loc_raw = data.get('location', '')
                        loc_clean = loc_raw.split('·')[0].strip() if '·' in loc_raw else loc_raw
                        
                        job_entry = {
                            'title': data.get('title', ''),
                            'company': data.get('company', ''),
                            'location': loc_clean,
                            'description': data.get('desc', ''),
                            'salary': data.get('salary', ''),
                            'url': job_url,
                            'keyword': keyword,
                            'search_location': location,
                            'source': 'linkedin',
                        }
                        all_jobs.append(job_entry)
                        
                        if (idx + 1) % 5 == 0:
                            logger.info(f"   ... {idx+1}/{len(to_extract)}")
                
                except Exception as e:
                    logger.warning(f"   ⚠️ Errore: {e}")
                
                time.sleep(0.5)
        
        page.close()
        browser.close()
    
    logger.info(f"\n📊 TOTALE: {len(all_jobs)} job unici estratti")
    return all_jobs


def save_to_db(jobs):
    """Save jobs to DB."""
    if not jobs:
        return 0
    db_client.initialize_db()
    inserted = 0
    for job in jobs:
        dedup_key = job.get('url') or f"{job['title']}|{job['company']}"
        system_id = hashlib.md5(dedup_key.encode()).hexdigest()
        if db_client.is_job_processed(system_id):
            continue
        
        source_raw = json.dumps({
            'keyword': job.get('keyword', ''),
            'salary': job.get('salary', ''),
            'search_location': job.get('search_location', ''),
        })
        
        db_client.save_job({
            'system_id': system_id,
            'source': job.get('source', 'linkedin'),
            'source_id': job.get('url', '').split('/')[-1].split('?')[0],
            'title': job['title'],
            'company': job['company'],
            'url': job.get('url', ''),
            'description': job.get('description', ''),
            'publication_date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            'location': job.get('location', ''),
            'candidate_url': job.get('url', ''),
            'source_raw': source_raw,
        })
        inserted += 1
    
    logger.info(f"💾 DB: {inserted} nuovi inseriti")
    return inserted


def main():
    parser = argparse.ArgumentParser(description="LinkedIn Auth Scraper")
    parser.add_argument('--keywords', type=str, help='Comma-separated keywords')
    parser.add_argument('--locations', type=str, default='Brescia,Italy',
                        help='Comma-separated locations')
    parser.add_argument('--max-jobs', type=int, default=15, help='Max jobs to extract')
    parser.add_argument('--dry-run', action='store_true', help='Print without saving')
    parser.add_argument('--cookies', type=str, default=COOKIES_FILE)
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    keywords = args.keywords.split(',') if args.keywords else None
    locations = args.locations.split(',') if args.locations else None
    
    cookies = load_cookies(args.cookies)
    if not cookies:
        logger.error("❌ Cookie non trovati! Esporta i cookie con Cookie-Editor da linkedin.com")
        return
    
    logger.info("🍪 Cookie LinkedIn caricati ✅")
    
    jobs = scrape_linkedin(
        cookies=cookies, keywords=keywords, locations=locations,
        max_jobs=args.max_jobs, dry_run=args.dry_run
    )
    
    if not args.dry_run and jobs:
        total = save_to_db(jobs)
        logger.info(f"\n✅ Completato: {total} nuovi job salvati su {len(jobs)} estratti")
    
    # Highlights Brescia
    brescia = [j for j in jobs if 'brescia' in j.get('location', '').lower() or 
               'brescia' in j.get('description', '').lower()]
    if brescia:
        logger.info(f"\n📍 A BRESCIA ({len(brescia)}):")
        for j in brescia[:10]:
            logger.info(f"  • {j['title'][:45]} — {j['company'][:20]}")
    
    # Dry run mostra risultati
    if args.dry_run:
        print(f"\n📋 PRIMI {len(jobs)} JOB:")
        for j in jobs:
            desc = j.get('description', '')[:100].replace('\n', ' ')
            print(f"  [{j['title'][:40]}] {j['company'][:20]} | {j['location'][:20]}")
            if desc:
                print(f"    📄 {desc}...")


if __name__ == '__main__':
    main()

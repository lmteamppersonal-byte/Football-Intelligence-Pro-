import logging
import requests
import cloudscraper
import json
import os
import time
import random
from typing import Optional, Tuple, Dict, Any
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urlparse
from utils.logging_config import setup_logging
from dotenv import load_dotenv

load_dotenv()
logger = setup_logging("sofascore")

# Configs Default from Env
REQUEST_DELAY_MIN = float(os.environ.get("REQUEST_DELAY_MIN", 2.0))
REQUEST_DELAY_MAX = float(os.environ.get("REQUEST_DELAY_MAX", 5.0))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", 4))
RETRY_BACKOFF_BASE = float(os.environ.get("RETRY_BACKOFF_BASE", 1.0))
JITTER_FACTOR = float(os.environ.get("JITTER_FACTOR", 0.3))
COOKIE_PATH = os.path.expanduser(os.environ.get("COOKIE_PATH", "~/.football_intel/cookies.json"))
DRY_RUN = os.environ.get("DRY_RUN", "False").lower() == "true"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

class SofaClient:
    def __init__(self, base_url="https://api.sofascore.com/api/v1"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.scraper = cloudscraper.create_scraper(browser={'custom': DEFAULT_HEADERS['User-Agent']})
        
        # Load persisted cookies
        self._load_cookies()

    def _get_delay(self, attempt: int = 0) -> float:
        base = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        if attempt > 0:
            backoff = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
            jitter = backoff * random.uniform(-JITTER_FACTOR, JITTER_FACTOR)
            base += (backoff + jitter)
        return max(0.5, base)

    def _save_cookies(self):
        try:
            os.makedirs(os.path.dirname(COOKIE_PATH), exist_ok=True)
            cookies_dict = requests.utils.dict_from_cookiejar(self.session.cookies)
            # Merge with cloudscraper cookies just in case
            cookies_dict.update(requests.utils.dict_from_cookiejar(self.scraper.cookies))
            with open(COOKIE_PATH, "w") as f:
                json.dump(cookies_dict, f)
            logger.info("Cookies synced to disk.")
        except Exception as e:
            logger.error(f"Failed to save cookies: {e}")

    def _load_cookies(self):
        try:
            if os.path.exists(COOKIE_PATH):
                with open(COOKIE_PATH, "r") as f:
                    cookies_dict = json.load(f)
                cookiejar = requests.utils.cookiejar_from_dict(cookies_dict)
                self.session.cookies.update(cookiejar)
                self.scraper.cookies.update(cookiejar)
                logger.info("Cookies loaded from disk.")
        except Exception as e:
            logger.error(f"Failed to load cookies: {e}")

    def _sync_cookies_requests_to_selenium(self, driver):
        domain = urlparse(self.base_url).netloc
        for c in self.session.cookies:
            try:
                driver.add_cookie({'name': c.name, 'value': c.value, 'domain': f".{domain}"})
            except Exception:
                pass

    def _sync_cookies_selenium_to_requests(self, driver):
        for c in driver.get_cookies():
            self.session.cookies.set(c['name'], c['value'], domain=c.get('domain'))
            self.scraper.cookies.set(c['name'], c['value'], domain=c.get('domain'))
        self._save_cookies()

    def _selenium_get(self, url: str) -> Optional[Dict]:
        if DRY_RUN:
            logger.warning("Dry run enabled. Skipping Selenium fallback.")
            return None
            
        logger.info(f"Fallback to Selenium Headless for {url}")
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(f"user-agent={DEFAULT_HEADERS['User-Agent']}")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        driver = None
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            
            # Prime the domain for cookies
            driver.get("https://www.sofascore.com/robots.txt")
            self._sync_cookies_requests_to_selenium(driver)
            
            driver.get(url)
            time.sleep(3 + random.uniform(0, 2))  # Wait for JS challenge
            
            self._sync_cookies_selenium_to_requests(driver)
            
            # Try to grab JSON
            scripts = driver.find_elements("tag name", "script")
            for s in scripts:
                inner = s.get_attribute("innerHTML")
                if inner and "{" in inner and "}" in inner:
                    try: return json.loads(inner)
                    except: pass
            
            pres = driver.find_elements("tag name", "pre")
            if pres:
                try: return json.loads(pres[0].text)
                except: pass
            
            body = driver.find_element("tag name", "body").text
            return json.loads(body)
        except Exception as e:
            logger.error(f"Selenium fallback failed: {e}")
            return None
        finally:
            if driver:
                driver.quit()

    def fetch(self, path: str) -> Optional[Dict]:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        
        # Level 1: Requests
        for attempt in range(MAX_RETRIES):
            delay = self._get_delay(attempt)
            time.sleep(delay)
            
            try:
                r = self.session.get(url, timeout=10)
                if r.status_code == 200:
                    self._save_cookies()
                    return r.json()
                elif r.status_code == 403:
                    logger.warning(f"Requests got 403. Attempt {attempt + 1}/{MAX_RETRIES}")
                else:
                    logger.warning(f"Requests got {r.status_code}")
            except Exception as e:
                logger.error(f"Requests Exception: {e}")

        # Level 2: Cloudscraper
        logger.info(f"Requests exhausted. Trying Cloudscraper.")
        for attempt in range(2):
            time.sleep(self._get_delay(attempt))
            try:
                r = self.scraper.get(url, timeout=15)
                if r.status_code == 200:
                    for ck in r.cookies:
                        self.session.cookies.set(ck.name, ck.value, domain=ck.domain)
                    self._save_cookies()
                    return r.json()
                logger.warning(f"Cloudscraper got {r.status_code}")
            except Exception as e:
                logger.error(f"Cloudscraper Exception: {e}")
        
        # Level 3: Selenium
        return self._selenium_get(url)

client = SofaClient()

def get_player_stats(player_id: str) -> Tuple[Optional[Dict], str]:
    """Helper for fetching player profile and summary stats"""
    profile = client.fetch(f"/player/{player_id}")
    if not profile:
        return None, "❌ Falha ao buscar perfil do jogador."
        
    stats = None
    urls_to_try = [
        f"/player/{player_id}/statistics/season/summary",
        f"/player/{player_id}/unique-tournament-statistics/Football",
        # Generic fallback id depending on sofascore API changes
    ]
    
    for u in urls_to_try:
        stats = client.fetch(u)
        if stats:
            break
            
    return {"profile": profile, "stats": stats}, "✅ Scraping concluído."

def parse_player_id(url_or_str: str) -> Optional[str]:
    import re
    if not url_or_str:
        return None
    s = str(url_or_str).strip()
    if s.isdigit():
        return s
    m = re.search(r"/player/(?:[^/]+/)?(?P<id>\d+)", s)
    if m:
        return m.group("id")
    m2 = re.search(r"(?P<id>\d{4,})", s)
    if m2:
        return m2.group("id")
    return None

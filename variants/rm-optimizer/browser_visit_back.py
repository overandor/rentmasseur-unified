"""Selenium worker for reciprocal RentMasseur profile visits.

The browser, not a private profile API, performs every visit. The worker never
solves or bypasses CAPTCHA; it stops and reports a blocked run when one appears.
"""

from __future__ import annotations

import hashlib
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional
from urllib.parse import urljoin, urlparse


BASE_URL = "https://rentmasseur.com"
LOGIN_URL = f"{BASE_URL}/login"
VISITOR_PAGES = (
    f"{BASE_URL}/account/dashboard",
    f"{BASE_URL}/dashboard",
    f"{BASE_URL}/account/visitors",
    f"{BASE_URL}/visitors",
)

RESERVED_ROOTS = {
    "about", "account", "admin", "api", "blog", "blogs", "contact",
    "dashboard", "faq", "help", "login", "logout", "mailbox", "map",
    "privacy", "register", "search", "settings", "signup", "terms",
}


@dataclass
class VisitResult:
    username: str
    url: str
    status: str
    elapsed_seconds: float
    final_url: str = ""
    error: str = ""


def _chrome(headless: bool = True):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1100")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
    )
    binary = os.environ.get("CHROME_BIN")
    if binary:
        options.binary_location = binary
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(45)
    return driver


def _captcha_present(driver) -> bool:
    return bool(driver.execute_script("""
        const text = (document.body?.innerText || '').toLowerCase();
        return Boolean(
          document.querySelector('iframe[src*="captcha" i], iframe[src*="challenge" i], .g-recaptcha, [class*="captcha" i], [id*="captcha" i]') ||
          text.includes('verify you are human') || text.includes('security challenge')
        );
    """))


def _login(driver, username: str, password: str) -> None:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    driver.get(LOGIN_URL)
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    if _captcha_present(driver):
        raise RuntimeError("captcha_blocked_at_login")

    user = driver.execute_script("""
      return document.querySelector('input[type="email"], input[name*="email" i], input[name*="user" i], input[id*="email" i], input[id*="user" i]');
    """)
    secret = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
    if not user or not secret:
        raise RuntimeError("login_fields_not_found")
    user.clear()
    user.send_keys(username)
    secret.clear()
    secret.send_keys(password)

    submitted = driver.execute_script("""
      const password = document.querySelector('input[type="password"]');
      const form = password?.closest('form');
      const submit = form?.querySelector('button[type="submit"], input[type="submit"]') ||
        [...document.querySelectorAll('button')].find(b => /log.?in|sign.?in/i.test(b.innerText));
      if (!submit) return false;
      submit.click();
      return true;
    """)
    if not submitted:
        raise RuntimeError("login_submit_not_found")

    WebDriverWait(driver, 35).until(lambda d: "/login" not in urlparse(d.current_url).path)
    if _captcha_present(driver):
        raise RuntimeError("captcha_blocked_after_login")


def _profile_candidate(url: str) -> Optional[tuple[str, str]]:
    parsed = urlparse(urljoin(BASE_URL, url))
    if parsed.netloc not in {"rentmasseur.com", "www.rentmasseur.com"}:
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) != 1:
        return None
    username = parts[0].lower()
    if username in RESERVED_ROOTS or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,49}", username):
        return None
    return username, f"{BASE_URL}/{parts[0]}"


def _discover_visitors(driver, owner_username: str, limit: int) -> List[Dict[str, str]]:
    found: Dict[str, str] = {}
    for page in VISITOR_PAGES:
        if len(found) >= limit:
            break
        try:
            driver.get(page)
            time.sleep(1.5)
            if _captcha_present(driver):
                raise RuntimeError("captcha_blocked_during_discovery")
            links = driver.execute_script("""
              const all = [...document.querySelectorAll('a[href]')];
              const visitorContainers = [...document.querySelectorAll('[class*="visitor" i], [id*="visitor" i], [data-testid*="visitor" i]')];
              const contextual = visitorContainers.flatMap(node => [...node.querySelectorAll('a[href]')]);
              const heading = [...document.querySelectorAll('h1,h2,h3,h4')].find(h => /visitor|visited/i.test(h.innerText));
              const nearHeading = heading?.parentElement ? [...heading.parentElement.querySelectorAll('a[href]')] : [];
              return [...new Set([...contextual, ...nearHeading, ...all])].map(a => a.href);
            """) or []
            for href in links:
                candidate = _profile_candidate(href)
                if not candidate:
                    continue
                username, url = candidate
                if username == owner_username.lower():
                    continue
                found.setdefault(username, url)
                if len(found) >= limit:
                    break
        except RuntimeError:
            raise
        except Exception:
            continue
    return [{"username": name, "url": url} for name, url in found.items()]


def run_visit_back(
    *,
    username: str,
    password: str,
    limit: int = 50,
    delay_seconds: float = 2.5,
    headless: bool = True,
    progress: Optional[Callable[[Dict], None]] = None,
) -> Dict:
    if not username or not password:
        raise RuntimeError("rentmasseur_credentials_missing")
    limit = max(1, min(int(limit), 100))
    delay_seconds = max(1.5, min(float(delay_seconds), 15.0))
    started = time.time()
    driver = _chrome(headless=headless)
    results: List[VisitResult] = []
    blocked_reason = ""
    try:
        _login(driver, username, password)
        visitors = _discover_visitors(driver, username, limit)
        if progress:
            progress({"phase": "visiting", "discovered": len(visitors), "completed": 0})
        for index, visitor in enumerate(visitors):
            t0 = time.time()
            try:
                driver.get(visitor["url"])
                time.sleep(delay_seconds)
                if _captcha_present(driver):
                    blocked_reason = "captcha_blocked_during_visits"
                    results.append(VisitResult(visitor["username"], visitor["url"], "blocked", round(time.time() - t0, 2), driver.current_url, blocked_reason))
                    break
                final_path = urlparse(driver.current_url).path.rstrip("/")
                expected_path = urlparse(visitor["url"]).path.rstrip("/")
                ok = final_path == expected_path and "/login" not in final_path
                results.append(VisitResult(visitor["username"], visitor["url"], "visited" if ok else "unverified", round(time.time() - t0, 2), driver.current_url))
            except Exception as exc:
                results.append(VisitResult(visitor["username"], visitor["url"], "failed", round(time.time() - t0, 2), getattr(driver, "current_url", ""), str(exc)[:180]))
            if progress:
                progress({"phase": "visiting", "discovered": len(visitors), "completed": index + 1, "last": asdict(results[-1])})
    except Exception as exc:
        blocked_reason = str(exc)[:180]
        visitors = []
    finally:
        driver.quit()

    finished = time.time()
    receipt_source = "|".join(f"{r.username}:{r.status}" for r in results)
    receipt = hashlib.sha256(f"{started}:{receipt_source}".encode()).hexdigest()
    return {
        "status": "blocked" if blocked_reason else "completed",
        "engine": "selenium_chromium",
        "browser_visits": True,
        "discovered": len(visitors),
        "visited": sum(r.status == "visited" for r in results),
        "unverified": sum(r.status == "unverified" for r in results),
        "failed": sum(r.status == "failed" for r in results),
        "blocked_reason": blocked_reason,
        "started_at": datetime.fromtimestamp(started, timezone.utc).isoformat(),
        "finished_at": datetime.fromtimestamp(finished, timezone.utc).isoformat(),
        "elapsed_seconds": round(finished - started, 2),
        "receipt_sha256": receipt,
        "results": [asdict(r) for r in results],
    }

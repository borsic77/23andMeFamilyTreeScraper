"""
scraper.py

Automates login to 23andMe and navigates to the Family Tree page.
From there, it sets up the base for capturing family tree data (to be expanded).
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
from pathlib import Path
from rich import print
import getpass
import json
from typing import Optional

import requests
from requests import Response

EXPORT_DIR = Path("23andme_exports")
EXPORT_DIR.mkdir(exist_ok=True)



def _seed_session_cookies(driver: webdriver.Chrome) -> requests.Session:
    """Copy Selenium cookies from the browser to a requests session."""
    session = requests.Session()
    for cookie in driver.get_cookies():
        cookie_kwargs = {}
        if cookie.get("domain"):
            cookie_kwargs["domain"] = cookie["domain"]
        if cookie.get("path"):
            cookie_kwargs["path"] = cookie["path"]
        if cookie.get("secure") is not None:
            cookie_kwargs["secure"] = cookie["secure"]
        if cookie.get("expiry"):
            cookie_kwargs["expires"] = cookie["expiry"]
        session.cookies.set(cookie["name"], cookie["value"], **cookie_kwargs)
    return session


def _apply_default_headers(driver: webdriver.Chrome, session: requests.Session, profile_id: str) -> None:
    """Populate session headers so requests look like authenticated AJAX calls."""
    ajax_headers = {
        "User-Agent": driver.execute_script("return navigator.userAgent;"),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": f"https://you.23andme.com/p/{profile_id}/family/tree/",
    }
    session.headers.update(ajax_headers)

    csrf_token = None
    xsrf_token = None
    for name, value in session.cookies.get_dict().items():
        lower = name.lower()
        if "csrftoken" in lower and not csrf_token:
            csrf_token = value
        if "xsrf" in lower and not xsrf_token:
            xsrf_token = value

    if csrf_token:
        session.headers.setdefault("X-CSRFToken", csrf_token)
    if xsrf_token:
        session.headers.setdefault("X-XSRF-TOKEN", xsrf_token)


def create_authenticated_session(driver: webdriver.Chrome, profile_id: str) -> requests.Session:
    """Extract cookies from Selenium and create a requests.Session with them."""
    session = _seed_session_cookies(driver)
    _apply_default_headers(driver, session, profile_id)
    return session


def _fetch_json(session: requests.Session, url: str, description: str) -> dict:
    """Fetch a JSON response and raise a helpful exception if parsing fails."""
    response: Response = session.get(url)
    try:
        response.raise_for_status()
    except requests.HTTPError as error:
        raise RuntimeError(
            f"Failed to fetch {description}: HTTP {response.status_code} from {url}"
        ) from error

    content_type = response.headers.get("Content-Type", "")
    if "json" not in content_type.lower():
        snippet = response.text[:200].strip()
        raise RuntimeError(
            f"Expected JSON while fetching {description} but got {content_type or 'unknown content-type'}.\n"
            f"Response snippet: {snippet}"
        )

    try:
        return response.json()
    except json.JSONDecodeError as error:
        snippet = response.text[:200].strip()
        raise RuntimeError(
            f"Could not decode JSON for {description}. Response snippet: {snippet}"
        ) from error


def _fetch_json_via_browser(driver: webdriver.Chrome, url: str, description: str) -> dict:
    """Execute fetch inside the browser context to leverage existing authenticated session."""
    script = """
    const url = arguments[0];
    const callback = arguments[arguments.length - 1];

    fetch(url, {
        credentials: 'include',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        const contentType = response.headers.get('content-type') || '';
        return response.text().then(text => {
            callback({
                ok: response.ok,
                status: response.status,
                statusText: response.statusText,
                contentType,
                text
            });
        });
    })
    .catch(error => {
        callback({
            ok: false,
            error: error ? error.toString() : 'Unknown error'
        });
    });
    """

    result = driver.execute_async_script(script, url)
    if not isinstance(result, dict):
        raise RuntimeError(f"Unexpected browser fetch result for {description}: {result}")

    if not result.get("ok"):
        snippet = (result.get("text") or "").strip()[:200]
        status = result.get("status")
        status_text = result.get("statusText") or result.get("error", "Unknown error")
        raise RuntimeError(
            f"Browser fetch failed for {description}: {status} {status_text}. Response snippet: {snippet}"
        )

    content_type = (result.get("contentType") or "").lower()
    text = result.get("text") or ""

    if "json" not in content_type:
        snippet = text.strip()[:200]
        raise RuntimeError(
            f"Browser fetch expected JSON for {description} but received {content_type or 'unknown content-type'}.\n"
            f"Response snippet: {snippet}"
        )

    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        snippet = text.strip()[:200]
        raise RuntimeError(
            f"Browser fetch could not decode JSON for {description}. Response snippet: {snippet}"
        ) from error


def _fetch_json_with_fallback(
    session: requests.Session,
    url: str,
    description: str,
    driver: Optional[webdriver.Chrome] = None,
) -> dict:
    """Try fetching JSON via requests session, falling back to browser context when needed."""
    try:
        return _fetch_json(session, url, description)
    except RuntimeError as error:
        if driver is None:
            raise
        print(
            f"[yellow]Session fetch for {description} failed ({error}). Retrying via browser context...[/yellow]"
        )
        return _fetch_json_via_browser(driver, url, description)

def init_browser(headless: bool = True) -> webdriver.Chrome:
    """Initialize a Chrome browser with options."""
    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=options)
    return driver


def login(driver: webdriver.Chrome, email: str, password: str) -> bool:
    """Login to 23andMe and return True if successful."""
    print("[bold blue]Navigating to login page...[/bold blue]")
    driver.get("https://you.23andme.com/")
    time.sleep(2)

    email_input = driver.find_element(By.ID, "id_username")
    password_input = driver.find_element(By.ID, "id_password")
    email_input.send_keys(email)
    password_input.send_keys(password)
    password_input.send_keys(Keys.RETURN)
    time.sleep(5)

    try:
        # Wait for the 2FA page
        if "Enter verification code" in driver.page_source or driver.find_elements(By.ID, "id_token"):
            print("[yellow]2FA required. Please check your email for the verification code.[/yellow]")
            while True:
                try:
                    verification_input = driver.find_element(By.ID, "id_token")
                    break
                except:
                    time.sleep(1)
            code = input("Enter the verification code: ")
            verification_input.send_keys(code)
            submit_button = driver.find_element(By.ID, "mfa-verify-button")
            submit_button.click()
            time.sleep(5)
    except Exception as e:
        print(f"[red]Error during 2FA step: {e}[/red]")

    print("[green]Logged in successfully.[/green]")
    return True


def extract_profile_id(driver: webdriver.Chrome) -> str:
    """Extracts the current profile_id from cookies."""
    for cookie in driver.get_cookies():
        if cookie["name"] == "current-profile-id":
            return cookie["value"]
    raise ValueError("Could not find profile_id in cookies")


def fetch_and_save_relatives(
    session: requests.Session,
    profile_id: str,
    limit: int = 10,
    *,
    driver: Optional[webdriver.Chrome] = None,
) -> None:
    """Fetch relatives data from 23andMe and save it to a JSON file."""
    url = f"https://you.23andme.com/p/{profile_id}/family/relatives/ajax/?limit={limit}"

    print(f"[green]Fetching {limit} relatives...[/green]")
    data = _fetch_json_with_fallback(session, url, f"{limit} relatives", driver=driver)

    filename = f"relatives_{limit}.json"
    with open(filename, "w", encoding="utf-8") as f:
        import json
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[bold green]Saved to {filename}[/bold green]")


def fetch_tree_data(
    session: requests.Session,
    profile_id: str,
    *,
    driver: Optional[webdriver.Chrome] = None,
) -> None:
    """Fetch tree structure and annotations and save as JSON files."""
    base_url = f"https://you.23andme.com/p/{profile_id}/family/tree"
    endpoints = {
        "tree": f"{base_url}/ajax/?health=false",
        "annotations": f"{base_url}/annotations/"
    }

    for name, url in endpoints.items():
        print(f"Fetching {name} data...")
        data = _fetch_json_with_fallback(session, url, f"{name} data", driver=driver)

        file_path = Path(f"{name}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"Saved {name} data to {file_path}")

def copy_cookies_to_session(driver: webdriver.Chrome) -> requests.Session:
    """Copy cookies from Selenium to requests.Session."""
    return _seed_session_cookies(driver)


def navigate_to_tree(driver: webdriver.Chrome) -> None:
    """Navigate to the Family Tree page."""
    print("[bold blue]Navigating to family tree page...[/bold blue]")
    driver.get("https://you.23andme.com/family/tree/")
    time.sleep(5)
    print("[bold yellow]Inspecting tree page completed.[/bold yellow]")

def run_scraper(export_dir: Path) -> None:
    """Run the full scraping workflow and save output to the given directory."""
    email = input("23andMe Email: ")
    password = getpass.getpass("23andMe Password: ")

    driver = init_browser(headless=False)
    try:
        if login(driver, email, password):
            navigate_to_tree(driver)
            profile_id = extract_profile_id(driver)
            print(f"[bold green]Using profile ID:[/bold green] {profile_id}")

            session = create_authenticated_session(driver, profile_id)

            export_dir.mkdir(parents=True, exist_ok=True)
            for limit in [10]:
                data = _fetch_json_with_fallback(
                    session,
                    f"https://you.23andme.com/p/{profile_id}/family/relatives/ajax/?limit={limit}",
                    f"{limit} relatives",
                    driver=driver,
                )
                (export_dir / f"relatives_{limit}.json").write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                )

            for name, url in {
                "tree": f"https://you.23andme.com/p/{profile_id}/family/tree/ajax/?health=false",
                "annotations": f"https://you.23andme.com/p/{profile_id}/family/tree/annotations/"
            }.items():
                data = _fetch_json_with_fallback(session, url, f"{name} data", driver=driver)
                (export_dir / f"{name}.json").write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
    finally:
        driver.quit()


if __name__ == "__main__":
    email = input("23andMe Email: ")
    password = getpass.getpass("23andMe Password: ")

    driver = init_browser(headless=False)
    try:
        if login(driver, email, password):
            navigate_to_tree(driver)
            profile_id = extract_profile_id(driver)
            print(f"[bold green]Using profile ID:[/bold green] {profile_id}")

            session = create_authenticated_session(driver, profile_id)
            for limit in [10, 100, 1500]:
                fetch_and_save_relatives(session, profile_id, limit, driver=driver)
            fetch_tree_data(session, profile_id, driver=driver)

            input("\n[bold cyan]Press Enter to close the browser...[/bold cyan]")
    finally:
        driver.quit()

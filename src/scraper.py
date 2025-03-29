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
import requests

EXPORT_DIR = Path("23andme_exports")
EXPORT_DIR.mkdir(exist_ok=True)



def create_authenticated_session(driver: webdriver.Chrome) -> requests.Session:
    """Extract cookies from Selenium and create a requests.Session with them."""
    session = requests.Session()

    for cookie in driver.get_cookies():
        session.cookies.set(cookie['name'], cookie['value'])

    # Add headers for requests to look like an AJAX call
    session.headers.update({
        "User-Agent": driver.execute_script("return navigator.userAgent;"),
        "Accept": "*/*",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://you.23andme.com/family/tree/",
    })

    return session

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


def fetch_and_save_relatives(session: requests.Session, profile_id: str, limit: int = 10) -> None:
    """Fetch relatives data from 23andMe and save it to a JSON file."""
    url = f"https://you.23andme.com/p/{profile_id}/family/relatives/ajax/?limit={limit}"

    print(f"[green]Fetching {limit} relatives...[/green]")
    response = session.get(url)
    response.raise_for_status()

    data = response.json()

    filename = f"relatives_{limit}.json"
    with open(filename, "w", encoding="utf-8") as f:
        import json
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[bold green]Saved to {filename}[/bold green]")


def fetch_tree_data(session: requests.Session, profile_id: str) -> None:
    """Fetch tree structure and annotations and save as JSON files."""
    base_url = f"https://you.23andme.com/p/{profile_id}/family/tree"
    endpoints = {
        "tree": f"{base_url}/ajax/?health=false",
        "annotations": f"{base_url}/annotations/"
    }

    for name, url in endpoints.items():
        print(f"Fetching {name} data...")
        response = session.get(url)
        response.raise_for_status()
        data = response.json()

        file_path = Path(f"{name}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"Saved {name} data to {file_path}")

def copy_cookies_to_session(driver: webdriver.Chrome) -> requests.Session:
    """Copy cookies from Selenium to requests.Session."""
    session = requests.Session()
    for cookie in driver.get_cookies():
        session.cookies.set(cookie["name"], cookie["value"])
    return session


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

            session = create_authenticated_session(driver)

            export_dir.mkdir(parents=True, exist_ok=True)
            for limit in [10]:
                data = session.get(
                    f"https://you.23andme.com/p/{profile_id}/family/relatives/ajax/?limit={limit}"
                ).json()
                (export_dir / f"relatives_{limit}.json").write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                )

            for name, url in {
                "tree": f"https://you.23andme.com/p/{profile_id}/family/tree/ajax/?health=false",
                "annotations": f"https://you.23andme.com/p/{profile_id}/family/tree/annotations/"
            }.items():
                data = session.get(url).json()
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

            session = create_authenticated_session(driver)
            for limit in [10, 100, 1500]:
                fetch_and_save_relatives(session, profile_id, limit)
            fetch_tree_data(session, profile_id)

            input("\n[bold cyan]Press Enter to close the browser...[/bold cyan]")
    finally:
        driver.quit()


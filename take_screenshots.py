"""Capture screenshots of the Plan de Contrôle application for guide/README."""
from playwright.sync_api import sync_playwright
import time

BASE = "http://127.0.0.1:8002"
OUT = "static/screenshots"

PAGES = [
    ("login", "/login", None),
    ("dashboard", "/dashboard", None),
    ("controls_list", "/controls", None),
    ("control_detail", "/controls/1", None),
    ("campagne", "/campagne", None),
    ("results_pending", "/results/pending", None),
    ("admin", "/admin", None),
    ("settings", "/settings", None),
    ("settings_ldap", "/settings#ldap", None),
    ("activity", "/activity", None),
    ("guide", "/guide", None),
]


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()

        # Login first
        page.goto(f"{BASE}/login")
        page.fill("input[name=username]", "admin")
        page.fill("input[name=password]", "erwanbogosse2026")
        page.click("button[type=submit]")
        page.wait_for_url(f"{BASE}/dashboard", timeout=5000)
        print("Logged in")

        for name, path, extra in PAGES:
            if name == "login":
                # Take login page in a fresh context
                ctx2 = browser.new_context(viewport={"width": 1400, "height": 900})
                p2 = ctx2.new_page()
                p2.goto(f"{BASE}/login")
                p2.wait_for_load_state("networkidle")
                p2.screenshot(path=f"{OUT}/{name}.png", full_page=False)
                print(f"  {name}.png")
                ctx2.close()
                continue

            try:
                page.goto(f"{BASE}{path}")
                page.wait_for_load_state("networkidle", timeout=8000)
                time.sleep(0.4)  # let charts render
                page.screenshot(path=f"{OUT}/{name}.png", full_page=False)
                print(f"  {name}.png")
            except Exception as e:
                print(f"  SKIP {name}: {e}")

        browser.close()
        print("Done.")


if __name__ == "__main__":
    run()

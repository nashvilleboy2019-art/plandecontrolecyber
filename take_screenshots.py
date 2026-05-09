"""Capture screenshots of the Plan de Contrôle application for guide/README."""
from playwright.sync_api import sync_playwright
import time

BASE = "http://127.0.0.1:8002"
OUT = "static/screenshots"


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

        def shot(name, path=None, action=None, wait=0.6):
            if path:
                page.goto(f"{BASE}{path}")
                page.wait_for_load_state("networkidle", timeout=10000)
            if action:
                action()
            time.sleep(wait)
            page.screenshot(path=f"{OUT}/{name}.png", full_page=False)
            print(f"  {name}.png")

        # Login page (fresh context, not authenticated)
        ctx2 = browser.new_context(viewport={"width": 1400, "height": 900})
        p2 = ctx2.new_page()
        p2.goto(f"{BASE}/login")
        p2.wait_for_load_state("networkidle")
        p2.screenshot(path=f"{OUT}/login.png", full_page=False)
        print("  login.png")
        ctx2.close()

        # Dashboard — Vue annuelle (default)
        shot("dashboard", "/dashboard", wait=1.0)

        # Dashboard — Vue mensuelle
        def click_mensuel():
            page.click("button:has-text('Vue mensuelle')")
            time.sleep(0.3)
        shot("dashboard_mensuel", action=click_mensuel, wait=0.6)

        # Dashboard — Indicateurs
        def click_indicateurs():
            page.goto(f"{BASE}/dashboard")
            page.wait_for_load_state("networkidle", timeout=10000)
            page.click("button:has-text('Indicateurs')")
            time.sleep(0.8)  # wait for sparklines to render
        shot("dashboard_indicateurs", action=click_indicateurs, wait=0.5)

        # Other pages
        try:
            shot("controls_list", "/controls")
        except Exception as e:
            print(f"  SKIP controls_list: {e}")

        try:
            shot("control_detail", "/controls/1")
        except Exception as e:
            print(f"  SKIP control_detail: {e}")

        try:
            shot("campagne", "/campagne")
        except Exception as e:
            print(f"  SKIP campagne: {e}")

        try:
            shot("results_pending", "/results/pending")
        except Exception as e:
            print(f"  SKIP results_pending: {e}")

        try:
            shot("admin", "/admin")
        except Exception as e:
            print(f"  SKIP admin: {e}")

        try:
            shot("settings", "/settings")
        except Exception as e:
            print(f"  SKIP settings: {e}")

        try:
            def scroll_ldap():
                page.evaluate("document.getElementById('ldap') && document.getElementById('ldap').scrollIntoView()")
            shot("settings_ldap", "/settings", action=scroll_ldap, wait=0.4)
        except Exception as e:
            print(f"  SKIP settings_ldap: {e}")

        try:
            shot("activity", "/activity")
        except Exception as e:
            print(f"  SKIP activity: {e}")

        try:
            shot("guide", "/guide")
        except Exception as e:
            print(f"  SKIP guide: {e}")

        browser.close()
        print("\nDone.")


if __name__ == "__main__":
    run()

import os
import smtplib
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

URL = "https://www.signupgenius.com/go/10C0C4EA5A82DA64-issue#/"
PASSCODE = "1946"

# --- Email config (loaded from GitHub Secrets / environment variables) ---
GMAIL_USER   = os.environ["GMAIL_USER"]    # your Gmail address
GMAIL_PASS   = os.environ["GMAIL_PASS"]    # Gmail App Password (not your real password)
NOTIFY_EMAIL = os.environ["NOTIFY_EMAIL"]  # where to send alerts (can be same as GMAIL_USER)


def send_email(subject: str, body: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = NOTIFY_EMAIL
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, NOTIFY_EMAIL, msg.as_string())
    print("📧 Notification email sent.")


def check_slots() -> list[str]:
    """
    Returns a list of available slot descriptions, or an empty list if none.
    """
    available = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"Loading {URL} ...")
        page.goto(URL, wait_until="networkidle", timeout=30_000)

        # --- Handle passcode prompt if present ---
        try:
            passcode_input = page.wait_for_selector(
                "input[type='password'], input[placeholder*='passcode' i], input[placeholder*='password' i]",
                timeout=6_000
            )
            if passcode_input:
                print("Passcode prompt detected — entering code...")
                passcode_input.fill(PASSCODE)
                # Click submit / Go button near the input
                page.keyboard.press("Enter")
                page.wait_for_load_state("networkidle", timeout=15_000)
        except PlaywrightTimeout:
            print("No passcode prompt found — continuing.")

        # --- Wait for signup slots to render ---
        try:
            page.wait_for_selector(".SUGtablerow, .slot-row, [class*='slot'], [class*='Slot']",
                                   timeout=15_000)
        except PlaywrightTimeout:
            print("Slot rows not found — page may have changed structure.")
            browser.close()
            return []

        # --- Parse slots ---
        # SignUpGenius marks open slots with text like "Sign Up" or an empty spot column
        rows = page.query_selector_all(".SUGtablerow, .slot-row")
        for row in rows:
            text = row.inner_text().strip()
            # An open slot typically contains "Sign Up" and does NOT say "FILLED"
            if "Sign Up" in text and "FILLED" not in text.upper():
                available.append(text.replace("\n", " | "))

        browser.close()

    return available


def main():
    print("=== SignUpGenius Slot Checker ===")
    try:
        slots = check_slots()
    except Exception as e:
        print(f"ERROR during check: {e}")
        # Don't crash the Action — just exit cleanly so it retries next run
        sys.exit(0)

    if slots:
        print(f"✅ {len(slots)} open slot(s) found!")
        body = "Open passport appointment slot(s) found on SignUpGenius:\n\n"
        body += "\n\n".join(f"• {s}" for s in slots)
        body += f"\n\nBook now: {URL}"
        send_email("🚨 Passport Slot Available — Book Now!", body)
    else:
        print("❌ No open slots found. Will check again next run.")


if __name__ == "__main__":
    main()

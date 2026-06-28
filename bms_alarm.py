"""
BookMyShow Ticket-Drop Alarm - GitHub Actions edition
======================================================
Runs ONE check pass per execution (GitHub Actions re-triggers this on a
schedule, e.g. every 5 minutes - there's no infinite loop needed here).

Watches Allu Cinemas: Kokapet's own date-specific BookMyShow page (URL
pattern: .../buytickets/ALUC/YYYYMMDD) and fires a loud Pushover EMERGENCY
alert the moment the target movie's name appears in that date's listing.
Remembers which targets already fired (alerted_state.json, committed back
to this repo by the workflow) so it won't re-alert on every run.
"""

import os
import sys
import json
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright

PUSHOVER_USER_KEY = os.environ["PUSHOVER_USER_KEY"]
PUSHOVER_APP_TOKEN = os.environ["PUSHOVER_APP_TOKEN"]

WATCHES = [
    {
        "label": "The Odyssey - Fri 17 Jul",
        "url": "https://in.bookmyshow.com/cinemas/HYD/allu-cinemas-kokapet/buytickets/ALUC/20260717",
        "match_text": "Odyssey",
    },
    {
        "label": "The Odyssey - Sat 18 Jul",
        "url": "https://in.bookmyshow.com/cinemas/HYD/allu-cinemas-kokapet/buytickets/ALUC/20260718",
        "match_text": "Odyssey",
    },
    {
        "label": "The Odyssey - Sun 19 Jul",
        "url": "https://in.bookmyshow.com/cinemas/HYD/allu-cinemas-kokapet/buytickets/ALUC/20260719",
        "match_text": "Odyssey",
    },
    {
        "label": "Spider-Man: Brand New Day - Sat 1 Aug",
        "url": "https://in.bookmyshow.com/cinemas/HYD/allu-cinemas-kokapet/buytickets/ALUC/20260801",
        "match_text": "Brand New Day",
    },
    {
        "label": "Spider-Man: Brand New Day - Sun 2 Aug",
        "url": "https://in.bookmyshow.com/cinemas/HYD/allu-cinemas-kokapet/buytickets/ALUC/20260802",
        "match_text": "Brand New Day",
    },
]

# Note: these dates are currently too far out and BookMyShow redirects them
# back to today's date - that's expected and safe. The check below will
# simply find no match (correctly reporting "not live yet") until
# BookMyShow itself opens that date in its calendar, at which point the
# same URL starts showing the real listing and detection kicks in
# automatically - no need to update these URLs manually later.

STATE_FILE = Path("alerted_state.json")


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def send_emergency_alert(title, message):
    """Pushover priority-2 'Emergency' alert: loud siren, repeats every 60s
    until acknowledged in the app, auto-stops after 3 hours either way."""
    resp = requests.post(
        "https://api.pushover.net/1/messages.json",
        data={
            "token": PUSHOVER_APP_TOKEN,
            "user": PUSHOVER_USER_KEY,
            "title": title,
            "message": message,
            "priority": 2,
            "retry": 60,
            "expire": 10800,
            "sound": "siren",
        },
        timeout=15,
    )
    resp.raise_for_status()
    print(f"[ALERT SENT] {title}")


def check_one(page, watch):
    page.goto(watch["url"], wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)  # let client-side rendering settle
    content = page.content()
    return watch["match_text"].lower() in content.lower()


def main():
    state = load_state()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        )
        page = context.new_page()

        for watch in WATCHES:
            label = watch["label"]
            if state.get(label):
                print(f"[{label}] already alerted, skipping.")
                continue

            try:
                found = check_one(page, watch)
            except Exception as e:
                print(f"[{label}] check failed: {e}")
                continue

            if found:
                print(f"[{label}] BOOKING IS LIVE!")
                send_emergency_alert(
                    f"Tickets live: {label}",
                    "Allu Cinemas Kokapet just listed this show on this date. Book now.",
                )
                state[label] = True
            else:
                print(f"[{label}] not live yet.")

        browser.close()

    save_state(state)


if __name__ == "__main__":
    if "--test" in sys.argv:
        send_emergency_alert("Test alert", "If your phone just buzzed loudly, Pushover is working.")
    else:
        main()

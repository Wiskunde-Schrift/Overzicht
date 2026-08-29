"""
Haalt de iCloud agenda (ICS-feed) op en zet de eerstvolgende afspraken
om naar agenda.json, zodat de website die zonder CORS-problemen kan inlezen.

De echte agenda-link staat NIET in dit script, maar in een GitHub
repository secret genaamd ICLOUD_ICAL_URL (zie Settings > Secrets and
variables > Actions in je repo).
"""

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

import requests
from icalendar import Calendar

MAX_EVENTS = 25
LOOKAHEAD_DAYS = 120  # negeer afspraken verder dan ~4 maanden vooruit


def to_utc_datetime(dt):
    """Zet een date of datetime object om naar een timezone-aware UTC datetime."""
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    # het is een 'date' (hele dag afspraak, geen tijd)
    return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)


def main():
    ical_url = os.environ.get("ICLOUD_ICAL_URL")
    if not ical_url:
        print("Fout: ICLOUD_ICAL_URL secret ontbreekt.", file=sys.stderr)
        sys.exit(1)

    # webcal:// werkt niet met requests, https:// wel
    fetch_url = ical_url.replace("webcal://", "https://")

    response = requests.get(fetch_url, timeout=30)
    response.raise_for_status()

    calendar = Calendar.from_ical(response.content)

    now_utc = datetime.now(timezone.utc)
    cutoff_utc = now_utc + timedelta(days=LOOKAHEAD_DAYS)

    events = []

    for component in calendar.walk("VEVENT"):
        dtstart_field = component.get("dtstart")
        if dtstart_field is None:
            continue

        raw_dt = dtstart_field.dt
        event_dt_utc = to_utc_datetime(raw_dt)

        # sla verlopen of te ver vooruitliggende afspraken over
        if event_dt_utc < now_utc or event_dt_utc > cutoff_utc:
            continue

        is_all_day = isinstance(raw_dt, date) and not isinstance(raw_dt, datetime)
        title = str(component.get("summary", "Zonder titel"))

        events.append({
            "title": title,
            "date": event_dt_utc.date().isoformat(),
            "time": None if is_all_day else event_dt_utc.strftime("%H:%M"),
            "_sort_key": event_dt_utc.isoformat(),
        })

    events.sort(key=lambda e: e["_sort_key"])
    events = events[:MAX_EVENTS]
    for e in events:
        del e["_sort_key"]

    output = {
        "generated_at": now_utc.isoformat(),
        "events": events,
    }

    with open("agenda.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"agenda.json geschreven met {len(events)} afspraken.")


if __name__ == "__main__":
    main()

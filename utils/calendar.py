import os
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# === CONFIGURATION ===
SCOPES = ['https://www.googleapis.com/auth/calendar']
CLIENT_SECRET_FILE = ""
TOKEN_FILE = "token.json"

# === AUTHENTICATION ===
def get_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)

# === FREE SLOTS ===
def get_free_slots(start, end):
    service = get_service()

    busy_result = service.freebusy().query(body={
        "timeMin": start.isoformat(),
        "timeMax": end.isoformat(),
        "timeZone": "Europe/Paris",
        "items": [{"id": "primary"}]
    }).execute()

    busy_periods = busy_result['calendars']['primary']['busy']
    free_slots = []

    current = start

    for period in busy_periods:
        busy_start = datetime.fromisoformat(period["start"])
        busy_end = datetime.fromisoformat(period["end"])

        if current < busy_start:
            adjusted_start = max(current, current.replace(hour=8, minute=0))
            adjusted_end = min(busy_start, current.replace(hour=23, minute=59))
            if adjusted_start < adjusted_end:
                free_slots.append({
                    "start": adjusted_start.isoformat(),
                    "end": adjusted_end.isoformat()
                })

        current = max(current, busy_end)

    if current < end:
        adjusted_start = max(current, current.replace(hour=8, minute=0))
        adjusted_end = end.replace(hour=23, minute=59)
        if adjusted_start < adjusted_end:
            free_slots.append({
                "start": adjusted_start.isoformat(),
                "end": adjusted_end.isoformat()
            })

    return free_slots

# === ADD EVENT ===
def add_event(title, start, end):
    service = get_service()

    event = {
        "summary": title,
        "start": {
            "dateTime": start.isoformat(),
            "timeZone": "Europe/Paris"
        },
        "end": {
            "dateTime": end.isoformat(),
            "timeZone": "Europe/Paris"
        }
    }

    created = service.events().insert(calendarId="primary", body=event).execute()
    print(f"✅ Event created: {created.get('htmlLink')}")

# === GET ALL EVENTS ===
def get_events_from_calendar(start, end):
    service = get_service()
    events_result = service.events().list(
        calendarId='primary',
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return events_result.get('items', [])

# === GET REVISION SESSIONS ===
def get_revision_sessions():
    service = get_service()

    now = datetime.now().isoformat()
    future = (datetime.now() + timedelta(days=14)).isoformat()

    events_result = service.events().list(
        calendarId='primary',
        timeMin=now,
        timeMax=future,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])

    revision_sessions = []
    for event in events:
        if '📖 Study:' in event.get("summary", ""):
            revision_sessions.append({
                "id": event["id"],
                "title": event["summary"].replace("📖 Study: ", "").strip(),
                "start": event["start"].get("dateTime", ""),
                "end": event["end"].get("dateTime", "")
            })

    return revision_sessions

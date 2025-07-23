from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import os

def get_google_credentials(scopes):
    token_path = 'token.json'
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', scopes)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    return creds

def create_event(summary, start_time_iso, end_time_iso, description=None):
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    creds = get_google_credentials(SCOPES)
    service = build('calendar', 'v3', credentials=creds)
    event = {
        'summary': summary,
        'description': description,
        'start': {'dateTime': start_time_iso, 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end_time_iso, 'timeZone': 'Asia/Kolkata'},
    }
    created_event = service.events().insert(calendarId='primary', body=event).execute()
    print(f"Event created: {created_event.get('htmlLink')}")

if __name__ == "__main__":
    # Example event details
    summary = "Team Meeting"
    start_time_iso = "2025-07-21T10:00:00"
    end_time_iso = "2025-07-21T11:00:00"
    description = "Discuss project updates and next steps."
    create_event(summary, start_time_iso, end_time_iso, description)

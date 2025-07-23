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

def list_calendars():
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    creds = get_google_credentials(SCOPES)
    service = build('calendar', 'v3', credentials=creds)
    calendars = service.calendarList().list().execute()
    for calendar in calendars.get('items', []):
        print(f"Calendar: {calendar['summary']}")
        print(f"Access Role: {calendar['accessRole']}")
        print(f"ID: {calendar['id']}")
        print("-" * 40)

if __name__ == "__main__":
    list_calendars()

import datetime
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

import smtplib
from email.mime.text import MIMEText
from base64 import urlsafe_b64encode

check_same_day = True

def setup():
    token_file = os.path.join(os.path.dirname(__file__), 'token.json')
    creds_file = os.path.join(os.path.dirname(__file__), 'credentials.json')
    SCOPES = [
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/gmail.send'
    ]
    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                creds_file, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
    return creds

def calendar(creds):
    service = build('calendar', 'v3', credentials=creds)

    today = datetime.datetime.today().date()
    now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    events_result = service.events().list(calendarId='primary', timeMin=now,
                                        maxResults=30, singleEvents=True,
                                        orderBy='startTime').execute()
    events = events_result.get('items', [])
    if not events:
        print('No upcoming events found.')

    first = {}
    for event in events:
        # Docs on events https://developers.google.com/calendar/api/v3/reference/events
        # Let's look at only confirmed events
        if event['status'] != 'confirmed':
            print('Skipping as not confirmed: %s' % event['summary'])
            continue
        # If it's date, it's an all day event, usually ignore.
        if 'date' in event['start']:
            print('Skipping as all day event: %s' % event['summary'])
            continue
        if 'dateTime' in event['start']:
            first = {
                "event": event, 
                "when": datetime.datetime.strptime(event['start']['dateTime'], "%Y-%m-%dT%H:%M:%S%z")
            }
            break

    if not first:
        print('No events coming up.')
        return
    
    if check_same_day and first["when"].date() != today:
        print('Next event is not today: %s' % first["when"].date())
        return

    return first


def mail(creds, event):
    service = build('gmail', 'v1', credentials=creds)

    content = """First meeting: %s
Day: %s
About: %s

This is a friendly reminder in case you are running or sleeping in.
""" % (
        event['when'].strftime("%H:%M %p"), 
        event['when'].strftime("%A %d %b"),
        event['event']['summary']
    )

    message = MIMEText(content)
    message["from"] = "andymckay@github.com"
    message["to"] = "andy@clearwind.ca"
    message["subject"] = "First meeting is at %s" % event['when'].strftime("%H:%M %p")
    body = {'raw': urlsafe_b64encode(message.as_string().encode()).decode()}

    try:
        service.users().messages().send(userId='me', body=body).execute()
        print('Mail sent to: %s' % message["to"])
    except Exception as error:
        print('An error occurred: %s' % error)
        

if __name__ == '__main__':
    creds = setup()
    event = calendar(creds)
    if event:
        print("Got event, emailing.")
        mail(creds, event)
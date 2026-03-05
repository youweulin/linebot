import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import json

def test():
    token_json = os.environ.get("GOOGLE_DRIVE_OAUTH_JSON")
    if not token_json:
        print("No OAuth token found")
        return
    
    creds_info = json.loads(token_json)
    creds = Credentials.from_authorized_user_info(creds_info)
    
    try:
        service = build('tasks', 'v1', credentials=creds)
        results = service.tasklists().list(maxResults=10).execute()
        items = results.get('items', [])
        
        if not items:
            print('No task lists found.')
        else:
            print('Task lists:')
            for item in items:
                print(u'{0} ({1})'.format(item['title'], item['id']))
    except Exception as e:
        print(f"Error: {e}")

test()

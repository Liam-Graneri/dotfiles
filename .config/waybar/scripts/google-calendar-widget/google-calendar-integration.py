import datetime
import json
import os.path
import re
import subprocess as s
import sys

import pandas as pd
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def get_future_events(api_obj, calendar_obj, n_results, now):
    # print(calendar_obj['summary'])
    cal_id = calendar_obj['id']
    events_result = api_obj.events().list(
        calendarId=cal_id, timeMin=now, maxResults=n_results,
        singleEvents=True, orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    if not events:
        # print('\tNo upcoming events found.')
        return []
    return events


def log_events(events, calendar_name, work=False):
    # Prints and logs the next (at least) 3 events per calendar
    events_df = pd.DataFrame.from_dict(
        {'calendar': [''], 'summary': [''], 'start': [''], 'end': ['']})
    for event in events:
        event_name = event.get('summary', 'Summary not in keys')
        if (work) and ('liam' not in event_name.lower()):
            # print('\tNo upcoming events found.')
            continue
        else:
            None
        event['calendar'] = calendar_name
        for time in ['start', 'end']:
            for key in event[time].keys():
                if 'date' in key:
                    event[time] = event[time][key]
                    break
        event['summary'] = event['calendar'] if work else event['summary']
        events_df = events_df.append(event, ignore_index=True)
    events_df = events_df.dropna(subset=['calendar'])
    return events_df


def tooltip_output(df):
    # Formats output for custom waybar widget tooltip
    df = df.loc[df['summary'] != 'last_updated'].copy()
    # Custom outputs are newline separated, the intital string will be used for main bar text
    output_string = '\n'
    for date in sorted(df['start_date_string'].unique()):
        # Subsequent string is used for tooltip (\r is used instead of newline within this string)
        output_string += f'--- {date} ---\r'
        date_df = df.loc[df['start_date_string'] == date].copy()
        for event in date_df['summary'].unique():
            start_time = date_df.loc[date_df['summary'] == event]['start_time_string'].unique()[
                0]
            duration = date_df.loc[date_df['summary'] == event]['duration_hours'].unique()[
                0]
            output_string += f'{start_time}: {event} ({duration}h)\r'
        output_string += '\r'
    output_string = output_string.strip('\r')
    print(output_string)
    return output_string


def update_events(now):
    # Gets authorisation through google API services using `credentials.json` and `token.json`
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    creds = None
    token_path = '/home/liam/.config/waybar/scripts/google-calendar-widget/token.json'
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(
            token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                '/home/liam/.config/waybar/scripts/google-calendar-widget/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    try:
        df = pd.DataFrame.from_dict(
            {'calendar': [''], 'summary': [''], 'start': [''], 'end': ['']})
        service = build('calendar', 'v3', credentials=creds)

        # Calls the calendar API
        now_utc = datetime.datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
        page_token = None
        calendar_list = service.calendarList().list(pageToken=page_token).execute()

        for calendar_list_entry in calendar_list['items']:
            personal_calendars = [
                'Uni - .*', 'liamgraneri71@gmail.com', 'Family'
            ]
            matches = [True if re.match(
                x, calendar_list_entry['summary']) else False for x in personal_calendars]
            # If calendar is identified as a personal calendar
            if True in matches:
                events = get_future_events(
                    service, calendar_list_entry, 3, now_utc)
                if events != []:
                    df = pd.concat([df, log_events(
                        events, calendar_list_entry['summary'])])
            # If calendar identifies as external (generally a booking calendar)
            else:
                events = get_future_events(
                    service, calendar_list_entry, 10, now_utc)
                if events != []:
                    df = pd.concat([df, log_events(
                        events, calendar_list_entry['summary'], work=True)])

        # Sorting events_df for Output
        # Removes unnecessary info (empty vals/irrelevant cols)
        df = df.loc[(df['start'] != '') & (df['start'].str.contains('\d', regex=True))][[
            'calendar', 'summary', 'start', 'end']].reset_index(drop=True)
        # Reformats time information into datetime to get duration
        for col in ['start', 'end']:
            # Extracts date and creates string output format column
            df[f'{col}_date'] = pd.to_datetime(df[col].apply(lambda x: re.search(
                '\D*([\d-]*)\D*', x).groups()[0] if re.search('\D*([\d-]*)\D*', x) != None else None))
            df[f'{col}_date_string'] = df[f'{col}_date'].dt.strftime(
                "%d-%m-%Y")
            # Extracts time and creates string output format column
            df[f'{col}_time'] = df[col].apply(lambda x: re.search(
                '\dT([\d:]*)', x).groups()[0] if re.search('\dT([\d:]*)', x) != None else None)
            df[f'{col}_time'] = pd.to_datetime(
                df[f'{col}_date_string'] + " " + df[f'{col}_time'])
            df[f'{col}_time_string'] = df[f'{col}_time'].dt.strftime(
                "%I:%M %p")
        # Calculates event duration
        df = df.dropna(subset=['start_time'])
        df['duration_hours'] = df['end_time'] - df['start_time']
        df['duration_hours'] = df['duration_hours'].dt.components['hours'] + \
            (df['duration_hours'].dt.components['minutes'] / 60)

        df = df.append({'summary': 'last_updated',
                       'start_time': now}, ignore_index=True)
        df.to_csv(
            '/home/liam/.config/waybar/scripts/google-calendar-widget/schedule.csv')
        return tooltip_output(df), df

    except HttpError as error:
        print(f'An error occurred: {error}')


# Calls notification daemon if start time is more or less now
def notify_current_event(t_minus, schedule, now, header):
    schedule['start_time'] = pd.to_datetime(schedule['start_time'])
    # 30s as the script is repeated every minute
    s30 = datetime.timedelta(seconds=30)
    delta = datetime.timedelta(minutes=t_minus)
    start_soon = (schedule['start_time'] <= (
        now - delta + s30)) & (schedule['start_time'] >= (now - delta - s30))
    upcoming_event = schedule.loc[start_soon]
    if len(upcoming_event) > 0:
        for event in sorted(upcoming_event['summary'].unique()):
            event_time = upcoming_event.loc[upcoming_event['summary']
                                            == event]['start_time_string'].iloc[0]
            event_calendar = upcoming_event.loc[upcoming_event['start_time_string']
                                                == event]['calendar'].iloc[0]
            s.call(['notify-send', '-i', '/home/liam/Pictures/google_calendar_logo.png',
                   '-p', f'{header} - {event_calendar}', f'{event}: {event}'])


def notify_next_event(now, schedule):
    schedule['start_time'] = pd.to_datetime(schedule['start_time'])
    after_now = schedule.loc[schedule['start_time'] > now].copy()
    next_event = after_now.loc[after_now['start_time']
                               == after_now['start_time'].min()].copy()
    event_title = next_event['summary'].iloc[0]
    event_start_time = next_event['start_time_string'].iloc[0]
    event_start_date = next_event['start_date_string'].iloc[0]
    event_calendar = next_event['calendar'].iloc[0]
    s.run(['notify-send', '-i', '/home/liam/.config/waybar/scripts/google-calendar-widget/google_calendar_logo.png', '-t', '4000',
          '-p', f'Next Event - {event_calendar}', f' --- {event_start_date} --- \n{event_start_time}: {event_title}'])
    print(
        f'Next Event:\n--- {event_start_date} ---\n{event_start_time}: {event_title}')


def main():
    now = datetime.datetime.now()
    schedule_path = '/home/liam/.config/waybar/scripts/google-calendar-widget/schedule.csv'
    if os.path.exists(schedule_path):
        schedule = pd.read_csv(schedule_path)
        last_updated = pd.to_datetime(
            schedule.loc[schedule['summary'] == 'last_updated']['start_time'].iloc[0])
        h1 = datetime.timedelta(hours=1)
        if last_updated > (now - h1):
            final_output = tooltip_output(schedule)
        else:
            final_output, schedule = update_events(now)
    else:
        final_output, schedule = update_events(now)
    if '--show_next' in sys.argv:
        notify_next_event(now, schedule)

    notify_current_event(5, schedule, now, '5 Minute Reminder')
    notify_current_event(0, schedule, now, 'Event Starting Now')
    return final_output


main()

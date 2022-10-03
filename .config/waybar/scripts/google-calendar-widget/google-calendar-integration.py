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

now = datetime.datetime.now()
now_utc = datetime.datetime.utcnow().isoformat() + "Z"


class CalendarObj:
    def __init__(self, api, cal_dict, n_results, work):
        self.api = api
        self.cal_dict = cal_dict
        self.n_results = n_results
        self.work = work
        self.id_no = cal_dict.get('id')
        self.name = cal_dict.get('summary')

    def get_events(self):
        events = self.api.events().list(calendarId=self.id_no, timeMin=now_utc,
                                        maxResults=self.n_results, singleEvents=True, orderBy='startTime').execute().get('items')
        if not events:
            return None

        event_details = {'summary': [], 'start': [], 'end': []}

        for event in events:
            if (self.work) and ('liam' not in event['summary'].lower()):
                continue
            event_details['summary'].append(event['summary'])
            for time in ['start', 'end']:
                for key in event[time].keys():
                    if 'date' in key:
                        event_details[time].append(event[time][key])
                        break
        events_df = pd.DataFrame.from_dict(event_details)
        events_df['calendar'] = self.name
        events_df.loc[events_df['summary'] == 'liam', 'summary'] = self.name
        events_df = events_df.dropna(subset=['start'])
        return events_df


def tooltip_output(df):
    # Formats output for custom waybar widget tooltip
    df = df.loc[df['summary'] != 'last_updated'].copy()
    df['start_dt'] = pd.to_datetime(df['start_dt'])
    df = df.sort_values('start_dt').reset_index(drop=True)
    # Custom outputs are newline separated, the intital string will be used for main bar text
    output_string = '\n'
    for date in df['start_date'].unique():
        # Subsequent string is used for tooltip (\r is used instead of newline within this string)
        output_string += f'--- {date} ---\r'
        date_df = df.loc[df['start_date'] == date]
        for event in date_df['summary'].unique():
            time = date_df.loc[date_df['summary']
                               == event]['start_time'].iloc[0]
            duration = date_df.loc[date_df['summary']
                                   == event]['duration'].iloc[0]
            duration_str = f' ({duration}h)' if pd.notna(duration) else ''
            output_string += f'{time}:  {event}{duration_str}\r'
        output_string += '\r'
    output_string = output_string.strip('\r')
    print(output_string)
    return output_string


def get_auth():
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
    return creds


def update_events():
    creds = get_auth()
    df = pd.DataFrame.from_dict(
        {'calendar': [''], 'summary': [''], 'start': [''], 'end': ['']})
    service = build('calendar', 'v3', credentials=creds)

    # Calls the calendar API
    personal_calendars = ['Uni -.*', '.*@gmail.com', 'Family']
    calendar_list = service.calendarList().list().execute()
    df_exists = False
    for calendar_list_entry in calendar_list['items']:
        calendar = CalendarObj(
            service, calendar_list_entry, n_results=3, work=False)
        calendar.work = True not in [True if re.match(
            x, calendar.name) else False for x in personal_calendars]
        calendar.n_results = 5 if calendar.work else 10
        if not df_exists:
            events = calendar.get_events()
            df_exists = True
        else:
            events = pd.concat([events, calendar.get_events()])

    # Removes unnecessary info (empty vals/irrelevant cols)
    time_regex = '(\d\d\d\d)-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)'
    date_regex = '(\d\d\d\d)-(\d\d)-(\d\d)'
    regex_groups = ['year', 'month', 'day', 'hour', 'minute', 'second']

    for moment in ['start', 'end']:
        moment_df = events[['summary', moment]]
        for group, time_obj in enumerate(regex_groups):
            if group < 3:
                moment_df[time_obj] = pd.to_numeric(moment_df[moment].apply(
                    lambda x: re.search(date_regex, x).groups()[group] if re.match(date_regex, x) else None))
            else:
                moment_df[time_obj] = pd.to_numeric(moment_df[moment].apply(
                    lambda x: re.search(time_regex, x).groups()[group] if re.match(time_regex, x) else None))

        moment_df = moment_df.drop(columns=(['summary', moment]))
        events[f'{moment}_dt'] = pd.to_datetime(moment_df)
        events.loc[events[f'{moment}_dt'].isna(), f'{moment}_dt'] = pd.to_datetime(
            moment_df.loc[moment_df['hour'].isna()][['year', 'month', 'day']])
        events[f'{moment}_date'] = events[f'{moment}_dt'].dt.strftime(
            '%e-%m-%Y')
        events[f'{moment}_time'] = events[f'{moment}_dt'].dt.strftime(
            '%I:%M %p')
    events['duration'] = ((events['end_dt'] - events['start_dt']
                           ).astype('timedelta64[m]'))/60
    events.loc[events['duration'] == 24, 'duration'] = None
    events = events.sort_values('start_dt').reset_index(drop=True)
    events = events.drop_duplicates(subset=['summary'])
    events = events.append(
        {'summary': 'last_updated', 'start_dt': now}, ignore_index=True)
    events.to_csv(
        '/home/liam/.config/waybar/scripts/google-calendar-widget/schedule.csv')
    return events


# Calls notification daemon if start time is more or less now
def notify_current_event(t_minus, schedule, header):
    schedule = schedule.loc[schedule['summary'] != 'last_updated']
    schedule['start_dt'] = pd.to_datetime(schedule['start_dt'])
    # 30s as the script is repeated every minute
    s30 = datetime.timedelta(seconds=30)
    delta = datetime.timedelta(minutes=t_minus)
    start_soon = (schedule['start_dt'] <= (
        now + delta + s30)) & (schedule['start_dt'] >= (now + delta - s30))
    upcoming_event = schedule.loc[start_soon]
    if len(upcoming_event) > 0:
        for event in sorted(upcoming_event['summary'].unique()):
            time = upcoming_event.loc[upcoming_event['summary']
                                      == event]['start_time'].iloc[0]
            calendar = upcoming_event.loc[upcoming_event['summary']
                                          == event]['calendar'].iloc[0]
            s.call(['notify-send', '-i', '/home/liam/Pictures/google_calendar_logo.png',
                   '-p', f'{header}: {calendar}', f'{time}: {event}'])


def notify_next_event(schedule):
    schedule['start_dt'] = pd.to_datetime(schedule['start_dt'])
    schedule = schedule.loc[schedule['duration'].notna()]
    df = schedule.loc[schedule['start_dt'] > now]
    df = df.loc[df['start_dt'] == df['start_dt'].min()]
    event_details = {}
    for detail in ['summary', 'calendar', 'start_date', 'start_time', 'duration']:
        event_details[detail] = df[detail].iloc[0]
    s.run(['notify-send', '-i', '/home/liam/.config/waybar/scripts/google-calendar-widget/google_calendar_logo.png', '-t', '4000',
          '-p', f'Next Event:\n --- {event_details["start_date"]} --- ', f'{event_details["start_time"]}: {event_details["summary"]} ({event_details["duration"]}h)'])


def main():
    schedule_path = '/home/liam/.config/waybar/scripts/google-calendar-widget/schedule.csv'
    if os.path.exists(schedule_path):
        schedule = pd.read_csv(schedule_path)
        last_updated = pd.to_datetime(
            schedule.loc[schedule['summary'] == 'last_updated']['start_dt'].iloc[0])
        if last_updated <= (now - datetime.timedelta(hours=1)):
            schedule = update_events()
    else:
        schedule = update_events()

    final_output = tooltip_output(schedule)

    schedule_only_events = schedule.loc[schedule['summary'] != 'last_updated'].copy(
    )
    if '--show_next' in sys.argv:
        notify_next_event(schedule_only_events)

    notify_current_event(5, schedule_only_events, '5 Minute Reminder')
    notify_current_event(0, schedule_only_events, 'Event Starting Now')
    return final_output


main()

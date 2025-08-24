import yaml
import datetime
import pandas as pd
import holidays
from collections import Counter

def load_config(yaml_path):
    with open(yaml_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)


def daterange(start_date, end_date):
    for n in range((end_date - start_date).days + 1):
        yield start_date + datetime.timedelta(n)


def get_working_days(start_date, end_date, country='FR'):
    fr_holidays = holidays.country_holidays(country)
    working_days, holiday_days = [], []
    for day in daterange(start_date, end_date):
        if day.weekday() < 5:
            if day in fr_holidays:
                holiday_days.append((day, fr_holidays[day]))
            else:
                working_days.append(day)
    return working_days, holiday_days


def schedule_to_dataframe(schedule):
    rows = []
    for date, assignments in sorted(schedule.items()):
        rows.append({
            "Date": date.strftime("%Y-%m-%d"),
            "Affectation 1": assignments[0] if len(assignments) > 0 else "",
            "Affectation 2": assignments[1] if len(assignments) > 1 else ""
        })
    return pd.DataFrame(rows)


def schedule_summary(schedule):
    affectations = list(schedule["Affectation 1"]) + list(schedule["Affectation 2"])
    count = Counter(affectations)
    summary = pd.DataFrame(list(count.items()), columns=['Lieu', 'Nombre vacations'])
    return summary.sort_values(by='Nombre vacations', ascending=False)

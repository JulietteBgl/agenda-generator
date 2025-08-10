import yaml
import random
import datetime
from collections import defaultdict
import pandas as pd
import holidays

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


def is_available(person_cfg, date):
    weekday = date.weekday()
    return (
        str(date) not in person_cfg.get('holidays', []) and
        weekday in person_cfg.get('available_weekdays', list(range(5)))
    )


def choose_person_balanced(people_cfg, date, assigned_days, target_days):
    available = [p for p, cfg in people_cfg.items()
                 if is_available(cfg, date) and assigned_days[p] < target_days[p]]
    if not available:
        return None
    available.sort(key=lambda p: assigned_days[p])
    return available[0]


def allocate_days(config, working_days):
    total_slots = len(working_days) * 2
    demand = {k: v['nb_radiologists'] * 9 for k, v in config.items()}
    total_demand = sum(demand.values())
    slots_by_place = {k: round(d / total_demand * total_slots) for k, d in demand.items()}

    slots = [place for place, count in slots_by_place.items() for _ in range(count)]
    random.shuffle(slots)

    schedule = defaultdict(list)
    day_index = 0
    advanced_assignments = {}
    target_days_by_person = {}

    for place, cfg in config.items():
        if cfg.get("advanced_split"):
            people = cfg['people']
            total = slots_by_place[place]
            base = total // len(people)
            extra = total % len(people)
            target_days_by_person[place] = {
                p: base + (1 if i < extra else 0)
                for i, p in enumerate(people)
            }
            advanced_assignments[place] = defaultdict(int)

    for i in range(0, len(slots) - 1, 2):
        if day_index >= len(working_days):
            break
        day = working_days[day_index]
        loc1, loc2 = slots[i], slots[i + 1]
        if loc1 == loc2:
            continue

        def format_slot(place_key):
            cfg = config[place_key]
            if cfg.get("advanced_split"):
                person = choose_person_balanced(
                    cfg['people'], day,
                    advanced_assignments[place_key],
                    target_days_by_person[place_key]
                )
                if person:
                    advanced_assignments[place_key][person] += 1
                    return f"{cfg['name']} - {person}"
                else:
                    return f"{cfg['name']} - ??"
            return cfg['name']

        schedule[day].extend([
            format_slot(loc1),
            format_slot(loc2)
        ])
        day_index += 1

    return schedule


def schedule_to_dataframe(schedule):
    rows = []
    for date, assignments in sorted(schedule.items()):
        rows.append({
            "Date": date.strftime("%Y-%m-%d"),
            "Affectation 1": assignments[0] if len(assignments) > 0 else "",
            "Affectation 2": assignments[1] if len(assignments) > 1 else ""
        })
    return pd.DataFrame(rows)

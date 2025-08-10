import yaml
import datetime
import pandas as pd
import holidays

from collections import defaultdict
from math import floor

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
    schedule = defaultdict(list)

    # 1) Quotas finaux par Largest Remainder (sur nb_radiologists)
    weights = {k: max(0, int(v.get('nb_radiologists', 0))) for k, v in config.items()}
    total_w = sum(weights.values())
    if total_w == 0:
        return schedule

    raw = {k: weights[k] / total_w * total_slots for k in config}
    base = {k: floor(raw[k]) for k in config}
    assigned = sum(base.values())
    remainder = total_slots - assigned
    for k, _ in sorted(((k, raw[k] - base[k]) for k in config),
                       key=lambda x: (-x[1], x[0])):
        if remainder <= 0:
            break
        base[k] += 1
        remainder -= 1
    quotas = base

    # 2) SWRR pour générer une séquence de sites (longueur = total_slots)
    eff_weights = quotas.copy()
    total_eff_w = sum(eff_weights.values())
    current = {k: 0 for k in config}
    remaining = quotas.copy()

    seq = []
    while len(seq) < total_slots:
        # incrémente les scores pour ceux qui restent
        for k in remaining:
            if remaining[k] > 0:
                current[k] += eff_weights.get(k, 0)
        # choisit le meilleur
        candidates = [k for k in remaining if remaining[k] > 0]
        if not candidates:
            break
        best = max(candidates, key=lambda k: (current[k], k))  # stable
        current[best] -= total_eff_w
        remaining[best] -= 1
        seq.append(best)

    # 3) Prépare l’équilibrage par personne (advanced_split)
    advanced_assignments = {}
    target_days_by_person = {}
    for place, cfg in config.items():
        if cfg.get("advanced_split"):
            people = cfg.get('people', {})
            total = quotas.get(place, 0)
            if total > 0 and people:
                base_p = total // len(people)
                extra = total % len(people)
                target_days_by_person[place] = {
                    p: base_p + (1 if i < extra else 0)
                    for i, p in enumerate(people)
                }
                advanced_assignments[place] = defaultdict(int)

    def format_slot(place_key, day):
        cfg = config[place_key]
        if cfg.get("advanced_split"):
            person = choose_person_balanced(
                cfg['people'], day,
                advanced_assignments.get(place_key, defaultdict(int)),
                target_days_by_person.get(place_key, {})
            )
            if person:
                advanced_assignments[place_key][person] += 1
                return f"{cfg['name']} - {person}"
            else:
                return f"{cfg['name']} - ??"
        return cfg['name']

    # 4) Compose les jours (2 créneaux/jour), en forçant pair_same_day si possible
    idx = 0
    for day in working_days:
        if idx >= len(seq):
            break

        first = seq[idx]; idx += 1
        second = None

        if config[first].get("pair_same_day", False):
            # Cherche la prochaine occurrence de `first` et l'avance pour la paire
            j = idx
            while j < len(seq) and seq[j] != first:
                j += 1
            if j < len(seq):
                # Avance cette occurrence à la position 'idx'
                seq.pop(j)
                second = first
            # sinon: pas d'autre slot pour ce site -> on prendra le next normal

        if second is None:
            if idx < len(seq):
                second = seq[idx]; idx += 1

        schedule[day].append(format_slot(first, day))
        if second is not None:
            schedule[day].append(format_slot(second, day))

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

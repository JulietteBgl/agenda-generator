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

def _people_names(people_cfg):
    return list(people_cfg.keys()) if isinstance(people_cfg, dict) else list(people_cfg)


def _is_available(person_name, day, people_cfg):
    """Check if a person is available on a given date."""
    cfg = people_cfg.get(person_name, {}) if isinstance(people_cfg, dict) else {}

    if isinstance(day, int):
        return True

    weekday = day.weekday()
    day_str = day.strftime("%Y-%m-%d")

    return (
            day_str not in cfg.get('holidays', []) and
            weekday in cfg.get('available_weekdays', list(range(5)))
    )


def allocate_days(config, working_days):
    total_slots = len(working_days) * 2
    schedule = defaultdict(list)
    if total_slots <= 0:
        return schedule

    # Quotas via Largest Remainder
    weights = {k: max(0, int(v.get('nb_radiologists', 0))) for k, v in config.items()}
    total_w = sum(weights.values())
    if total_w == 0:
        return schedule

    raw = {k: weights[k] / total_w * total_slots for k in config}
    base = {k: floor(raw[k]) for k in config}
    remainder = total_slots - sum(base.values())
    for k, _ in sorted(((k, raw[k] - base[k]) for k in config), key=lambda x: (-x[1], x[0])):
        if remainder <= 0: break
        base[k] += 1;
        remainder -= 1
    quotas = base

    # Génère une séquence lissée de sites (SWRR) de longueur = total_slots
    eff_w = quotas.copy()
    total_eff_w = sum(eff_w.values())
    current = {k: 0 for k in config}
    remaining = quotas.copy()
    seq = []
    while len(seq) < total_slots:
        for k in remaining:
            if remaining[k] > 0:
                current[k] += eff_w.get(k, 0)
        cands = [k for k in remaining if remaining[k] > 0]
        if not cands: break
        best = max(cands, key=lambda k: (current[k], k))
        current[best] -= total_eff_w
        remaining[best] -= 1
        seq.append(best)

    # Compteurs pour l'équilibrage des médecins
    counts = defaultdict(lambda: defaultdict(int))  # counts[place][person]
    last_used = defaultdict(lambda: defaultdict(lambda: -10 ** 9))  # last_used[place][person]

    def pick_person(place_key, day_obj, day_idx, exclude=None):
        cfg = config[place_key]
        people_cfg = cfg.get('people', {})
        names = _people_names(people_cfg)
        if not names:
            return None

        excl = set(exclude or [])
        candidates = [p for p in names if p not in excl and _is_available(p, day_obj, people_cfg)]
        if not candidates:
            # si tout le monde est exclu/indispo, on retire l'exclusion
            candidates = [p for p in names if _is_available(p, day_obj, people_cfg)]
            if not candidates:
                candidates = names  # dernier recours: tout le monde

        # Tri par (nb affectations croissant, ancienneté, nom)
        candidates.sort(key=lambda p: (counts[place_key][p], last_used[place_key][p], p))
        chosen = candidates[0]
        counts[place_key][chosen] += 1
        last_used[place_key][chosen] = day_idx
        return chosen

    def format_site_plus_person(place_key, day_obj, day_idx, exclude_person=None):
        cfg = config[place_key]
        if cfg.get("advanced_split"):
            person = pick_person(place_key, day_obj, day_idx, exclude=exclude_person)
            if person:
                return f"{cfg['name']} - {person}"
            return f"{cfg['name']} - ??"
        return cfg['name']

    # Compose les jours (2 créneaux/jour) avec pair_same_day strict
    idx = 0
    for day_idx, day in enumerate(working_days):
        if idx >= len(seq): break
        first_site = seq[idx];
        idx += 1

        # Tenter d'avoir le même site si pair_same_day
        if config[first_site].get("pair_same_day", False):
            j = idx
            while j < len(seq) and seq[j] != first_site:
                j += 1
            if j < len(seq):
                seq.pop(j)
                second_site = first_site
            else:
                second_site = seq[idx] if idx < len(seq) else None
                if second_site is not None: idx += 1
        else:
            second_site = seq[idx] if idx < len(seq) else None
            if second_site is not None: idx += 1

        # Affectations (évite le même médecin 2x si possible)
        if second_site == first_site and config[first_site].get("advanced_split"):
            names = _people_names(config[first_site].get('people', {}))
            s1 = format_site_plus_person(first_site, day, day_idx, exclude_person=None)
            chosen1 = s1.split(" - ", 1)[1] if " - " in s1 else None
            excl = set() if len(names) == 1 else ({chosen1} if chosen1 else set())
            s2 = format_site_plus_person(first_site, day, day_idx, exclude_person=excl)
            schedule[day].extend([s1, s2])
        else:
            s1 = format_site_plus_person(first_site, day, day_idx, exclude_person=None)
            schedule[day].append(s1)
            if second_site:
                s2 = format_site_plus_person(second_site, day, day_idx, exclude_person=None)
                schedule[day].append(s2)

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

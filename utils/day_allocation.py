import random
from collections import defaultdict
from math import floor


def allocate_days(config, working_days):
    list_paired_sites = [site for site in config if config[site]['pair_same_day']]
    total_slots = len(working_days) * 2
    print('Total slots to allocate:', total_slots)
    schedule = defaultdict(list)
    if total_slots <= 0:
        return schedule

    def site_is_available(place_key, day_obj):
        # check if a site is available on a specific day
        cfg = config[place_key]

        if not cfg.get("advanced_split"):
            return True

        weekday = day_obj.weekday()
        available_weekdays = cfg.get('available_weekdays', list(range(5)))
        day_str = day_obj.strftime("%Y-%m-%d")
        holidays = cfg.get('holidays', [])

        return weekday in available_weekdays and day_str not in holidays

    # Quotas via Largest Remainder
    weights = {k: max(0, int(v.get('nb_radiologists', 0))) for k, v in config.items()}
    total_w = sum(weights.values())
    if total_w == 0:
        return schedule

    raw = {k: weights[k] / total_w * total_slots for k in config}
    base = {k: floor(raw[k]) for k in config}
    remainder = total_slots - sum(base.values())

    for k, _ in sorted(((k, raw[k] - base[k]) for k in config), key=lambda x: (-x[1], x[0])):
        if remainder <= 0:
            break
        base[k] += 1
        remainder -= 1

    # Adjust quotas for pair_same_day sites - they should have an even number of slots
    quotas = base.copy()
    for site in list_paired_sites:
        if quotas[site] % 2 == 1:  # Si impair
            quotas[site] += 1  # Rendre pair

    # Distribute lost slots to un-even sites
    lost_slots = sum(quotas.values()) - total_slots
    non_pair_sites = [k for k in config if not config[k].get("pair_same_day", False)]
    i = 0
    while lost_slots > 0 and non_pair_sites:
        if quotas[non_pair_sites[i % len(non_pair_sites)]] > 1:
            quotas[non_pair_sites[i % len(non_pair_sites)]] -= 1
            lost_slots -= 1
        i += 1
        if i > len(non_pair_sites) * 10:
            break

    late_sites = [site for site in quotas if not quotas[site] % 10 == 0 and site[:4].lower() != "majo"]
    if not late_sites:
        late_sites = ['']

    # Use SWRR to create a sequence
    eff_w = quotas.copy()
    total_eff_w = sum(eff_w.values())
    current = {k: 0 for k in config}
    remaining = quotas.copy()
    seq = []
    while len(seq) < sum(quotas.values()):
        for k in remaining:
            if remaining[k] > 0:
                current[k] += eff_w.get(k, 0)
        cands = [k for k in remaining if remaining[k] > 0]
        if not cands: break
        best = max(cands, key=lambda k: (current[k], k))
        current[best] -= total_eff_w
        remaining[best] -= 1
        seq.append(best)

    # Create days distribution
    for day in working_days:
        if len(seq) == 0:
            print(f"No more slots available for day {day}")
            break

        first_site = None
        idx_first = None
        for i, site in enumerate(seq):
            if site_is_available(site, day):
                first_site = site
                idx_first = i
                break

        if first_site is not None:

            # Remove first site from sequence
            seq.pop(idx_first)

            # Manage second site
            second_site = None
            if config[first_site].get("pair_same_day", False):
                for i, site in enumerate(seq):
                    if site == first_site:
                        second_site = site
                        seq.pop(i)
                        break

                if second_site is None:
                    print(f"Warning: no more occurence of {first_site} found")
                    second_site = first_site  # Fallback
            else:
                idx_second = None
                for i, site in enumerate(seq):
                    if (site[:9] != first_site[:9] and
                            site not in list_paired_sites and
                            site_is_available(site, day)):
                        second_site = site
                        idx_second = i
                        break

                if idx_second is not None:
                    seq.pop(idx_second)
                else:
                    second_site = random.choice(late_sites)

        else:
            first_site = second_site = None

        # Affectations
        assignments = []
        if first_site:
            assignments.append(config[first_site]['name'])
        else:
            assignments.append(None)
        if second_site:
            assignments.append(config[second_site]['name'])
        else:
            assignments.append(None)
        schedule[day] = assignments

    return schedule
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

    def get_site_key_from_name(site_name):
        for key, cfg in config.items():
            if cfg['name'] == site_name:
                return key
        return None

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

    # Backfilling phase: redistribute remaining sites in seq
    print("\n=== Backfilling stage===")
    print(f"Remaining sites in seq: {len(seq)}")

    # Count None for each date
    none_counts = {day: schedule[day].count(None) for day in schedule}
    days_with_none = [day for day in schedule if none_counts[day] > 0]

    if days_with_none and seq:
        print(f"Number of days with None: {len(days_with_none)}")

        # For each remaining site in seq, find an exchange
        remaining_seq = seq.copy()

        for site_to_place in remaining_seq:
            print("remaining_seq", remaining_seq)
            print('site_to_place', site_to_place)
            if not site_to_place:
                continue

            print(f"\nTrying to place: {site_to_place} ({config[site_to_place]['name']})")

            # Find all days with None
            placed = False
            for problem_day in days_with_none:
                if placed:
                    break

                # Find the slot with None in problem_day
                for slot_idx in range(len(schedule[problem_day])):
                    if schedule[problem_day][slot_idx] is not None:
                        continue

                    swap_found = False
                    for swap_day in working_days:
                        if swap_found:
                            break
                        if swap_day >= problem_day:
                            continue

                        for swap_slot_idx in range(len(schedule[swap_day])):
                            site_name_to_swap = schedule[swap_day][swap_slot_idx]
                            if site_name_to_swap is None:
                                continue

                            site_key_to_swap = get_site_key_from_name(site_name_to_swap)
                            if site_key_to_swap is None:
                                continue

                            # Condition 1: site_to_swap must be available on problem_day (to fill the None)
                            if not site_is_available(site_key_to_swap, problem_day):
                                continue

                            # Condition 2: site_to_place must be available on swap_day (to replace site_to_swap)
                            if not site_is_available(site_to_place, swap_day):
                                continue

                            # Check pair_same_day constraints for site_to_swap
                            if config[site_key_to_swap].get("pair_same_day", False):
                                if schedule[swap_day].count(site_name_to_swap) != 2:
                                    continue

                            # Check constraints on problem_day for site_to_swap
                            other_slot_idx = 1 - slot_idx
                            other_site_name = schedule[problem_day][other_slot_idx]

                            valid_on_problem = True
                            if config[site_key_to_swap].get("pair_same_day", False):
                                if other_site_name is not None and other_site_name != site_name_to_swap:
                                    valid_on_problem = False
                            else:
                                if other_site_name == site_name_to_swap:
                                    valid_on_problem = False
                                other_site_key = get_site_key_from_name(other_site_name) if other_site_name else None
                                if other_site_key and site_key_to_swap[:9] == other_site_key[:9]:
                                    valid_on_problem = False

                            if not valid_on_problem:
                                continue

                            # Check constraints on swap_day for site_to_place
                            swap_other_slot = 1 - swap_slot_idx
                            swap_other_site = schedule[swap_day][swap_other_slot]

                            valid_on_swap = True
                            if config[site_to_place].get("pair_same_day", False):
                                if swap_other_site != config[site_to_place]['name']:
                                    valid_on_swap = False
                            else:
                                if swap_other_site == config[site_to_place]['name']:
                                    valid_on_swap = False
                                swap_other_key = get_site_key_from_name(swap_other_site) if swap_other_site else None
                                if swap_other_key and site_to_place[:9] == swap_other_key[:9]:
                                    valid_on_swap = False

                            if not valid_on_swap:
                                continue

                            # Make the exchange!
                            print(f"  Exchange found:")
                            print(f"    - {config[site_to_place]['name']} to {swap_day.strftime('%Y-%m-%d')}")
                            print(
                                f"    - {site_name_to_swap} from {swap_day.strftime('%Y-%m-%d')} to {problem_day.strftime('%Y-%m-%d')}")

                            schedule[problem_day][slot_idx] = site_name_to_swap
                            schedule[swap_day][swap_slot_idx] = config[site_to_place]['name']

                            seq.remove(site_to_place)
                            swap_found = True
                            placed = True
                            break

                    if placed:
                        break

            if not placed:
                print(f"  ⚠️ Unable to place {config[site_to_place]['name']}")

    final_none_counts = {day: schedule[day].count(None) for day in working_days}
    total_none = sum(final_none_counts.values())
    print(f"\n=== Final result: {total_none} remaining None, {len(seq)} unassigned sites in seq ===")

    return schedule
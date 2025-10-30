from collections import defaultdict
from math import floor
import random


def allocate_majorelle_fridays(majorelle_sites, working_days):
    """
    Pré-alloue les vendredis pour les sites Majorelle
    Chaque site doit avoir exactement 4 vendredis par trimestre
    """
    fridays = [day for day in working_days if day.weekday() == 4]  # 4 = vendredi
    friday_allocation = {}

    if not majorelle_sites or not fridays:
        return friday_allocation

    # Vérifier qu'on a assez de vendredis (au moins 12 pour 3 sites * 4 vendredis)
    total_fridays_needed = len(majorelle_sites) * 4
    if len(fridays) < total_fridays_needed:
        print(f"Warning: Not enough Fridays ({len(fridays)}) for Majorelle sites (need {total_fridays_needed})")
        return friday_allocation

    # Diviser les vendredis en groupes pour assurer une distribution équilibrée
    # On divise en 4 périodes pour assurer que chaque site ait des vendredis répartis
    period_size = len(fridays) // 4
    periods = []
    for i in range(4):
        start_idx = i * period_size
        if i == 3:  # Dernière période prend les vendredis restants
            periods.append(fridays[start_idx:])
        else:
            periods.append(fridays[start_idx:start_idx + period_size])

    # Allouer un vendredi de chaque période à chaque site
    for site in majorelle_sites:
        friday_allocation[site] = []
        for period in periods:
            if period:
                # Choisir un vendredi de cette période qui n'est pas encore alloué
                available = [f for f in period if not any(f in friday_allocation[s] for s in friday_allocation)]
                if available:
                    chosen = available[0]  # On pourrait randomiser ici si souhaité
                    friday_allocation[site].append(chosen)

    return friday_allocation


def allocate_days(config, working_days):
    list_paired_sites = [site for site in config if config[site]['pair_same_day']]
    total_slots = len(working_days) * 2
    print('Total slots to allocate:', total_slots)
    schedule = defaultdict(list)
    if total_slots <= 0:
        return schedule

    # Pré-allouer les vendredis pour les sites Majorelle
    majorelle_sites = [k for k in config if k.startswith('majorelle_')]
    friday_allocation = allocate_majorelle_fridays(majorelle_sites, working_days)

    # Tracker pour les vendredis Majorelle déjà utilisés
    majorelle_friday_used = {site: 0 for site in majorelle_sites}

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

        # Vérifier si c'est un vendredi et si on doit placer un site Majorelle
        is_friday = day.weekday() == 4
        majorelle_for_today = None

        if is_friday:
            # Vérifier si un site Majorelle doit être placé ce vendredi
            for site in majorelle_sites:
                if site in friday_allocation and day in friday_allocation[site]:
                    if majorelle_friday_used[site] < 4:  # Limite de 4 vendredis
                        majorelle_for_today = site
                        majorelle_friday_used[site] += 1
                        break

        first_site = None
        idx_first = None

        # Si on a un site Majorelle à placer ce vendredi, le prioriser
        if majorelle_for_today and majorelle_for_today in seq:
            # Trouver l'index du site Majorelle dans seq
            for i, site in enumerate(seq):
                if site == majorelle_for_today:
                    first_site = site
                    idx_first = i
                    break

        # Sinon, procéder normalement
        if first_site is None:
            for i, site in enumerate(seq):
                # Éviter de placer un site Majorelle le vendredi s'il a déjà ses 4 vendredis
                if is_friday and site in majorelle_sites:
                    if majorelle_friday_used.get(site, 0) >= 4:
                        continue

                if site_is_available(site, day):
                    first_site = site
                    idx_first = i

                    # Si c'est un vendredi et un site Majorelle, compter
                    if is_friday and site in majorelle_sites:
                        majorelle_friday_used[site] = majorelle_friday_used.get(site, 0) + 1
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
            else:
                idx_second = None
                for i, site in enumerate(seq):
                    # Éviter de placer un autre site Majorelle le vendredi s'il a déjà ses 4 vendredis
                    if is_friday and site in majorelle_sites:
                        if majorelle_friday_used.get(site, 0) >= 4:
                            continue

                    if (site[:9] != first_site[:9] and
                            site not in list_paired_sites and
                            site_is_available(site, day)):
                        second_site = site
                        idx_second = i

                        # Si c'est un vendredi et un site Majorelle, compter
                        if is_friday and site in majorelle_sites:
                            majorelle_friday_used[site] = majorelle_friday_used.get(site, 0) + 1
                        break

                if idx_second is not None:
                    seq.pop(idx_second)
                else:
                    second_site = None

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

    # Afficher le compte de vendredis pour chaque site Majorelle
    print("\nVendredis alloués aux sites Majorelle avant backfilling:")
    for site in majorelle_sites:
        print(f"  {config[site]['name']}: {majorelle_friday_used.get(site, 0)} vendredis")

    # Count None for each date
    none_counts = {day: schedule[day].count(None) for day in schedule}
    days_with_none = [day for day in schedule if none_counts[day] > 0]

    if days_with_none and seq:
        print(f"Number of days with None: {len(days_with_none)}")
        print("Note: Durant le backfilling, les sites Majorelle peuvent avoir 3-5 vendredis (flexibilité ±1)")

        # For each remaining site in seq, find an exchange
        remaining_seq = seq.copy()

        for site_to_place in remaining_seq:
            print("remaining_seq", remaining_seq)
            print('site_to_place', site_to_place)
            if not site_to_place:
                continue

            print(f"\nTrying to place: {site_to_place} ({config[site_to_place]['name']})")

            # Si c'est un site Majorelle, afficher son compte actuel de vendredis
            if site_to_place in majorelle_sites:
                current_fridays = majorelle_friday_used.get(site_to_place, 0)
                print(f"  (Site Majorelle avec {current_fridays} vendredis actuellement)")

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

                            # MODIFICATION: Flexibilité pour les vendredis Majorelle durant le backfilling (3-5 vendredis OK)
                            if swap_day.weekday() == 4 and site_to_place in majorelle_sites:
                                # Permettre jusqu'à 5 vendredis durant le backfilling
                                if majorelle_friday_used.get(site_to_place, 0) >= 5:
                                    continue
                            if problem_day.weekday() == 4 and site_key_to_swap in majorelle_sites:
                                # Permettre jusqu'à 5 vendredis durant le backfilling
                                if majorelle_friday_used.get(site_key_to_swap, 0) >= 5:
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
                            print(
                                f"    - {config[site_to_place]['name']} to {swap_day.strftime('%Y-%m-%d')} ({'Vendredi' if swap_day.weekday() == 4 else 'autre jour'})")
                            print(
                                f"    - {site_name_to_swap} from {swap_day.strftime('%Y-%m-%d')} to {problem_day.strftime('%Y-%m-%d')} ({'Vendredi' if problem_day.weekday() == 4 else 'autre jour'})")

                            # Mettre à jour le compteur de vendredis si nécessaire
                            if swap_day.weekday() == 4 and site_to_place in majorelle_sites:
                                majorelle_friday_used[site_to_place] = majorelle_friday_used.get(site_to_place, 0) + 1
                                print(
                                    f"    → {config[site_to_place]['name']} a maintenant {majorelle_friday_used[site_to_place]} vendredis")
                            if problem_day.weekday() == 4 and site_key_to_swap in majorelle_sites:
                                majorelle_friday_used[site_key_to_swap] = majorelle_friday_used.get(site_key_to_swap,
                                                                                                    0) + 1
                                print(
                                    f"    → {config[site_key_to_swap]['name']} a maintenant {majorelle_friday_used[site_key_to_swap]} vendredis")

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

    # Phase de rééquilibrage des vendredis Majorelle
    print("\n=== Phase de rééquilibrage des vendredis Majorelle ===")

    # Compter les vendredis actuels pour chaque site Majorelle
    majorelle_friday_count = {}
    for site in majorelle_sites:
        count = 0
        for day in working_days:
            if day.weekday() == 4:  # Vendredi
                if config[site]['name'] in schedule[day]:
                    count += 1
        majorelle_friday_count[site] = count

    print("Compte initial des vendredis:")
    for site in majorelle_sites:
        print(f"  {config[site]['name']}: {majorelle_friday_count[site]} vendredis")

    # Identifier les sites hors limites
    sites_under = [site for site in majorelle_sites if majorelle_friday_count[site] < 3]

    # Essayer de rééquilibrer : prendre des vendredis pour les donner aux sites < 3
    if sites_under:
        print(f"\nSites Majorelle avec moins de 3 vendredis: {[config[s]['name'] for s in sites_under]}")

        for site_under in sites_under:
            while majorelle_friday_count[site_under] < 3:
                exchange_done = False

                # PRIORITÉ 1: Chercher d'abord dans les sites NON-Majorelle
                non_majorelle_sites = [s for s in config.keys() if s not in majorelle_sites]

                print(f"\n  Tentative d'échange avec des sites NON-Majorelle pour {config[site_under]['name']}...")
                for donor_site in non_majorelle_sites:
                    if exchange_done:
                        break

                    # Trouver un vendredi du donneur et un non-vendredi du receveur pour échanger
                    for day in working_days:
                        if exchange_done:
                            break

                        # Chercher un vendredi où le donneur NON-Majorelle est présent
                        if day.weekday() == 4 and config[donor_site]['name'] in schedule[day]:
                            donor_slot = schedule[day].index(config[donor_site]['name'])

                            # Chercher un jour non-vendredi où le receveur (Majorelle) est présent
                            for swap_day in working_days:
                                if swap_day.weekday() != 4 and config[site_under]['name'] in schedule[swap_day]:
                                    receiver_slot = schedule[swap_day].index(config[site_under]['name'])

                                    # Vérifier que les deux peuvent échanger leurs jours
                                    if (site_is_available(site_under, day) and
                                            site_is_available(donor_site, swap_day)):

                                        # Vérifier les contraintes avec les autres affectations
                                        other_friday_slot = 1 - donor_slot
                                        other_swap_slot = 1 - receiver_slot

                                        friday_other = schedule[day][other_friday_slot]
                                        swap_other = schedule[swap_day][other_swap_slot]

                                        # Vérifier qu'on ne crée pas de conflits
                                        valid_exchange = True

                                        # Pas deux fois le même site
                                        if friday_other == config[site_under]['name']:
                                            valid_exchange = False
                                        if swap_other == config[donor_site]['name']:
                                            valid_exchange = False

                                        # Pas deux sites du même groupe ensemble
                                        friday_other_key = get_site_key_from_name(
                                            friday_other) if friday_other else None
                                        swap_other_key = get_site_key_from_name(swap_other) if swap_other else None

                                        if friday_other_key and site_under[:9] == friday_other_key[:9]:
                                            valid_exchange = False
                                        if swap_other_key and donor_site[:9] == swap_other_key[:9]:
                                            valid_exchange = False

                                        # Vérifier pair_same_day
                                        if config[donor_site].get("pair_same_day", False):
                                            if schedule[swap_day].count(config[donor_site]['name']) != 1:
                                                valid_exchange = False
                                        if config[site_under].get("pair_same_day", False):
                                            if schedule[day].count(config[site_under]['name']) != 1:
                                                valid_exchange = False

                                        if valid_exchange:
                                            print(f"\n✓ Rééquilibrage trouvé avec site NON-Majorelle:")
                                            print(
                                                f"  {config[donor_site]['name']} (NON-Majorelle)")
                                            print(
                                                f"    passe du vendredi {day.strftime('%Y-%m-%d')} au {swap_day.strftime('%Y-%m-%d')}")
                                            print(
                                                f"  {config[site_under]['name']} (Majorelle avec {majorelle_friday_count[site_under]} vendredis)")
                                            print(
                                                f"    passe du {swap_day.strftime('%Y-%m-%d')} au vendredi {day.strftime('%Y-%m-%d')}")

                                            # Faire l'échange
                                            schedule[day][donor_slot] = config[site_under]['name']
                                            schedule[swap_day][receiver_slot] = config[donor_site]['name']

                                            # Mettre à jour le compteur pour le site Majorelle
                                            majorelle_friday_count[site_under] += 1

                                            print(
                                                f"  Nouveau compte: {config[site_under]['name']}={majorelle_friday_count[site_under]} vendredis")

                                            exchange_done = True
                                            break

                # PRIORITÉ 2: Si pas d'échange trouvé avec les non-Majorelle, chercher dans les sites Majorelle (4-5 vendredis)
                if not exchange_done:
                    print(f"\n  Pas d'échange trouvé avec les NON-Majorelle, tentative avec les sites Majorelle...")
                    donor_candidates = [s for s in majorelle_sites if
                                        majorelle_friday_count[s] >= 4 and s != site_under]
                    donor_candidates.sort(
                        key=lambda s: -majorelle_friday_count[s])  # Prioriser ceux avec le plus de vendredis

                    for donor_site in donor_candidates:
                        if exchange_done:
                            break

                        # Trouver un vendredi du donneur et un non-vendredi du receveur pour échanger
                        for day in working_days:
                            if exchange_done:
                                break

                            # Chercher un vendredi où le donneur est présent
                            if day.weekday() == 4 and config[donor_site]['name'] in schedule[day]:
                                donor_slot = schedule[day].index(config[donor_site]['name'])

                                # Chercher un jour non-vendredi où le receveur est présent
                                for swap_day in working_days:
                                    if swap_day.weekday() != 4 and config[site_under]['name'] in schedule[swap_day]:
                                        receiver_slot = schedule[swap_day].index(config[site_under]['name'])

                                        # Vérifier que les deux peuvent échanger leurs jours
                                        if (site_is_available(site_under, day) and
                                                site_is_available(donor_site, swap_day)):

                                            # Vérifier les contraintes avec les autres affectations
                                            other_friday_slot = 1 - donor_slot
                                            other_swap_slot = 1 - receiver_slot

                                            friday_other = schedule[day][other_friday_slot]
                                            swap_other = schedule[swap_day][other_swap_slot]

                                            # Vérifier qu'on ne crée pas de conflits
                                            valid_exchange = True

                                            # Pas deux fois le même site
                                            if friday_other == config[site_under]['name']:
                                                valid_exchange = False
                                            if swap_other == config[donor_site]['name']:
                                                valid_exchange = False

                                            # Pas deux sites Majorelle ensemble
                                            friday_other_key = get_site_key_from_name(
                                                friday_other) if friday_other else None
                                            swap_other_key = get_site_key_from_name(swap_other) if swap_other else None

                                            if friday_other_key and site_under[:9] == friday_other_key[:9]:
                                                valid_exchange = False
                                            if swap_other_key and donor_site[:9] == swap_other_key[:9]:
                                                valid_exchange = False

                                            # Vérifier pair_same_day
                                            if config[donor_site].get("pair_same_day", False):
                                                if schedule[swap_day].count(config[donor_site]['name']) != 1:
                                                    valid_exchange = False
                                            if config[site_under].get("pair_same_day", False):
                                                if schedule[day].count(config[site_under]['name']) != 1:
                                                    valid_exchange = False

                                            if valid_exchange:
                                                print(f"\n✓ Rééquilibrage trouvé avec site Majorelle:")
                                                print(
                                                    f"  {config[donor_site]['name']} (donneur Majorelle avec {majorelle_friday_count[donor_site]} vendredis)")
                                                print(
                                                    f"    passe du vendredi {day.strftime('%Y-%m-%d')} au {swap_day.strftime('%Y-%m-%d')}")
                                                print(
                                                    f"  {config[site_under]['name']} (receveur Majorelle avec {majorelle_friday_count[site_under]} vendredis)")
                                                print(
                                                    f"    passe du {swap_day.strftime('%Y-%m-%d')} au vendredi {day.strftime('%Y-%m-%d')}")

                                                # Faire l'échange
                                                schedule[day][donor_slot] = config[site_under]['name']
                                                schedule[swap_day][receiver_slot] = config[donor_site]['name']

                                                # Mettre à jour les compteurs
                                                majorelle_friday_count[donor_site] -= 1
                                                majorelle_friday_count[site_under] += 1

                                                print(
                                                    f"  Nouveau compte: {config[donor_site]['name']}={majorelle_friday_count[donor_site]}, {config[site_under]['name']}={majorelle_friday_count[site_under]}")

                                                exchange_done = True
                                                break

                if not exchange_done:
                    print(
                        f"\n⚠ Impossible de rééquilibrer {config[site_under]['name']} (reste à {majorelle_friday_count[site_under]} vendredis)")
                    break

    # Vérification finale des vendredis Majorelle
    print("\n=== Vérification finale des vendredis Majorelle ===")
    print("Objectif: 4 vendredis par site (flexibilité 3-5 acceptée si nécessaire)")
    for site in majorelle_sites:
        count = 0
        for day in working_days:
            if day.weekday() == 4:  # Vendredi
                if config[site]['name'] in schedule[day]:
                    count += 1
        status = ""
        if count == 4:
            status = "✓ Objectif atteint"
        elif count in [3, 5]:
            status = "⚠ Acceptable (flexibilité)"
        else:
            status = "✗ Hors limites"
        print(f"{config[site]['name']}: {count} vendredis {status}")

    return schedule

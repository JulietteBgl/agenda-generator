from collections import defaultdict
from math import floor


def allocate_days(config, working_days):
    total_slots = len(working_days) * 2
    schedule = defaultdict(list)
    if total_slots <= 0:
        return schedule

    # Fonction pour vérifier si un site est disponible un jour donné
    def site_is_available(place_key, day_obj):
        cfg = config[place_key]
        if not cfg.get("advanced_split"):
            return True  # Sites simples toujours disponibles

        # Pour les sites advanced_split, vérifier les jours de disponibilité
        weekday = day_obj.weekday()
        available_weekdays = cfg.get('available_weekdays', list(range(5)))

        # Vérifier les congés (holidays)
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

    # Compose les jours (2 créneaux/jour) avec pair_same_day strict
    idx = 0
    for day_idx, day in enumerate(working_days):
        if idx >= len(seq): break

        # Vérifier que le premier site est disponible
        while idx < len(seq) and not site_is_available(seq[idx], day):
            idx += 1

        if idx >= len(seq): break

        first_site = seq[idx]
        idx += 1

        # Tenter d'avoir le même site si pair_same_day
        if config[first_site].get("pair_same_day", False):
            # Pour pair_same_day, on force le second site à être identique
            second_site = first_site
            # Mais on consomme quand même le prochain slot dans la séquence pour maintenir l'équilibre
            if idx < len(seq):
                idx += 1
        else:
            second_site = seq[idx] if idx < len(seq) else None
            if second_site is not None:
                # Vérifier que le second site est disponible
                while idx < len(seq) and not site_is_available(seq[idx], day):
                    idx += 1
                if idx < len(seq):
                    second_site = seq[idx]
                    idx += 1
                else:
                    second_site = None

        # Affectations
        assignments = []
        if first_site:
            assignments.append(config[first_site]['name'])
        if second_site:
            assignments.append(config[second_site]['name'])

        schedule[day] = assignments

    return schedule
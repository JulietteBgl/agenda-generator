from math import floor
from typing import Dict, List


class SequenceGenerator:
    """Compute quotas for each site and create the allocation sequence of sites with SWRR"""

    @staticmethod
    def calculate_quotas(config: Dict, total_slots: int) -> Dict[str, int]:
        """Compute quotas for each site depending on their weight with the Largest Remainder Method"""
        weights = {k: max(0, int(v.get('nb_radiologists', 0))) for k, v in config.items()}
        total_w = sum(weights.values())

        if total_w == 0:
            return {}

        raw = {k: weights[k] / total_w * total_slots for k in config}
        base = {k: floor(raw[k]) for k in config}
        remainder = total_slots - sum(base.values())

        for k, _ in sorted(((k, raw[k] - base[k]) for k in config),
                           key=lambda x: (-x[1], x[0])):
            if remainder <= 0:
                break
            base[k] += 1
            remainder -= 1

        return base

    @staticmethod
    def adjust_for_paired_sites(quotas: Dict[str, int], config: Dict,
                                total_slots: int) -> Dict[str, int]:
        adjusted = quotas.copy()
        list_paired_sites = [site for site in config if config[site]['pair_same_day']]

        for site in list_paired_sites:
            if adjusted[site] % 2 == 1:
                adjusted[site] += 1

        lost_slots = sum(adjusted.values()) - total_slots
        non_pair_sites = [site for site in config
                          if not config[site].get("pair_same_day", False)
                          and adjusted[site] % 2 == 0
                          and not site.lower().startswith("majo")
                          ]

        i = 0
        while lost_slots > 0 and non_pair_sites:
            if adjusted[non_pair_sites[i % len(non_pair_sites)]] > 1:
                adjusted[non_pair_sites[i % len(non_pair_sites)]] -= 1
                lost_slots -= 1
            i += 1
            if i > len(non_pair_sites) * 10:
                break

        return adjusted

    @staticmethod
    def generate_sequence(quotas: Dict[str, int], config: Dict) -> List[str]:
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
            if not cands:
                break

            best = max(cands, key=lambda k: (current[k], k))
            current[best] -= total_eff_w
            remaining[best] -= 1
            seq.append(best)

        return seq

from typing import Dict, List


class SequenceGenerator:
    """Create the allocation sequence of sites with SWRR"""

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

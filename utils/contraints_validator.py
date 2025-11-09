from typing import Dict, List, Optional


class ConstraintValidator:
    """Validate constraints"""

    def __init__(self, config: Dict):
        self.config = config
        self.list_paired_sites = [site for site in config if config[site]['pair_same_day']]

    def validate_second_site(self, first_site: str, second_site: str) -> bool:
        if not second_site or not first_site:
            return False

        if self.config[first_site].get("pair_same_day", False):
            return second_site == first_site

        if second_site == first_site:
            return False
        if second_site[:9] == first_site[:9]:
            return False
        if second_site in self.list_paired_sites:
            return False

        return True

    def validate_swap(self, site_to_place: str, site_to_swap: str,
                      problem_day_schedule: List[str], swap_day_schedule: List[str],
                      slot_idx: int, swap_slot_idx: int) -> bool:
        """Check if a swap is possible between 2 days"""
        other_slot_idx = 1 - slot_idx
        other_site_name = problem_day_schedule[other_slot_idx]

        if not self._validate_site_on_day(site_to_swap, other_site_name,
                                          problem_day_schedule):
            return False

        swap_other_slot = 1 - swap_slot_idx
        swap_other_site = swap_day_schedule[swap_other_slot]

        if not self._validate_site_on_day_by_key(site_to_place, swap_other_site):
            return False

        return True

    def _validate_site_on_day(self, site_name: str, other_site_name: str,
                              day_schedule: List[str]) -> bool:
        site_key = self._get_site_key_from_name(site_name)
        if not site_key:
            return False

        if self.config[site_key].get("pair_same_day", False):
            if day_schedule.count(site_name) == 2:
                return True
            if other_site_name == site_name or other_site_name is None:
                return True
            return False
        else:
            if other_site_name == site_name:
                return False
            other_site_key = self._get_site_key_from_name(other_site_name) if other_site_name else None
            if other_site_key and site_key[:9] == other_site_key[:9]:
                return False

        return True

    def _validate_site_on_day_by_key(self, site_key: str, other_site_name: str) -> bool:
        site_name = self.config[site_key]['name']

        if self.config[site_key].get("pair_same_day", False):
            if other_site_name != site_name:
                return False
        else:
            if other_site_name == site_name:
                return False
            other_site_key = self._get_site_key_from_name(other_site_name) if other_site_name else None
            if other_site_key and site_key[:9] == other_site_key[:9]:
                return False

        return True

    def _get_site_key_from_name(self, site_name: str) -> Optional[str]:
        for key, cfg in self.config.items():
            if cfg['name'] == site_name:
                return key
        return None

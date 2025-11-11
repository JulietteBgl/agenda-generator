from collections import defaultdict
from datetime import date
from typing import Dict, List, Optional, Tuple

from model.constraints_validator import ConstraintValidator
from model.generate_sequence import SequenceGenerator
from model.majorelle_manager import MajorelleManager
from utils.tools import get_site_key_from_name


class ScheduleAllocator:
    """Classe principale pour l'allocation du planning"""

    def __init__(self, config: Dict, working_days: List[date]):
        self.config = config
        self.working_days = working_days
        self.total_slots = len(working_days) * 2
        self.schedule = defaultdict(list)

        self.majorelle_sites = [k for k in config if k.startswith('majorelle_')]
        self.majorelle_manager = MajorelleManager(self.majorelle_sites, config)
        self.constraint_validator = ConstraintValidator(config)

    def allocate(self) -> Dict[date, List[str]]:
        print('Total slots to allocate:', self.total_slots)

        if self.total_slots <= 0:
            return self.schedule

        # Phase 1: Pre-allocation of fridays for Majorelle
        self.majorelle_manager.allocate_fridays(self.working_days)

        # Phase 2: Compute quotas and create sequence
        quotas = self._calculate_quotas()
        seq = SequenceGenerator.generate_sequence(quotas, self.config)

        # Phase 3: main allocation
        self._main_allocation(seq)

        # Phase 4: Backfilling
        self._backfilling(seq)

        # Phase 5: Rebalance fridays
        self._rebalance_majorelle_fridays()

        return self.schedule

    def _calculate_quotas(self) -> Dict[str, int]:
        quotas = SequenceGenerator.calculate_quotas(self.config, self.total_slots)
        quotas = SequenceGenerator.adjust_for_paired_sites(quotas, self.config,
                                                         self.total_slots)
        return quotas

    def _main_allocation(self, seq: List[str]):
        for day in self.working_days:
            if len(seq) == 0:
                print(f"No more slots available for day {day}")
                break

            first_site, second_site = self._allocate_day(day, seq)

            assignments = [self.config[first_site]['name'] if first_site else None,
                           self.config[second_site]['name'] if second_site else None]
            self.schedule[day] = assignments

    def _allocate_day(self, day: date, seq: List[str]) -> Tuple[Optional[str], Optional[str]]:
        is_friday = day.weekday() == 4

        majorelle_for_today = self.majorelle_manager.should_place_majorelle_on_friday(day)

        first_site, idx_first = self._find_first_site(day, seq,
                                                      majorelle_for_today, is_friday)

        if first_site is None:
            return None, None

        seq.pop(idx_first)

        if is_friday and first_site in self.majorelle_sites:
            self.majorelle_manager.increment_friday_count(first_site)

        second_site = self._find_second_site(first_site, day, seq, is_friday)

        return first_site, second_site

    def _find_first_site(self, day: date, seq: List[str],
                         majorelle_for_today: Optional[str],
                         is_friday: bool) -> Tuple[Optional[str], Optional[int]]:

        if majorelle_for_today and majorelle_for_today in seq:
            for i, site in enumerate(seq):
                if site == majorelle_for_today:
                    return site, i

        for i, site in enumerate(seq):
            if is_friday and not self.majorelle_manager.can_place_on_friday(site):
                continue

            if site in self.majorelle_sites:
                remaining_occurrences = seq.count(site)

                if is_friday:
                    if day in self.majorelle_manager.friday_allocation.get(site, []):
                        # On peut le placer même s'il ne reste qu'1 slot
                        pass
                    else:
                        future_fridays = self.majorelle_manager.get_future_friday_count(site, day, False)
                        if remaining_occurrences <= future_fridays:
                            continue
                else:
                    future_fridays = self.majorelle_manager.get_future_friday_count(site, day, False)
                    if remaining_occurrences <= future_fridays:
                        print(f"  ⚠️ {self.config[site]['name']}: {remaining_occurrences} slots restants "
                              f"mais {future_fridays} vendredis futurs → réservation")
                        continue

            if self.constraint_validator.is_available(site, day):
                return site, i

        return None, None

    def _find_second_site(self, first_site: str, day: date,
                          seq: List[str], is_friday: bool) -> Optional[str]:
        if self.config[first_site].get("pair_same_day", False):
            for i, site in enumerate(seq):
                if site == first_site:
                    seq.pop(i)
                    return site
            print(f"Warning: no more occurence of {first_site} found")
            return None
        else:
            for i, site in enumerate(seq):
                if is_friday and not self.majorelle_manager.can_place_on_friday(site):
                    continue

                if site in self.majorelle_sites:
                    remaining_occurrences = seq.count(site)

                    if is_friday:
                        if day in self.majorelle_manager.friday_allocation.get(site, []):
                            pass
                        else:
                            future_fridays = self.majorelle_manager.get_future_friday_count(site, day, False)
                            if remaining_occurrences <= future_fridays:
                                continue
                    else:
                        future_fridays = self.majorelle_manager.get_future_friday_count(site, day, False)
                        if remaining_occurrences <= future_fridays:
                            continue

                if (self.constraint_validator.validate_second_site(first_site, site) and
                        self.constraint_validator.is_available(site, day)):

                    if is_friday and site in self.majorelle_sites:
                        self.majorelle_manager.increment_friday_count(site)
                    seq.pop(i)
                    return site

            return None

    def _backfilling(self, seq: List[str]):
        print("\n=== Backfilling stage===")
        print(f"Remaining sites in seq: {len(seq)} ({seq})")

        print("\nVendredis alloués aux sites Majorelle avant backfilling:")
        for site in self.majorelle_sites:
            count = self.majorelle_manager.get_friday_count(site)
            print(f"  {self.config[site]['name']}: {count} vendredis")

        none_counts = {day: self.schedule[day].count(None) for day in self.schedule}
        days_with_none = [day for day in self.schedule if none_counts[day] > 0]

        if not days_with_none or not seq:
            return

        print(f"Number of days with None: {len(days_with_none)}")
        print("Note: Durant le backfilling, les sites Majorelle peuvent avoir 3-5 vendredis (flexibilité ±1)")

        remaining_seq = seq.copy()
        for site_to_place in remaining_seq:
            if not site_to_place:
                continue

            self._try_place_site_backfilling(site_to_place, days_with_none, seq)

        final_none_counts = {day: self.schedule[day].count(None) for day in self.working_days}
        total_none = sum(final_none_counts.values())
        print(f"\n=== Final result: {total_none} remaining None, {len(seq)} unassigned sites in seq ===")

    def _try_place_site_backfilling(self, site_to_place: str,
                                    days_with_none: List[date], seq: List[str]):
        print(f"\nTrying to place: {site_to_place} ({self.config[site_to_place]['name']})")

        if site_to_place in self.majorelle_sites:
            current_fridays = self.majorelle_manager.get_friday_count(site_to_place)
            print(f"  (Site Majorelle avec {current_fridays} vendredis actuellement)")

        for problem_day in days_with_none:
            for slot_idx in range(len(self.schedule[problem_day])):
                if self.schedule[problem_day][slot_idx] is not None:
                    continue

                if self._find_swap_for_backfilling(site_to_place, problem_day,
                                                   slot_idx, seq):
                    return

        print(f"  ⚠️ Unable to place {self.config[site_to_place]['name']}")

    def _find_swap_for_backfilling(self, site_to_place: str, problem_day: date,
                                   slot_idx: int, seq: List[str]) -> bool:
        for swap_day in self.working_days:
            if swap_day >= problem_day or self._day_contains_paired_site(swap_day):
                continue

            for swap_slot_idx in range(len(self.schedule[swap_day])):
                site_name_to_swap = self.schedule[swap_day][swap_slot_idx]
                if site_name_to_swap is None:
                    continue

                site_key_to_swap = get_site_key_from_name(self.config, site_name_to_swap)
                if site_key_to_swap is None:
                    continue

                if self._validate_backfilling_swap(site_to_place, site_key_to_swap,
                                                   problem_day, swap_day,
                                                   slot_idx, swap_slot_idx):
                    self._execute_swap(site_to_place, site_key_to_swap,
                                       site_name_to_swap, problem_day, swap_day,
                                       slot_idx, swap_slot_idx, seq)
                    return True

        return False

    def _day_contains_paired_site(self, day: date) -> bool:
        day_schedule = self.schedule[day]
        for site_name in day_schedule:
            if site_name:
                site_key = get_site_key_from_name(self.config, site_name)
                if site_key and self.config[site_key].get("pair_same_day", False):
                    return True
        return False

    def _validate_backfilling_swap(self, site_to_place: str, site_to_swap: str,
                                   problem_day: date, swap_day: date,
                                   slot_idx: int, swap_slot_idx: int) -> bool:

        if not self.constraint_validator.is_available(site_to_swap, problem_day):
            return False
        if not self.constraint_validator.is_available(site_to_place, swap_day):
            return False


        if swap_day.weekday() == 4 and site_to_place in self.majorelle_sites:
            if self.majorelle_manager.get_friday_count(site_to_place) >= 5:
                return False
        if problem_day.weekday() == 4 and site_to_swap in self.majorelle_sites:
            if self.majorelle_manager.get_friday_count(site_to_swap) >= 5:
                return False

        return self.constraint_validator.validate_swap(
            site_to_place, self.config[site_to_swap]['name'],
            self.schedule[problem_day], self.schedule[swap_day],
            slot_idx, swap_slot_idx
        )

    def _execute_swap(self, site_to_place: str, site_key_to_swap: str,
                      site_name_to_swap: str, problem_day: date, swap_day: date,
                      slot_idx: int, swap_slot_idx: int, seq: List[str]):
        print(f"  Exchange found:")
        print(f"    - {self.config[site_to_place]['name']} to {swap_day.strftime('%Y-%m-%d')} "
              f"({'Vendredi' if swap_day.weekday() == 4 else 'autre jour'})")
        print(f"    - {site_name_to_swap} from {swap_day.strftime('%Y-%m-%d')} to "
              f"{problem_day.strftime('%Y-%m-%d')} "
              f"({'Vendredi' if problem_day.weekday() == 4 else 'autre jour'})")

        if swap_day.weekday() == 4 and site_to_place in self.majorelle_sites:
            self.majorelle_manager.increment_friday_count(site_to_place)
            count = self.majorelle_manager.get_friday_count(site_to_place)
            print(f"    → {self.config[site_to_place]['name']} a maintenant {count} vendredis")

        if problem_day.weekday() == 4 and site_key_to_swap in self.majorelle_sites:
            self.majorelle_manager.increment_friday_count(site_key_to_swap)
            count = self.majorelle_manager.get_friday_count(site_key_to_swap)
            print(f"    → {self.config[site_key_to_swap]['name']} a maintenant {count} vendredis")

        self.schedule[problem_day][slot_idx] = site_name_to_swap
        self.schedule[swap_day][swap_slot_idx] = self.config[site_to_place]['name']
        seq.remove(site_to_place)

    def _rebalance_majorelle_fridays(self):
        print("\n=== Phase de rééquilibrage des vendredis Majorelle ===")

        majorelle_friday_count = self._count_majorelle_fridays()

        print("Compte initial des vendredis:")
        for site in self.majorelle_sites:
            print(f"  {self.config[site]['name']}: {majorelle_friday_count[site]} vendredis")

        sites_under = [site for site in self.majorelle_sites
                       if majorelle_friday_count[site] < 3]

        if not sites_under:
            self._print_final_friday_verification()
            return

        print(f"\nSites Majorelle avec moins de 3 vendredis: "
              f"{[self.config[s]['name'] for s in sites_under]}")

        for site_under in sites_under:
            self._rebalance_single_site(site_under, majorelle_friday_count)

        self._print_final_friday_verification()

    def _count_majorelle_fridays(self) -> Dict[str, int]:
        counts = {}
        for site in self.majorelle_sites:
            count = 0
            for day in self.working_days:
                if day.weekday() == 4 and self.config[site]['name'] in self.schedule[day]:
                    count += 1
            counts[site] = count
        return counts

    def _rebalance_single_site(self, site_under: str,
                               majorelle_friday_count: Dict[str, int]):
        while majorelle_friday_count[site_under] < 3:
            # Priorité 1: Swap with non-Majorelle sites
            if self._try_rebalance_with_non_majorelle(site_under, majorelle_friday_count):
                continue

            # Priorité 2: Swap with Majorelle
            if self._try_rebalance_with_majorelle(site_under, majorelle_friday_count):
                continue

            print(f"\n⚠ Impossible de rééquilibrer {self.config[site_under]['name']} "
                  f"(reste à {majorelle_friday_count[site_under]} vendredis)")
            break

    def _try_rebalance_with_non_majorelle(self, site_under: str,
                                          majorelle_friday_count: Dict[str, int]) -> bool:
        non_majorelle_sites = [s for s in self.config.keys()
                               if s not in self.majorelle_sites]

        print(f"\n  Tentative d'échange avec des sites NON-Majorelle pour "
              f"{self.config[site_under]['name']}...")

        for donor_site in non_majorelle_sites:
            if self._execute_rebalance_exchange(site_under, donor_site,
                                                majorelle_friday_count, False):
                return True
        return False

    def _try_rebalance_with_majorelle(self, site_under: str,
                                      majorelle_friday_count: Dict[str, int]) -> bool:
        print(f"\n  Pas d'échange trouvé avec les NON-Majorelle, "
              f"tentative avec les sites Majorelle...")

        donor_candidates = [s for s in self.majorelle_sites
                            if majorelle_friday_count[s] >= 4 and s != site_under]
        donor_candidates.sort(key=lambda s: -majorelle_friday_count[s])

        for donor_site in donor_candidates:
            if self._execute_rebalance_exchange(site_under, donor_site,
                                                majorelle_friday_count, True):
                return True
        return False

    def _execute_rebalance_exchange(self, receiver_site: str, donor_site: str,
                                    majorelle_friday_count: Dict[str, int],
                                    is_majorelle_donor: bool) -> bool:
        for day in self.working_days:
            if day.weekday() != 4:
                continue

            if self.config[donor_site]['name'] not in self.schedule[day]:
                continue

            donor_slot = self.schedule[day].index(self.config[donor_site]['name'])

            for swap_day in self.working_days:
                if swap_day.weekday() == 4:
                    continue

                if self.config[receiver_site]['name'] not in self.schedule[swap_day]:
                    continue

                receiver_slot = self.schedule[swap_day].index(
                    self.config[receiver_site]['name']
                )

                if not self._validate_rebalance_exchange(
                        receiver_site, donor_site, day, swap_day,
                        donor_slot, receiver_slot
                ):
                    continue

                self._perform_rebalance_exchange(
                    receiver_site, donor_site, day, swap_day,
                    donor_slot, receiver_slot, majorelle_friday_count,
                    is_majorelle_donor
                )
                return True

        return False

    def _validate_rebalance_exchange(self, receiver_site: str, donor_site: str,
                                     friday: date, swap_day: date,
                                     donor_slot: int, receiver_slot: int) -> bool:
        if not self.constraint_validator.is_available(receiver_site, friday):
            return False
        if not self.constraint_validator.is_available(donor_site, swap_day):
            return False

        return self.constraint_validator.validate_swap(
            receiver_site, self.config[donor_site]['name'],
            self.schedule[friday], self.schedule[swap_day],
            donor_slot, receiver_slot
        )

    def _perform_rebalance_exchange(self, receiver_site: str, donor_site: str,
                                    friday: date, swap_day: date,
                                    donor_slot: int, receiver_slot: int,
                                    majorelle_friday_count: Dict[str, int],
                                    is_majorelle_donor: bool):
        donor_type = "Majorelle" if is_majorelle_donor else "NON-Majorelle"

        print(f"\n✓ Rééquilibrage trouvé avec site {donor_type}:")
        print(f"  {self.config[donor_site]['name']} ({donor_type})")

        if is_majorelle_donor:
            print(f"    avec {majorelle_friday_count[donor_site]} vendredis")

        print(f"    passe du vendredi {friday.strftime('%Y-%m-%d')} au "
              f"{swap_day.strftime('%Y-%m-%d')}")
        print(f"  {self.config[receiver_site]['name']} (Majorelle avec "
              f"{majorelle_friday_count[receiver_site]} vendredis)")
        print(f"    passe du {swap_day.strftime('%Y-%m-%d')} au vendredi "
              f"{friday.strftime('%Y-%m-%d')}")

        self.schedule[friday][donor_slot] = self.config[receiver_site]['name']
        self.schedule[swap_day][receiver_slot] = self.config[donor_site]['name']

        if is_majorelle_donor:
            majorelle_friday_count[donor_site] -= 1
        majorelle_friday_count[receiver_site] += 1

        print(f"  Nouveau compte: ", end="")
        if is_majorelle_donor:
            print(f"{self.config[donor_site]['name']}={majorelle_friday_count[donor_site]}, ",
                  end="")
        print(f"{self.config[receiver_site]['name']}={majorelle_friday_count[receiver_site]}")

    def _print_final_friday_verification(self):
        print("\n=== Vérification finale des vendredis Majorelle ===")
        print("Objectif: 4 vendredis par site (flexibilité 3-5 acceptée si nécessaire)")

        final_counts = self._count_majorelle_fridays()

        for site in self.majorelle_sites:
            count = final_counts[site]
            if count == 4:
                status = "✓ Objectif atteint"
            elif count in [3, 5]:
                status = "⚠ Acceptable (flexibilité)"
            else:
                status = "✗ Hors limites"
            print(f"{self.config[site]['name']}: {count} vendredis {status}")

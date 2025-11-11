from datetime import date
from typing import List, Dict, Optional

from model.validator import ScheduleValidator


class MajorelleManager:
    """Manage fridays allocation to Majorelle sites"""

    def __init__(self, majorelle_sites: List[str], config: Dict):
        self.majorelle_sites = majorelle_sites
        self.config = config
        self.friday_allocation = {}
        self.friday_used = {site: 0 for site in majorelle_sites}
        self.constraints_validator = ScheduleValidator(config)

    def allocate_fridays(self, working_days: List[date]) -> Dict[str, List[date]]:
        """
        Allocates Fridays to Majorelle sites.
        Each site should have 4 fridays in the targeted semester.
        Takes into account site availability (holidays/vacations).
        """
        fridays = [day for day in working_days if day.weekday() == 4]

        if not self.majorelle_sites or not fridays:
            return self.friday_allocation

        site_available_fridays = {}
        for site in self.majorelle_sites:
            site_available_fridays[site] = [
                friday for friday in fridays
                if self.constraints_validator.is_available(site, friday)
            ]

            if len(site_available_fridays[site]) < 4:
                print(f"Warning: Site {self.config[site]['name']} has only "
                      f"{len(site_available_fridays[site])} Fridays available (need 4)")

        total_allocations_possible = sum(min(len(fridays), 4) for fridays in site_available_fridays.values())

        if total_allocations_possible < len(self.majorelle_sites) * 4:
            print(f"Warning: Cannot allocate 4 Fridays to all Majorelle sites due to availability constraints")

        self._allocate_with_availability(fridays, site_available_fridays)

        return self.friday_allocation

    def _allocate_with_availability(self, all_fridays: List[date],
                                    site_available_fridays: Dict[str, List[date]]):
        """
        Allocate Fridays to sites while respecting availability constraints.
        Try to distribute evenly across the semester periods.
        """
        periods = self._split_fridays_into_periods(all_fridays)

        for site in self.majorelle_sites:
            self.friday_allocation[site] = []

        for period_idx, period in enumerate(periods):
            sites_needing_friday = list(self.majorelle_sites)

            for friday in period:
                if not sites_needing_friday:
                    break

                available_sites = [
                    site for site in sites_needing_friday
                    if friday in site_available_fridays[site]
                       and len(self.friday_allocation[site]) < 4
                       and not self._is_friday_allocated(friday)
                ]

                if available_sites:
                    # Prioritize sites with few fridays available
                    chosen_site = min(available_sites,
                                      key=lambda s: (len(self.friday_allocation[s]), s))
                    self.friday_allocation[chosen_site].append(friday)
                    sites_needing_friday.remove(chosen_site)

        for site in self.majorelle_sites:
            current_count = len(self.friday_allocation[site])
            if current_count < 4:
                remaining_fridays = [
                    f for f in site_available_fridays[site]
                    if not self._is_friday_allocated(f)
                ]

                for friday in remaining_fridays[:4 - current_count]:
                    self.friday_allocation[site].append(friday)

                self.friday_allocation[site].sort()

        print("\n=== Friday allocation for Majorelle sites ===")
        for site in self.majorelle_sites:
            allocated_count = len(self.friday_allocation[site])
            status = "✓" if allocated_count == 4 else f"⚠ ({allocated_count}/4)"
            print(f"{self.config[site]['name']}: {status}")
            if allocated_count < 4:
                holidays = self.config[site].get('holidays', [])
                if holidays:
                    print(f"  Note: {len(holidays)} days of holidays configured")

    @staticmethod
    def _split_fridays_into_periods(fridays: List[date]) -> List[List[date]]:
        """Split Fridays into 4 periods for even distribution"""
        if not fridays:
            return [[], [], [], []]

        period_size = len(fridays) // 4
        periods = []

        for i in range(4):
            start_idx = i * period_size
            if i == 3:
                periods.append(fridays[start_idx:])
            else:
                periods.append(fridays[start_idx:start_idx + period_size])

        return periods

    def _is_friday_allocated(self, friday: date) -> bool:
        """Check if a friday has been already allocated to any site"""
        return any(friday in self.friday_allocation[s] for s in self.friday_allocation)

    def should_place_majorelle_on_friday(self, day: date) -> Optional[str]:
        """Determine if a Majorelle site should be placed on this Friday"""
        if day.weekday() != 4:
            return None

        for site in self.majorelle_sites:
            if site in self.friday_allocation and day in self.friday_allocation[site]:
                if self.friday_used[site] < 4:
                    # Double-check availability in case config changed
                    if self.constraints_validator.is_available(site, day):
                        return site
                    else:
                        print(f"Warning: {self.config[site]['name']} was allocated to "
                              f"{day.strftime('%Y-%m-%d')} but is no longer available")
        return None

    def increment_friday_count(self, site: str):
        """Increment the count of Fridays used for a site"""
        if site in self.friday_used:
            self.friday_used[site] += 1

    def get_friday_count(self, site: str) -> int:
        """Get the current count of Fridays for a site"""
        return self.friday_used.get(site, 0)

    def can_place_on_friday(self, site: str, is_backfilling: bool = False) -> bool:
        """Check if a site can be placed on a Friday"""
        if site not in self.majorelle_sites:
            return True

        current_count = self.get_friday_count(site)
        max_allowed = 5 if is_backfilling else 4
        return current_count < max_allowed

    def get_future_friday_count(self, site: str, current_date: date, include_current: bool = False) -> int:
        if site not in self.majorelle_sites or site not in self.friday_allocation:
            return 0

        future_fridays = [
            friday for friday in self.friday_allocation[site]
            if friday > current_date or (include_current and friday == current_date)
        ]

        return len(future_fridays)

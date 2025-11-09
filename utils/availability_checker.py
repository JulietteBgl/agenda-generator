from datetime import date
from typing import Dict, Optional


class SiteAvailabilityChecker:
    """Check sites availability"""

    def __init__(self, config: Dict):
        self.config = config

    def is_available(self, site_key: str, day: date) -> bool:
        cfg = self.config[site_key]

        if not cfg.get("advanced_split"):
            return True

        weekday = day.weekday()
        available_weekdays = cfg.get('available_weekdays', list(range(5)))
        day_str = day.strftime("%Y-%m-%d")
        holidays = cfg.get('holidays', [])

        return weekday in available_weekdays and day_str not in holidays

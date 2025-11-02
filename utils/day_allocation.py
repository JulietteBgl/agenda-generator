from typing import Dict, List
from datetime import date

from utils.schedule_allocator import ScheduleAllocator


def allocate_days(config: Dict, working_days: List[date]) -> Dict[date, List[str]]:
    allocator = ScheduleAllocator(config, working_days)
    return allocator.allocate()

from dataclasses import dataclass


@dataclass
class Routine:
    id: str
    name: str
    description: str
    active: bool


@dataclass
class Step:
    id: str
    routine_id: str
    order_index: int
    title: str
    description: str
    expected_time: str  # "HH:MM", 24h local time
    window_minutes: int  # how long after expected_time the step is still "on time"


@dataclass
class Completion:
    id: str
    step_id: str
    routine_id: str
    completed_at: str  # ISO 8601 timestamp
    log_date: str  # "YYYY-MM-DD", the day this completion counts toward

import os
import json
from typing import Dict, Any


def _atomic_write_json(path: str, data: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _default_stats() -> Dict[str, Any]:
    return {
        "streak": {
            "current": 0,
            "max": 0,
            "last_study_date": ""
        },
        "activity_log": {}
    }


class UserStatsStore:
    """Global user stats: streak + daily activity counts.

    Stored in a single JSON file at {base_dir}/user_stats.json.
    Dates are YYYY-MM-DD strings in the user's local timezone
    (caller is responsible for passing local date, not UTC).
    """

    def __init__(self, base_dir: str):
        self.path = os.path.join(base_dir, "user_stats.json")

    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self.path):
            return _default_stats()
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return _default_stats()
            # Ensure required keys exist (forward-compat with old files)
            data.setdefault("streak", _default_stats()["streak"])
            data.setdefault("activity_log", {})
            data["streak"].setdefault("current", 0)
            data["streak"].setdefault("max", 0)
            data["streak"].setdefault("last_study_date", "")
            return data
        except (json.JSONDecodeError, OSError):
            return _default_stats()

    def _save(self, data: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        _atomic_write_json(self.path, data)

    def record_activity(self, date_str: str) -> Dict[str, Any]:
        """Record one activity event on the given local date string (YYYY-MM-DD).

        Updates streak (current + max) and increments activity_log[date_str].
        Returns the updated stats dict.
        """
        data = self._load()
        streak = data["streak"]
        last = streak.get("last_study_date", "")

        if date_str != last:
            # Check if consecutive day
            if last and _is_consecutive(last, date_str):
                streak["current"] += 1
            elif date_str != last:
                # Gap or first ever — reset (but only if actually a new date)
                streak["current"] = 1

            streak["last_study_date"] = date_str
            streak["max"] = max(streak["max"], streak["current"])

        # Increment activity count
        log: Dict[str, int] = data["activity_log"]
        log[date_str] = log.get(date_str, 0) + 1

        self._save(data)
        return data

    def get_stats(self) -> Dict[str, Any]:
        return self._load()


def _is_consecutive(prev: str, curr: str) -> bool:
    """Return True if curr is exactly one calendar day after prev."""
    try:
        from datetime import date
        p = date.fromisoformat(prev)
        c = date.fromisoformat(curr)
        return (c - p).days == 1
    except ValueError:
        return False

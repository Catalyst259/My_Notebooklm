import os
import json
from typing import Dict, Any, List


def _atomic_write_json(path: str, data: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


class QuizHistoryStore:
    """Per-assistant quiz result history.

    Layout: {base_dir}/{assistant_id}/records.json
    Each record: {date, score, count, difficulty}
      - date: YYYY-MM-DD (local timezone, caller-provided)
      - score: float 0-1 (average score for this attempt)
      - count: int (number of questions)
      - difficulty: str
    """

    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    def _path(self, assistant_id: str) -> str:
        return os.path.join(self.base_dir, assistant_id, "records.json")

    def _load(self, assistant_id: str) -> List[Dict[str, Any]]:
        path = self._path(assistant_id)
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def append(self, assistant_id: str, record: Dict[str, Any]) -> None:
        """Append one quiz result record."""
        os.makedirs(os.path.join(self.base_dir, assistant_id), exist_ok=True)
        records = self._load(assistant_id)
        records.append(record)
        _atomic_write_json(self._path(assistant_id), records)

    def get_recent(self, assistant_id: str, n: int = 10) -> List[Dict[str, Any]]:
        """Return the n most recent records."""
        records = self._load(assistant_id)
        return records[-n:] if len(records) > n else records

    def get_all(self, assistant_id: str) -> List[Dict[str, Any]]:
        return self._load(assistant_id)

import os
import json
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_write_json(path: str, data: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


class ReviewStore:
    """JSON-file-backed review item collection for a single assistant.

    Layout:
      {base_dir}/{assistant_id}/items/{item_id}.json
      {base_dir}/{assistant_id}/_index.json
      {base_dir}/{assistant_id}/daily_queue_{date}.json
    """

    INDEX_FILE = "_index.json"
    ITEMS_SUBDIR = "items"

    def __init__(self, base_dir: str, assistant_id: str):
        self.assistant_id = assistant_id
        self.dir = os.path.join(base_dir, assistant_id)
        self.items_dir = os.path.join(self.dir, self.ITEMS_SUBDIR)
        os.makedirs(self.items_dir, exist_ok=True)

    # --- index helpers -----------------------------------------------------

    def _index_path(self) -> str:
        return os.path.join(self.dir, self.INDEX_FILE)

    def _load_index(self) -> List[Dict[str, Any]]:
        path = self._index_path()
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
        return []

    def _save_index(self, index: List[Dict[str, Any]]) -> None:
        _atomic_write_json(self._index_path(), index)

    def _upsert_index(self, item: Dict[str, Any]) -> None:
        front_preview = str(item.get("snapshot", {}).get("front", ""))[:60]
        entry = {
            "id": item["id"],
            "type": item["type"],
            "status": item["status"],
            "next_review": item["srs"]["next_review"],
            "front_preview": front_preview,
            "source_type": item["source"]["type"],
            "updated_at": item["updated_at"],
        }
        index = self._load_index()
        index = [e for e in index if e["id"] != item["id"]]
        index.insert(0, entry)
        self._save_index(index)

    def _remove_from_index(self, item_id: str) -> None:
        index = [e for e in self._load_index() if e["id"] != item_id]
        self._save_index(index)

    # --- item file helpers -------------------------------------------------

    def _item_path(self, item_id: str) -> str:
        return os.path.join(self.items_dir, f"{item_id}.json")

    def _load_item(self, item_id: str) -> Dict[str, Any]:
        path = self._item_path(item_id)
        if not os.path.exists(path):
            raise KeyError(item_id)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_item(self, item: Dict[str, Any]) -> None:
        _atomic_write_json(self._item_path(item["id"]), item)
        self._upsert_index(item)

    # --- public API --------------------------------------------------------

    def list_items(self, include_archived: bool = False) -> List[Dict[str, Any]]:
        """Return index entries, newest first. Exclude archived unless requested."""
        index = self._load_index()
        if not include_archived:
            index = [e for e in index if e.get("status") != "archived"]
        return index

    def create_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new review item. Caller must provide all required fields except id/timestamps."""
        item_id = "rv_" + uuid.uuid4().hex[:8]
        now = _now_iso()
        full_item = {
            "id": item_id,
            "assistant_id": self.assistant_id,
            "type": item["type"],
            "status": item.get("status", "active"),
            "snapshot": item["snapshot"],
            "source": item["source"],
            "srs": item["srs"],
            "created_at": now,
            "updated_at": now,
        }
        self._save_item(full_item)
        return full_item

    def get_item(self, item_id: str) -> Dict[str, Any]:
        return self._load_item(item_id)

    def exists(self, item_id: str) -> bool:
        return os.path.exists(self._item_path(item_id))

    def update_item(self, item_id: str, **fields) -> Dict[str, Any]:
        """Update specific fields of an item. Automatically updates updated_at."""
        item = self._load_item(item_id)
        for k, v in fields.items():
            if k in ("id", "assistant_id", "created_at"):
                continue  # immutable
            item[k] = v
        item["updated_at"] = _now_iso()
        self._save_item(item)
        return item

    def delete_item(self, item_id: str) -> None:
        path = self._item_path(item_id)
        if os.path.exists(path):
            os.remove(path)
        self._remove_from_index(item_id)

    def archive_item(self, item_id: str) -> Dict[str, Any]:
        return self.update_item(item_id, status="archived")

    def reactivate_item(self, item_id: str) -> Dict[str, Any]:
        return self.update_item(item_id, status="active")

    # --- daily queue -------------------------------------------------------

    def _queue_path(self, date: str) -> str:
        return os.path.join(self.dir, f"daily_queue_{date}.json")

    def load_daily_queue(self, date: str) -> Optional[Dict[str, Any]]:
        path = self._queue_path(date)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def save_daily_queue(self, date: str, queue: Dict[str, Any]) -> None:
        _atomic_write_json(self._queue_path(date), queue)

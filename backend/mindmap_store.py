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


def _count_nodes(node: Optional[Dict[str, Any]]) -> int:
    if not node or not isinstance(node, dict):
        return 0
    total = 1
    for child in node.get("children") or []:
        total += _count_nodes(child)
    return total


def _empty_jsmind(title: str, root_id: str = "root") -> Dict[str, Any]:
    return {
        "meta": {"name": title, "version": "1.0"},
        "format": "node_tree",
        "data": {
            "id": root_id,
            "topic": title,
            "data": {},
            "children": [],
        },
    }


class MindMapStore:
    """JSON-file-backed mind-map collection for a single assistant.

    Layout mirrors SessionStore:
      {base_dir}/{assistant_id}/{map_id}.json   one file per mind-map
      {base_dir}/{assistant_id}/_index.json     ordered list, newest first
    """

    INDEX_FILE = "_index.json"

    def __init__(self, base_dir: str, assistant_id: str):
        self.assistant_id = assistant_id
        self.dir = os.path.join(base_dir, assistant_id)
        os.makedirs(self.dir, exist_ok=True)

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

    def _upsert_index(self, mindmap: Dict[str, Any]) -> None:
        node_count = _count_nodes(mindmap.get("jsmind", {}).get("data"))
        entry = {
            "id": mindmap["id"],
            "title": mindmap["title"],
            "updated_at": mindmap["updated_at"],
            "node_count": node_count,
        }
        index = self._load_index()
        index = [e for e in index if e["id"] != mindmap["id"]]
        index.insert(0, entry)
        self._save_index(index)

    def _remove_from_index(self, map_id: str) -> None:
        index = [e for e in self._load_index() if e["id"] != map_id]
        self._save_index(index)

    # --- file helpers ------------------------------------------------------

    def _map_path(self, map_id: str) -> str:
        return os.path.join(self.dir, f"{map_id}.json")

    def _load_map(self, map_id: str) -> Dict[str, Any]:
        path = self._map_path(map_id)
        if not os.path.exists(path):
            raise KeyError(map_id)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_map(self, mindmap: Dict[str, Any]) -> None:
        _atomic_write_json(self._map_path(mindmap["id"]), mindmap)
        self._upsert_index(mindmap)

    # --- public API --------------------------------------------------------

    def list(self) -> List[Dict[str, Any]]:
        return self._load_index()

    def create(self, title: Optional[str] = None) -> Dict[str, Any]:
        map_id = "mm_" + uuid.uuid4().hex[:8]
        clean_title = (title or "新思维导图").strip() or "新思维导图"
        now = _now_iso()
        mindmap = {
            "id": map_id,
            "assistant_id": self.assistant_id,
            "title": clean_title,
            "created_at": now,
            "updated_at": now,
            "jsmind": _empty_jsmind(clean_title),
        }
        self._save_map(mindmap)
        return mindmap

    def get(self, map_id: str) -> Dict[str, Any]:
        return self._load_map(map_id)

    def exists(self, map_id: str) -> bool:
        return os.path.exists(self._map_path(map_id))

    def save(
        self,
        map_id: str,
        title: Optional[str] = None,
        jsmind_json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        mindmap = self._load_map(map_id)
        if title is not None:
            new_title = title.strip() or mindmap["title"]
            mindmap["title"] = new_title
        if jsmind_json is not None:
            mindmap["jsmind"] = jsmind_json
            if "meta" in jsmind_json and isinstance(jsmind_json["meta"], dict):
                jsmind_json["meta"]["name"] = mindmap["title"]
        mindmap["updated_at"] = _now_iso()
        self._save_map(mindmap)
        return mindmap

    def delete(self, map_id: str) -> None:
        path = self._map_path(map_id)
        if os.path.exists(path):
            os.remove(path)
        self._remove_from_index(map_id)

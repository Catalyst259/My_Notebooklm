import os
import json
import uuid
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_write_json(path: str, data: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _derive_title(text: str, max_chars: int = 30) -> str:
    """First line of the user's message, trimmed."""
    if not text:
        return "新对话"
    first_line = re.split(r"[\r\n]", text.strip(), maxsplit=1)[0].strip()
    if not first_line:
        return "新对话"
    if len(first_line) > max_chars:
        return first_line[:max_chars] + "…"
    return first_line


class SessionStore:
    """JSON-file-backed multi-session conversation history for a single assistant.

    Layout:
      {base_dir}/{assistant_id}/{session_id}.json   one file per session
      {base_dir}/{assistant_id}/_index.json         ordered list, newest first
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

    def _upsert_index(self, session: Dict[str, Any]) -> None:
        entry = {
            "id": session["id"],
            "title": session["title"],
            "updated_at": session["updated_at"],
            "message_count": len(session["messages"]),
        }
        index = self._load_index()
        index = [e for e in index if e["id"] != session["id"]]
        index.insert(0, entry)
        self._save_index(index)

    def _remove_from_index(self, session_id: str) -> None:
        index = [e for e in self._load_index() if e["id"] != session_id]
        self._save_index(index)

    # --- session file helpers ---------------------------------------------

    def _session_path(self, session_id: str) -> str:
        return os.path.join(self.dir, f"{session_id}.json")

    def _load_session(self, session_id: str) -> Dict[str, Any]:
        path = self._session_path(session_id)
        if not os.path.exists(path):
            raise KeyError(session_id)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_session(self, session: Dict[str, Any]) -> None:
        _atomic_write_json(self._session_path(session["id"]), session)
        self._upsert_index(session)

    # --- public API -------------------------------------------------------

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Return index entries (id, title, updated_at, message_count), newest first."""
        return self._load_index()

    def create(self, title: Optional[str] = None) -> Dict[str, Any]:
        session_id = uuid.uuid4().hex
        now = _now_iso()
        session = {
            "id": session_id,
            "assistant_id": self.assistant_id,
            "title": (title or "新对话").strip() or "新对话",
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
        self._save_session(session)
        return session

    def get(self, session_id: str) -> Dict[str, Any]:
        return self._load_session(session_id)

    def exists(self, session_id: str) -> bool:
        return os.path.exists(self._session_path(session_id))

    def rename(self, session_id: str, title: str) -> Dict[str, Any]:
        session = self._load_session(session_id)
        new_title = (title or "").strip() or session["title"]
        session["title"] = new_title
        session["updated_at"] = _now_iso()
        self._save_session(session)
        return session

    def delete(self, session_id: str) -> None:
        path = self._session_path(session_id)
        if os.path.exists(path):
            os.remove(path)
        self._remove_from_index(session_id)

    def append_message(self, session_id: str, role: str, content: str) -> Dict[str, Any]:
        session = self._load_session(session_id)
        session["messages"].append({
            "role": role,
            "content": content,
            "ts": _now_iso(),
        })
        # Auto-title from the first user message if still on the default.
        if role == "user" and session["title"] == "新对话":
            session["title"] = _derive_title(content)
        session["updated_at"] = _now_iso()
        self._save_session(session)
        return session

    def replace_last_assistant(self, session_id: str, content: str) -> Dict[str, Any]:
        """Used by /regenerate: overwrite the last assistant message in place."""
        session = self._load_session(session_id)
        for i in range(len(session["messages"]) - 1, -1, -1):
            if session["messages"][i]["role"] == "assistant":
                session["messages"][i]["content"] = content
                session["messages"][i]["ts"] = _now_iso()
                break
        else:
            session["messages"].append({
                "role": "assistant",
                "content": content,
                "ts": _now_iso(),
            })
        session["updated_at"] = _now_iso()
        self._save_session(session)
        return session

    def pop_last_assistant(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Drop the trailing assistant message if present. Returns the popped message or None."""
        session = self._load_session(session_id)
        if session["messages"] and session["messages"][-1]["role"] == "assistant":
            popped = session["messages"].pop()
            session["updated_at"] = _now_iso()
            self._save_session(session)
            return popped
        return None

    def delete_message_pair(self, session_id: str, index: int) -> Dict[str, Any]:
        """Delete the message at ``index`` and its paired turn so user/assistant pairing stays intact.

        Rule: if the target is a user message, also drop the following assistant
        message (if any). If the target is an assistant message, also drop the
        preceding user message (if any). Out-of-range raises IndexError.
        """
        session = self._load_session(session_id)
        msgs = session["messages"]
        if index < 0 or index >= len(msgs):
            raise IndexError(f"message index {index} out of range")

        target = msgs[index]
        to_drop = {index}
        if target["role"] == "user" and index + 1 < len(msgs) and msgs[index + 1]["role"] == "assistant":
            to_drop.add(index + 1)
        elif target["role"] == "assistant" and index - 1 >= 0 and msgs[index - 1]["role"] == "user":
            to_drop.add(index - 1)

        session["messages"] = [m for i, m in enumerate(msgs) if i not in to_drop]
        session["updated_at"] = _now_iso()
        self._save_session(session)
        return session

    def get_messages_for_llm(self, session_id: str) -> List[Dict[str, str]]:
        """Return messages stripped to OpenAI-compatible {role, content} dicts."""
        session = self._load_session(session_id)
        return [{"role": m["role"], "content": m["content"]} for m in session["messages"]]

    def most_recent_session_id(self) -> Optional[str]:
        index = self._load_index()
        if not index:
            return None
        return index[0]["id"]

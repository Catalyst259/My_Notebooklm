import os


class MemoryStore:
    """Per-assistant plain-text memory note, prepended to the system prompt."""

    MAX_BYTES = 8 * 1024  # cap so a runaway note can't blow up the prompt

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _path(self, assistant_id: str) -> str:
        return os.path.join(self.base_dir, f"{assistant_id}.txt")

    def read(self, assistant_id: str) -> str:
        path = self._path(assistant_id)
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def write(self, assistant_id: str, text: str) -> None:
        text = (text or "").strip()
        if len(text.encode("utf-8")) > self.MAX_BYTES:
            raise ValueError(f"备忘内容过长（超过 {self.MAX_BYTES} 字节）")

        path = self._path(assistant_id)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)

    def delete(self, assistant_id: str) -> None:
        path = self._path(assistant_id)
        if os.path.exists(path):
            os.remove(path)

import json
from typing import AsyncGenerator, List, Optional

from openai import AsyncOpenAI


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


class MindMapEngine:
    """Streaming AI operations for mind-maps over DeepSeek.

    All three operations yield SSE-formatted strings:
      {"content": "...", "done": false}   incremental chunk
      {"content": "", "done": true}        end-of-stream
      {"error": "...", "done": true}       failure (terminates the stream)

    The engine never knows which map the output is targeted at; the frontend
    is responsible for applying parsed bullets to its local jsmind instance.
    """

    LLM_BASE_URL = "https://api.deepseek.com"
    LLM_MODEL = "deepseek-chat"

    def __init__(self, knowledge_base, rag_engine, assistant_id: str, assistant_name: str):
        self.knowledge_base = knowledge_base
        self.rag_engine = rag_engine
        self.assistant_id = assistant_id
        self.assistant_name = assistant_name

    async def _stream(
        self,
        api_key: str,
        messages: list,
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        client = AsyncOpenAI(api_key=api_key, base_url=self.LLM_BASE_URL)
        try:
            stream = await client.chat.completions.create(
                model=self.LLM_MODEL,
                messages=messages,
                stream=True,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield _sse({"content": delta.content, "done": False})
        except Exception as e:
            yield _sse({"error": str(e), "done": True})
            return

        yield _sse({"content": "", "done": True})

    async def stream_generate_tree(
        self,
        api_key: str,
        topic: str,
        depth: int = 2,
        width: int = 4,
    ) -> AsyncGenerator[str, None]:
        if not topic or not topic.strip():
            yield _sse({"error": "主题不能为空", "done": True})
            return

        depth = max(1, min(int(depth or 2), 3))
        width = max(2, min(int(width or 4), 8))

        messages = self.rag_engine.build_mindmap_messages(
            "generate_tree",
            topic=topic.strip(),
            depth=depth,
            width=width,
        )
        async for evt in self._stream(api_key, messages, max_tokens=2048):
            yield evt

    async def stream_expand_node(
        self,
        api_key: str,
        path: List[str],
        siblings: Optional[List[str]] = None,
        count: int = 4,
    ) -> AsyncGenerator[str, None]:
        if not path:
            yield _sse({"error": "节点路径不能为空", "done": True})
            return

        count = max(1, min(int(count or 4), 8))
        messages = self.rag_engine.build_mindmap_messages(
            "expand_node",
            path=path,
            siblings=siblings or [],
            count=count,
        )
        async for evt in self._stream(api_key, messages, max_tokens=1024):
            yield evt

    async def stream_generate_note(
        self,
        api_key: str,
        path: List[str],
    ) -> AsyncGenerator[str, None]:
        if not path:
            yield _sse({"error": "节点路径不能为空", "done": True})
            return

        messages = self.rag_engine.build_mindmap_messages(
            "generate_note",
            path=path,
        )
        async for evt in self._stream(api_key, messages, max_tokens=512):
            yield evt

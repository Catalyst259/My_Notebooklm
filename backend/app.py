import os
import re
import uuid
import shutil
import asyncio
import json
import random
import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Query
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from sentence_transformers import SentenceTransformer

from file_processor import FileProcessor
from knowledge_base import KnowledgeBase
from rag_engine import RAGEngine, build_generic_system_prompt
from quiz_engine import QuizEngine
from session_store import SessionStore
from memory_store import MemoryStore
from mindmap_store import MindMapStore
from mindmap_engine import MindMapEngine
from review_store import ReviewStore
from review_engine import ReviewEngine
from llm_grading import _extract_json as _llm_extract_json
from user_stats import UserStatsStore
from quiz_history import QuizHistoryStore

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
UPLOAD_BASE_DIR = os.path.join(BASE_DIR, 'data', 'uploaded')
VECTOR_STORE_BASE_DIR = os.path.join(BASE_DIR, 'data', 'vector_store')
SESSIONS_BASE_DIR = os.path.join(BASE_DIR, 'data', 'sessions')
MEMORY_BASE_DIR = os.path.join(BASE_DIR, 'data', 'memory')
MINDMAPS_BASE_DIR = os.path.join(BASE_DIR, 'data', 'mindmaps')
REVIEWS_BASE_DIR = os.path.join(BASE_DIR, 'data', 'reviews')
QUIZ_HISTORY_BASE_DIR = os.path.join(BASE_DIR, 'data', 'quiz_history')
USER_STATS_PATH = os.path.join(BASE_DIR, 'data')
ASSISTANTS_CONFIG_PATH = os.path.join(BASE_DIR, 'data', 'assistants_config.json')
os.makedirs(UPLOAD_BASE_DIR, exist_ok=True)
os.makedirs(VECTOR_STORE_BASE_DIR, exist_ok=True)
os.makedirs(SESSIONS_BASE_DIR, exist_ok=True)
os.makedirs(MEMORY_BASE_DIR, exist_ok=True)
os.makedirs(MINDMAPS_BASE_DIR, exist_ok=True)
os.makedirs(REVIEWS_BASE_DIR, exist_ok=True)
os.makedirs(QUIZ_HISTORY_BASE_DIR, exist_ok=True)

# --- Default Assistant Configuration (seed for first run) ---
_DEFAULT_ASSISTANTS = {
    "data_structures": {
        "id": "data_structures",
        "name": "数据结构与算法",
        "icon": "📚",
        "description": "C++ 数据结构与算法学习助手，支持教材、代码、笔记上传",
        "system_prompt_key": "data_structures",
        "color": "#4f46e5"
    },
    "computer_systems": {
        "id": "computer_systems",
        "name": "计算机系统",
        "icon": "💻",
        "description": "计算机系统学习助手（组成原理、操作系统、体系结构）",
        "system_prompt_key": "computer_systems",
        "color": "#059669"
    },
    "discrete_math": {
        "id": "discrete_math",
        "name": "离散数学",
        "icon": "🔢",
        "description": "离散数学学习助手（数理逻辑、图论、组合数学）",
        "system_prompt_key": "discrete_math",
        "color": "#d97706"
    },
    "machine_learning": {
        "id": "machine_learning",
        "name": "机器学习",
        "icon": "🤖",
        "description": "机器学习学习助手（监督学习、深度学习、NLP等）",
        "system_prompt_key": "machine_learning",
        "color": "#dc2626"
    }
}

_ICON_PALETTE = ["📖", "🎓", "🔬", "💡", "🧠", "📐", "🌐", "⚡", "🔧", "🎯"]
_COLOR_PALETTE = ["#6366f1", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316", "#06b6d4",
                  "#84cc16", "#a855f7", "#e11d48", "#0891b2"]


def _load_assistants_config() -> Dict[str, Any]:
    if os.path.exists(ASSISTANTS_CONFIG_PATH):
        with open(ASSISTANTS_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return dict(_DEFAULT_ASSISTANTS)


def _save_assistants_config(config: Dict[str, Any]):
    with open(ASSISTANTS_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


ASSISTANTS_CONFIG = _load_assistants_config()
_save_assistants_config(ASSISTANTS_CONFIG)

# --- Global shared instances ---
file_processor = FileProcessor()
# Shared embedding model loaded once - all KB instances use the same model
EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
print(f"Loading shared embedding model: {EMBEDDING_MODEL_NAME}...")
_embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
print("Shared embedding model loaded.")


# --- Assistant Registry ---
# Each assistant gets its own KnowledgeBase, RAGEngine, and conversation history
class AssistantInstance:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        assistant_id = config["id"]
        vector_store_path = os.path.join(VECTOR_STORE_BASE_DIR, assistant_id)
        os.makedirs(vector_store_path, exist_ok=True)
        
        self.knowledge_base = KnowledgeBase(
            model_name=EMBEDDING_MODEL_NAME,
            vector_store_path=vector_store_path,
            model=_embedding_model
        )
        self.rag_engine = RAGEngine(
            knowledge_base=self.knowledge_base,
            assistant_id=assistant_id,
            system_prompt=config.get("system_prompt")
        )
        self.quiz_engine = QuizEngine(
            knowledge_base=self.knowledge_base,
            assistant_id=assistant_id,
            assistant_name=config["name"]
        )
        self.session_store = SessionStore(SESSIONS_BASE_DIR, assistant_id)
        self.mindmap_store = MindMapStore(MINDMAPS_BASE_DIR, assistant_id)
        self.mindmap_engine = MindMapEngine(
            knowledge_base=self.knowledge_base,
            rag_engine=self.rag_engine,
            assistant_id=assistant_id,
            assistant_name=config["name"],
        )
        self.review_store = ReviewStore(REVIEWS_BASE_DIR, assistant_id)
        self.review_engine = ReviewEngine(self.review_store, assistant_id)


# Shared memory store across assistants (one file per assistant_id).
memory_store = MemoryStore(MEMORY_BASE_DIR)

# Global stores for streak and quiz history
user_stats_store = UserStatsStore(USER_STATS_PATH)
quiz_history_store = QuizHistoryStore(QUIZ_HISTORY_BASE_DIR)


# Initialize all assistants
assistant_registry: Dict[str, AssistantInstance] = {}
for config in ASSISTANTS_CONFIG.values():
    assistant_registry[config["id"]] = AssistantInstance(config)


def get_assistant(assistant_id: str) -> AssistantInstance:
    """Get assistant instance by ID, or raise 404."""
    if assistant_id not in assistant_registry:
        raise HTTPException(status_code=404, detail=f"Assistant '{assistant_id}' not found")
    return assistant_registry[assistant_id]


def get_upload_dir(assistant_id: str) -> str:
    """Get upload directory for a specific assistant."""
    upload_dir = os.path.join(UPLOAD_BASE_DIR, assistant_id)
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


# --- FastAPI app ---
app = FastAPI(title="Multi-Subject Learning Assistant")

# CORS: allow frontend on any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/assistants")
async def list_assistants():
    """Get list of available assistants."""
    return {
        "assistants": [
            {
                "id": config["id"],
                "name": config["name"],
                "icon": config["icon"],
                "description": config["description"],
                "color": config["color"]
            }
            for config in ASSISTANTS_CONFIG.values()
        ]
    }


@app.get("/api/stats")
async def stats(assistant_id: str = Query("data_structures")):
    """Get knowledge base statistics for a specific assistant."""
    assistant = get_assistant(assistant_id)
    return assistant.knowledge_base.get_stats()


@app.post("/api/upload")
async def upload_file(
    files: List[UploadFile] = File(...),
    assistant_id: str = Form("data_structures")
):
    """
    Upload one or more files, process them (parse + chunk + embed), and add to knowledge base
    of the specified assistant.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    assistant = get_assistant(assistant_id)
    upload_dir = get_upload_dir(assistant_id)
    results = []

    for file in files:
        if not file.filename:
            results.append({
                "file_name": "unknown",
                "success": False,
                "error": "No filename provided"
            })
            continue

        # Generate UUID filename
        file_ext = os.path.splitext(file.filename)[1].lower()
        file_uuid = uuid.uuid4().hex
        safe_filename = f"{file_uuid}{file_ext}"
        file_path = os.path.join(upload_dir, safe_filename)

        # Read and save file
        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)

        # Calculate file hash
        file_hash = hashlib.sha256(content).hexdigest()

        # Process the file
        try:
            result = file_processor.process_file(file_path)
        except Exception as e:
            # Clean up on failure
            if os.path.exists(file_path):
                os.remove(file_path)
            results.append({
                "file_name": file.filename,
                "success": False,
                "error": str(e)
            })
            continue

        # Add chunks to the assistant's knowledge base with full metadata
        try:
            assistant.knowledge_base.add_chunks(
                chunks=result['chunks'],
                file_uuid=file_uuid,
                original_name=file.filename,
                physical_path=file_path,
                file_size=len(content),
                file_hash=file_hash,
                total_tokens=result['total_tokens']
            )
            results.append({
                "file_name": file.filename,
                "success": True,
                "chunk_count": result['chunk_count'],
                "total_tokens": result['total_tokens'],
                "file_uuid": file_uuid
            })
        except Exception as e:
            # Clean up on failure
            if os.path.exists(file_path):
                os.remove(file_path)
            results.append({
                "file_name": file.filename,
                "success": False,
                "error": str(e)
            })

    success_count = sum(1 for r in results if r.get('success', False))
    return {
        "message": f"已处理 {len(files)} 个文件，{success_count} 个成功",
        "results": results
    }


@app.get("/api/files")
async def list_files(assistant_id: str = Query("data_structures")):
    """List all files in the assistant's knowledge base."""
    assistant = get_assistant(assistant_id)
    files = assistant.knowledge_base.get_files()
    return {"files": files}


@app.delete("/api/files/{file_uuid}")
async def delete_file(
    file_uuid: str,
    assistant_id: str = Query("data_structures")
):
    """Delete a specific file from the knowledge base."""
    assistant = get_assistant(assistant_id)
    try:
        assistant.knowledge_base.delete_file(file_uuid)
        return {"message": "文件已删除", "file_uuid": file_uuid}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/chat")
async def chat(
    message: str = Form(...),
    api_key: str = Form(...),
    assistant_id: str = Form("data_structures"),
    session_id: str = Form(""),
    client_date: str = Form("")
):
    """
    Chat endpoint with streaming response for a specific assistant.
    Uses RAG to retrieve context, then calls DeepSeek API.

    If ``session_id`` is empty or unknown, a new session is created and its id
    is emitted in the final SSE event so the client can adopt it.
    """
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key is required.")

    assistant = get_assistant(assistant_id)
    store = assistant.session_store

    # Resolve / create session
    if not session_id or not store.exists(session_id):
        session = store.create()
        session_id = session["id"]

    history = store.get_messages_for_llm(session_id)
    memory_note = memory_store.read(assistant_id)

    messages = assistant.rag_engine.build_messages(
        message,
        history=history,
        memory_note=memory_note,
    )

    # Persist user turn immediately (so a mid-stream disconnect still records the question).
    store.append_message(session_id, "user", message)

    if client_date:
        user_stats_store.record_activity(client_date)

    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )

    async def generate():
        full_response = ""
        try:
            stream = await client.chat.completions.create(
                model="deepseek-chat",
                messages=messages, # type: ignore
                stream=True,
                temperature=0.7,
                max_tokens=4096
            ) # type: ignore

            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        content = delta.content
                        full_response += content
                        yield f"data: {json.dumps({'content': content, 'done': False, 'session_id': session_id})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True, 'session_id': session_id})}\n\n"
            return

        store.append_message(session_id, "assistant", full_response)

        yield f"data: {json.dumps({'content': '', 'done': True, 'session_id': session_id})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/clear")
async def clear_history(assistant_id: str = Form("data_structures")):
    """Deprecated: delete the most-recent session for an assistant.

    Kept for compatibility with older frontends. Prefer ``DELETE /api/sessions/{id}``.
    """
    assistant = get_assistant(assistant_id)
    sid = assistant.session_store.most_recent_session_id()
    if sid:
        assistant.session_store.delete(sid)
    return {"message": "对话历史已清空", "assistant_id": assistant_id, "deleted_session_id": sid}


# --- Sessions ---------------------------------------------------------------

@app.get("/api/sessions")
async def list_sessions(assistant_id: str = Query("data_structures")):
    """List sessions for an assistant (newest first)."""
    assistant = get_assistant(assistant_id)
    return {"sessions": assistant.session_store.list_sessions()}


@app.post("/api/sessions")
async def create_session(
    assistant_id: str = Form("data_structures"),
    title: str = Form("")
):
    """Create a new empty session."""
    assistant = get_assistant(assistant_id)
    session = assistant.session_store.create(title=title or None)
    return {"session": session}


@app.get("/api/sessions/{session_id}")
async def get_session(
    session_id: str,
    assistant_id: str = Query("data_structures")
):
    """Fetch a full session (with all messages)."""
    assistant = get_assistant(assistant_id)
    try:
        return {"session": assistant.session_store.get(session_id)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@app.patch("/api/sessions/{session_id}")
async def rename_session(
    session_id: str,
    title: str = Form(...),
    assistant_id: str = Form("data_structures")
):
    """Rename a session."""
    assistant = get_assistant(assistant_id)
    try:
        return {"session": assistant.session_store.rename(session_id, title)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@app.delete("/api/sessions/{session_id}")
async def delete_session(
    session_id: str,
    assistant_id: str = Query("data_structures")
):
    """Delete a session."""
    assistant = get_assistant(assistant_id)
    assistant.session_store.delete(session_id)
    return {"message": "会话已删除", "session_id": session_id}


@app.delete("/api/sessions/{session_id}/messages/{index}")
async def delete_message(
    session_id: str,
    index: int,
    assistant_id: str = Query("data_structures")
):
    """Delete one message and its paired turn so user/assistant pairing stays intact."""
    assistant = get_assistant(assistant_id)
    try:
        session = assistant.session_store.delete_message_pair(session_id, index)
        return {"session": session}
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except IndexError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/sessions/{session_id}/regenerate")
async def regenerate_last(
    session_id: str,
    api_key: str = Form(...),
    assistant_id: str = Form("data_structures")
):
    """Re-run the last user turn after dropping the previous assistant reply.

    Streams the new reply just like /api/chat. Requires that the session ends
    in either an assistant or user turn; otherwise returns 400.
    """
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key is required.")

    assistant = get_assistant(assistant_id)
    store = assistant.session_store
    try:
        session = store.get(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session["messages"]:
        raise HTTPException(status_code=400, detail="会话为空，无法重新生成。")

    # Drop trailing assistant reply if present so we can re-ask the last user message.
    store.pop_last_assistant(session_id)
    session = store.get(session_id)
    if not session["messages"] or session["messages"][-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="最近一条不是用户消息，无法重新生成。")

    last_user_message = session["messages"][-1]["content"]

    # Build the LLM call from history minus the trailing user turn (it goes in as `query`).
    history_for_llm = [
        {"role": m["role"], "content": m["content"]}
        for m in session["messages"][:-1]
    ]
    memory_note = memory_store.read(assistant_id)
    messages = assistant.rag_engine.build_messages(
        last_user_message,
        history=history_for_llm,
        memory_note=memory_note,
    )

    client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    async def generate():
        full_response = ""
        try:
            stream = await client.chat.completions.create(
                model="deepseek-chat",
                messages=messages, # type: ignore
                stream=True,
                temperature=0.7,
                max_tokens=4096
            ) # type: ignore
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        full_response += delta.content
                        yield f"data: {json.dumps({'content': delta.content, 'done': False, 'session_id': session_id})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True, 'session_id': session_id})}\n\n"
            return

        store.append_message(session_id, "assistant", full_response)
        yield f"data: {json.dumps({'content': '', 'done': True, 'session_id': session_id})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# --- Memory note ------------------------------------------------------------

@app.get("/api/memory")
async def get_memory(assistant_id: str = Query("data_structures")):
    """Get the per-assistant memory note (plain text)."""
    get_assistant(assistant_id)  # 404 if unknown
    return {"assistant_id": assistant_id, "memory": memory_store.read(assistant_id)}


@app.put("/api/memory")
async def save_memory(
    assistant_id: str = Form("data_structures"),
    memory: str = Form("")
):
    """Save the per-assistant memory note."""
    get_assistant(assistant_id)
    try:
        memory_store.write(assistant_id, memory)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "备忘已保存", "assistant_id": assistant_id}


# --- Mind-Maps --------------------------------------------------------------

@app.get("/api/mindmaps")
async def list_mindmaps(assistant_id: str = Query("data_structures")):
    """List all mind-maps for an assistant (newest first)."""
    assistant = get_assistant(assistant_id)
    return {"mindmaps": assistant.mindmap_store.list()}


@app.post("/api/mindmaps")
async def create_mindmap(
    assistant_id: str = Form("data_structures"),
    title: str = Form("")
):
    """Create a new mind-map with a single root node."""
    assistant = get_assistant(assistant_id)
    mindmap = assistant.mindmap_store.create(title=title or None)
    return {"mindmap": mindmap}


@app.get("/api/mindmaps/{map_id}")
async def get_mindmap(
    map_id: str,
    assistant_id: str = Query("data_structures")
):
    """Fetch a full mind-map by id."""
    assistant = get_assistant(assistant_id)
    try:
        return {"mindmap": assistant.mindmap_store.get(map_id)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Mind-map not found")


@app.put("/api/mindmaps/{map_id}")
async def save_mindmap(
    map_id: str,
    assistant_id: str = Form("data_structures"),
    title: str = Form(""),
    jsmind_json: str = Form("")
):
    """Overwrite a mind-map's title and/or jsmind blob."""
    assistant = get_assistant(assistant_id)
    try:
        jsmind_data: Optional[Dict[str, Any]] = None
        if jsmind_json:
            try:
                jsmind_data = json.loads(jsmind_json)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid jsmind_json")
            if not isinstance(jsmind_data, dict):
                raise HTTPException(status_code=400, detail="jsmind_json must be an object")
        mindmap = assistant.mindmap_store.save(
            map_id,
            title=title if title else None,
            jsmind_json=jsmind_data,
        )
        return {"mindmap": mindmap}
    except KeyError:
        raise HTTPException(status_code=404, detail="Mind-map not found")


@app.delete("/api/mindmaps/{map_id}")
async def delete_mindmap(
    map_id: str,
    assistant_id: str = Query("data_structures")
):
    """Delete a mind-map."""
    assistant = get_assistant(assistant_id)
    assistant.mindmap_store.delete(map_id)
    return {"message": "思维导图已删除", "map_id": map_id}


# --- Mind-Map AI streaming endpoints ---

def _mindmap_sse_response(generator):
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/mindmaps/ai/generate-tree")
async def mindmap_generate_tree(
    api_key: str = Form(...),
    assistant_id: str = Form("data_structures"),
    topic: str = Form(...),
    depth: int = Form(2),
    width: int = Form(4),
):
    """Stream a Markdown-bullet mind-map tree for a given topic."""
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key is required.")
    assistant = get_assistant(assistant_id)
    return _mindmap_sse_response(
        assistant.mindmap_engine.stream_generate_tree(
            api_key=api_key, topic=topic, depth=depth, width=width,
        )
    )


@app.post("/api/mindmaps/ai/expand-node")
async def mindmap_expand_node(
    api_key: str = Form(...),
    assistant_id: str = Form("data_structures"),
    path_json: str = Form(...),
    siblings_json: str = Form("[]"),
    count: int = Form(4),
):
    """Stream Markdown-bullet child nodes for the target node identified by path."""
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key is required.")
    assistant = get_assistant(assistant_id)
    try:
        path = json.loads(path_json)
        siblings = json.loads(siblings_json) if siblings_json else []
        if not isinstance(path, list) or not isinstance(siblings, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="path_json/siblings_json must be JSON arrays.")
    return _mindmap_sse_response(
        assistant.mindmap_engine.stream_expand_node(
            api_key=api_key, path=path, siblings=siblings, count=count,
        )
    )


@app.post("/api/mindmaps/ai/generate-note")
async def mindmap_generate_note(
    api_key: str = Form(...),
    assistant_id: str = Form("data_structures"),
    path_json: str = Form(...),
):
    """Stream a short Markdown note for the target node identified by path."""
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key is required.")
    assistant = get_assistant(assistant_id)
    try:
        path = json.loads(path_json)
        if not isinstance(path, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="path_json must be a JSON array.")
    return _mindmap_sse_response(
        assistant.mindmap_engine.stream_generate_note(api_key=api_key, path=path)
    )


@app.post("/api/quiz/generate")
async def generate_quiz(
    api_key: str = Form(...),
    assistant_id: str = Form("data_structures"),
    count: int = Form(5),
    difficulty: str = Form("medium"),
    question_types: str = Form("mixed"),
    topic: str = Form("")
):
    """Generate a quiz for the selected assistant."""
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key is required.")
    assistant = get_assistant(assistant_id)
    try:
        return await assistant.quiz_engine.generate(
            api_key=api_key,
            count=count,
            difficulty=difficulty,
            question_types=question_types,
            topic=topic
        )
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quiz generation failed: {str(e)}")


@app.post("/api/quiz/grade")
async def grade_quiz(
    api_key: str = Form(...),
    assistant_id: str = Form("data_structures"),
    questions_json: str = Form(...),
    answers_json: str = Form(...),
    client_date: str = Form(""),
    difficulty: str = Form("medium")
):
    """Grade a submitted quiz. Auto-enroll wrong items into review."""
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key is required.")
    assistant = get_assistant(assistant_id)
    try:
        questions = json.loads(questions_json)
        answers = json.loads(answers_json)
        if not isinstance(questions, list) or not isinstance(answers, dict):
            raise ValueError("Invalid quiz payload.")
        grade_result = await assistant.quiz_engine.grade(api_key, questions, answers)

        # Record quiz history and activity
        if client_date:
            results_list = grade_result.get("results", [])
            if results_list:
                avg_score = sum(float(r.get("score", 0)) for r in results_list) / len(results_list)
                quiz_history_store.append(assistant_id, {
                    "date": client_date,
                    "score": round(avg_score, 4),
                    "count": len(results_list),
                    "difficulty": difficulty,
                })
            user_stats_store.record_activity(client_date)

        # Auto-enroll wrong items (score < 0.8) into review.
        for i, q in enumerate(questions):
            result = grade_result["results"][i] if i < len(grade_result["results"]) else {}
            score = float(result.get("score", 0))
            if score >= 0.8:
                continue
            qtype = q.get("type", "short_answer")
            item_type = "mcq" if qtype == "single_choice" else "qa"
            snapshot = {
                "front": q.get("question", ""),
                "back": q.get("answer", ""),
                "answer_key": q.get("answer", ""),
                "options": q.get("options", []),
                "explanation": q.get("explanation", ""),
                "user_answer": str(answers.get(q.get("id", ""), "")),
            }
            source = {
                "type": "quiz_wrong",
                "ref": q.get("id", ""),
                "label": q.get("knowledge_point", ""),
                "initial_signal": score,
            }
            srs = assistant.review_engine.seed_srs(item_type, initial_signal=score)
            new_item = assistant.review_store.create_item({
                "type": item_type,
                "snapshot": snapshot,
                "source": source,
                "srs": srs,
            })
            assistant.review_engine.add_to_today_queue_if_due(new_item)

        return grade_result
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quiz grading failed: {str(e)}")


@app.post("/api/kb/clear")
async def clear_knowledge_base(assistant_id: str = Form("data_structures")):
    """Clear the knowledge base for a specific assistant."""
    assistant = get_assistant(assistant_id)
    assistant.knowledge_base.clear()
    return {"message": "知识库已清空", "assistant_id": assistant_id}


def _generate_assistant_id(name: str) -> str:
    slug = re.sub(r'[^a-zA-Z0-9一-鿿]+', '_', name).strip('_').lower()
    if not slug:
        slug = "assistant"
    short_id = uuid.uuid4().hex[:6]
    return f"{slug}_{short_id}"


@app.post("/api/assistants/create")
async def create_assistant(
    name: str = Form(...),
    description: str = Form(...)
):
    """Create a new custom assistant."""
    name = name.strip()
    description = description.strip()
    if not name:
        raise HTTPException(status_code=400, detail="助手名称不能为空")
    if not description:
        raise HTTPException(status_code=400, detail="助手描述不能为空")

    assistant_id = _generate_assistant_id(name)

    icon = random.choice(_ICON_PALETTE)
    color = random.choice(_COLOR_PALETTE)
    system_prompt = build_generic_system_prompt(name, description)

    config = {
        "id": assistant_id,
        "name": name,
        "icon": icon,
        "description": description,
        "system_prompt_key": assistant_id,
        "system_prompt": system_prompt,
        "color": color
    }

    ASSISTANTS_CONFIG[assistant_id] = config
    _save_assistants_config(ASSISTANTS_CONFIG)

    assistant_registry[assistant_id] = AssistantInstance(config)

    return {
        "message": f"助手「{name}」创建成功",
        "assistant": {
            "id": assistant_id,
            "name": name,
            "icon": icon,
            "description": description,
            "color": color
        }
    }


@app.post("/api/assistants/delete")
async def delete_assistant(
    assistant_id: str = Form(...)
):
    """Delete an assistant and clean up all its data."""
    if assistant_id not in assistant_registry:
        raise HTTPException(status_code=404, detail=f"助手 '{assistant_id}' 不存在")

    assistant = assistant_registry[assistant_id]

    assistant.knowledge_base.clear()

    vector_store_path = os.path.join(VECTOR_STORE_BASE_DIR, assistant_id)
    if os.path.exists(vector_store_path):
        shutil.rmtree(vector_store_path)

    upload_dir = os.path.join(UPLOAD_BASE_DIR, assistant_id)
    if os.path.exists(upload_dir):
        shutil.rmtree(upload_dir)

    sessions_dir = os.path.join(SESSIONS_BASE_DIR, assistant_id)
    if os.path.exists(sessions_dir):
        shutil.rmtree(sessions_dir)

    mindmaps_dir = os.path.join(MINDMAPS_BASE_DIR, assistant_id)
    if os.path.exists(mindmaps_dir):
        shutil.rmtree(mindmaps_dir)

    reviews_dir = os.path.join(REVIEWS_BASE_DIR, assistant_id)
    if os.path.exists(reviews_dir):
        shutil.rmtree(reviews_dir)

    quiz_history_dir = os.path.join(QUIZ_HISTORY_BASE_DIR, assistant_id)
    if os.path.exists(quiz_history_dir):
        shutil.rmtree(quiz_history_dir)

    memory_store.delete(assistant_id)

    del assistant_registry[assistant_id]

    ASSISTANTS_CONFIG.pop(assistant_id, None)
    _save_assistants_config(ASSISTANTS_CONFIG)

    return {"message": f"助手已删除", "assistant_id": assistant_id}


# --- Review endpoints ------------------------------------------------------
# NB: Fixed-path routes (/queue/today, /draft) MUST come before /{item_id}
# parameterized routes, since FastAPI matches in declaration order.

@app.get("/api/reviews")
async def list_reviews(
    assistant_id: str = Query("data_structures"),
    include_archived: bool = Query(False),
):
    """List review items (index entries)."""
    assistant = get_assistant(assistant_id)
    return {"items": assistant.review_store.list_items(include_archived=include_archived)}


@app.get("/api/reviews/queue/today")
async def get_today_queue(
    assistant_id: str = Query("data_structures"),
    date: str = Query(""),
):
    """Get or generate today's review queue, with the full item dicts inlined."""
    assistant = get_assistant(assistant_id)
    queue = assistant.review_engine.get_or_create_today_queue(today=date or None)
    items_by_id: Dict[str, Any] = {}
    for entry in queue.get("entries", []):
        try:
            items_by_id[entry["item_id"]] = assistant.review_store.get_item(entry["item_id"])
        except KeyError:
            continue
    return {"queue": queue, "items": items_by_id}


@app.post("/api/reviews/draft")
async def draft_review_card(
    api_key: str = Form(...),
    assistant_id: str = Form("data_structures"),
    source_content: str = Form(...),
    source_context: str = Form(""),
):
    """AI-draft a review card from user-provided content."""
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key is required.")
    assistant = get_assistant(assistant_id)
    try:
        messages = assistant.rag_engine.build_review_card_messages(
            source_content=source_content,
            source_context=source_context,
        )
        client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        completion = await client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,  # type: ignore
            temperature=0.5,
            max_tokens=512,
        )
        raw = completion.choices[0].message.content or ""
        payload = _llm_extract_json(raw)
        front = str(payload.get("front", "")).strip()
        back = str(payload.get("back", "")).strip()
        if not front or not back:
            raise ValueError("LLM 未返回有效的 front/back。")
        return {"front": front, "back": back}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Card drafting failed: {str(e)}")


@app.post("/api/reviews")
async def create_review_item(
    assistant_id: str = Form("data_structures"),
    item_type: str = Form(...),
    snapshot_json: str = Form(...),
    source_json: str = Form(...),
):
    """Create a new review item (manual or from draft)."""
    assistant = get_assistant(assistant_id)
    try:
        snapshot = json.loads(snapshot_json)
        source = json.loads(source_json)
        if not isinstance(snapshot, dict) or not isinstance(source, dict):
            raise ValueError("snapshot_json and source_json must be objects.")
        srs = assistant.review_engine.seed_srs(item_type)
        item = assistant.review_store.create_item({
            "type": item_type,
            "snapshot": snapshot,
            "source": source,
            "srs": srs,
        })
        assistant.review_engine.add_to_today_queue_if_due(item)
        return {"item": item}
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/reviews/{item_id}")
async def get_review_item(
    item_id: str,
    assistant_id: str = Query("data_structures"),
):
    """Fetch a single review item."""
    assistant = get_assistant(assistant_id)
    try:
        return {"item": assistant.review_store.get_item(item_id)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Review item not found")


@app.patch("/api/reviews/{item_id}")
async def update_review_item(
    item_id: str,
    assistant_id: str = Form("data_structures"),
    snapshot_json: str = Form(""),
    status: str = Form(""),
):
    """Update a review item. PRD Q16: only card snapshots are mutable."""
    assistant = get_assistant(assistant_id)
    try:
        item = assistant.review_store.get_item(item_id)
        updates = {}
        if snapshot_json:
            if item.get("type") != "card":
                raise HTTPException(status_code=400, detail="只有手动卡片可以编辑快照。")
            snapshot = json.loads(snapshot_json)
            if not isinstance(snapshot, dict):
                raise ValueError("snapshot_json must be an object.")
            updates["snapshot"] = snapshot
        if status:
            if status not in ("active", "archived"):
                raise ValueError("status must be 'active' or 'archived'.")
            updates["status"] = status
        result = assistant.review_store.update_item(item_id, **updates)
        return {"item": result}
    except KeyError:
        raise HTTPException(status_code=404, detail="Review item not found")
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/reviews/{item_id}")
async def delete_review_item(
    item_id: str,
    assistant_id: str = Query("data_structures"),
):
    """Delete a review item."""
    assistant = get_assistant(assistant_id)
    assistant.review_store.delete_item(item_id)
    return {"message": "Review item deleted", "item_id": item_id}


@app.post("/api/reviews/{item_id}/archive")
async def archive_review_item(
    item_id: str,
    assistant_id: str = Form("data_structures"),
):
    assistant = get_assistant(assistant_id)
    try:
        item = assistant.review_store.archive_item(item_id)
        return {"item": item}
    except KeyError:
        raise HTTPException(status_code=404, detail="Review item not found")


@app.post("/api/reviews/{item_id}/reactivate")
async def reactivate_review_item(
    item_id: str,
    assistant_id: str = Form("data_structures"),
):
    assistant = get_assistant(assistant_id)
    try:
        item = assistant.review_store.reactivate_item(item_id)
        return {"item": item}
    except KeyError:
        raise HTTPException(status_code=404, detail="Review item not found")


@app.post("/api/reviews/{item_id}/grade")
async def grade_review_item(
    item_id: str,
    assistant_id: str = Form("data_structures"),
    user_response_json: str = Form(...),
    api_key: str = Form(""),
    client_date: str = Form(""),
):
    """Grade a review item, update SRS, and mark the entry done in today's queue.

    Per PRD Q20, api_key is optional: self_rating in user_response is allowed
    even when no key is configured.
    """
    assistant = get_assistant(assistant_id)
    try:
        item = assistant.review_store.get_item(item_id)
        user_response = json.loads(user_response_json)
        if not isinstance(user_response, dict):
            raise ValueError("user_response_json must be an object.")
        grade_result = await assistant.review_engine.grade_item(api_key, item, user_response)
        score = float(grade_result.get("score", 0))
        assistant.review_engine.apply_grade(item, score)
        assistant.review_store.update_item(item_id, srs=item["srs"])

        if client_date:
            user_stats_store.record_activity(client_date)

        # Update today's queue progress.
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        queue = assistant.review_store.load_daily_queue(today)
        if queue is not None:
            for entry in queue.get("entries", []):
                if entry.get("item_id") == item_id:
                    entry["status"] = "done"
                    entry["grade"] = score
                    entry["graded_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            assistant.review_store.save_daily_queue(today, queue)

        return {"grade": grade_result, "item": item}
    except KeyError:
        raise HTTPException(status_code=404, detail="Review item not found")
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Grading failed: {str(e)}")


@app.get("/api/stats/user")
async def get_user_stats():
    """Global streak and activity log."""
    return user_stats_store.get_stats()


@app.get("/api/stats/dashboard/{assistant_id}")
async def get_dashboard_stats(
    assistant_id: str,
    date: str = Query(""),
):
    """Dashboard data for one assistant: quiz history, review completion rate, KB stats."""
    assistant = get_assistant(assistant_id)

    quiz_records = quiz_history_store.get_recent(assistant_id, n=10)

    # Review completion rate for today
    review_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    queue = assistant.review_store.load_daily_queue(review_date)
    review_rate: Optional[float] = None
    review_done = 0
    review_total = 0
    if queue is not None:
        entries = queue.get("entries", [])
        review_total = len(entries)
        review_done = sum(1 for e in entries if e.get("status") == "done")
        review_rate = round(review_done / review_total, 4) if review_total > 0 else 0.0

    kb_stats = assistant.knowledge_base.get_stats()

    return {
        "assistant_id": assistant_id,
        "quiz_history": quiz_records,
        "review": {
            "date": review_date,
            "total": review_total,
            "done": review_done,
            "rate": review_rate,
        },
        "kb": kb_stats,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

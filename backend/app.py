import os
import re
import uuid
import shutil
import asyncio
import json
import random
import hashlib
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

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
UPLOAD_BASE_DIR = os.path.join(BASE_DIR, 'data', 'uploaded')
VECTOR_STORE_BASE_DIR = os.path.join(BASE_DIR, 'data', 'vector_store')
ASSISTANTS_CONFIG_PATH = os.path.join(BASE_DIR, 'data', 'assistants_config.json')
os.makedirs(UPLOAD_BASE_DIR, exist_ok=True)
os.makedirs(VECTOR_STORE_BASE_DIR, exist_ok=True)

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
        self.conversation_history: List[dict] = []


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
    assistant_id: str = Form("data_structures")
):
    """
    Chat endpoint with streaming response for a specific assistant.
    Uses RAG to retrieve context, then calls DeepSeek API.
    """
    # Validate API key
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key is required.")

    assistant = get_assistant(assistant_id)

    # Build RAG-enhanced messages using assistant's RAG engine and history
    messages = assistant.rag_engine.build_messages(message, assistant.conversation_history)

    # Store user message
    assistant.conversation_history.append({"role": "user", "content": message})

    # DeepSeek API config (locked)
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )

    async def generate():
        """Stream response from DeepSeek and accumulate."""
        full_response = ""
        try:
            stream = await client.chat.completions.create(
                model="deepseek-chat",  # deepseek-v4-flash equivalent
                messages=messages,
                stream=True,
                temperature=0.7,
                max_tokens=4096
            )

            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        content = delta.content
                        full_response += content
                        yield f"data: {json.dumps({'content': content, 'done': False})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
            return

        # Store assistant response
        assistant.conversation_history.append({"role": "assistant", "content": full_response})

        # Keep history manageable (last ~20 turns)
        while len(assistant.conversation_history) > 40:
            assistant.conversation_history.pop(0)

        yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"

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
    """Clear conversation history for a specific assistant."""
    assistant = get_assistant(assistant_id)
    assistant.conversation_history.clear()
    return {"message": "对话历史已清空", "assistant_id": assistant_id}


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
    answers_json: str = Form(...)
):
    """Grade a submitted quiz."""
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key is required.")
    assistant = get_assistant(assistant_id)
    try:
        questions = json.loads(questions_json)
        answers = json.loads(answers_json)
        if not isinstance(questions, list) or not isinstance(answers, dict):
            raise ValueError("Invalid quiz payload.")
        return await assistant.quiz_engine.grade(api_key, questions, answers)
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

    del assistant_registry[assistant_id]

    ASSISTANTS_CONFIG.pop(assistant_id, None)
    _save_assistants_config(ASSISTANTS_CONFIG)

    return {"message": f"助手已删除", "assistant_id": assistant_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

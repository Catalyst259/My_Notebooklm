import json
import re
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI


def extract_choice_letter(text: str) -> Optional[str]:
    """Extract the first A-D letter from text (case-insensitive)."""
    match = re.search(r"\b([A-D])\b", text.upper())
    return match.group(1) if match else None


def _extract_json(text: str) -> Dict[str, Any]:
    """Extract JSON from LLM output (strips Markdown code fences)."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise


async def grade_subjective_items(
    api_key: str,
    items: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Grade subjective (non-MCQ) items via DeepSeek.

    Each input item must have: id, type, question, reference_answer, user_answer.
    Returns: list of {question_id, score, is_correct, feedback, reference_answer},
             score clamped to [0,1], is_correct defaults to score >= 0.8.
    """
    prompt = f"""
请为以下测验答案评分。每题满分 1 分，可以给 0、0.5 或 1。
只输出合法 JSON，不要输出 Markdown。

输入:
{json.dumps(items, ensure_ascii=False)}

输出结构:
{{
  "results": [
    {{
      "question_id": "q1",
      "score": 0,
      "is_correct": false,
      "feedback": "简短中文反馈",
      "reference_answer": "参考答案"
    }}
  ]
}}
"""
    client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    completion = await client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "你是严格但鼓励学生的中文助教，只输出 JSON。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=2048,
    )
    raw = completion.choices[0].message.content or ""
    payload = _extract_json(raw)
    results = payload.get("results", [])
    normalized = []
    for r in results:
        score = float(r.get("score", 0))
        score = max(0, min(score, 1))
        normalized.append({
            "question_id": str(r.get("question_id", "")),
            "score": score,
            "is_correct": bool(r.get("is_correct", score >= 0.8)),
            "feedback": str(r.get("feedback", "")),
            "reference_answer": str(r.get("reference_answer", "")),
        })
    return normalized

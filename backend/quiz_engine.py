import json
import re
import uuid
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI


class QuizEngine:
    """Generates and grades quizzes using RAG context and an LLM."""

    def __init__(self, knowledge_base, assistant_id: str, assistant_name: str):
        self.knowledge_base = knowledge_base
        self.assistant_id = assistant_id
        self.assistant_name = assistant_name
        self.max_context_chars = 5000

    def _retrieve_context(self, topic: str = "", top_k: int = 8) -> tuple[str, List[str], bool]:
        query = topic.strip() or self.assistant_name
        results = self.knowledge_base.search(query, top_k=top_k)
        if not results:
            return "知识库暂无可用资料，请基于该学科的通用知识出题。", [], False

        parts = []
        source_files = []
        total = 0
        for item in results:
            source = item.get("file_name", "unknown")
            if source not in source_files:
                source_files.append(source)
            entry = f"来源: {source}\n内容:\n{item.get('text', '').strip()}\n"
            if total + len(entry) > self.max_context_chars:
                break
            parts.append(entry)
            total += len(entry)

        return "\n---\n".join(parts), source_files, True

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
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

    async def generate(
        self,
        api_key: str,
        count: int = 5,
        difficulty: str = "medium",
        question_types: str = "mixed",
        topic: str = "",
    ) -> Dict[str, Any]:
        count = max(1, min(count, 10))
        context, source_files, used_kb = self._retrieve_context(topic)

        prompt = f"""
你是{self.assistant_name}的专业助教。请基于资料为学生生成测验题。

学科: {self.assistant_name}
题目数量: {count}
难度: {difficulty}
题型: {question_types}
用户指定主题: {topic or "未指定"}

资料:
{context}

只输出合法 JSON，不要输出 Markdown。JSON 结构必须为:
{{
  "title": "测验标题",
  "questions": [
    {{
      "id": "q1",
      "type": "single_choice|short_answer|code_reading|proof",
      "question": "题干",
      "options": ["A. ...", "B. ..."],
      "answer": "参考答案",
      "explanation": "解析",
      "knowledge_point": "知识点",
      "source_files": ["资料文件名"]
    }}
  ]
}}

规则:
1. 单选题必须有 4 个选项，并在 answer 中给出正确选项字母和简短答案。
2. 简答、代码理解、证明题的 options 使用空数组。
3. 若资料不足，可以结合通用学科知识，但题目要标明相关知识点。
4. 所有内容使用中文。
"""
        client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        completion = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你只输出可被 json.loads 解析的 JSON。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
            max_tokens=4096,
        )
        raw = completion.choices[0].message.content or ""
        try:
            payload = self._extract_json(raw)
        except Exception as exc:
            raise ValueError(f"模型返回的测验 JSON 无法解析: {exc}")

        questions = payload.get("questions")
        if not isinstance(questions, list) or not questions:
            raise ValueError("模型未返回有效题目。")

        normalized = []
        for i, q in enumerate(questions[:count], start=1):
            qid = str(q.get("id") or f"q{i}")
            qtype = q.get("type") or "short_answer"
            options = q.get("options") if isinstance(q.get("options"), list) else []
            q_sources = q.get("source_files") if isinstance(q.get("source_files"), list) else source_files
            normalized.append({
                "id": qid,
                "type": qtype,
                "question": str(q.get("question", "")).strip(),
                "options": options,
                "answer": str(q.get("answer", "")).strip(),
                "explanation": str(q.get("explanation", "")).strip(),
                "knowledge_point": str(q.get("knowledge_point", "")).strip(),
                "source_files": q_sources,
            })

        return {
            "quiz_id": uuid.uuid4().hex,
            "assistant_id": self.assistant_id,
            "title": payload.get("title") or f"{self.assistant_name}测验",
            "used_knowledge_base": used_kb,
            "questions": normalized,
        }

    async def grade(self, api_key: str, questions: List[Dict[str, Any]], answers: Dict[str, str]) -> Dict[str, Any]:
        if not questions:
            raise ValueError("没有可评分的题目。")

        direct_results = []
        subjective_items = []

        for q in questions:
            qid = str(q.get("id", ""))
            user_answer = str(answers.get(qid, "")).strip()
            answer = str(q.get("answer", "")).strip()
            qtype = q.get("type")

            if qtype == "single_choice":
                correct_letter = self._choice_letter(answer)
                user_letter = self._choice_letter(user_answer)
                is_correct = bool(correct_letter and user_letter and correct_letter == user_letter)
                direct_results.append({
                    "question_id": qid,
                    "score": 1 if is_correct else 0,
                    "is_correct": is_correct,
                    "feedback": "回答正确。" if is_correct else f"回答错误。参考答案: {answer}",
                    "reference_answer": answer,
                })
            else:
                subjective_items.append({
                    "id": qid,
                    "type": qtype,
                    "question": q.get("question", ""),
                    "reference_answer": answer,
                    "user_answer": user_answer,
                })

        subjective_results = []
        if subjective_items:
            subjective_results = await self._grade_subjective(api_key, subjective_items)

        by_id = {r["question_id"]: r for r in direct_results + subjective_results}
        ordered = []
        for q in questions:
            qid = str(q.get("id", ""))
            ordered.append(by_id.get(qid, {
                "question_id": qid,
                "score": 0,
                "is_correct": False,
                "feedback": "未能评分。",
                "reference_answer": q.get("answer", ""),
            }))

        total = sum(float(r.get("score", 0)) for r in ordered)
        return {
            "total_score": total,
            "max_score": len(questions),
            "results": ordered,
        }

    @staticmethod
    def _choice_letter(text: str) -> Optional[str]:
        match = re.search(r"\b([A-D])\b", text.upper())
        return match.group(1) if match else None

    async def _grade_subjective(self, api_key: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
        payload = self._extract_json(raw)
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

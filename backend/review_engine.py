from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from review_store import ReviewStore, _now_iso
from llm_grading import grade_subjective_items, extract_choice_letter


SELF_RATING_TO_SCORE = {
    "again": 0.0,
    "hard":  0.5,
    "good":  1.0,
}


def _today_iso_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _date_plus(date_str: str, days: int) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return (d + timedelta(days=days)).strftime("%Y-%m-%d")


def _days_between(later: str, earlier: str) -> int:
    a = datetime.strptime(later, "%Y-%m-%d")
    b = datetime.strptime(earlier, "%Y-%m-%d")
    return (a - b).days


class ReviewEngine:
    """Owns SRS scheduling and queue generation for review items."""

    DAILY_CAP = 20

    def __init__(self, review_store: ReviewStore, assistant_id: str):
        self.store = review_store
        self.assistant_id = assistant_id

    # --- SRS seeding & update ---------------------------------------------

    def seed_srs(self, item_type: str, initial_signal: Optional[float] = None) -> Dict[str, Any]:
        """Initial srs block for new item.

        mcq/qa with signal 0.5 -> interval 2, next = +2 days
        otherwise -> interval 0, next = today (so item lands in today's queue)
        """
        today = _today_iso_date()
        if item_type in ("mcq", "qa") and initial_signal == 0.5:
            interval = 2
        else:
            interval = 0
        return {
            "interval_days": interval,
            "ease": 2.5,
            "next_review": _date_plus(today, interval),
            "review_count": 0,
            "last_grade": initial_signal if item_type in ("mcq", "qa") else None,
        }

    def apply_grade(self, item: Dict[str, Any], score: float) -> Dict[str, Any]:
        """Mutate item with new srs based on grade."""
        srs = dict(item.get("srs", {}))
        today = _today_iso_date()
        current_interval = int(srs.get("interval_days", 1) or 1)
        if score >= 1.0:
            new_interval = max(1, round(current_interval * 2.5))
        else:
            new_interval = 1
        srs["interval_days"] = new_interval
        srs["next_review"] = _date_plus(today, new_interval)
        srs["review_count"] = int(srs.get("review_count", 0)) + 1
        srs["last_grade"] = score
        item["srs"] = srs
        return item

    # --- daily queue -------------------------------------------------------

    def _source_weight(self, item: Dict[str, Any]) -> int:
        """Lower is higher priority."""
        source = item.get("source", {})
        src = source.get("type", "")
        last_grade = item.get("srs", {}).get("last_grade")
        if last_grade is None:
            last_grade = source.get("initial_signal")
        if src == "quiz_wrong" and last_grade == 0:
            return 0
        if src == "quiz_wrong" and last_grade == 0.5:
            return 1
        if src == "quiz_wrong":
            return 2
        return 3

    def build_daily_queue(self, today: str) -> Dict[str, Any]:
        """Generate today's queue from active due items, capped at DAILY_CAP."""
        index = self.store.list_items(include_archived=False)
        candidates: List[Dict[str, Any]] = []
        for entry in index:
            if entry.get("next_review", "9999-12-31") > today:
                continue
            try:
                candidates.append(self.store.get_item(entry["id"]))
            except KeyError:
                continue

        def sort_key(it: Dict[str, Any]):
            days_overdue = _days_between(today, it["srs"]["next_review"])
            return (
                -days_overdue,
                self._source_weight(it),
                it.get("created_at", ""),
            )

        candidates.sort(key=sort_key)
        selected = candidates[:self.DAILY_CAP]
        return {
            "date": today,
            "assistant_id": self.assistant_id,
            "generated_at": _now_iso(),
            "entries": [
                {"item_id": it["id"], "status": "pending"} for it in selected
            ],
        }

    def get_or_create_today_queue(self, today: Optional[str] = None) -> Dict[str, Any]:
        today = today or _today_iso_date()
        existing = self.store.load_daily_queue(today)
        if existing is not None:
            return existing
        queue = self.build_daily_queue(today)
        self.store.save_daily_queue(today, queue)
        return queue

    def add_to_today_queue_if_due(self, item: Dict[str, Any]) -> None:
        """If `item` is due today and today's queue already exists on disk, append it."""
        today = _today_iso_date()
        next_review = item.get("srs", {}).get("next_review", "9999-12-31")
        if next_review > today:
            return
        queue = self.store.load_daily_queue(today)
        if queue is None:
            return
        entries = queue.get("entries", [])
        if any(e.get("item_id") == item["id"] for e in entries):
            return
        if len(entries) >= self.DAILY_CAP:
            return
        entries.append({"item_id": item["id"], "status": "pending"})
        queue["entries"] = entries
        self.store.save_daily_queue(today, queue)

    # --- grading dispatch --------------------------------------------------

    async def grade_item(
        self,
        api_key: str,
        item: Dict[str, Any],
        user_response: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Grade a single review item by type dispatch.

        Returns: {score, is_correct, feedback, reference_answer, used_fallback}
        """
        item_type = item["type"]
        snapshot = item.get("snapshot", {})
        reference_answer = str(
            snapshot.get("answer_key")
            or snapshot.get("back")
            or ""
        )

        # Explicit self-rating short-circuit (works for any type).
        self_rating = user_response.get("self_rating")
        if self_rating is not None:
            score = self._coerce_rating(self_rating)
            return {
                "score": score,
                "is_correct": score >= 0.8,
                "feedback": "已根据自评更新进度。",
                "reference_answer": reference_answer,
                "used_fallback": True,
            }

        if item_type == "mcq":
            user_answer = str(user_response.get("answer", "")).strip()
            correct_letter = extract_choice_letter(str(snapshot.get("answer_key", "")))
            user_letter = extract_choice_letter(user_answer)
            is_correct = bool(correct_letter and user_letter and correct_letter == user_letter)
            score = 1.0 if is_correct else 0.0
            explanation = str(snapshot.get("explanation", "")).strip()
            feedback = "回答正确。" if is_correct else (
                f"回答错误。参考答案: {correct_letter or reference_answer}"
                + (f"\n解析: {explanation}" if explanation else "")
            )
            return {
                "score": score,
                "is_correct": is_correct,
                "feedback": feedback,
                "reference_answer": reference_answer,
                "used_fallback": False,
            }

        if item_type == "qa":
            user_answer = str(user_response.get("answer", "")).strip()
            if not api_key or not user_answer:
                # Fall back to self-rating (treated as 0.5 if neutral signal absent).
                return {
                    "score": 0.5,
                    "is_correct": False,
                    "feedback": "未提供 API Key 或答案为空，已按模糊处理；请用自评按钮覆盖。",
                    "reference_answer": reference_answer,
                    "used_fallback": True,
                }
            grade_input = [{
                "id": item["id"],
                "type": "short_answer",
                "question": snapshot.get("front", ""),
                "reference_answer": reference_answer,
                "user_answer": user_answer,
            }]
            try:
                results = await grade_subjective_items(api_key, grade_input)
            except Exception as exc:
                return {
                    "score": 0.5,
                    "is_correct": False,
                    "feedback": f"LLM 批改失败 ({exc})；已按模糊处理，可用自评覆盖。",
                    "reference_answer": reference_answer,
                    "used_fallback": True,
                }
            r = results[0] if results else {}
            score = float(r.get("score", 0))
            return {
                "score": score,
                "is_correct": bool(r.get("is_correct", score >= 0.8)),
                "feedback": str(r.get("feedback", "")),
                "reference_answer": str(r.get("reference_answer", reference_answer)),
                "used_fallback": False,
            }

        # card -> always self-rating; if not provided, default to 'hard'
        return {
            "score": 0.5,
            "is_correct": False,
            "feedback": "卡片类型需要自评。",
            "reference_answer": reference_answer,
            "used_fallback": True,
        }

    @staticmethod
    def _coerce_rating(rating: Any) -> float:
        if isinstance(rating, (int, float)):
            return max(0.0, min(1.0, float(rating)))
        s = str(rating).lower().strip()
        if s in SELF_RATING_TO_SCORE:
            return SELF_RATING_TO_SCORE[s]
        try:
            return max(0.0, min(1.0, float(s)))
        except ValueError:
            return 0.5

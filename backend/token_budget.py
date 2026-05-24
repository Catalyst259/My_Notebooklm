from typing import List, Dict

from file_processor import FileProcessor


# Shared tokenizer (jieba + whitespace) — same as the chunker, so chunk-size
# constants and history-budget constants are expressed in the same units.
_tokenizer = FileProcessor()

# Per-message structural overhead in tokens (role marker + separators).
# Roughly matches OpenAI's "4 tokens per message" rule of thumb.
PER_MESSAGE_OVERHEAD = 4

DEFAULT_HISTORY_BUDGET = 6000


def count_message_tokens(message: Dict[str, str]) -> int:
    """Approximate token count for a single chat message dict."""
    content = message.get("content", "") or ""
    return _tokenizer.count_tokens(content) + PER_MESSAGE_OVERHEAD


def trim_history(
    history: List[Dict[str, str]],
    budget: int = DEFAULT_HISTORY_BUDGET,
) -> List[Dict[str, str]]:
    """Keep the newest suffix of ``history`` whose total token count fits in ``budget``.

    Walks newest-to-oldest, accumulating until the next message would exceed
    the budget. Always returns at least the most recent message (even if it
    alone exceeds the budget — the caller still needs the user's latest turn
    to be visible).
    """
    if not history:
        return []

    kept_reverse: List[Dict[str, str]] = []
    used = 0
    for msg in reversed(history):
        cost = count_message_tokens(msg)
        if kept_reverse and used + cost > budget:
            break
        kept_reverse.append(msg)
        used += cost

    return list(reversed(kept_reverse))

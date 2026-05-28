# Review Feature — Phased Implementation Plan

## Context

This plan implements the spaced-repetition review system specified in `plans/review-feature-prd.md`. It mirrors verified patterns from the existing codebase: persistence follows `session_store.py` / `mindmap_store.py`; API endpoints follow `app.py` form/query conventions; frontend follows the `mindmapManager` singleton model.

Each phase is self-contained. A new chat session can pick up any phase by reading: (1) this plan, (2) `plans/review-feature-prd.md`, (3) the cited reference files listed in Phase 0.

**Locked decisions** (22 design choices) are recorded in the PRD's "Implementation Decisions" section. Do not re-litigate them mid-implementation; if a decision proves wrong, surface it before changing.

---

## Phase 0: Documentation Discovery (read before starting)

These code locations are the authoritative templates. Read them before writing any new code. Do NOT invent alternative patterns.

### Backend persistence template

- `backend/session_store.py:9-18` — `_now_iso()` and `_atomic_write_json()` helpers (copy verbatim into `review_store.py`)
- `backend/session_store.py:49-82` — `_index_path`, `_load_index`, `_save_index`, `_upsert_index`, `_remove_from_index` (mirror exactly)
- `backend/mindmap_store.py:42-47` — class docstring with file-layout comment (mirror style)
- `backend/mindmap_store.py:112-158` — `list / create / get / exists / save / delete` public surface

**Conventions verified:**
- Per-assistant subdirectory: `{base_dir}/{assistant_id}/`
- One JSON file per entity: `{entity_id}.json`
- One `_index.json` per assistant; entries are lightweight derived metadata, newest first
- Missing entity → raise `KeyError`
- Corrupt `_index.json` → return `[]` (silent recovery)
- Atomic write: write to `.tmp`, then `os.replace`
- No schema validation, no version field, no locking — full rewrite per save

### Quiz grading template (for shared subjective grading)

- `backend/quiz_engine.py:40-52` — `_extract_json()`: strips ```json fences, falls back to outermost `{...}`
- `backend/quiz_engine.py:201-204` — `_choice_letter()`: `re.search(r"\b([A-D])\b", text.upper())`
- `backend/quiz_engine.py:206-251` — `_grade_subjective()`: prompt template, DeepSeek call, normalization with `score` clamped to `[0,1]` and `is_correct` defaulting to `score >= 0.8`

**Anti-patterns to avoid:**
- Do NOT add Pydantic models; the codebase uses dict-based payloads
- Do NOT add retry loops; existing engine has none
- Do NOT add timeout configs beyond what `AsyncOpenAI` provides
- Do NOT invent `correct_answer` field in returns — the convention is `reference_answer`

### API endpoint template

- `backend/app.py:108-138` — `AssistantInstance.__init__` composition (add `review_store` and `review_engine` here)
- `backend/app.py:150-154` — `get_assistant()` 404 helper (reuse, do not duplicate)
- `backend/app.py:411-561` — session CRUD endpoints (mirror form/query conventions)
- `backend/app.py:589-736` — mind-map CRUD + streaming endpoints (closest analog to review endpoints)
- `backend/app.py:661-670` — `_mindmap_sse_response()` helper (reuse for any review streaming, or copy the wrapper)
- `backend/app.py:739-788` — quiz endpoints (note `questions_json` / `answers_json` form-string convention)

**Conventions verified:**
- GET/DELETE: `assistant_id: str = Query("data_structures")`
- POST/PUT: `assistant_id: str = Form("data_structures")`
- Complex payloads: stringified JSON in form fields (e.g. `snapshot_json`, `source_json`)
- API key check: `if not api_key: raise HTTPException(status_code=400, detail="API Key is required.")`
- `KeyError` → 404; `ValueError` / `IndexError` / `json.JSONDecodeError` → 400; generic → 500

### Frontend manager template

- `frontend/js/app.js:19-31` — manager init order (`reviewManager.init()` goes here)
- `frontend/js/app.js:88-109` — `setBodyMode()` and list-container toggle (add `'review'` mode + `reviewListContainer`)
- `frontend/js/mindmap.js:9-34` — singleton skeleton with `_inited` guard (recommended style)
- `frontend/js/mindmap.js:97-115` — view switching pattern (deactivate all `.view`, activate target, call `app.setBodyMode`)
- `frontend/js/mindmap.js:248-280` — modal show/hide + focus pattern
- `frontend/js/mindmap.js:721-765` — debounced autosave + `flushSave()` + `_forceFlushSync()` via `sendBeacon` (NOT needed for review v1 because each item submission is its own PUT, but the unload pattern may still be relevant for daily-queue progress)
- `frontend/js/quiz.js:181-275` — single-question render + submit pattern (closest analog to one-at-a-time review)
- `frontend/js/api.js:211-252` — `generateQuiz` / `gradeQuiz` reference for new review API methods
- `frontend/js/api.js:305-354` — mind-map CRUD API methods (mirror shape exactly)
- `frontend/js/api.js:356-396` — streaming API method shape (for AI card draft endpoint)

**Known mismatches (do not propagate):**
- `frontend/js/quiz.js:247-253` reads `result.user_answer` / `result.correct_answer` but backend returns neither. For review, the new frontend code must use `result.reference_answer` (the actual backend field). Do not copy the quiz.js mismatch into review.js.

**Singleton export style:** `const reviewManager = window.reviewManager = new ReviewManager();` (matches `mindmapManager`).

### Index.html script load order

The new `<script src="js/review.js?v=1"></script>` must load **before** `app.js` (because `app.js` calls `reviewManager.init()`). Same pattern as `js/mindmap.js`.

---

## Phase 1: Backend persistence — `review_store.py`

**Goal:** Implement durable per-assistant storage of review items and daily queues. No SRS logic, no LLM, no API endpoints yet.

### What to implement

Create `backend/review_store.py` modeled on `backend/mindmap_store.py:1-159`.

**File layout:**
```
data/reviews/{assistant_id}/
  items/{item_id}.json          ← one file per review item
  _index.json                   ← lightweight summary, newest first
  daily_queue_{YYYY-MM-DD}.json ← one file per day
```

**Class signature:**
```python
class ReviewStore:
    """JSON-file-backed review item collection for a single assistant.

    Layout:
      {base_dir}/{assistant_id}/items/{item_id}.json
      {base_dir}/{assistant_id}/_index.json
      {base_dir}/{assistant_id}/daily_queue_{date}.json
    """

    INDEX_FILE = "_index.json"
    ITEMS_SUBDIR = "items"

    def __init__(self, base_dir: str, assistant_id: str): ...

    # Items
    def list_items(self, include_archived: bool = False) -> List[Dict[str, Any]]: ...
    def create_item(self, item: Dict[str, Any]) -> Dict[str, Any]: ...
    def get_item(self, item_id: str) -> Dict[str, Any]: ...
    def exists(self, item_id: str) -> bool: ...
    def update_item(self, item_id: str, **fields) -> Dict[str, Any]: ...
    def delete_item(self, item_id: str) -> None: ...
    def archive_item(self, item_id: str) -> Dict[str, Any]: ...
    def reactivate_item(self, item_id: str) -> Dict[str, Any]: ...

    # Daily queue
    def load_daily_queue(self, date: str) -> Optional[Dict[str, Any]]: ...
    def save_daily_queue(self, date: str, queue: Dict[str, Any]) -> None: ...
```

**Item JSON shape** (matches PRD):
```json
{
  "id": "rv_xxxxxxxx",
  "assistant_id": "data_structures",
  "type": "mcq | qa | card",
  "status": "active | archived",
  "snapshot": {
    "front": "...",
    "back": "...",
    "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
    "answer_key": "B",
    "explanation": "..."
  },
  "source": {
    "type": "quiz_wrong | chat_message | mindmap_node",
    "ref": "...",
    "label": "..."
  },
  "srs": {
    "interval_days": 1,
    "ease": 2.5,
    "next_review": "2026-05-29",
    "review_count": 0,
    "last_grade": null
  },
  "created_at": "2026-05-28T12:00:00Z",
  "updated_at": "2026-05-28T12:00:00Z"
}
```

**Index entry shape:**
```json
{
  "id": "rv_xxxxxxxx",
  "type": "mcq",
  "status": "active",
  "next_review": "2026-05-29",
  "front_preview": "first 60 chars of snapshot.front",
  "source_type": "quiz_wrong",
  "updated_at": "..."
}
```

**Daily queue JSON shape:**
```json
{
  "date": "2026-05-28",
  "assistant_id": "data_structures",
  "generated_at": "...",
  "entries": [
    { "item_id": "rv_xxxxxxxx", "status": "pending" },
    { "item_id": "rv_yyyyyyyy", "status": "done", "grade": 0.5, "graded_at": "..." }
  ]
}
```

### Documentation references

- Copy `_now_iso` and `_atomic_write_json` verbatim from `session_store.py:9-18`
- Mirror `_load_index` / `_save_index` / `_upsert_index` / `_remove_from_index` from `session_store.py:49-82`
- Mirror `create` / `get` / `exists` / `delete` from `mindmap_store.py:112-158`
- Use `uuid.uuid4().hex[:8]` and prefix with `"rv_"` for item ids (mirrors `mm_<8hex>` from `mindmap_store.py`)

### Verification checklist

- [ ] Round-trip: `create_item → get_item → update_item → list_items → archive_item → reactivate_item → delete_item` works via `curl` or Python REPL
- [ ] `list_items(include_archived=False)` excludes archived; `include_archived=True` includes them
- [ ] Corrupt `_index.json` returns `[]` (test by writing invalid JSON to the file, then calling `list_items`)
- [ ] Missing item file raises `KeyError`
- [ ] `daily_queue_2026-05-28.json` survives round-trip
- [ ] Atomic write: kill process mid-save, verify either old or new file present, never a partial `.tmp` left

### Anti-pattern guards

- Do NOT use Pydantic models; pure dicts only
- Do NOT introduce schema validation; trust callers
- Do NOT add a separate index for daily queues (each daily queue file is self-describing)
- Do NOT skip `_atomic_write_json` for any write path

---

## Phase 2: Backend SRS scheduling — `review_engine.py`

**Goal:** Implement the spaced-repetition scheduling logic and queue generation. No LLM yet; subjective grading dispatch comes in Phase 3.

### What to implement

Create `backend/review_engine.py`. This is a deep module that owns:
- Initial SRS seeding for newly created items
- SRS update on grade
- Daily queue selection with priority sorting and the 20-item soft cap
- Self-rating dispatch for `card` items

**Class signature:**
```python
class ReviewEngine:
    """Owns SRS scheduling and queue generation for review items."""

    DAILY_CAP = 20

    def __init__(self, review_store: ReviewStore, assistant_id: str): ...

    # Item creation
    def seed_srs(self, item_type: str, initial_signal: Optional[float] = None) -> Dict[str, Any]:
        """Return the initial srs block for a new item.

        Rules (locked in PRD Q12):
          - mcq/qa with initial_signal == 0.0  → interval_days=1, ease=2.5, next_review=tomorrow
          - mcq/qa with initial_signal == 0.5  → interval_days=2, ease=2.5, next_review=+2 days
          - card                              → interval_days=1, ease=2.5, next_review=tomorrow
        """

    # SRS update
    def apply_grade(self, item: Dict[str, Any], score: float) -> Dict[str, Any]:
        """Mutate and return item with new srs block.

        Rules (locked in PRD Q5):
          - score == 1.0 → interval_days *= 2.5 (rounded), next_review = today + new_interval
          - score == 0.0 or score == 0.5 → interval_days = 1, next_review = tomorrow
          - review_count += 1
          - last_grade = score
        """

    # Queue generation
    def build_daily_queue(self, today: str) -> Dict[str, Any]:
        """Generate today's queue per PRD Q13/Q14.

        Selection:
          1. Filter active items with next_review <= today
          2. Sort by priority:
             a. Days overdue (more = higher priority)
             b. Source weakness: quiz_wrong (last_grade==0) > quiz_wrong (last_grade==0.5) > card
             c. Created_at ascending (older first)
          3. Cap at DAILY_CAP entries
        """

    # Resume / regenerate logic
    def get_or_create_today_queue(self, today: str) -> Dict[str, Any]:
        """If daily_queue_{today}.json exists, return it. Otherwise build and persist."""
```

### Documentation references

- For datetime handling, follow `session_store.py:9-11` style (`datetime.now(timezone.utc)`)
- For ID/date formatting, use `YYYY-MM-DD` strings (do not introduce a Date class)
- This module has no direct codebase analog — it is the new logic this feature adds

### Verification checklist

- [ ] Unit test (small Python script or pytest): seed for `(qa, 0.0)` returns interval 1; seed for `(qa, 0.5)` returns interval 2
- [ ] `apply_grade` with score 1 on interval=2 produces interval=5
- [ ] `apply_grade` with score 0 on any interval resets to 1
- [ ] `build_daily_queue` returns ≤ 20 entries even when 50 items are due
- [ ] Priority sort: a 5-day-overdue card sorts ahead of a 0-day-overdue quiz_wrong
- [ ] `get_or_create_today_queue` is idempotent: calling twice on same date returns same queue
- [ ] Calling on a new date generates a fresh queue

### Anti-pattern guards

- Do NOT add user-configurable SRS parameters; the constants are locked
- Do NOT add minute-level scheduling; date granularity only
- Do NOT use `datetime.now()` without timezone; always `timezone.utc`
- Do NOT discard overdue items above the cap; they remain due and roll over

---

## Phase 3: Shared subjective grading

**Goal:** Extract `_grade_subjective` from `quiz_engine.py` into a shared function, then have both `quiz_engine.QuizEngine` and a new `review_engine.ReviewEngine.grade_item` call it.

### What to implement

1. **New module: `backend/llm_grading.py`** (or place in `rag_engine.py` if you prefer minimal new files — but a separate file is cleaner since it has no RAG dependency).

Function signature:
```python
async def grade_subjective_items(
    api_key: str,
    items: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Grade subjective (non-MCQ) items via DeepSeek.

    Each input item must have: id, type, question, reference_answer, user_answer.
    Returns: list of {question_id, score, is_correct, feedback, reference_answer},
             score clamped to [0,1], is_correct defaults to score >= 0.8.
    """
```

2. **Update `backend/quiz_engine.py:206-251`:** Delete the local `_grade_subjective` method and have `QuizEngine.grade(...)` call `grade_subjective_items(api_key, subjective_items)` instead.

3. **Add to `review_engine.py`:**
```python
async def grade_item(
    self,
    api_key: str,
    item: Dict[str, Any],
    user_response: Dict[str, Any]
) -> Dict[str, Any]:
    """Grade a single review item by type dispatch.

    user_response shape varies by type:
      - mcq:  {"answer": "B"}
      - qa:   {"answer": "..."}        # if api_key empty → self_rating path
      - qa:   {"self_rating": 0.5}     # explicit self-rating
      - card: {"self_rating": 1.0}

    Returns: {score: 0|0.5|1, is_correct: bool, feedback: str, reference_answer: str, used_fallback: bool}
    """
```

Type dispatch:
- `mcq`: use `QuizEngine._choice_letter` (move it to `llm_grading.py` as a public `extract_choice_letter`, or duplicate the 4-line regex)
- `qa`: if `user_response.get("self_rating") is not None` OR `api_key` is empty/falsy → self-rating path; otherwise call `grade_subjective_items`
- `card`: always self-rating

Self-rating mapping:
```python
SELF_RATING_TO_SCORE = {
    "again": 0.0,  # "不会"
    "hard":  0.5,  # "模糊"
    "good":  1.0,  # "会"
}
```

### Documentation references

- Copy the prompt block verbatim from `quiz_engine.py:213-225`
- Copy the `AsyncOpenAI` call block verbatim from `quiz_engine.py:227-237`
- Copy the normalization loop verbatim from `quiz_engine.py:239-251`
- Use `_extract_json` from `quiz_engine.py:40-52` — either move it to `llm_grading.py` as a module-level helper or import it from `quiz_engine`

### Verification checklist

- [ ] `quiz_engine.py` no longer defines `_grade_subjective`
- [ ] Existing quiz grading endpoint (`POST /api/quiz/grade`) still works end-to-end (regression check: generate a quiz, answer, submit, verify result structure unchanged)
- [ ] `grade_item` for `mcq` with correct answer returns `score=1, used_fallback=False`, no LLM call
- [ ] `grade_item` for `qa` with empty api_key returns `used_fallback=True` and uses self-rating
- [ ] `grade_item` for `card` always returns `used_fallback=True`

### Anti-pattern guards

- Do NOT change the prompt wording when extracting — preserve exact behavior
- Do NOT introduce a new `correct_answer` field; the established field is `reference_answer`
- Do NOT call the LLM for `mcq`; local grading is required for performance and determinism

---

## Phase 4: AI card drafting

**Goal:** When the user marks chat content or a mind-map node for review, an endpoint generates a draft `{front, back}` for them to review and edit.

### What to implement

1. **Add to `backend/rag_engine.py`:**

```python
REVIEW_CARD_DRAFT_PROMPT = (
    "你正在帮助学生把一段学习内容整理成一张复习卡片。"
    "请基于提供的内容生成一张 Anki 风格的卡片："
    "front 是一个简短的问题或提示（不超过 50 字），"
    "back 是简明的中文答案（2-4 句话，可包含必要的代码或公式）。"
    "只输出合法 JSON，不要输出 Markdown 代码块。"
    "结构：{\"front\": \"...\", \"back\": \"...\"}"
)


def build_review_card_messages(
    self,
    source_content: str,
    source_context: str = "",
) -> List[Dict[str, str]]:
    """Build messages for AI card drafting. RAG retrieval is optional here
    since the source_content is already user-selected; do a top-3 retrieval
    on source_content to supply supporting context but cap at 1500 chars."""
```

2. **Add endpoint `POST /api/reviews/ai/draft-card`:**

```python
@app.post("/api/reviews/ai/draft-card")
async def draft_review_card(
    api_key: str = Form(...),
    assistant_id: str = Form(...),
    source_content: str = Form(...),
    source_context: str = Form(""),
):
    """Returns {"front": "...", "back": "..."} as JSON (not streamed)."""
```

This endpoint is NOT streamed — the response is short (one JSON object) and the user must edit it in a modal before saving. Streaming adds complexity without benefit here.

### Documentation references

- Prompt structure mirrors `MINDMAP_OP_PROMPTS["generate_note"]` style in `rag_engine.py` (concise, output-format strict)
- API call follows `quiz_engine.py:227-237` (non-streaming `chat.completions.create`)
- JSON parsing follows `quiz_engine.py:40-52` (`_extract_json`)

### Verification checklist

- [ ] `curl -X POST /api/reviews/ai/draft-card -F api_key=... -F assistant_id=... -F source_content="红黑树是一种自平衡二叉搜索树"` returns valid JSON with non-empty `front` and `back`
- [ ] Empty `api_key` → 400 with "API Key is required."
- [ ] LLM failure (bad JSON, network error) → 502 with descriptive message

### Anti-pattern guards

- Do NOT stream this endpoint
- Do NOT auto-create a review item here — the endpoint only returns the draft; the create endpoint (Phase 5) is what persists
- Do NOT call the full chat-style RAG pipeline; this is a one-shot small completion

---

## Phase 5: Review CRUD + grade endpoints

**Goal:** Expose the full HTTP surface for review items and the daily queue. Wire `ReviewStore` and `ReviewEngine` into `AssistantInstance`.

### What to implement

1. **Update `backend/app.py:27-40`:** Add `REVIEWS_BASE_DIR = os.path.join(BASE_DIR, 'data', 'reviews')` and `os.makedirs(REVIEWS_BASE_DIR, exist_ok=True)`.

2. **Update `backend/app.py:108-138`:** In `AssistantInstance.__init__`, add:
```python
self.review_store = ReviewStore(REVIEWS_BASE_DIR, assistant_id)
self.review_engine = ReviewEngine(self.review_store, assistant_id)
```

3. **Update `delete_assistant` endpoint:** Add `shutil.rmtree(os.path.join(REVIEWS_BASE_DIR, assistant_id), ignore_errors=True)`.

4. **Add endpoints:**

| Method | Path | Form/Query | Purpose |
|---|---|---|---|
| GET | `/api/reviews/items` | `assistant_id` (Q), `include_archived` (Q, default false) | List items |
| POST | `/api/reviews/items` | `assistant_id`, `type`, `snapshot_json`, `source_json`, `initial_signal` (optional) | Create item |
| GET | `/api/reviews/items/{item_id}` | `assistant_id` (Q) | Get one |
| PUT | `/api/reviews/items/{item_id}` | `assistant_id`, `snapshot_json` (only allowed for `card` type) | Edit card snapshot |
| DELETE | `/api/reviews/items/{item_id}` | `assistant_id` (Q) | Delete |
| POST | `/api/reviews/items/{item_id}/archive` | `assistant_id` | Archive |
| POST | `/api/reviews/items/{item_id}/reactivate` | `assistant_id` | Reactivate |
| GET | `/api/reviews/today` | `assistant_id` (Q) | Get-or-create today's queue, returns queue + items |
| POST | `/api/reviews/grade` | `api_key`, `assistant_id`, `item_id`, `response_json` | Grade one item, update SRS + queue entry |
| POST | `/api/reviews/today/finish` | `assistant_id` | Force-close today's queue, returns summary |

5. **Auto-enroll hook:** In the existing `POST /api/quiz/grade` endpoint (`app.py:758-788`), after grading succeeds, iterate `results` and for each `score < 1.0`:
   - Find the matching question by id
   - Build a `snapshot` from the question (front=question, back=answer, options/answer_key/explanation if mcq)
   - Build a `source` of `{type: "quiz_wrong", ref: "<quiz_id or question_id>", label: f"测验「{quiz_title}」"}`
   - Determine `initial_signal` (0.0 or 0.5) based on score
   - Call `assistant.review_store.create_item(...)` with srs seeded by `assistant.review_engine.seed_srs(...)`

### Documentation references

- Mirror endpoint shape from `app.py:589-736` (mindmap CRUD)
- Mirror form/query convention strictly: GET/DELETE use `Query`, POST/PUT use `Form`
- Mirror error mapping: `KeyError → 404`, `json.JSONDecodeError → 400`, `ValueError → 400`
- API key check: copy `if not api_key: raise HTTPException(status_code=400, detail="API Key is required.")` from `app.py:740-741`

### Verification checklist

- [ ] Full curl round-trip: create → get → list → grade → archive → reactivate → delete
- [ ] After a quiz is graded with 2 wrong answers, `GET /api/reviews/items` lists 2 new items
- [ ] `GET /api/reviews/today` on first call generates a queue; second call returns the same queue
- [ ] `PUT /api/reviews/items/{mcq_id}` with `snapshot_json` returns 400 (mcq is immutable)
- [ ] `PUT /api/reviews/items/{card_id}` with `snapshot_json` succeeds
- [ ] `POST /api/reviews/grade` with `response_json={"answer":"B"}` for an mcq with answer_key "B" returns `score=1` and updates `next_review` to ~3 days out
- [ ] Deleting an assistant removes `data/reviews/{assistant_id}/`

### Anti-pattern guards

- Do NOT make all fields editable; only `card` snapshot is editable (PRD Q16)
- Do NOT delete archived items automatically; archive is reversible (PRD Q18)
- Do NOT regenerate the daily queue when a grade is submitted — only update the corresponding queue entry's `status` and `grade`
- Do NOT raise on missing API key in `/api/reviews/grade` — allow grade submission with `self_rating` in the `response_json`

---

## Phase 6: Frontend — review view skeleton + today's queue

**Goal:** Wire up `reviewView`, the "📝 复习" studio button, the today-queue flow, and the completion summary page.

### What to implement

1. **`frontend/index.html`:**

- In the studio panel `<div class="studio-tools">` (currently has `generateQuizBtn`, `openMindmapBtn`, `memoryBtn`), add:
```html
<button id="openReviewBtn" class="tool-btn">
    <span class="material-symbols-outlined">event_repeat</span>
    <span class="tool-btn__label">复习</span>
</button>
```

- In `<main class="content">`, add a new view after `mindmapView`:
```html
<div id="reviewView" class="view">
    <div class="review-toolbar">
        <div class="review-tabs">
            <button id="reviewTabToday" class="review-tab active">今日复习</button>
            <button id="reviewTabAll" class="review-tab">全部</button>
        </div>
    </div>
    <div id="reviewTodayPanel" class="review-panel"></div>
    <div id="reviewAllPanel" class="review-panel" hidden></div>
</div>
```

- Bump CSS/JS cache version. Add `<script src="js/review.js?v=1"></script>` before `app.js`.

2. **`frontend/js/api.js`** — add methods mirroring shape of `getMindmap` / `saveMindmap` / `streamGenerateNote`:

```javascript
async listReviewItems(assistantId, includeArchived = false)
async createReviewItem(assistantId, type, snapshot, source, initialSignal = null)
async getReviewItem(assistantId, itemId)
async updateReviewItem(assistantId, itemId, snapshot)  // card only
async deleteReviewItem(assistantId, itemId)
async archiveReviewItem(assistantId, itemId)
async reactivateReviewItem(assistantId, itemId)
async getTodayReview(assistantId)
async gradeReviewItem(apiKey, assistantId, itemId, response)
async finishTodayReview(assistantId)
async draftReviewCard(apiKey, assistantId, sourceContent, sourceContext = "")
```

3. **`frontend/js/review.js`** — new file, exports `window.reviewManager` singleton mirroring `mindmapManager` structure (`mindmap.js:9-34`):

```javascript
class ReviewManager {
    constructor() {
        this._inited = false;
        this.currentTab = 'today';
        this.todayQueue = null;        // {date, entries, items: {id: full item}}
        this.currentIndex = 0;          // index into todayQueue.entries pointing to next pending
        this.allItems = [];
        this.showArchived = false;
    }

    init() { /* bind listeners, similar to mindmap.js:64-93 */ }
    async show() { /* view switch, similar to mindmap.js:97-115 */ }
    onAssistantChanged() { /* reset state, similar to mindmap.js:122-133 */ }

    // Today panel
    async loadToday() { /* fetch today queue + items, render current pending */ }
    renderCurrentItem() { /* show one item with type-specific UI */ }
    async submitCurrentItem(response) { /* POST grade, advance index, show feedback briefly */ }
    showCompletionSummary() { /* end-of-day summary per PRD Q21 */ }

    // All panel
    async loadAll() { /* list items, render table */ }

    // Manual add (called from chat.js and mindmap.js)
    async openDraftCardModal(sourceType, sourceRef, sourceContent, sourceContext) { /* AI draft → preview → save */ }
}

const reviewManager = window.reviewManager = new ReviewManager();
```

4. **`frontend/js/app.js:19-31`** — add `reviewManager.init()` to the init sequence.

5. **`frontend/js/app.js:88-109`** — extend `setBodyMode`:
- Add `'review'` mode; add class `'is-review'` to body
- Show `reviewListContainer` (a new sidebar list, optional in v1 — can be omitted; the today queue is the primary surface)

6. **One-item-at-a-time rendering** (PRD Q8):

- `mcq`: render question + 4 radio options, "提交" button → calls `gradeReviewItem` with `{answer: letter}`
- `qa`: render question + textarea + "提交" button (LLM path) AND "我不会答 / 模糊 / 会" three-button row (self-rating path, always available as fallback per PRD Q20)
- `card`: render `front`, "查看答案" button reveals `back`, then "不会 / 模糊 / 会" row

After submit:
- Show inline feedback (the response's `feedback` + `reference_answer`)
- Show "下一题" button → advance `currentIndex`, re-render
- If all entries done → `showCompletionSummary()`

7. **Completion summary** (PRD Q21):
```
今天完成 N 条 · 答对 X · 模糊 Y · 答错 Z

[需要重点回看]
- front 1
  back 1
  下次 K 天后再来
- front 2
  ...

[回到助手主页]
```

### Documentation references

- Singleton skeleton: `frontend/js/mindmap.js:9-34`
- View switching: `frontend/js/mindmap.js:97-115` (deactivate all `.view`, activate target)
- Modal patterns: `frontend/js/mindmap.js:248-280`
- Single-question rendering: `frontend/js/quiz.js:127-179` (note: do NOT copy the `correct_answer`/`user_answer` field name mistake from `quiz:247-253`)
- Init order: `frontend/js/app.js:19-31`
- Body mode switch: `frontend/js/app.js:88-109`

### Verification checklist

- [ ] Clicking "复习" in the studio panel switches to `reviewView`
- [ ] First visit with no items shows an empty state with explanation
- [ ] After running a quiz with wrong answers, the today queue shows them
- [ ] Submitting an mcq with correct answer shows green feedback, advances to next item
- [ ] Submitting a wrong answer shows red feedback, advances to next item
- [ ] qa item: typing an answer + submit calls LLM grading and shows score 0/0.5/1
- [ ] qa item: clicking self-rate buttons (without typing) also works (fallback path)
- [ ] card item: "查看答案" reveals back; clicking "会" advances and posts `{self_rating: 1.0}`
- [ ] Refreshing mid-session reloads at the next pending item
- [ ] After all items done, completion summary shows correct counts and the wrong/uncertain items list
- [ ] Switching assistants while in review view resets state and loads the new assistant's queue

### Anti-pattern guards

- Do NOT use `EventSource` for the AI draft endpoint; it's a one-shot JSON POST, not SSE
- Do NOT show all items at once; PRD Q8 requires one-at-a-time
- Do NOT block on LLM failure for qa items; always offer self-rating as a fallback (PRD Q20)
- Do NOT use `result.correct_answer` field name — backend returns `reference_answer`

---

## Phase 7: Frontend — manual entry from chat + mind-map

**Goal:** Add "加入复习" entry points in chat messages and mind-map nodes, wired through the AI card drafting flow.

### What to implement

1. **Chat integration (`frontend/js/chat.js`):**

In `renderMessage` (around `chat.js:205-245`), for `role === 'assistant'` messages, add another action button next to the existing delete/regen buttons:

```javascript
const reviewBtn = document.createElement('button');
reviewBtn.className = 'msg-action-btn';
reviewBtn.title = '加入复习';
reviewBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size:16px;">event_repeat</span>';
reviewBtn.addEventListener('click', () => this.addToReview(index));
actions.appendChild(reviewBtn);
```

Add method:
```javascript
async addToReview(messageIndex) {
    const msg = this.messages[messageIndex];
    if (!msg || msg.role !== 'assistant') return;
    const sessionTitle = document.getElementById('currentSessionTitle')?.textContent || '对话';
    await reviewManager.openDraftCardModal(
        'chat_message',
        `${this.currentSessionId}:${messageIndex}`,
        msg.content,
        `来自对话「${sessionTitle}」`
    );
}
```

2. **Mind-map integration (`frontend/js/mindmap.js`):**

Find the context-menu handler around `mindmap.js:_onCanvasContextMenu` (where rename/delete/expand options are listed). Add a new menu item "加入复习" that:

```javascript
async addNodeToReview(nodeId) {
    const node = this.jm.get_node(nodeId);
    if (!node) return;
    const path = this._getPathToRoot(nodeId).map(n => n.topic).join(' → ');
    const note = (node.data && node.data.note) || '';
    const content = note || node.topic;
    const context = `来自思维导图节点：${path}`;
    await reviewManager.openDraftCardModal('mindmap_node', `${this.currentMap.id}:${nodeId}`, content, context);
}
```

3. **Draft card modal (`frontend/js/review.js`):**

```javascript
async openDraftCardModal(sourceType, sourceRef, sourceContent, sourceContext) {
    const apiKey = localStorage.getItem('deepseek_api_key');
    if (!apiKey) {
        showToast('请先在设置中保存 API 密钥', 'error');
        return;
    }
    const assistantId = app.currentAssistant?.id;
    if (!assistantId) return;

    // Show modal in loading state
    this._showModal('reviewDraftCardModal');
    document.getElementById('reviewDraftCardStatus').textContent = 'AI 正在起草...';
    document.getElementById('reviewDraftCardFront').value = '';
    document.getElementById('reviewDraftCardBack').value = '';

    try {
        const draft = await api.draftReviewCard(apiKey, assistantId, sourceContent, sourceContext);
        document.getElementById('reviewDraftCardFront').value = draft.front || '';
        document.getElementById('reviewDraftCardBack').value = draft.back || '';
        document.getElementById('reviewDraftCardStatus').textContent = '请检查并编辑后保存';
        // store source meta on the modal for the save handler
        this._pendingDraft = { sourceType, sourceRef, sourceContext };
    } catch (e) {
        showToast('生成卡片失败，可手动填写', 'warning');
        document.getElementById('reviewDraftCardStatus').textContent = '生成失败，请手动填写';
        this._pendingDraft = { sourceType, sourceRef, sourceContext };
    }
}

async confirmDraftCard() {
    const front = document.getElementById('reviewDraftCardFront').value.trim();
    const back = document.getElementById('reviewDraftCardBack').value.trim();
    if (!front || !back) { showToast('front 和 back 都不能为空', 'error'); return; }
    const { sourceType, sourceRef, sourceContext } = this._pendingDraft;
    await api.createReviewItem(
        app.currentAssistant.id,
        'card',
        { front, back },
        { type: sourceType, ref: sourceRef, label: sourceContext }
    );
    this._hideModal('reviewDraftCardModal');
    showToast('已加入复习', 'success');
}
```

Add the modal HTML to `index.html` (mirroring `mindmapNewBlankModal` style — see `index.html:308-320`).

### Documentation references

- Chat action button pattern: `chat.js:218-238`
- Mind-map context menu: search `mindmap.js` for `_onCanvasContextMenu` and surrounding handlers
- Modal HTML pattern: `index.html:308-320` (`mindmapNewBlankModal`)
- Modal show/hide and focus: `mindmap.js:248-255`

### Verification checklist

- [ ] In an active chat, every assistant message shows the "加入复习" button
- [ ] Clicking it opens the draft modal in loading state, then populates `front`/`back`
- [ ] User can edit `front`/`back` and save
- [ ] After saving, the new card appears in the "全部" tab and in tomorrow's queue
- [ ] In mind-map view, right-clicking a node shows "加入复习" in the context menu
- [ ] Selecting it for a node with a note uses the note as source; node without a note uses the topic
- [ ] LLM failure on draft endpoint still allows manual fill + save
- [ ] No API key → toast, modal does not open

### Anti-pattern guards

- Do NOT auto-save the card without user confirmation (PRD Q15: user must preview/edit)
- Do NOT add a "加入复习" button to user messages — only assistant messages have value as review material
- Do NOT capture the long-term memory note as a card source (PRD Out of Scope)

---

## Phase 8: Final verification

**Goal:** End-to-end verification of the full closed loop, plus regression checks on existing features.

### Verification checklist

**End-to-end review loop:**
- [ ] Generate a quiz → answer wrong → submit → quiz grade page shows; review items auto-enrolled
- [ ] Switch to review view → today's queue shows the wrong items
- [ ] Complete all items → completion summary correct
- [ ] Wait one day (or manipulate `next_review` via direct file edit) → fresh queue generates the next day
- [ ] Mark an item as "已掌握" → it disappears from today; reappear toggle in "全部" tab → "重新加入复习" resets it

**Manual entry:**
- [ ] Add a card from a chat message → appears in tomorrow's queue
- [ ] Add a card from a mind-map node → appears in tomorrow's queue
- [ ] Edit a card from "全部" tab → snapshot updates

**Fallback paths:**
- [ ] Clear API key in settings → review still works for mcq (local grade) and via self-rating for qa/card
- [ ] Re-add API key → qa items grade via LLM again

**Regression checks (existing features must still work):**
- [ ] Generate a regular quiz (no review) — same behavior as before (run through `frontend/js/quiz.js` flow)
- [ ] Send a chat message — streaming works
- [ ] Create / edit a mind map — AI ops still work
- [ ] Long-term memory note still saved and used in chat prompt

**Anti-pattern grep checks:**
- [ ] `grep -n "correct_answer" frontend/js/review.js` returns no matches (must use `reference_answer`)
- [ ] `grep -n "_grade_subjective" backend/quiz_engine.py` returns no matches (extracted in Phase 3)
- [ ] `grep -n "EventSource" frontend/js/review.js` returns no matches (no SSE for draft endpoint)
- [ ] `grep -rn "data/reviews" backend/` only appears in `app.py` and `review_store.py`

**Storage integrity:**
- [ ] After running the full loop, `data/reviews/{assistant_id}/` contains expected files: `items/`, `_index.json`, `daily_queue_{today}.json`
- [ ] Deleting an assistant cleans up all of `data/reviews/{assistant_id}/`

### Anti-pattern guards

- Do NOT skip the regression checks — past phases have already touched `quiz_engine.py` and `app.py`
- Do NOT mark this phase done while the completion summary is broken or the auto-enroll hook is silently failing

---

## Commit Granularity (recommended)

One commit per phase. Phase 0 has no code, so commits start at Phase 1.

1. Phase 1: `feat(review): add ReviewStore with file-per-item persistence`
2. Phase 2: `feat(review): add ReviewEngine SRS scheduling`
3. Phase 3: `refactor(quiz): extract subjective grading into shared module`
4. Phase 4: `feat(review): add AI card drafting endpoint`
5. Phase 5: `feat(review): add CRUD/grade endpoints + quiz auto-enroll`
6. Phase 6: `feat(review): add review view with today queue and completion summary`
7. Phase 7: `feat(review): add manual entry from chat and mind-map`
8. Phase 8: verification only — no commit

---

## Cross-Phase Notes

- **API key handling:** consistent with current code — read from `localStorage` on the frontend, passed as `Form` field to backend, no server-side storage.
- **Date format:** always `YYYY-MM-DD` strings for SRS dates; always `datetime.now(timezone.utc).isoformat(timespec="seconds")` for timestamps. Do not mix formats.
- **Item IDs:** `rv_<8 hex>`, mirroring `mm_<8 hex>` and quiz id conventions.
- **Soft cap behavior:** when more than 20 items are due, the excess remain due (their `next_review` is in the past) and will be picked up on subsequent days. The cap only limits today's selection, never deletes or defers explicitly.
- **Self-rating mapping:** `again=0.0`, `hard=0.5`, `good=1.0`. This drives the same `apply_grade` flow as LLM scoring.
- **Out-of-scope reminders** (do not implement, even if tempting):
  - Cross-assistant aggregated queue
  - Search / filter / batch ops in "全部" tab
  - Learning curve charts / streaks / badges
  - AI auto-extraction without explicit user action
  - Editable wrong-answer snapshots
  - Markdown import/export of review libraries

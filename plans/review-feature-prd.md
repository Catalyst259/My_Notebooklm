## Problem Statement

当前的学习助手已经具备三个明显的工作室能力：生成测验、思维导图、长期备忘。它们分别覆盖了检测理解、整理知识结构、保存长期偏好，但仍然缺少一个真正的复习闭环。

从学生视角看，现状的问题不是"缺少更多内容生成工具"，而是"学过之后系统不会持续推动我复习"。做完测验后，错题只停留在结果页；在聊天中遇到一个自己没掌握的知识点，或者在思维导图里整理出一个关键概念，也没有一个低摩擦的方法把它沉淀成后续复习任务。结果是：

- 测验帮助学生发现不会的内容，但不会自动转成之后的学习动作。
- 思维导图帮助学生整理结构，但不会进入后续记忆强化流程。
- 长期备忘是给助手看的长期偏好，不是给学生自己的学习材料池。
- 学生没有"今天该复习什么"这个明确入口，产品更像一组离散工具，而不是一套持续推进学习的系统。

用户需要的不是另一个并列的内容生产器，而是一个把"错题、知识点、主动标记"变成"今日待复习队列"的复习系统，让产品从一次性使用工具演进为每日可打开的学习工作台。

## Solution

新增一个独立的"复习"能力，形成按助手隔离的每日待复习闭环。

从用户视角看，这个功能应当这样工作：

- 做完测验后，所有未满分题目会自动进入该助手的复习池。
- 在聊天中遇到重要知识点，或在思维导图中整理出关键节点时，用户可以一键加入复习。
- 系统会基于简化 SRS（间隔重复）算法，为每个助手每天生成一个最多 20 条的"今日待复习"队列。
- 用户进入复习页后，一条一条完成复习：单选题即时机判，问答类即时批改，手动卡片支持翻面后自评。
- 每完成一条，系统立即更新这条复习项的下次到期时间，并持久化今天的进度；中途退出后回来可以继续。
- 当日完成后，用户能看到本次完成情况和需要重点回看的内容。

这个方案不会替代现有测验和思维导图，而是把它们连成闭环：

- 测验负责发现不会。
- 聊天与思维导图负责暴露和整理知识点。
- 复习系统负责把这些材料调度成持续记忆强化动作。

## User Stories

1. As a student, I want wrong quiz answers to automatically enter a review pool, so that I do not need to manually recreate the questions I got wrong.
2. As a student, I want partially correct quiz answers to also enter review, so that I can reinforce concepts I only half understood.
3. As a student, I want the system to separate review pools by assistant, so that each subject keeps a clear learning context.
4. As a student, I want a clear "today's review" entry point, so that I know exactly what to study next.
5. As a student, I want today's review queue to be finite, so that the workload feels manageable.
6. As a student, I want overdue items to be prioritized, so that I catch up on neglected material first.
7. As a student, I want fully wrong quiz items to be prioritized over partially correct ones, so that the weakest areas come back sooner.
8. As a student, I want manually added cards to join the same review pool as wrong answers, so that all reviewable knowledge lives in one place.
9. As a student, I want to add a chat answer to review with one action, so that I can capture concepts when I notice confusion.
10. As a student, I want to add a mind-map node to review, so that structured knowledge can become memory practice.
11. As a student, I want the system to draft review cards with AI, so that creating cards from chat and mind maps is low friction.
12. As a student, I want to preview and edit an AI-drafted card before saving it, so that I can correct awkward or inaccurate phrasing.
13. As a student, I want the review system to support different item types, so that multiple-choice, subjective answers, and cards each keep their natural format.
14. As a student, I want multiple-choice review items to be graded instantly without an LLM call, so that review is fast and reliable.
15. As a student, I want short-answer and proof-style review items to be graded using the same teaching quality as quizzes, so that feedback stays consistent.
16. As a student, I want card-style review items to support self-evaluation, so that I can still review even when no objective answer check exists.
17. As a student, I want to review one item at a time, so that the flow feels lightweight instead of like a full exam.
18. As a student, I want immediate feedback after each reviewed item, so that I can correct mistakes while the attempt is fresh.
19. As a student, I want the next review date to update immediately after each item, so that progress is never lost.
20. As a student, I want to stop in the middle of a review session and continue later, so that accidental refreshes or interruptions do not waste effort.
21. As a student, I want today's queue and progress to persist per day, so that I do not see already-completed items again on the same day.
22. As a student, I want a new day to generate a fresh queue automatically, so that review continues naturally without manual resets.
23. As a student, I want new review items from fully wrong quiz answers to come back sooner than partially correct ones, so that the spacing reflects my mastery.
24. As a student, I want manually added cards to start with a short interval, so that newly captured knowledge is reinforced quickly.
25. As a student, I want review items to store a stable content snapshot, so that they still work even if the original chat, quiz result, or mind map changes later.
26. As a student, I want each review item to remember where it came from, so that I can understand the source context and trust the material.
27. As a student, I want to see whether a review item came from a quiz, a chat answer, or a mind-map node, so that I know why it is in my queue.
28. As a student, I want a separate review view in the studio, so that review feels like a first-class workflow rather than an afterthought inside quizzes.
29. As a student, I want the review view to default to today's queue, so that the most actionable task is front and center.
30. As a student, I want a simple "all review items" tab, so that I can inspect what has accumulated over time.
31. As a student, I want to delete obsolete review items, so that the pool stays relevant.
32. As a student, I want to mark a review item as mastered, so that I can intentionally retire it from future review.
33. As a student, I want mastered items to be reversible instead of deleted, so that I can reactivate them later if needed.
34. As a student, I want archived items hidden from my daily queue, so that my active review workload stays focused.
35. As a student, I want to reactivate an archived item, so that previously mastered material can re-enter review when needed.
36. As a student, I want card items to remain editable after creation, so that I can improve wording or tighten the prompt-answer pair.
37. As a student, I want wrong-answer snapshots to stay immutable, so that they remain faithful records of what I originally got wrong.
38. As a student, I want review to continue even if my API key is missing, so that the system never blocks a review habit.
39. As a student, I want subjective review items to fall back to self-rating when LLM grading is unavailable, so that I can still finish today's queue.
40. As a student, I want to see the reference answer when self-rating a subjective item, so that I have enough information to judge my own response.
41. As a student, I want a brief completion summary at the end of today's review, so that I get a sense of closure and performance.
42. As a student, I want to immediately revisit the items I missed or found difficult today, so that I can reflect while memory is still warm.
43. As a student, I want review to feel connected to the rest of the learning assistant, so that the product behaves like one integrated study system.
44. As a student, I want the review system to reuse existing assistant context and grading behavior, so that different subjects retain their specific teaching style.
45. As a student, I want the review workflow to avoid unnecessary configuration, so that I can start using it without learning a separate tool.
46. As a student, I want queue generation to respect a simple spacing model, so that mastered items fade out and weak items return quickly.
47. As a student, I want review items to survive browser refreshes and app restarts, so that study progress is durable.
48. As a student, I want the review pool to stay aligned with my actual mistakes and deliberate knowledge capture, so that it reflects what I truly need to remember.
49. As a student, I want to build a repeatable daily study habit around the assistant, so that the product helps me over time, not just in one session.
50. As a student, I want the assistant to become a daily study workspace, so that learning, organizing, testing, and reviewing all happen in one place.

## Implementation Decisions

- Add a dedicated review capability as a new top-level studio workflow rather than embedding review inside the quiz workflow. The review experience is conceptually about maintaining and consuming a persistent review pool, not generating and completing a one-off assessment.
- Keep review data isolated per assistant. This matches the existing architecture where knowledge base, sessions, mind maps, and memory are already partitioned by assistant, and it preserves subject-specific teaching context.
- Introduce a deep `review_store` module responsible for review-item persistence and daily queue persistence. It should hide file layout details behind a simple CRUD-and-query interface so the rest of the app works in terms of items, queues, and status changes rather than raw files.
- Use file-backed JSON storage in the same style as existing session and mind-map persistence. Each review item lives in its own JSON file, and each day has its own persisted queue/progress file. This keeps writes small, reduces blast radius on corruption, and aligns with the current codebase's persistence model.
- Model review material as multiple item types under one review system: `mcq`, `qa`, and `card`. All item types must expose a unified grading outcome in the form of mastery signals that drive the same SRS update path.
- Create a `review_engine` deep module that owns queue generation, SRS scheduling, type dispatch for grading, self-rating fallback, and end-of-review aggregation. This engine should present a small stable interface to the API layer even though it encapsulates multiple internal behaviors.
- Keep quiz generation and review management as separate concerns. Review should reuse quiz grading capabilities where helpful, but it should not be bolted into quiz generation flows or force the quiz engine to own review state.
- Extract subjective grading into a shared capability so both quiz grading and review grading can use the same prompt and scoring behavior for non-multiple-choice items.
- Continue using local grading for multiple-choice review items. This preserves fast, deterministic behavior and avoids unnecessary LLM calls for the most objective item type.
- Use AI-assisted draft generation for manually added cards. When the user marks content from chat or a mind-map node, the system should propose a `front/back` card that the user can review and edit before saving.
- Use content snapshot plus source metadata for every review item. The snapshot guarantees the item remains usable even if the original chat, quiz output, or mind map changes, while source metadata preserves traceability and user trust.
- Auto-enroll every quiz item with `score < 1` into the review pool. This includes both fully wrong and partially correct answers so the system captures both obvious gaps and shaky understanding.
- Seed newly added review items with simple initial SRS values based on origin and mastery signal. Fully wrong quiz items should return sooner than partially correct ones; manually added cards should start on a short interval.
- Use a simplified SRS rule rather than a full Anki-style parameter space. A correct result expands the interval multiplicatively; an incorrect result resets the interval to a short revisit. The design prioritizes predictability and ease of explanation over algorithmic sophistication.
- Cap daily queue size with a soft upper bound and deterministic prioritization. Prioritize overdue items first, then the weakest quiz-derived items, then lower-priority items. Excess due items should remain due and roll into later days, not be discarded.
- Persist daily queue membership and per-item progress for the current date. Re-entering review on the same day must continue from the next pending item instead of recomputing a fresh list each time.
- Regenerate the daily queue only when the calendar day changes for that assistant. This prevents order instability and duplicate exposure during the same day.
- Support a dedicated review view with two lightweight tabs: today's review and all review items. The all-items tab is intentionally simple in v1 and exists to provide inspection, deletion, and archive/reactivation controls rather than full library management.
- Allow editing only for user-authored or AI-drafted `card` items. Quiz-derived `mcq` and `qa` snapshots should remain effectively immutable so they preserve the factual record of what the student previously missed.
- Use an `archived` state rather than hard deletion for "已掌握". Archived items should disappear from active scheduling but remain restorable, allowing the student to reintroduce material without losing history.
- Add three entry paths into review: automatic quiz enrollment, chat-based manual marking, and mind-map-based manual marking. These are the three highest-value integration points with the existing product surface.
- Treat long-term memory as out of scope for review-item sourcing. Long-term memory is a prompt-conditioning preference store for the assistant, not a student-facing knowledge capture system.
- Design the review interaction as one item at a time with immediate feedback and immediate state persistence. This makes interruptions cheap, aligns with SRS usage patterns, and avoids forcing card-like review into a full-quiz submission flow.
- For subjective items, allow fallback from LLM grading to self-rating when API credentials are missing or the request fails. The fallback should still show the reference answer and drive the same SRS update path.
- End each daily session with a concise completion summary plus a short review of missed or uncertain items. This provides closure and reinforces weak spots while memory is still active.
- Keep v1 intentionally light on management features. No search, advanced filters, batch actions, cross-assistant aggregation, analytics dashboards, or gamification should be introduced in the first version.

## Testing Decisions

- Good tests should validate externally visible behavior rather than implementation details. For review, that means asserting persisted review-item states, queue composition, grading outcomes, archive/reactivation effects, and fallback behavior instead of asserting internal helper usage or specific prompt strings.
- The highest-value tests are on deep modules with stable interfaces: the review store and the review engine. These modules encapsulate most of the feature complexity and can be tested in isolation from the UI.
- Review-store tests should cover item creation, snapshot persistence, archive/reactivation transitions, daily queue persistence, and safe single-item updates.
- Review-engine tests should cover queue selection, prioritization, initial SRS seeding, interval updates after grading, subjective fallback to self-rating, and end-of-session summary generation.
- Shared subjective-grading extraction should be tested at the boundary that matters to callers: given a normalized subjective item input, it returns normalized scoring output or activates the expected fallback path.
- API-level tests, if added later, should focus on endpoint contracts and cross-module orchestration: auto-enrolling wrong quiz items, creating cards from chat/mind-map sources, loading today's queue, submitting review outcomes, and moving items into or out of archive.
- Frontend behavior should be verified manually because the repository currently has no established frontend test framework. Manual verification should cover the golden path and interruption paths: start review, refresh mid-session, continue, complete, archive, reactivate, and manually add from both chat and mind maps.
- Prior art for testing style in this codebase is limited because the repository currently has no formal automated test suite. The design should therefore favor modules whose public interfaces are straightforward to test with small JSON fixtures and without spinning up the full app.
- Because file-backed persistence is already an established pattern in the project, tests should use temporary directories and assert on resulting JSON state rather than mocking persistence internals.

## Out of Scope

- Cross-assistant unified review queues
- Advanced search, filtering, and batch operations for the review library
- Analytics dashboards, streaks, badges, or other gamification systems
- AI auto-extraction of review items from uploads or full conversations without explicit user action
- Editing quiz-derived wrong-answer snapshots
- Rich visualizations such as learning curves or charts
- Import/export of review libraries
- Mobile-specific review UX beyond what naturally works in the existing layout
- Complex SRS tuning interfaces or user-configurable algorithm parameters
- Replacing quizzes with review or merging quiz and review into a single workflow

## Further Notes

- This feature should be described to users as the missing fourth leg of the study workflow: chat to learn, mind maps to organize, quizzes to detect gaps, review to retain.
- The architecture should continue the project's preference for simple, explicit modules over introducing a database or heavy framework abstraction.
- The review feature becomes significantly more valuable because mind maps already exist. A node-level "加入复习" action turns a static structure into a live memorization queue.
- The distinction between long-term memory and review should remain crisp in product language. Long-term memory teaches the assistant how to help the student; review items teach the student what to remember.
- Because the repository does not appear to have an external issue tracker configuration available in the current context, this PRD is being captured as an in-repo planning artifact rather than being published to a tracker with a triage label.

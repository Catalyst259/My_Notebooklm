# 思维导图功能实现计划 (Mind-Map Feature)

## Context

为多学科学习助手新增第四个核心功能：**思维导图 (Mind-Map)**，与 `chat` / `quiz` 并列。学生可在每个助手下创建多个思维导图，AI 利用该助手的 RAG 知识库帮助生成树结构、扩展节点子项、补全节点笔记。

目标用户场景：学生正在学习某个主题（如"红黑树"），想以可视化方式整理概念结构，并随时让 AI 基于上传的教材/笔记补充内容。

## Design Decisions (Locked)

下表汇总了 21 轮设计讨论的结论。实现时必须遵循这些决定；如发现某条决定在落地中确实不合理，**先与用户确认再改**。

| 维度 | 决定 |
|---|---|
| 形态 | 学习/复习工具（学生主导，AI 协助），非只读概览、非测验 |
| 结构 | 严格树（一根多叉、每节点单父），不做图/概念图，不做跨支引用 |
| 归属 | 每个助手下的独立集合，与 `sessions` 平级 |
| 节点 schema | `{id, text, note?, children}`，`note` 为 Markdown |
| AI 操作 | 仅三个：**生成整树** / **扩展节点（加子节点）** / **生成笔记** |
| AI 输出格式 | 树类操作输出 Markdown 项目符号；笔记操作输出 Markdown 文本 |
| RAG 查询 | 自然语言拼接的"根→节点"路径；扩展节点时把已有兄弟拼入 prompt 抑制重复 |
| LLM 流式 | 三个操作全部 SSE 流式；前端边接收边解析项目符号增量加节点 |
| 取消行为 | 取消保留已生成内容（与 chat 一致） |
| 编辑能力 | 重命名 / 删除子树 / 添加空子节点 / 节点级 AI 操作；**不做**拖拽改父、撤销 |
| 渲染库 | `jsmind`（vendor 到 `frontend/js/vendor/`） |
| 存储格式 | jsmind 原生 JSON，外面包一层 session 风格的 envelope |
| 存储路径 | `data/mindmaps/{assistant_id}/{map_id}.json` |
| 视图位置 | 新顶层视图 `mindmapView`，从侧栏"⚙️ 操作"里的 `🧠 思维导图` 按钮进入 |
| 创建入口 | 两个按钮：`+ 空白思维导图` / `+ AI 生成思维导图`（后者打开主题/深度/宽度/标题 modal） |
| API 形态 | 客户端权威（client-authoritative）；3 个 AI 端点彼此独立 |
| 持久化策略 | 防抖自动保存 2s + 视图切换/卸载/AI 操作完成时强制刷新；失败保留脏状态重试 |
| Prompt 分层 | 两层：复用学科 system prompt + 新增 `MINDMAP_OP_PROMPTS` 操作指令 |
| 上限 | 单图软上限 500 节点（超限阻止 AI 操作并 toast 提示） |
| 导出 | 仅 Markdown：文件下载 + 复制到剪贴板；**v1 不做导入** |

## 不做范围（v1 OUT）

明确不在本次实现内的项目（任何"顺手做了"都属于范围蔓延，请勿）：

- 概念图 / 任意图结构、跨支引用
- 节点级 KB 引用 (citations) 与标签 (tags)
- "整理树 / 找缺失 / 合并重复"等 AI 操作
- 拖拽改父、撤销/重做
- PNG/SVG 导出、JSON 导出、Markdown 导入
- 多 tab 冲突处理（超过 LWW）
- LLM-rewrite-then-retrieve 的查询改写
- 思维导图与 session 的双向绑定 / "session → 思维导图"
- 多根、协作/共享、移动端布局

## 架构总览

### 后端新增/修改

```
backend/
  app.py                ← 新增 8 个端点 + AssistantInstance 注入 + delete 清理
  mindmap_store.py      ← 新文件，仿 session_store.py
  mindmap_engine.py     ← 新文件，仿 quiz_engine.py
  rag_engine.py         ← 新增 MINDMAP_OP_PROMPTS / build_mindmap_messages
```

依赖方向：`MindMapEngine → RAGEngine → KnowledgeBase`；`app.py` 只做 HTTP 编排，不写 AI 逻辑。

### 前端新增/修改

```
frontend/
  index.html            ← 新视图节点 + 模态框 + 4 处新 <script> / <link>
  css/styles.css        ← 在末尾新增 /* === Mind Map === */ 区块
  js/
    api.js              ← 新增 8 个方法（5 CRUD + 3 stream）
    app.js              ← 注册 mindmapView 切换逻辑、按钮回调
    mindmap.js          ← 新文件，导出 mindmapManager 单例
    vendor/
      jsmind.js         ← vendor 文件
      jsmind.css        ← vendor 文件
```

`index.html` 脚本加载顺序（缓存参数同步 bump）：

```html
<link rel="stylesheet" href="css/styles.css?v=5">
<link rel="stylesheet" href="js/vendor/jsmind.css">
...
<script src="js/vendor/jsmind.js"></script>
<script src="js/api.js?v=5"></script>
<script src="js/chat.js?v=5"></script>
<script src="js/quiz.js?v=5"></script>
<script src="js/upload.js?v=5"></script>
<script src="js/mindmap.js?v=1"></script>
<script src="js/app.js?v=5"></script>
```

## 数据契约

### 单个 mind-map JSON

```json
{
  "id": "mm_a1b2c3d4",
  "assistant_id": "data_structures",
  "title": "红黑树",
  "created_at": "2026-05-24T10:00:00Z",
  "updated_at": "2026-05-24T10:30:00Z",
  "jsmind": {
    "meta": { "name": "红黑树", "version": "1.0" },
    "format": "node_tree",
    "data": {
      "id": "root",
      "topic": "红黑树",
      "data": { "note": "..." },
      "children": [
        { "id": "n1", "topic": "性质", "data": { "note": "..." }, "children": [] }
      ]
    }
  }
}
```

- 节点的 `note` 存放在 jsmind 的 `data.note`（jsmind 支持任意自定义 data）。
- `id` 形如 `mm_<8 位 hex>`，文件名与 envelope 中 `id` 一致：`{map_id}.json`。

## API 设计

### CRUD（5 个）

| Method | Path | Inputs | Output |
|---|---|---|---|
| GET | `/api/mindmaps` | `assistant_id` (query) | `{ "mindmaps": [{id, title, updated_at, node_count}] }` |
| POST | `/api/mindmaps` | `assistant_id` (form), `title` (form) | `{ "mindmap": <full> }`，初始化为含单一根节点 `title` |
| GET | `/api/mindmaps/{map_id}` | `assistant_id` (query) | `{ "mindmap": <full> }` |
| PUT | `/api/mindmaps/{map_id}` | `assistant_id` (form), `title` (form), `jsmind_json` (form) | `{ "mindmap": <full> }`，全量覆盖 |
| DELETE | `/api/mindmaps/{map_id}` | `assistant_id` (query) | `{ "message": "已删除" }` |

- 404 处理：未知 `assistant_id` / `map_id` 一律 404。
- `node_count` 在列表中由后端计算（遍历 jsmind 树）以便前端展示和 500 上限校验。

### AI 流式（3 个，全部 SSE）

| Method | Path | Inputs |
|---|---|---|
| POST | `/api/mindmaps/ai/generate-tree` | `api_key`, `assistant_id`, `topic`, `depth` (1-3, 默认 2), `width` (默认 4) |
| POST | `/api/mindmaps/ai/expand-node` | `api_key`, `assistant_id`, `path_json` (从根到目标节点的 text 数组), `siblings_json` (兄弟 text 数组), `count` (默认 4) |
| POST | `/api/mindmaps/ai/generate-note` | `api_key`, `assistant_id`, `path_json` |

SSE 事件结构（与 `/api/chat` 一致）：

```
data: {"content": "- 红黑树\n", "done": false}
data: {"content": "  - 性质\n", "done": false}
...
data: {"content": "", "done": true}
data: {"error": "...", "done": true}     # 失败
```

- AI 端点与 `map_id` 解耦：不知道是哪张图，只生成内容；前端负责把内容应用到本地 jsmind 实例。
- 错误处理与 `/api/chat` 对齐（401/超时/上游异常都 yield `error` 事件）。

## 实现阶段

### Phase 1: 后端骨架（无 AI）

**目标**：可创建/列出/读取/保存/删除 mind-map（用占位数据）。

1. 在 `app.py` 顶部加 `MINDMAPS_BASE_DIR = os.path.join(BASE_DIR, 'data', 'mindmaps')`，`os.makedirs(..., exist_ok=True)`。

2. 新建 `backend/mindmap_store.py`：
   - 类签名严格参照 `session_store.py`。
   - `__init__(base_dir, assistant_id)`：`self.dir = base_dir/assistant_id`，确保存在。
   - 方法：`list()` / `create(title)` / `get(map_id)` / `save(map_id, title, jsmind_json)` / `delete(map_id)` / `exists(map_id)`。
   - `create` 生成 `mm_<8hex>` id，写入含 envelope + 仅一个根节点（topic = title）的 JSON。
   - `save` 全量覆盖；更新 `updated_at` 为 UTC ISO8601。
   - `list` 返回包含 `node_count`（递归计数 jsmind 树）。
3. 在 `app.py` 的 `AssistantInstance.__init__` 中新增：
   ```python
   self.mindmap_store = MindMapStore(MINDMAPS_BASE_DIR, assistant_id)
   ```
4. 添加 5 个 CRUD 端点（沿用 `/api/sessions*` 的写法，包括 form / query 参数风格、HTTPException 处理）。
5. 在 `delete_assistant` 中新增：
   ```python
   mm_dir = os.path.join(MINDMAPS_BASE_DIR, assistant_id)
   if os.path.exists(mm_dir):
       shutil.rmtree(mm_dir)
   ```

**完成判定**：用 `curl` 走完一个 mindmap 的 create → get → save → list → delete 循环。

### Phase 2: RAG 集成 & AI 引擎

1. 在 `rag_engine.py` 末尾加 `MINDMAP_OP_PROMPTS`（中文，参考下方"Prompt 模板"小节）。
2. 在 `RAGEngine` 中新增 `build_mindmap_messages(op, *, topic=None, path=None, siblings=None, depth=None, width=None, count=None)`：
   - 拼接：`subject_system + "\n\n" + MINDMAP_OP_PROMPTS[op].format(...)`
   - 根据 op 推导 FAISS 查询字符串（参考"RAG 查询规则"小节）。
   - 检索 top_k 个 chunks 拼入 user message。
   - 返回 `[{role: "system", ...}, {role: "user", ...}]`。
3. 新建 `backend/mindmap_engine.py`：
   - `MindMapEngine(knowledge_base, rag_engine, assistant_id, assistant_name)`
   - `async def stream_generate_tree(api_key, topic, depth, width)` → async generator yielding SSE 字符串
   - `async def stream_expand_node(api_key, path, siblings, count)` → 同上
   - `async def stream_generate_note(api_key, path)` → 同上
   - 内部用 `AsyncOpenAI(base_url="https://api.deepseek.com")`，温度 0.7，`max_tokens` 笔记类 512、树类 2048。
   - 任何异常 yield `{"error": str(e), "done": true}` 然后 return。
4. `AssistantInstance` 中：
   ```python
   self.mindmap_engine = MindMapEngine(
       knowledge_base=self.knowledge_base,
       rag_engine=self.rag_engine,
       assistant_id=assistant_id,
       assistant_name=config["name"],
   )
   ```
5. 添加 3 个 AI 端点（薄壳，直接 `StreamingResponse(engine.stream_*(...))`）。

**完成判定**：`curl -X POST ... /api/mindmaps/ai/generate-tree` 能看到流式输出符合 `- xxx\n  - yyy\n` 格式。

### Phase 3: 前端基础视图

1. `index.html`：
   - 在 `<main class="content">` 内新增 `<div id="mindmapView" class="view">`，结构类似 `chatView` 的左侧栏 + 主区。
   - 左侧栏：标题"思维导图" + 两个新建按钮 + 列表容器。
   - 主区：工具栏（标题、保存状态、`📝 复制` `⬇ 导出` `🛠 操作` 按钮）+ `jsmind` 挂载点 `<div id="mindmapCanvas">`。
   - 在 `actionsSection` 内 `generateQuizBtn` 旁加 `<button id="openMindmapBtn">🧠 思维导图</button>`。
   - 新增模态框 `mindmapNewBlankModal`（仅标题输入）、`mindmapNewAiModal`（标题/主题/深度/宽度）、`mindmapRenameModal`、`mindmapAiPanelModal`（节点 AI 操作的二级确认）。
   - 引入 vendor jsmind 的 `<link>` 和 `<script>`，并加入 `mindmap.js`。
2. `js/api.js`：扩展 `api` 单例：
   ```js
   listMindmaps(assistantId)
   createMindmap(assistantId, title)
   getMindmap(assistantId, mapId)
   saveMindmap(assistantId, mapId, title, jsmindJson)
   deleteMindmap(assistantId, mapId)
   streamGenerateTree(apiKey, assistantId, topic, depth, width, { onChunk, onDone, onError, signal })
   streamExpandNode(apiKey, assistantId, path, siblings, count, { onChunk, onDone, onError, signal })
   streamGenerateNote(apiKey, assistantId, path, { onChunk, onDone, onError, signal })
   ```
   - 流式方法仿照 chat.js 当前的手写 SSE 消费，但允许 `AbortController` 取消。
3. `js/mindmap.js`：导出 `window.mindmapManager`，至少包含：
   - `init()`：绑定按钮、初始化空 jsmind 实例。
   - `show(assistantId)`：切到该视图，加载 mindmap 列表，恢复上次打开的 map。
   - `openMap(mapId)`：从后端拉数据 → `jm.show(jsmindJson)`。
   - `createBlank()` / `createWithAi(opts)`：创建后立即打开。
   - 节点上下文菜单（右键或 hover icon）：重命名、删除、加子节点、AI 扩展、AI 生成笔记。
   - 流式接收时的 `BulletStreamParser`（见下方）。
   - 防抖自动保存 + 状态徽章。
   - `exportMarkdown()` / `copyMarkdown()`。
   - 500 节点上限检查。
4. `js/app.js`：注册 `openMindmapBtn` 点击切到 `mindmapView`，与现有 view 切换逻辑保持一致。

### Phase 4: 流式解析与节点拼接

实现 `BulletStreamParser`（在 `mindmap.js` 内部，不必外暴露）：

- 维护行缓冲 `buffer`（接收文本累加）。
- 每收到 chunk：将 `buffer + chunk` 按 `\n` 切，最后一段留回 buffer，其余每行尝试解析为 `/^(\s*)- (.+)$/`：
  - 缩进必须是 2 空格倍数，否则该行计入 `skippedLines`。
  - 计算 depth = 缩进 / 2。
  - 维护 `stack[depth] = nodeId`，新节点的父 = `stack[depth - 1]`（顶层节点父 = 操作锚点：树生成时是根，扩展节点时是被扩展的节点）。
  - 调 `jm.add_node(parentId, newId, topic)`，把新 id push 到 `stack[depth]`，截断 `stack[depth+1..]`。
  - 节点数若超 500：停止接收并 abort SSE，提示 toast。
- `onDone` 时：把 buffer 剩余尝试再解析一次；`skippedLines > 0` 时 toast `"AI 输出有 N 行无法解析，已忽略。"`；若总有效节点 = 0 toast `"AI 未生成内容，请重试"`。
- `onError` / `cancel`：保留已加入的节点；force-flush 保存。

### Phase 5: 自动保存

- 每次编辑（rename / add / delete / AI op 完成）将 `dirty = true` 并启动 2s 防抖。
- `setInterval` 不需要；用 `setTimeout` + 清理。
- 触发保存时：徽章 → `保存中…`；成功 → `已保存`；失败 → `保存失败（重试）`，2s 后下一次防抖自动重试。
- 强制刷新点（直接清防抖、立即 PUT）：
  - 视图切换（在 `app.js` 切走 mindmapView 前调 `mindmapManager.flushSave()`）。
  - `window.addEventListener('visibilitychange', ...)`。
  - 每个 AI 流式操作 `onDone` 之后。
  - AI 操作开始前（force-save 旧状态作为快照保险）。

### Phase 6: 导出与剪贴板

- `mindmapToMarkdown(jsmindData) -> string`：
  - 第一行 `# {title}\n\n`。
  - 递归遍历，深度 `d` 对应 `'  '.repeat(d) + '- ' + topic`。
  - 如有 `data.note`：紧接下一行用 `'  '.repeat(d+1) + '> ' + note`（多行 note 每行都加前缀和 `>`）。
- 导出：`Blob([md], { type: 'text/markdown' })` + `URL.createObjectURL` + `<a download="{safeTitle}.md">` 触发点击。
- 复制：`navigator.clipboard.writeText(md)`；失败回退 `document.execCommand('copy')`，toast 提示。

### Phase 7: 边界与错误

按 Q17 默认值实现：

- 空 KB：检索结果为 0 时不要 raise，只在 `prompt` 中省略 context 块；后端 SSE 在第一帧 yield 一条 `{"warning": "KB empty"}` 让前端 toast 一次"当前无 KB 命中，使用通用知识"。
- AI 流式失败：照 SSE error 帧处理，保留已生成节点。
- 0 有效节点：见 Phase 4 toast 规则。
- 500 节点上限：AI 操作开始前预判（当前 + 估算最大新增 > 500）则直接 toast 拒绝；流式过程中超限则中止并 toast。
- 助手删除：见 Phase 1 step 5。
- 多 tab：LWW，无额外代码。

## Prompt 模板（写入 `rag_engine.py` 的 `MINDMAP_OP_PROMPTS`）

```python
MINDMAP_OP_PROMPTS = {
    "generate_tree": (
        "你正在为学生生成一份学习思维导图。"
        "请仅输出严格的 Markdown 项目符号列表，使用 `-` 和两个空格缩进。"
        "深度不超过 {depth} 层，每个父节点不超过 {width} 个直接子节点。"
        "不要输出标题、序号、说明文字、代码块或多余空行。"
        "第一行必须是根主题（不缩进），随后为其子结构。"
        "主题：{topic}"
    ),
    "expand_node": (
        "你正在为已有的思维导图节点生成子节点。"
        "节点路径（从根到目标）：{path}\n"
        "目标节点已有的兄弟节点：{siblings}\n"
        "请仅输出 {count} 行 Markdown 项目符号，每行一个新的同级子节点（不嵌套，不缩进）。"
        "避免与已有兄弟重复；避免输出说明文字。"
    ),
    "generate_note": (
        "为思维导图节点撰写一段简洁的中文学习笔记，2–4 句话。"
        "必要时可包含 Markdown 代码块或数学公式。"
        "节点路径：{path}\n"
        "仅输出笔记正文，不要重复节点名，不要加 Markdown 标题。"
    ),
}
```

## RAG 查询规则

- `generate_tree`：query = `topic`。
- `expand_node`：query = `" - ".join(path)`（如 `"数据结构 - 哈希表 - 冲突处理"`）。
- `generate_note`：同 `expand_node`。

检索：`top_k = 5`，context 字符上限 4000（与 chat 一致；不照搬 quiz 的 8/5000，因为 mind-map 输出更短更聚焦）。

## 测试清单（人工，因仓库无自动测试框架）

后端：

- [ ] 5 个 CRUD 端点能正常工作（curl 各跑一遍）
- [ ] 3 个 AI 端点能返回符合预期格式的 SSE
- [ ] 删除助手时 `data/mindmaps/{aid}/` 被清空
- [ ] 空 KB 时 AI 操作不报错，正常出内容

前端：

- [ ] 进入 mindmapView，能看到列表（含空状态提示）
- [ ] 空白创建 → 出现单根节点画布；重命名/加子节点/删除子树都生效
- [ ] AI 生成思维导图 → 流式增长可见 → 完成后徽章变"已保存"
- [ ] 扩展节点 → 新增 N 个同级子节点；与已有兄弟不重复
- [ ] 生成笔记 → 节点点开侧栏（或 hover 浮窗）能看到 Markdown 渲染后的笔记
- [ ] 取消按钮中断流式，已生成部分保留
- [ ] 节点数接近 500 时 AI 操作被拒
- [ ] 导出 .md 文件内容正确（含 blockquote 笔记）
- [ ] 复制为 Markdown 后剪贴板内容正确
- [ ] 切到 chat 再切回，map 还是上次状态（依赖 force-flush）
- [ ] 刷新页面后状态恢复（依赖防抖保存生效）
- [ ] 删除助手后该助手的 mind-maps 不再出现

## 时序与依赖

阶段间是严格串行的（Phase N 依赖 N-1）。单个 Phase 内可并行。一个合理的提交粒度：

1. Phase 1：1 个 commit（后端 CRUD + 清理）。
2. Phase 2：1 个 commit（RAG 扩展 + AI 引擎 + AI 端点）。
3. Phase 3：1 个 commit（前端骨架 + 视图切换 + 列表）。
4. Phase 4：1 个 commit（流式解析 + 节点拼接 + AI 操作）。
5. Phase 5：1 个 commit（自动保存）。
6. Phase 6：1 个 commit（导出/剪贴板）。
7. Phase 7：1 个 commit（边界 toast + 上限校验）。

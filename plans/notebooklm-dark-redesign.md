# NotebookLM 风深色重构 (Frontend Visual Redesign)

## Problem Statement

学生在使用多学科学习助手时，反映前端"画风过于难看且古早"：

- 紫色渐变背景 (`linear-gradient(135deg, #667eea 0%, #764ba2 100%)`) 是 2020 年前后的"管理后台模板"配色，已严重过时。
- 大量 emoji（📚 🔑 🎯 📤 📁 📊 ⚙️ 🧠 ✨ 📝 ⬇）当图标，视觉风格不统一，且和现代产品的单色线条图标语言不符。
- "卡片 + 重投影 + 12px 圆角"的几何语汇是 Material Design v1 时期的旧范式，hover 时的 `translateY(-1px) + box-shadow` 反馈也属于古早表达。
- 单一长侧栏塞了 6 个 section（API Key / 助手切换 / 上传 / 文件列表 / 统计 / 操作），概念混杂、视觉冗长。
- 聊天用 80% 宽紫底气泡靠右/白底气泡靠左的即时消息样式，与"知识对话"场景不匹配，长 AI 回答和代码块体验差。
- 仅有浅色（且色调不健康），没有深色模式，夜间长时间学习刺眼。
- 5 类按钮（primary/secondary/warning/danger/success）滥用色彩语义，导致界面"花"。

学生希望以 NotebookLM 桌面 Web 端为参考，把整套前端的视觉语言、布局结构、组件样式统一升级到 2026 年现代产品的水准。

## Solution

全站重做前端视觉，深度对齐 NotebookLM 设计语言，**仅深色模式**，全 4 个视图（助手选择 / 聊天 / 测验 / 思维导图）和全部模态都覆盖。重做包括：

- **色系**：深色三档灰（底/面板/边）+ Google Dark Blue `#8AB4F8` 作为全局唯一强调色。
- **结构**：把单一长侧栏拆成 NotebookLM 标志性的 **Sources | Chat | Studio 三栏**，配置类操作收纳进 header 右上设置菜单。
- **几何**：面板 16px / 按钮 24px pill / 小元素 8px，**零投影**，靠 1px 边框 + 面板色差区分层级。
- **图标**：全部 emoji → Material Symbols Outlined（CDN）。
- **字体**：Inter（CDN）+ 系统中文 fallback。
- **聊天**：用户消息浅色 pill 气泡靠右 70% / AI 消息全宽无气泡纯文本 + brand 色圆头像 / 代码块独立深底卡。
- **输入框**：NotebookLM 标志性"24px 圆角输入卡片 + 右下角圆形 36px 蓝发送按钮"。
- **按钮分级**：三档极简（primary / secondary / danger），废弃 warning / success。
- **响应式**：桌面 ≥1200 三栏 / 平板 768–1199 隐藏 Studio / 手机 <768 仅 Chat + drawer。
- **JS 影响极小**：保留所有现有 DOM ID，仅重组 HTML 父子结构 + CSS 完全重写 + JS 5–10 处补丁。

## User Stories

1. As a 夜间学习的学生, I want 深色模式作为默认且唯一主题, so that 我长时间盯着屏幕做题/读 AI 回答时不会被刺眼的白底紫渐变疲劳。
2. As a 第一次打开应用的学生, I want 看到一个干净的"助手列表"全屏页, so that 我能像在 NotebookLM 选 notebook 一样一眼挑出今天要复习的学科。
3. As a 助手选择页的学生, I want 每张助手卡左上角有 brand 色徽章+ Material Symbol, so that 我能在 4 个学科里靠颜色和符号秒认出"数据结构是紫"、"机器学习是红"。
4. As a 进入聊天的学生, I want header 中央实时显示当前助手名加 brand 色圆点, so that 我永远清楚自己正在跟哪个助手讲话。
5. As a 常忘 API Key 状态的学生, I want header 右上有一个 ● / ○ 状态点提示 API Key 是否已配置, so that 我不用进设置页就知道自己能不能发消息。
6. As a 高频用户, I want API Key、切换助手、清空对话、清空知识库这些低频操作藏在 header 右上设置菜单, so that 我的主界面不会被一堆低频按钮塞满。
7. As a 上传资料的学生, I want Sources 栏单独承载"上传 + 文件列表 + 统计"三部分, so that 我管理学习资料时有一个明确的"资料栏"心智模型。
8. As a 用思维导图/测验的学生, I want Studio 栏顶部固定"思维导图 / 生成测验 / 长期备忘"三个工具入口, so that 我能像在 NotebookLM Studio 里那样集中触发学习工具。
9. As a 多对话切换的学生, I want Studio 栏下半部根据当前视图动态显示"会话列表"或"导图列表", so that 我不需要四栏才能管理多个会话/导图。
10. As a 做测验的学生, I want 进入 Quiz 视图后左右两栏自动隐藏, so that 我能专注答题不被资料和工具入口干扰。
11. As a 长 AI 回答的读者, I want AI 消息全宽不带气泡, so that 长段落、代码块、列表都能舒展地阅读，不会在窄气泡里被横向滚动。
12. As a 提问的学生, I want 自己的消息有浅色 pill 气泡靠右 70% 宽, so that 在长对话里我能一眼区分"我说的"和"AI 说的"。
13. As a 看代码的学生, I want AI 回答里的代码块用比页底更深的独立背景 (`#0F0F10`), so that 代码块永远像一个独立卡片，不论它包在用户气泡还是无气泡 AI 段落里。
14. As a 提问的学生, I want 输入区是一整块 24px 圆角的"输入卡片"含右下角圆形蓝发送按钮, so that 我对"这是一个独立的输入区域"有清晰的感知，而不是表单字段。
15. As a 键盘用户, I want `:focus-visible` 显示 2px 蓝描边焦点环, so that 我用 Tab 切换按钮/输入时能清楚看到当前焦点位置（但鼠标点击时不显示，不污染视觉）。
16. As a 滚动长对话的学生, I want 滚动条是 8px 宽、track 透明、thumb `#3C3C40` 的自定义样式, so that 浅灰系统默认滚动条不会破坏深色面板的统一感。
17. As a 复制文本的学生, I want 选中态是蓝 `#8AB4F8` 30% 透明底加白字, so that 选中态颜色和全局强调色统一，看起来像成品应用而非半成品深色主题。
18. As a 点击 AI 回答里链接的学生, I want 链接是蓝 `#8AB4F8` + 悬停加下划线, so that 链接颜色不会出现 Markdown 默认的紫红混搭。
19. As a 打开模态框的用户, I want 模态框是 `#2A2A2E` 面板 + 24px 圆角 + 1px 边框 + 零投影 + `rgba(0,0,0,0.6)` 遮罩, so that 模态框和全局深色面板系统融洽，且和按钮/输入卡的圆角语汇一致。
20. As a 偶尔在平板上访问的学生, I want 768–1199 屏幕宽度下 Studio 栏自动隐藏、Sources 栏可折叠, so that 平板上我仍然能正常聊天和管理资料，不会出现三栏挤死。
21. As a 用手机临时查看的学生, I want <768 屏幕宽度下只显示中央 Chat 栏，Sources 和 Studio 用左右滑出 drawer, so that 手机上聊天界面不会被挤变形。
22. As a 切换助手的学生, I want 点击 header "切换助手"后回到全屏助手列表页, so that 切换流程和 NotebookLM "回到 Notebooks 列表 → 选新 notebook" 完全一致。
23. As a 思维导图用户, I want 进入 Mind-Map 视图后 Studio 栏下半部自动从"会话列表"切到"导图列表", so that Studio 栏的下半部分始终对应"我当前在管理的东西"。
24. As a 模态框里输入的用户, I want 输入框是深面板色而非白底, so that 输入框不会在深色弹窗里突兀地亮起来。
25. As a 关注品牌一致性的学生, I want 4 个助手的 brand 色（紫/绿/橙/红）仅在徽章/圆点等"局部点缀"使用, so that 全局唯一强调色（蓝 `#8AB4F8`）不被助手色冲淡，4 色不会互相打架。
26. As a 关心可维护性的开发者, I want 所有颜色、间距、圆角通过 `:root` CSS 变量定义, so that 未来调整深浅档位/换强调色只需要改变量定义，不用全文搜索替换。
27. As a 关心稳定性的开发者, I want 所有现有 DOM ID 保留不变, so that 视觉重构期间 `getElementById` 等 JS 调用全部保持工作，功能 0 回归。
28. As a 实施这次重构的开发者, I want 工作分成 3 个阶段（基础设施 → 结构与组件 → 细节打磨）, so that 每阶段结束都能 reload 看效果、可独立验证，而不是一次性 1000+ 行改动堆在一起。

## Implementation Decisions

> 详细决策来自 `/grill-me` 20 轮设计讨论的结论；此处仅作落地契约。

### 设计令牌（Design Tokens）

通过 `:root` CSS 变量集中定义。**仅深色模式**，不做浅色与深色双套。

```css
:root {
  /* 色板 */
  --bg:           #1B1B1F;  /* 页底 */
  --panel:        #2A2A2E;  /* 面板/侧栏/卡片/模态/输入卡 */
  --panel-hover:  #33333A;  /* 卡片 hover */
  --border:       #3C3C40;  /* 1px 分隔线 / 描边 */
  --border-hover: #4A4A4F;  /* 滚动条 thumb hover */
  --text:         #E3E3E3;  /* 主文字 */
  --text-dim:     #9AA0A6;  /* 次文字 / 占位 / 标签 */
  --accent:       #8AB4F8;  /* 强调色 - 按钮/链接/焦点/选中态 */
  --code-bg:      #0F0F10;  /* 代码块 - 比页底更深 */
  --danger:       #F28B82;  /* danger 文字按钮 */
  --danger-soft:  rgba(242, 139, 130, 0.08); /* danger hover 底色 */

  /* 圆角 */
  --r-pill:  24px; /* 按钮 / 输入卡 / 模态 */
  --r-card:  16px; /* 面板 / 助手卡 / 会话项 */
  --r-small: 8px;  /* 输入框 / 代码块 / tag */
  --r-full:  9999px; /* 圆头像 / 圆图标按钮 */

  /* 间距、字号略 */
}
```

### 模块/区块切分

**注意**：本项目前端无构建、无模块系统（CLAUDE.md 明确："No build step, no modules"）。"模块"在此理解为 CSS 分层 + HTML 区块 + JS 补丁点，不是 JS 文件级模块。**不新增 JS 文件**。

| 区块 | 类型 | 修改文件 | 主要工作 |
|---|---|---|---|
| 设计令牌 | CSS 变量层 | `frontend/css/styles.css`（重写） | `:root` 内集中所有色/圆角/间距 token |
| 基础层 | CSS 全局 reset + 字体 + 滚动条 + 焦点 + 选中 | 同上 | 替换现有 reset，引 Inter / Material Symbols |
| 三栏外壳 | HTML + CSS | `frontend/index.html` 重组、styles.css 新 class | `.app-shell` / `.sources-panel` / `.chat-panel` / `.studio-panel` |
| Header | HTML + CSS | 同上 | 左 logo + "学习助手"、中助手名+brand 圆点、右 API 状态点+设置⚙菜单 |
| 助手选择视图 | HTML + CSS + body mode class | 同上 + `app.js` 微补丁 | 全屏布局；卡片改为 `--panel` 底 + brand 徽章；body 加 `is-assistant-selection` class 隐藏左右栏 |
| Chat 区 | HTML + CSS | 同上 | 用户气泡 pill 靠右 70% / AI 全宽无气泡 + brand 圆头像 / 代码块独立深底 |
| 输入卡片 | HTML + CSS | 同上 | 24px 圆角面板包 textarea，右下角圆形 36px 蓝发送 |
| Studio 栏 | HTML 重组 + JS 切换逻辑 | 同上 + `app.js` 视图切换函数补丁 | 上半工具入口、下半根据 view 动态显示 sessionList / mindmapList |
| Quiz 视图 | body mode class | `quiz.js` 进入/退出补丁 | body 加 `is-quiz-fullscreen` class，CSS 隐藏左右栏 |
| Mind-Map 视图 | HTML 重组 | `mindmap.js` 微补丁 | 把 `.mindmap-sidebar` 内容搬到 Studio 栏下半部 |
| 模态框 | CSS | styles.css | `.modal` / `.modal-overlay` / `.modal-label` / `.modal-actions` 全部深色化 |
| 按钮系统 | CSS | styles.css | 重定义 `.btn` `.btn-primary` `.btn-secondary` `.btn-danger`，废弃 warning/success（合并入 danger 或 secondary） |
| 响应式 | CSS @media | styles.css | 三档断点：1200 / 768 |

### HTML 结构契约

新的 `<body>` 顶层结构（保留所有原 ID）：

```
<body class="theme-dark"> <!-- 视图模式 class 动态切换 -->
  <header class="app-header">
    <div class="app-header__brand"> [logo + "学习助手"] </div>
    <div class="app-header__current"> [brand-dot + 助手名] </div>
    <div class="app-header__actions">
      <span id="apiKeyStatus" class="api-key-dot"></span>
      <button class="icon-btn" id="openSettingsBtn">settings</button>
    </div>
  </header>

  <main class="app-shell">
    <!-- Sources -->
    <aside class="sources-panel">
      <section id="uploadSection">...</section>
      <section id="fileListSection">...</section>
      <section id="statsSection">...</section>
    </aside>

    <!-- Chat / Mindmap / Quiz 中央区 -->
    <section class="main-panel">
      <div id="assistantSelectionView" class="view active">...</div>
      <div id="chatView" class="view">...</div>
      <div id="quizView" class="view">...</div>
      <div id="mindmapView" class="view">...</div>
    </section>

    <!-- Studio -->
    <aside class="studio-panel">
      <div class="studio-tools"> [测验 / 思维导图 / 备忘 按钮] </div>
      <div class="studio-list">
        <div id="sessionList" class="session-list" data-view="chat"></div>
        <div id="mindmapList" class="mindmap-list" data-view="mindmap" hidden></div>
      </div>
    </aside>
  </main>

  <!-- 设置抽屉（收纳原 API Key / 切换助手 / 清空对话 / 清空 KB） -->
  <div id="settingsDrawer" class="modal-overlay" style="display:none;">
    <div class="modal">
      <section><input id="apiKeyInput">...<button id="saveApiKeyBtn">保存</button></section>
      <section><button id="changeAssistantBtn">切换助手</button></section>
      <section><button id="clearHistoryBtn" class="btn-danger">清空对话</button></section>
      <section><button id="clearKbBtn" class="btn-danger">清空知识库</button></section>
    </div>
  </div>

  <!-- 其它模态框：原有 7 个全部保留，仅样式重写 -->
</body>
```

### JS 补丁点

JS 几乎不重写，仅以下补丁：

1. `app.js` 的 `showAssistantSelection()`：给 `<body>` 加 `is-assistant-selection` class，离开时移除。
2. `app.js` 当前助手切换：填充 `app-header__current` 内的 brand-dot + 助手名。
3. `app.js` 新增 `openSettingsBtn` 监听器：toggle `#settingsDrawer.style.display`。
4. `app.js` 当 API Key 保存/校验时，更新 `#apiKeyStatus` 上的 class（`is-set` / `is-unset`）。
5. `app.js`/`chat.js`/`mindmap.js` 视图切换时切换 Studio 栏下半部：根据当前 view 给 `#sessionList` / `#mindmapList` 加 / 移 `hidden`。
6. `quiz.js` 进入测验时给 `<body>` 加 `is-quiz-fullscreen` class，退出时移除。
7. `upload.js` 在生成文件列表 / 助手卡片 / 删除按钮等 innerHTML 处，把 emoji 字符替换为 `<span class="material-symbols-outlined">icon_name</span>`。

### 设计令牌 → 组件应用约定

- 任何"长得像面板的东西"统一用 `var(--panel)` + `var(--r-card)` + `1px solid var(--border)` + 无 `box-shadow`。
- 任何按钮类元素圆角 `var(--r-pill)`；图标按钮用 `var(--r-full)` + 36×36px。
- 任何文本输入框：在弹窗里继承 `--panel`，在输入卡里无边框，外层卡片用 `var(--r-pill)`。
- AI 头像：24×24 圆形，背景 = 当前助手的 brand color。
- 助手卡徽章：48×48 圆形，背景 = 该助手 brand color，内含白色单色 Material Symbol。
- 4 个助手图标符号建议：
  - `data_structures` → `account_tree`
  - `computer_systems` → `developer_board`
  - `discrete_math` → `function`
  - `machine_learning` → `smart_toy`

### 实施阶段（3 阶段交付）

#### 阶段 1：基础设施（不可见地基）
- 引入 Inter（Google Fonts CDN）和 Material Symbols Outlined（CDN）到 `index.html` `<head>`。
- 重写 `styles.css` 顶部：`:root` 变量、`*` reset、body 字体/底色、自定义滚动条、`:focus-visible`、`::selection`、链接样式。
- 此阶段结束后页面 reload 应该：背景已经是 `#1B1B1F`、文字已是 `#E3E3E3`、滚动条已变细，但布局仍乱（旧 class 已部分失效）。这是预期的中间态。

#### 阶段 2：结构与主要组件
- HTML 重组三栏 + header + 设置抽屉。
- 写 `.app-shell` / `.sources-panel` / `.chat-panel` / `.studio-panel` / `.app-header` 布局 CSS。
- 重写助手卡片、聊天消息（用户 pill / AI 无气泡 + 头像 / 代码块）、输入卡片、按钮系统、模态框样式。
- JS 补丁全部落地。
- emoji → Material Symbols 全量替换。
- 此阶段结束后页面 reload 应该：视觉已经是"基本是 NotebookLM 风"，所有功能（聊天/上传/测验/思维导图）正常工作。

#### 阶段 3：细节打磨
- 响应式断点 1200 / 768。
- 移动 drawer 滑出动画。
- 空状态 / 加载状态 / hover 动效细化。
- 各模态 / 列表项 / toast 的边角样式审查。
- 完成本次重构。

## Testing Decisions

本项目无测试框架（CLAUDE.md 明确："No test framework, linter, or type checker is configured"），且本次改动是**视觉重构 + DOM 重组**，没有新增可单测的纯逻辑模块。因此：

- **不引入新的测试框架**。视觉差异的自动化测试（如 Playwright + 视觉回归）超出本次 PRD 范围。
- **测试方式：人工 checkpoint 验证**。每个阶段结束后用浏览器手动跑下面的 checklist。

### 阶段 1 验收 checklist
- [ ] 页面 reload 后底色变为 `#1B1B1F`，文字 `#E3E3E3`，无任何紫色渐变残留。
- [ ] 滚动条变成 8px 宽、深灰 thumb。
- [ ] Tab 键切换焦点时出现 2px 蓝色 outline；鼠标点击时不出现。
- [ ] 选中任意文本，选中态是蓝色半透明。
- [ ] Console 无 404（确认 Inter 字体和 Material Symbols 加载成功）。

### 阶段 2 验收 checklist（**核心功能不回归**）
- [ ] 首次打开 → 助手选择页全屏显示 4 张卡片，无左右栏。
- [ ] 点击任意助手卡 → 进入聊天三栏布局，header 显示助手名 + brand 色圆点。
- [ ] API Key 保存/读取仍正常（点击 header ⚙ → 抽屉打开 → 输入 → 保存 → 抽屉关闭 → API 状态点变 "已配置"）。
- [ ] 上传 PDF/TXT 文件，文件出现在 Sources 栏的"已上传文件"列表里。
- [ ] 发起聊天，AI 流式回复正常显示（无气泡全宽 + brand 圆头像 + 代码块独立深底）。
- [ ] 用户消息显示为浅色 pill 气泡靠右 70%。
- [ ] Studio 栏底部显示当前会话列表，可新建/切换会话。
- [ ] 点击"生成测验" → 进入 Quiz 视图 → 左右栏自动隐藏（全屏沉浸）→ 答题 + 批改正常 → 退出测验后三栏恢复。
- [ ] 点击"思维导图" → 进入 Mind-Map 视图 → Studio 栏下半部从"会话列表"切到"导图列表" → jsmind 渲染正常 → AI 生成树/扩展节点/生成笔记三个 SSE 流式操作仍工作。
- [ ] 切换助手按钮 → 回到全屏助手列表页。
- [ ] 全站不存在任何 emoji 字符（页面源码/innerHTML 里搜不到 📚🔑🎯📤📁📊⚙️🧠✨📝⬇）。

### 阶段 3 验收 checklist
- [ ] 桌面 ≥1200：三栏正常显示。
- [ ] 平板 768–1199：Studio 栏隐藏，Sources 可折叠。
- [ ] 手机 <768：仅 Chat 显示，左右各有汉堡按钮唤出 drawer。
- [ ] toast / 空知识库状态 / 流式加载占位等细节状态视觉一致。

### 测试规范
- **只测外部行为**：能看到的渲染结果、能点的交互结果、能 reload 后保留的状态。
- **不测 CSS 内部实现**：不验证"是不是用了变量"、"是不是用了某个 class 名"。
- 视觉回归靠 reload + 肉眼对照 NotebookLM 截图。

## Out of Scope

- **浅色模式**。本次只做深色，未来如需浅色另起 PRD。
- **真正的主题切换器**。不提供"切换浅/深"的 UI 入口。
- **国际化（i18n）**。文案保持中文。
- **无障碍（a11y）深度审查**。本次保证 `:focus-visible` 焦点环可见、强调色对比度 ≥ 4.5:1，但不做 ARIA 标签全量补全 / 屏幕阅读器适配。
- **后端 API 改动**。所有 `/api/*` 端点形态不变。
- **新功能**。本次只重塑现有功能的视觉，不新增功能（不加新视图、不加新按钮、不加 AI 工具）。
- **自动化视觉回归测试** / **测试框架引入**。
- **JS 重构 / 模块化 / 引入构建工具**。`api.js` / `chat.js` / `quiz.js` / `upload.js` / `mindmap.js` / `app.js` 6 个文件的架构维持不变。
- **图标的离线 fallback**。Material Symbols 走 CDN，假设有网络。如未来需要离线则单独迁移到内联 SVG。
- **`apiKeyStatus` 已有的文字状态显示**。原本是文字 "已保存" / "未配置"，新版本将改为视觉色点，但 JS 里 `apiKeyStatus.textContent = ...` 这类调用可保留（隐藏文字、靠 class 控制点的颜色），避免 JS 改动扩大。

## Further Notes

### 与 `CLAUDE.md` 项目约定的关系
- 加载顺序（`api.js` → `chat.js` → `quiz.js` → `upload.js` → `mindmap.js` → `app.js`）**不变**。
- 全局单例（`window.api` / `chatManager` / `quizManager` / `uploadManager` / `app`）**不变**。
- `data/uploaded/` / `data/vector_store/` / 后端任何路径与契约**不变**。

### 与现有 ADR / plan 的关系
- 不修改 `plans/mindmap-feature.md` 里锁定的思维导图设计决策（节点 schema / 3 个 AI 操作 / 树结构限制等），仅重做其视觉外观。
- 不影响 `plans/sequential-roaming-mist.md` 里的内容（独立的另一个特性）。

### Brand 色复用约定
4 个助手 brand 色（紫 `#4f46e5` / 绿 `#059669` / 橙 `#d97706` / 红 `#dc2626`）保留来自 `backend/app.py` 的 `ASSISTANTS_CONFIG`。前端仅在以下 3 处使用 brand 色：
1. 助手卡片左上角 48px 圆形徽章
2. Header 中央"当前助手名"前的 8px 圆点
3. 聊天页 AI 消息左侧 24px 圆头像

其它任何地方（按钮、链接、强调、焦点环、选中态）**只用** 全局强调色 `--accent: #8AB4F8`。

### 实施版本号
`index.html` 中的 CSS / JS 查询参数版本号 (`?v=5` 等) 每个阶段递增以避开浏览器缓存：阶段 1 → `?v=6`，阶段 2 → `?v=7`，阶段 3 → `?v=8`。

# 测验选择题选项排版修复

## Context

测验界面中，单选题（`single_choice`）的选项在文本较短时显示正常，但当某个选项文本足够长以至于换行到第二行时，相邻的选项框会发生视觉上的相互重叠。

**根本原因：** `frontend/js/quiz.js` 把每个选项渲染为 `<label class="option">`，而 `<label>` 默认是 `display: inline`。`frontend/css/styles.css` 的 `.option` 规则给它加了 `padding: 10px`、`border` 和 `margin-bottom: 8px`，但这些属性在 inline 元素上的行为是异常的：
- `margin-top` / `margin-bottom` 对 inline 元素**不生效**，所以选项之间不会按预期产生 8px 的纵向间距。
- inline 元素的 `padding` 和 `border` 会绘制在相邻行内容之上，**不会**把后面的兄弟元素向下推开。

因此一旦某个 `.option` 因为文字过长换行变高，它的 padding / border 就会"压"到下一个 `.option` 上，造成肉眼可见的重叠。短文本时凑巧不重叠纯属偶然。

同时，当前结构 `<input> 选项文本` 是文字直接拼在 input 之后；当文字换行时，第二行会顶到 input 下方（而不是与文字首行左对齐），可读性也较差。

## 目标

让选择题选项无论文本多长都能正确分行、不重叠，且换行后的文字与首行左对齐（radio 在首行旁边）。

## 修改方案

只改 CSS，不动 JS / HTML 结构。修改文件：

- `frontend/css/styles.css`（`.options` / `.option` 规则块，约 537–558 行）

### 具体修改

将 `.options` 改为纵向 flex 容器，用 `gap` 控制选项之间的间距；将 `.option` 改为 `flex`，让 radio 与文本以两个 flex item 形式排布，从而获得稳定的换行对齐。

```css
.options {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 12px;
}

.option {
    display: flex;
    align-items: flex-start;   /* radio 与首行文字顶对齐 */
    gap: 8px;
    padding: 10px;
    background: white;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
    line-height: 1.5;
    word-break: break-word;    /* 长英文/代码也能正常换行 */
}

.option:hover {
    background: #f3f4f6;
    border-color: #4f46e5;
}

.option input[type="radio"] {
    margin: 0;                 /* 由 flex gap 接管间距 */
    margin-top: 0.2em;         /* 视觉上让 radio 与首行文字中线对齐 */
    flex-shrink: 0;            /* 防止 radio 被挤压变形 */
}
```

关键点说明：
1. `.option` 改为 `display: flex` 后，它变成 block-level box，`margin` 才会真正撑开纵向间距；这里用父容器 `.options` 的 `gap: 8px` 代替原先的 `margin-bottom: 8px`，效果等价且更干净。
2. `align-items: flex-start` + `flex-shrink: 0` 保证文字换行时第二行与第一行左对齐，radio 始终待在左上角而不被压扁。
3. 删除原 `.option input[type="radio"]` 的 `margin-right: 8px`（被 `gap` 取代），改为微调 `margin-top` 让 radio 与首行文字视觉对齐。

## 不修改的内容

- `frontend/js/quiz.js` 的 `renderQuestion` 渲染逻辑（123–134 行）保持不变。
- `frontend/index.html` 的 `quizView` 容器结构保持不变。
- 其他题型（`short_answer` / `code_reading` / `proof`）的 `textarea.answer-input` 样式不受影响。

## 验证步骤

1. 启动后端：`cd backend && python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload`
2. 启动前端：`cd frontend && python -m http.server 5500`
3. 浏览器打开 `http://127.0.0.1:5500`，进入任一助手 → 测验。
4. 生成一组单选题，并人工构造或挑选**至少一道选项文本足够长以至于换行**的题目（必要时可在 `quiz_engine.py` 临时调高 `count` 或在 prompt 里要求"较长的选项"以便快速触发）。
5. 检查项：
   - 长选项换行后，与下一个选项之间**仍有可见空隙**，没有视觉重叠。
   - 长选项的第二行起始位置与首行文字左边缘对齐，**不**跑到 radio 按钮下方。
   - 鼠标 hover 时整个选项框（含换行后的多行内容）整体高亮，边框颜色变化覆盖整块区域。
   - 短选项的视觉效果与改动前基本一致（不应明显变窄或变胖）。
6. 切换不同助手（数据结构 / 计算机系统 / 离散数学 / 机器学习）各做一次测验，确认四个助手的测验界面表现一致。

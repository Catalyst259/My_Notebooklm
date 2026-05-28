from typing import List, Dict, Any, Optional

from token_budget import trim_history, DEFAULT_HISTORY_BUDGET


# ============================================================
# 通用底座：所有学科助手共享的行为规范、RAG 规则、格式约定与教学风格。
# 各学科 prompt 只需提供「学科身份 + 范围 + 例子语言 + 学科特异规则」。
# ============================================================
_BASE_PROMPT_TEMPLATE = """你是一位精通{subject_name}的资深助教,由先进的大语言模型驱动。

## 教学范围
{subject_scope}

## 核心职责
帮助学习者**真正理解**概念、掌握方法,而非只给答案。回答需兼顾正确性、教学性与可操作性。

## 知识来源使用规则(RAG 专属,最高优先级)
1. **优先采用知识库**:若下文「参考片段」含相关内容,必须基于其作答,并在引用处用 `[来源: 文件名]` 标注。
2. **诚实标注盲区**:若参考片段不足以回答,必须明确说「资料中未直接提及」,再基于通用知识补充,并以「(基于通用知识,仅供参考)」标注。
3. **禁止编造**:绝不伪造来源、虚构定理、捏造 API 或函数签名。不确定时直接说「我不确定」。
4. **多片段冲突时**:指出冲突,按可信度排序,并说明你的判断依据。

## 默认回答结构
对实质性问题,按以下骨架组织(顺序可压缩,但层次要清晰):
1. **结论先行** —— 用 1-2 句直接回应核心问题
2. **原理讲解** —— 分步骤剖析;必要时用类比、对比表、ASCII 图示
3. **{example_section}** —— 给出可运行 / 可推导的具体例子
4. **延伸提醒**(可选) —— 常见误区、{complexity_hint}、相关知识点

事实性追问 / 简单问题可跳过此结构,直接给出答案。

## 格式规范
- 使用 Markdown。代码块**必须**标注语言(本学科默认使用 ```{code_lang}```),便于高亮与复制。
- 行内数学使用 \\( ... \\),独立公式使用 \\[ ... \\]。
- 引用知识库原文用 Markdown 引用块(`>`),并在末尾附 `[来源: 文件名]`。
- 列表层级不超过 3 层;超长解释优先用小标题切分,而非堆叠嵌套列表。

## 教学风格
- **澄清优先**:问题模糊或缺关键条件时,先反问澄清——不要猜意图后给出长篇错答。
- **难度自适应**:从用户措辞判断水平。术语熟练则跳过基础铺垫;措辞稚嫩则从直觉切入。
- **节制反问**:启发式反问每轮至多 1 处,避免回答被反问淹没。
- **不卖弄**:能用一句话讲清的,不展开成三段。
{subject_specific_block}
始终使用中文回复,保持专业、耐心、富有教育意义。"""


def _render_prompt(
    subject_name: str,
    subject_scope: str,
    example_section: str,
    code_lang: str,
    complexity_hint: str,
    subject_specific_rules: str = "",
) -> str:
    """Render the base prompt with the given subject deltas."""
    if subject_specific_rules.strip():
        subject_specific_block = f"\n## 学科特异规则\n{subject_specific_rules.strip()}\n"
    else:
        subject_specific_block = "\n"
    return _BASE_PROMPT_TEMPLATE.format(
        subject_name=subject_name,
        subject_scope=subject_scope,
        example_section=example_section,
        code_lang=code_lang,
        complexity_hint=complexity_hint,
        subject_specific_block=subject_specific_block,
    )


# ============================================================
# 学科特化:只填差异部分,其余继承底座。
# ============================================================
SYSTEM_PROMPTS = {
    "data_structures": _render_prompt(
        subject_name="C++ 数据结构与算法",
        subject_scope="线性表、栈与队列、树与图、堆、哈希、排序、查找、动态规划、贪心、回溯等核心算法与数据结构。",
        example_section="C++ 代码示例",
        code_lang="cpp",
        complexity_hint="时间 / 空间复杂度分析",
        subject_specific_rules=(
            "- 给出算法时必须分析时间与空间复杂度,并指出最坏 / 平均 / 最好情况的差异。\n"
            "- 代码使用现代 C++(C++17 起),合理使用 STL;裸指针操作需配注释说明所有权。\n"
            "- 涉及递归 / 分治时,给出递推式并尝试求解。"
        ),
    ),

    "computer_systems": _render_prompt(
        subject_name="计算机系统",
        subject_scope="计算机组成原理、操作系统、计算机体系结构、汇编语言、编译原理、计算机网络。",
        example_section="代码 / 汇编 / 时序图示例",
        code_lang="c",
        complexity_hint="性能 / 局部性 / 同步开销",
        subject_specific_rules=(
            "- 解释底层原理时,按「数字电路 → 微架构 → 指令集 → 操作系统 → 应用」层次自下而上剖析。\n"
            "- 涉及具体硬件 / OS 行为时,优先给出可验证的例子(Linux 内核片段、x86/ARM 汇编、`strace` 输出等)。\n"
            "- 区分「规范规定」与「实现细节」,避免将某厂商实现误述为通用行为。"
        ),
    ),

    "discrete_math": _render_prompt(
        subject_name="离散数学",
        subject_scope="数理逻辑、集合论、图论、组合数学、代数结构、数论基础、形式语言与自动机。",
        example_section="形式化推导 / 反例",
        code_lang="text",
        complexity_hint="复杂度 / 可判定性",
        subject_specific_rules=(
            "- 定理证明需给出严谨推理步骤,每步标明依据(定义 / 引理 / 已证结论)。\n"
            "- 引入抽象概念后立即给出具体实例与反例。\n"
            "- 公式与符号使用规范 LaTeX;集合 / 逻辑符号不与中文混排造成歧义。"
        ),
    ),

    "machine_learning": _render_prompt(
        subject_name="机器学习",
        subject_scope="监督 / 无监督 / 强化学习、深度学习、模型评估与调优、特征工程、NLP、计算机视觉。",
        example_section="Python 代码示例(NumPy / PyTorch / scikit-learn)",
        code_lang="python",
        complexity_hint="训练 / 推理复杂度 与 样本复杂度",
        subject_specific_rules=(
            "- 介绍算法时覆盖:核心思想、数学推导、适用场景、局限性与失败模式。\n"
            "- 代码示例使用 Python 主流库;张量操作标注形状(如 `# x: (B, T, D)`)。\n"
            "- 涉及超参 / 经验值时,说明其来源(论文 / 经验法则 / 任务相关),避免暗示「唯一正确值」。"
        ),
    ),
}


def build_generic_system_prompt(name: str, description: str) -> str:
    """Build a generic system prompt for user-created assistants."""
    return _render_prompt(
        subject_name=f"「{name}」领域",
        subject_scope=description,
        example_section="具体例子(代码 / 公式 / 案例)",
        code_lang="text",
        complexity_hint="关键权衡",
        subject_specific_rules="",
    )


# ============================================================
# 思维导图操作 prompt（叠加在学科 system prompt 之后）
# ============================================================
REVIEW_CARD_DRAFT_PROMPT = (
    "你正在帮助学生把一段学习内容整理成一张复习卡片。"
    "请基于提供的内容生成一张 Anki 风格的卡片："
    "front 是一个简短的问题或提示（不超过 50 字），"
    "back 是简明的中文答案（2-4 句话，可包含必要的代码或公式）。"
    "只输出合法 JSON，不要输出 Markdown 代码块。"
    "结构：{\"front\": \"...\", \"back\": \"...\"}"
)


MINDMAP_OP_PROMPTS = {
    "generate_tree": (
        "现在切换到「思维导图生成」模式。\n"
        "你正在为学生生成一份学习思维导图。\n"
        "## 严格输出规范\n"
        "- 仅输出 Markdown 项目符号列表，使用 `-` 开头，每级缩进**恰好 2 个空格**。\n"
        "- 第一行必须是根主题，不缩进，例如：`- {topic}`。\n"
        "- 深度不超过 {depth} 层（含根节点）。\n"
        "- 每个父节点的直接子节点不超过 {width} 个。\n"
        "- 节点文字保持精炼（不超过 20 字），不加序号、不加句号。\n"
        "- 不输出 Markdown 标题、说明文字、代码块、空行或任何前言/总结。\n"
        "- 不要在节点后追加解释，纯结构。\n"
        "## 主题\n{topic}"
    ),
    "expand_node": (
        "现在切换到「思维导图节点扩展」模式。\n"
        "你正在为已有思维导图中的一个节点生成新的子节点。\n"
        "## 节点信息\n"
        "- 路径（从根到目标节点）：{path}\n"
        "- 目标节点已有的兄弟子节点（必须避免重复）：{siblings}\n"
        "## 严格输出规范\n"
        "- 仅输出恰好 {count} 行 Markdown 项目符号，每行形如 `- 子节点名称`，**不缩进**、**不嵌套**。\n"
        "- 这些都是目标节点的同级新增子节点；不要把它们彼此嵌套，也不要把已有兄弟列出来。\n"
        "- 节点文字精炼（不超过 20 字），不带序号、不带句号。\n"
        "- 不输出 Markdown 标题、说明文字、代码块、空行或任何前言/总结。"
    ),
    "generate_note": (
        "现在切换到「思维导图节点笔记」模式。\n"
        "为思维导图中的某个节点撰写一段简洁的中文学习笔记。\n"
        "## 节点路径\n{path}\n"
        "## 严格输出规范\n"
        "- 2 至 4 句话；必要时可包含 Markdown 代码块或 LaTeX 公式（`\\(...\\)` / `\\[...\\]`）。\n"
        "- 仅输出笔记正文，不重复节点名，不加 Markdown 标题，不写「这是关于 XX 的笔记」之类的元话术。\n"
        "- 优先解释**核心定义**或**关键性质**，而不是泛泛而谈。"
    ),
}


def _format_path(path: List[str]) -> str:
    """Render a node path as 'A > B > C'."""
    return " > ".join(p.strip() for p in path if p and p.strip())


def _format_siblings(siblings: List[str]) -> str:
    """Render a list of sibling labels for display in prompts."""
    cleaned = [s.strip() for s in siblings if s and s.strip()]
    if not cleaned:
        return "（无）"
    return "、".join(cleaned)


class RAGEngine:
    """Builds prompts with RAG context for the LLM."""

    def __init__(self, knowledge_base, assistant_id: str = "data_structures", system_prompt: Optional[str] = None):
        self.knowledge_base = knowledge_base
        self.assistant_id = assistant_id
        self.system_prompt = system_prompt
        self.top_k = 5  # number of chunks to retrieve
        self.max_context_chars = 4000  # limit context length

    def retrieve_context(self, query: str) -> List[Dict[str, Any]]:
        """Retrieve relevant chunks from knowledge base."""
        results = self.knowledge_base.search(query, top_k=self.top_k)
        return results

    def _format_context(self, results: List[Dict[str, Any]]) -> str:
        """Format retrieved chunks into a readable context string."""
        if not results:
            return "（知识库中暂无相关内容）"

        context_parts = []
        total_chars = 0
        for i, r in enumerate(results):
            chunk_text = r['text'].strip()
            source = f"[来源: {r['file_name']}]"
            entry = f"参考片段 {i+1}:\n{chunk_text}\n{source}\n"

            if total_chars + len(entry) > self.max_context_chars:
                break

            context_parts.append(entry)
            total_chars += len(entry)

        return "\n".join(context_parts)

    def build_messages(
        self,
        query: str,
        history: Optional[List[Dict[str, str]]] = None,
        memory_note: str = "",
        history_budget: int = DEFAULT_HISTORY_BUDGET,
    ) -> List[Dict[str, str]]:
        """
        Build the full message list for the LLM call.

        Args:
            query: User's current question
            history: Previous conversation history [{"role": "user"|"assistant", "content": str}, ...]
            memory_note: Optional per-assistant memory note appended to the system prompt.
            history_budget: Token budget for trimming history before sending.

        Returns:
            List of messages in OpenAI-compatible format
        """
        # Retrieve relevant context
        results = self.retrieve_context(query)
        context = self._format_context(results)

        # Get system prompt for this assistant
        if self.system_prompt:
            system_prompt = self.system_prompt
        else:
            system_prompt = SYSTEM_PROMPTS.get(self.assistant_id, SYSTEM_PROMPTS["data_structures"])

        note = (memory_note or "").strip()
        if note:
            system_prompt = (
                f"{system_prompt}\n\n---\n"
                f"关于这位学习者的长期备忘（用户自己填写，请在回答时纳入考量）：\n{note}"
            )

        # Build contextualized user message
        user_message = f"""以下是从知识库中检索到的相关内容（可能包含中英文混合内容）：

{context}

---

基于以上知识，请回答用户的问题：

{query}"""

        messages = [
            {"role": "system", "content": system_prompt},
        ]

        # Add conversation history trimmed to a token budget.
        if history:
            messages.extend(trim_history(history, budget=history_budget))

        messages.append({"role": "user", "content": user_message})

        return messages

    def _get_subject_system_prompt(self) -> str:
        if self.system_prompt:
            return self.system_prompt
        return SYSTEM_PROMPTS.get(self.assistant_id, SYSTEM_PROMPTS["data_structures"])

    def build_mindmap_messages(
        self,
        op: str,
        *,
        topic: Optional[str] = None,
        path: Optional[List[str]] = None,
        siblings: Optional[List[str]] = None,
        depth: Optional[int] = None,
        width: Optional[int] = None,
        count: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        """Build messages for mind-map AI operations.

        op: 'generate_tree' | 'expand_node' | 'generate_note'
        """
        if op not in MINDMAP_OP_PROMPTS:
            raise ValueError(f"Unknown mind-map op: {op}")

        # --- Derive retrieval query
        if op == "generate_tree":
            if not topic:
                raise ValueError("topic is required for generate_tree")
            query = topic
        else:
            if not path:
                raise ValueError("path is required for this op")
            query = _format_path(path)

        results = self.retrieve_context(query)
        context = self._format_context(results)

        # --- Compose system prompt: subject persona + op instruction
        subject_prompt = self._get_subject_system_prompt()
        if op == "generate_tree":
            op_prompt = MINDMAP_OP_PROMPTS["generate_tree"].format(
                topic=topic,
                depth=depth or 2,
                width=width or 4,
            )
        elif op == "expand_node":
            op_prompt = MINDMAP_OP_PROMPTS["expand_node"].format(
                path=_format_path(path or []),
                siblings=_format_siblings(siblings or []),
                count=count or 4,
            )
        else:  # generate_note
            op_prompt = MINDMAP_OP_PROMPTS["generate_note"].format(
                path=_format_path(path or []),
            )

        full_system = subject_prompt + "\n\n---\n" + op_prompt

        user_message = (
            "以下是从知识库中检索到的相关参考片段：\n\n"
            f"{context}\n\n"
            "---\n"
            "请基于以上参考（若相关）以及你的通用知识，严格按上方"
            "「严格输出规范」生成内容。"
        )

        return [
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_message},
        ]

    def build_review_card_messages(
        self,
        source_content: str,
        source_context: str = "",
    ) -> List[Dict[str, str]]:
        """Build messages for AI card drafting. top-3 retrieval, capped at 1500 chars."""
        results = self.knowledge_base.search(source_content, top_k=3) if source_content else []
        context_parts = []
        total = 0
        for r in results:
            entry = f"参考片段（{r.get('file_name','')}）:\n{r.get('text','').strip()}\n"
            if total + len(entry) > 1500:
                break
            context_parts.append(entry)
            total += len(entry)
        context = "\n".join(context_parts) if context_parts else "（无相关参考片段）"

        subject_prompt = self._get_subject_system_prompt()
        full_system = subject_prompt + "\n\n---\n" + REVIEW_CARD_DRAFT_PROMPT

        ctx_note = f"\n上下文说明：{source_context}\n" if source_context else ""
        user_message = (
            f"以下是学生标记的学习内容：\n\n{source_content}\n"
            f"{ctx_note}\n"
            f"可参考的知识库片段：\n{context}\n\n"
            "请输出 JSON：{\"front\": \"...\", \"back\": \"...\"}"
        )

        return [
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_message},
        ]
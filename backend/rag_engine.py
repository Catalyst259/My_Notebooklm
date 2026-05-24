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
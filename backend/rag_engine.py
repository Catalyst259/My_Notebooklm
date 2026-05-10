from typing import List, Dict, Any, Optional


# System prompts for each assistant
SYSTEM_PROMPTS = {
    "data_structures": """你是一位精通 C++ 数据结构与算法的资深助教。

你的职责是帮助用户理解数据结构与算法的核心概念，并学会用 C++ 实现它们。

回答原则：
1. 回答应基于提供的知识上下文。如果知识库中有相关内容，请优先引用并详细展开。
2. 如果问题与知识库无关或知识库中没有相关信息，请如实说明你无法从资料中找到答案，然后尝试基于你自己的知识给出合理的建议。
3. 当被问及代码实现时，提供清晰、完整、带注释的 C++ 代码示例。
4. 对于算法问题，解释时间复杂度和空间复杂度。
5. 对于复杂概念，使用分步解释或类比来帮助理解。
6. 如果用户的问题不够清晰，请引导用户提供更多细节。

始终使用中文回复，保持专业、耐心且富有教育意义。""",

    "computer_systems": """你是一位精通计算机系统的资深助教。

你的教学范围包括：计算机组成原理、操作系统、计算机体系结构、汇编语言、编译原理、计算机网络等核心课程。

回答原则：
1. 回答应基于提供的知识上下文。如果知识库中有相关内容，请优先引用并详细展开。
2. 如果问题与知识库无关或知识库中没有相关信息，请如实说明你无法从资料中找到答案，然后尝试基于你自己的知识给出合理的建议。
3. 解释底层原理时，从数字电路→微架构→指令集→操作系统→上层应用的层次逐步剖析。
4. 对于操作系统和体系结构问题，提供具体的示例（如 Linux 内核代码片段、汇编代码）来佐证。
5. 对于复杂概念，使用分步解释或类比来帮助理解。
6. 如果用户的问题不够清晰，请引导用户提供更多细节。

始终使用中文回复，保持专业、耐心且富有教育意义。""",

    "discrete_math": """你是一位精通离散数学的资深助教。

你的教学范围包括：数理逻辑、集合论、图论、组合数学、代数结构、数论基础、形式语言与自动机等。

回答原则：
1. 回答应基于提供的知识上下文。如果知识库中有相关内容，请优先引用并详细展开。
2. 如果问题与知识库无关或知识库中没有相关信息，请如实说明你无法从资料中找到答案，然后尝试基于你自己的知识给出合理的建议。
3. 对于定理证明，给出严谨的推理步骤，必要时使用数学符号和逻辑表达。
4. 通过具体例子和反例来阐明抽象概念。
5. 对于复杂概念，使用分步解释或类比来帮助理解。
6. 如果用户的问题不够清晰，请引导用户提供更多细节。

始终使用中文回复，保持专业、耐心且富有教育意义。""",

    "machine_learning": """你是一位精通机器学习的资深助教。

你的教学范围包括：监督学习、无监督学习、深度学习、强化学习、模型评估与调优、特征工程、NLP、计算机视觉等。

回答原则：
1. 回答应基于提供的知识上下文。如果知识库中有相关内容，请优先引用并详细展开。
2. 如果问题与知识库无关或知识库中没有相关信息，请如实说明你无法从资料中找到答案，然后尝试基于你自己的知识给出合理的建议。
3. 提供代码示例时使用 Python，并配合 NumPy、PyTorch 或 scikit-learn 等主流库。
4. 解释算法时涵盖核心思想、数学原理、适用场景和局限性。
5. 对于复杂概念，使用分步解释或类比来帮助理解。
6. 如果用户的问题不够清晰，请引导用户提供更多细节。

始终使用中文回复，保持专业、耐心且富有教育意义。"""
}


def build_generic_system_prompt(name: str, description: str) -> str:
    """Build a generic system prompt for user-created assistants."""
    return f"""你是一位「{name}」领域的资深助教。

{description}

回答原则：
1. 回答应基于提供的知识上下文。如果知识库中有相关内容，请优先引用并详细展开。
2. 如果问题与知识库无关或知识库中没有相关信息，请如实说明你无法从资料中找到答案，然后尝试基于你自己的知识给出合理的建议。
3. 回答要条理清晰，必要时使用分步解释、例子或类比来帮助理解。
4. 对于涉及代码或公式的问题，提供清晰、完整、带注释的示例。
5. 对于复杂概念，分解为易于理解的部分。
6. 如果用户的问题不够清晰，请引导用户提供更多细节。

始终使用中文回复，保持专业、耐心且富有教育意义。"""


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

    def build_messages(self, query: str, history: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, str]]:
        """
        Build the full message list for the LLM call.
        
        Args:
            query: User's current question
            history: Previous conversation history [{"role": "user"|"assistant", "content": str}, ...]
        
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

        # Build contextualized user message
        user_message = f"""以下是从知识库中检索到的相关内容（可能包含中英文混合内容）：

{context}

---

基于以上知识，请回答用户的问题：

{query}"""

        messages = [
            {"role": "system", "content": system_prompt},
        ]

        # Add conversation history (exclude oldest if too long)
        if history:
            # Keep last N turns (rough heuristic)
            history_to_include = history[-10:]
            messages.extend(history_to_include)

        messages.append({"role": "user", "content": user_message})

        return messages
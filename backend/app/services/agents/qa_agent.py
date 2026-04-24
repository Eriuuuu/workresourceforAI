"""
GBMP 智能问答 Agent — 多轮 RAG，向量数据库 + 图数据库

检索策略：
  第 1 轮：用原始问题进行 RAG（向量 + 图数据库混合检索）
  → LLM 判断信息是否足以回答用户问题
  → 若不足：LLM 整理当前已知信息 + 生成下一轮检索方向
  → 若充足：直接整理信息并回答
  第 2~3 轮：用 LLM 生成的检索方向进行 RAG，结合之前已有信息再次判断
  最多 3 轮 RAG。
"""
import asyncio
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger

from app.services.agents.base import (
    BaseAgent, AgentRole, AgentResult, AgentContext,
    StepStatus,
)

# 最大 RAG 轮次
MAX_RAG_ROUNDS = 3


class GbmpQaAgent(BaseAgent):
    """
    GBMP 智能问答 Agent

    多轮 RAG 流程：
    1. 每轮执行向量+图数据库混合检索
    2. 由 LLM 判断信息是否充分、决定下一轮检索方向
    3. 最多 3 轮，最终由 LLM 整理信息并回答
    """

    role = AgentRole.GBMP_QA
    name = "GBMP 智能问答"
    description = "基于代码库知识图谱和向量检索的智能问答（支持多轮RAG）"

    # ---- Prompt 模板 ----

    # 每轮 RAG 后的「信息评估 + 检索方向生成」提示词
    _EVALUATE_PROMPT = """## 任务
你是一个代码知识库检索决策器。请根据用户问题、当前已检索到的信息，完成两件事：
1. 判断当前信息是否足以回答用户问题
2. 若不足，指出还需要检索哪些方向的内容

## 用户问题
{question}

## 已检索到的信息
{retrieved_summary}

## 已检索到的文件列表（{total_files} 个）
{retrieved_files}

## 已完成检索轮次
{current_round} / {max_rounds}

## 输出要求
请严格返回 JSON（不要有任何其他内容）：
```json
{{
  "is_sufficient": true/false,
  "analysis": "简要分析：当前信息的覆盖情况和缺失点",
  "search_direction": "如果 is_sufficient 为 false，给出下一轮应该检索的方向和关键词（不超过50字）。如果 is_sufficient 为 true，此字段留空字符串"
}}
```"""

    # 最终回答生成的提示词
    _ANSWER_PROMPT = """你是 GBMP 建模软件的代码专家。根据检索到的代码信息和用户的问题，给出准确、专业的回答。

## 用户问题
{question}

## 检索到的代码信息
{context}

## 要求
1. 基于检索到的真实代码内容回答，不要编造代码
2. 直接引用具体的文件路径、函数名、类名
3. 如果检索到的信息不足以完整回答，请如实说明哪些部分缺少信息
4. 用中文回答，确保准确、实用
5. 对代码功能进行专业解读"""

    def __init__(self):
        super().__init__()

    # ==================== 主流程 ====================

    async def execute(self, context: AgentContext) -> AgentResult:
        start = time.time()
        question = context.user_message

        logger.info(f"[{self.name}] 处理问题: {question[:100]}")

        # 检查检索系统是否可用
        retrieval_system = self._get_retrieval_system()
        if retrieval_system is None:
            return AgentResult(
                success=False,
                answer="问答系统未初始化，请先调用初始化接口。",
                agent_role=self.role.value,
                agent_name=self.name,
                processing_time=time.time() - start,
                error="未初始化",
                steps=context.steps,
            )

        # ---- 多轮 RAG 检索 ----
        all_retrieved: List[Dict[str, Any]] = []
        all_source_files: set = set()
        current_query = question
        actual_rounds = 0
        is_sufficient = False

        try:
            for round_num in range(1, MAX_RAG_ROUNDS + 1):
                actual_rounds = round_num

                # 步骤：RAG 检索
                rag_step = StepStatus(
                    step_name=f"RAG 检索 第 {round_num}/{MAX_RAG_ROUNDS} 轮",
                    status="running",
                    detail=f"检索: {current_query[:80]}",
                )
                context.steps.append(rag_step)
                self._emit_progress(context)

                # 执行混合检索（向量 + 图数据库），排除已检索过的文件
                round_results = await self._retrieve(
                    retrieval_system, current_query,
                    max_files=5, exclude_files=all_source_files,
                )

                # 统计新增文件
                new_files = 0
                for r in round_results:
                    fp = r.get("file_path", "")
                    if fp and fp not in all_source_files:
                        all_source_files.add(fp)
                        new_files += 1
                all_retrieved.extend(round_results)

                rag_step.status = "completed"
                rag_step.detail = f"检索到 {new_files} 个新文件，累计 {len(all_source_files)} 个文件"
                self._emit_progress(context)

                # 步骤：LLM 评估信息充分性
                eval_step = StepStatus(
                    step_name=f"信息评估 第 {round_num}/{MAX_RAG_ROUNDS} 轮",
                    status="running",
                    detail="LLM 正在评估检索结果是否充分...",
                )
                context.steps.append(eval_step)
                self._emit_progress(context)

                is_sufficient, search_direction = await self._evaluate_retrieval(
                    question=question,
                    all_retrieved=all_retrieved,
                    all_source_files=all_source_files,
                    current_round=round_num,
                )

                eval_step.status = "completed"
                if is_sufficient:
                    eval_step.detail = "信息已充分，准备生成回答"
                elif round_num >= MAX_RAG_ROUNDS:
                    eval_step.detail = "已达最大轮次，使用当前信息回答"
                else:
                    eval_step.detail = f"信息不足，下一轮方向: {search_direction[:60]}"
                self._emit_progress(context)

                # 信息充分或达到最大轮次 → 退出循环
                if is_sufficient or round_num >= MAX_RAG_ROUNDS:
                    break

                # 本轮无新增且无检索方向 → 避免无效循环
                if new_files == 0 and not search_direction.strip():
                    logger.info(f"[{self.name}] 无新增文件且无检索方向，停止检索")
                    break

                # 用 LLM 生成的检索方向作为下一轮 query
                current_query = search_direction.strip() if search_direction.strip() else question

        except Exception as e:
            logger.error(f"[{self.name}] RAG 检索异常: {e}", exc_info=True)

        # ---- 生成最终回答 ----
        answer_step = StepStatus(
            step_name="生成回答",
            status="running",
            detail="正在基于检索结果生成回答...",
        )
        context.steps.append(answer_step)
        self._emit_progress(context)

        try:
            context_text = self._build_context_text(all_retrieved)
            answer = await self._generate_answer(question, context_text)

            answer_step.status = "completed"
            answer_step.detail = f"回答生成完成（{len(answer)} 字）"

            # 更新对话历史
            context.conversation_history.append({"role": "user", "content": question})
            context.conversation_history.append({"role": "assistant", "content": answer})

            elapsed = time.time() - start
            context.agent_chain.append({
                "role": self.role.value,
                "name": self.name,
                "status": "completed",
            })

            return AgentResult(
                success=True,
                answer=answer,
                agent_role=self.role.value,
                agent_name=self.name,
                processing_time=elapsed,
                meta={
                    "source_files": sorted(all_source_files),
                    "files_count": len(all_source_files),
                    "rag_rounds": actual_rounds,
                    "retrieved_chunks": len(all_retrieved),
                },
                steps=context.steps,
            )

        except Exception as e:
            logger.error(f"[{self.name}] 回答生成失败: {e}", exc_info=True)
            answer_step.status = "failed"
            answer_step.detail = str(e)

            context.agent_chain.append({
                "role": self.role.value, "name": self.name, "status": "failed"
            })
            return AgentResult(
                success=False,
                answer=f"问答失败: {str(e)}",
                agent_role=self.role.value,
                agent_name=self.name,
                processing_time=time.time() - start,
                error=str(e),
                steps=context.steps,
            )

    # ==================== 核心方法 ====================

    async def _evaluate_retrieval(
        self,
        question: str,
        all_retrieved: List[Dict[str, Any]],
        all_source_files: set,
        current_round: int,
    ) -> Tuple[bool, str]:
        """
        由 LLM 评估当前检索信息是否充分，并生成下一轮检索方向。

        返回: (is_sufficient, search_direction)
        """
        from app.services.agents.llm_client import get_llm_client

        retrieved_summary = self._build_retrieval_summary(all_retrieved)
        retrieved_files = ", ".join(sorted(all_source_files))

        prompt = self._EVALUATE_PROMPT.format(
            question=question,
            retrieved_summary=retrieved_summary[:3000],
            retrieved_files=retrieved_files or "暂无",
            total_files=len(all_source_files),
            current_round=current_round,
            max_rounds=MAX_RAG_ROUNDS,
        )

        llm = get_llm_client()
        result = await llm.ask(
            question=prompt,
            system_message="你是一个代码知识库检索决策器。严格返回 JSON 格式，不要有任何其他内容。",
            temperature=0.1,
        )

        if not result.get("success"):
            logger.warning(f"[{self.name}] LLM 评估调用失败: {result.get('error')}")
            return False, ""

        parsed = self._parse_json(result.get("answer", ""))
        if parsed is None:
            return False, ""

        is_sufficient = bool(parsed.get("is_sufficient", False))
        search_direction = str(parsed.get("search_direction", ""))
        analysis = str(parsed.get("analysis", ""))

        logger.info(
            f"[{self.name}] 第 {current_round} 轮评估: "
            f"is_sufficient={is_sufficient}, analysis={analysis[:80]}, "
            f"search_direction={search_direction[:60]}"
        )

        return is_sufficient, search_direction

    async def _generate_answer(
        self, question: str, context_text: str
    ) -> str:
        """基于检索结果生成最终回答"""
        from app.services.agents.llm_client import get_llm_client

        llm = get_llm_client()
        prompt = self._ANSWER_PROMPT.format(
            question=question,
            context=context_text[:8000],
        )

        result = await llm.ask(
            question=prompt,
            system_message="你是 GBMP 建模软件的代码专家，请基于检索到的代码信息回答问题。",
            temperature=0.3,
        )

        if result.get("success"):
            return result["answer"]
        return f"回答生成失败: {result.get('error', '未知错误')}"

    # ==================== 检索执行 ====================

    async def _retrieve(
        self, retrieval_system, query: str, max_files: int = 5,
        exclude_files: Optional[set] = None,
    ) -> List[Dict[str, Any]]:
        """执行向量+图数据库混合检索（异步），排除已检索过的文件"""
        try:
            results = await asyncio.to_thread(
                retrieval_system.retrieve_relevant_code, query, max_files
            )
            if exclude_files:
                results = [
                    r for r in results
                    if r.get("file_path", "") not in exclude_files
                ]
            return results
        except Exception as e:
            logger.error(f"[{self.name}] 检索失败: {e}")
            return []

    # ==================== 辅助方法 ====================

    @staticmethod
    def _emit_progress(context: AgentContext):
        """将当前进度推送给前端（通过 API 层注入的回调函数）"""
        if hasattr(context, '_progress_callback') and callable(context._progress_callback):
            try:
                context._progress_callback({
                    "steps": [s.model_dump() for s in context.steps],
                    "agent_chain": context.agent_chain,
                })
            except Exception:
                pass

    @staticmethod
    def _build_retrieval_summary(retrieved: List[Dict[str, Any]]) -> str:
        """构建已检索信息的摘要，供 LLM 评估使用（含实体信息和匹配片段）"""
        if not retrieved:
            return "暂无检索结果"

        lines = []
        seen_files = set()
        for item in retrieved:
            fp = item.get("file_path", "")
            confidence = item.get("confidence") or item.get("metadata", {}).get("score", 0.5)

            if fp and fp not in seen_files:
                seen_files.add(fp)
                lines.append(f"【{fp}】(置信度: {confidence:.2f})")

                # 附带实体摘要信息（文件中包含哪些函数/类）
                entity_summary = item.get("entity_summary", "")
                if entity_summary:
                    lines.append(entity_summary)

                # 附带精确匹配的 chunk 片段
                matched_chunks = item.get("matched_chunks", [])
                if matched_chunks:
                    lines.append("匹配到的代码片段:")
                    for chunk in matched_chunks[:2]:
                        chunk_content = chunk.get("content", "")[:200]
                        lines.append(f"  >>> {chunk_content}")
            lines.append("")

        return "\n".join(lines) if lines else "暂无有效检索结果"

    @staticmethod
    def _build_context_text(retrieved: List[Dict[str, Any]]) -> str:
        """构建用于 LLM 回答的完整上下文文本（含实体结构信息）"""
        if not retrieved:
            return "未检索到相关代码信息。"

        seen_files = set()
        sections = []
        for item in retrieved:
            fp = item.get("file_path", "")
            content = item.get("content", "")
            if not content or fp in seen_files:
                continue
            seen_files.add(fp)

            # 附带实体结构信息
            entity_summary = item.get("entity_summary", "")
            header = f"--- {fp} ---"
            if entity_summary:
                header += f"\n{entity_summary}"

            sections.append(f"{header}\n{content[:3000]}")

        return "\n\n".join(sections) if sections else "未检索到相关代码信息。"

    @staticmethod
    def _parse_json(text: str) -> Optional[Dict]:
        """从 LLM 回答中提取 JSON（兼容 markdown 代码块包裹）"""
        if not text or not text.strip():
            return None

        json_str = text.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()

        if not json_str.startswith("{"):
            start = json_str.find("{")
            end = json_str.rfind("}")
            if start >= 0 and end > start:
                json_str = json_str[start:end + 1]
            else:
                return None

        try:
            parsed = json.loads(json_str)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None

    # ==================== 生命周期 ====================

    @property
    def is_initialized(self) -> bool:
        """检查 QA 系统是否已初始化"""
        qa_system = self._get_qa_system()
        return qa_system is not None and getattr(qa_system, 'is_initialized', False)

    @staticmethod
    def _get_qa_system():
        """获取全局 QA 系统实例（通过 qa_system_manager，避免循环引用）"""
        from app.services.agents.qa_system_manager import get_qa_system
        return get_qa_system()

    @staticmethod
    def _get_retrieval_system():
        """获取全局检索系统实例（HybridRetrievalSystem）"""
        from app.services.agents.qa_system_manager import get_qa_system
        qa_system = get_qa_system()
        if qa_system and hasattr(qa_system, 'retrieval_system'):
            return qa_system.retrieval_system
        return None

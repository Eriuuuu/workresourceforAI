"""
意图识别 Agent — 统一入口，补全意图并路由分发
"""
import json
import time
from typing import Dict, Any
from loguru import logger

from app.services.agents.base import (
    BaseAgent, AgentRole, AgentResult, AgentContext,
    StepStatus, get_registry,
)


class IntentRouterAgent(BaseAgent):
    """
    意图识别 Agent

    接收用户消息，通过 LLM 识别意图类别并补全意图描述，
    然后分发给对应 Agent 处理。
    """

    role = AgentRole.INTENT_ROUTER
    name = "意图识别"
    description = "识别用户意图、补全信息并路由到对应的专业 Agent"

    _CLASSIFY_PROMPT = """# 意图分类与补全提示词（支持中英文转化）

你是一个专业的意图分类器。请根据用户消息，完成以下任务：
1. 将用户消息归入三类意图之一；
2. 补全并细化用户的意图，形成一段完整、可执行的意图描述，**特别关注中英文实体的正确转化与保留**；
3. 给出置信度评分。

## 意图类别

| 类别 | 适用场景 |
|------|----------|
| `gbmp_qa` | 用户询问 **GBMP 代码库** 的相关知识：架构设计、模块功能、接口定义、实现细节、API 使用、配置、部署、故障排查等开发技术问题。 |
| `modeling` | 用户希望进行 **建筑建模** 操作：创建、修改、删除构件（梁、柱、板、墙、门、窗等）；生成或编辑建筑模型（楼层、空间、几何形状）；查询模型中构件或属性信息。 |
| `llm` | 不属于以上两类的通用问题：闲聊、问候、翻译、总结、写作、通用知识问答（与代码库/建模无关）、日常咨询等。 |

## 任务要求

### 1. 意图分类
从上述三个类别中选出最匹配的一个。

### 2. 意图补全与细化（重点）
将用户的需求转化为一段 **完整、具体、可执行** 的描述。补全时应遵循以下原则：

- **补全模糊信息**：若用户问题过于简略（如“怎么建墙”），根据领域常识补充合理的细节（墙的几何定义、参数、操作方式等）。
- **提取关键实体与约束**：明确用户提到的对象（构件类型、文件路径、函数名、属性值）、数量、位置、条件、范围等。
- **明确代码目标**（针对 `gbmp_qa`）：尽量指出目标文件、类、函数、模块或配置项。例如：“用户询问 `auth.py` 中的 `verify_token` 函数如何工作。”
- **明确建模操作**（针对 `modeling`）：指出构件类型、操作类型（创建/修改/删除/查询）、关键参数（尺寸、位置、材质等）。
- **合理推断，避免过度解读**：当信息不足时，使用“可能”“通常”等措辞，或基于常见场景给出默认假设，并在描述中说明。
- **结构化描述**：建议采用“用户希望 + 动作 + 目标对象 + 约束条件”的句式，使下游 Agent 一目了然。

#### **中英文转化规范（重要）**
- **保留英文原名**：当用户使用中文提及代码中的实体（类名、函数名、接口名、变量名、模块名、API 路径等）时，必须在补全描述中保留其原始英文名称。例如：
  - 用户说“`ComponentManager` 是干嘛的” → 补全中应写 `ComponentManager`，不要翻译成“组件管理器”。
  - 用户说“调用 `create_wall` 接口” → 补全中保留 `create_wall`。
- **中英文对照**：如果用户只提供了中文描述（如“构件管理器那个类”），但你知道对应的英文名（如 `ComponentManager`），可以在补全时用括号补充英文，格式为“中文（English）”。例如：“用户询问构件管理器（`ComponentManager`）类的职责。”
- **统一术语**：对于领域内的常见术语（如“梁”对应 `beam`，“柱”对应 `column`），在补全时建议同时给出中英文，以便下游 Agent 精确匹配。例如：“用户希望创建梁（`beam`）构件。”
- **API/路径保留原样**：涉及 URL、文件路径、配置键名等，保持原始大小写和分隔符。

**补全示例**（含中英文转化）：

| 用户消息 | 补全后的意图描述 |
|----------|------------------|
| “墙怎么建？” | 用户希望了解在建模系统中创建墙（`wall`）构件的方法，包括墙的几何定义（起点、终点、高度、厚度）以及可能的参数设置（如材质、定位）。 |
| “GBMP 的 `auth` 模块怎么用？” | 用户希望查询 GBMP 代码库中 `auth` 模块的使用方法，可能涉及认证函数（如 `login`、`verify_token`）或中间件配置。 |
| “调用 `create_beam` 接口需要传哪些参数？” | 用户希望了解 GBMP 代码库中 `create_beam` 接口的请求参数列表，包括必填字段（如长度、截面尺寸）和可选字段（如材质、ID）。 |
| “删除第3层的柱子” | 用户希望执行建模操作：删除模型中第3楼层（或第3层）上的所有柱子（`column`）构件。需要明确楼层标识和构件类型。 |
| “那个 `ComponentManager` 是干嘛的” | 用户希望查询 GBMP 代码库中 `ComponentManager` 类的职责、主要方法以及如何用于构件管理。 |
| “你好” | 用户发出问候，没有具体业务需求，期望获得通用回应。 |

### 3. 置信度评分
给出 `intent_confidence`，取值范围 1–5，含义如下：

- **5**：非常确定。用户消息包含明确的关键词或清晰的结构，几乎无歧义。
- **4**：比较确定。存在少量模糊点，但根据常见模式可以合理推断。
- **3**：一般确定。有一定歧义，需要依赖默认假设或上下文（若有）。
- **2**：不太确定。可能有多种合理解释，且缺乏足够上下文。
- **1**：完全不确定。消息极短、无意义或与三类意图均无明显关联。

## 输出格式

**严格**只返回以下 JSON 格式，不要包含任何额外文字、注释或 Markdown 代码块标记（即直接输出 JSON 字符串）：
{
  "intent": "gbmp_qa | modeling | llm",
  "reason": "简短说明分类依据，例如：用户明确询问 GBMP 代码库的接口实现。",
  "enriched_intent": "补全后的完整意图描述，注意中英文实体的规范转化。",
  "intent_confidence": 5
}"""

    async def execute(self, context: AgentContext) -> AgentResult:
        start = time.time()
        logger.info(f"[IntentRouter] 识别意图: {context.user_message[:100]}")

        try:
            # 通知前端：开始意图识别
            context.steps.append(StepStatus(
                step_name="意图识别与补全",
                status="running",
                detail="LLM 正在分析用户意图...",
            ))
            context.agent_chain.append({
                "role": self.role.value,
                "name": self.name,
                "status": "running",
            })
            self._emit_progress(context)

            # 构建包含对话历史的提示
            history_hint = ""
            if context.conversation_history:
                last_turns = context.conversation_history[-4:]  # 最近2轮
                history_hint = "\n\n最近的对话历史：\n"
                for turn in last_turns:
                    role = "用户" if turn["role"] == "user" else "助手"
                    history_hint += f"{role}: {turn['content'][:100]}\n"

            intent = await self._classify_intent(context.user_message, history_hint)
            logger.info(
                f"[IntentRouter] 识别结果: intent={intent['intent']}, "
                f"confidence={intent.get('intent_confidence', 3)}, "
                f"reason={intent['reason']}"
            )

            # 记录路由步骤（更新为 completed）
            if context.steps:
                for s in context.steps:
                    if s.step_name == "意图识别与补全":
                        s.status = "completed"
                        s.detail = f"识别为「{intent['reason']}」→ 分发至 {intent['intent']}"
                        break
            else:
                context.steps.append(StepStatus(
                    step_name="意图识别与补全",
                    status="completed",
                    detail=f"识别为「{intent['reason']}」→ 分发至 {intent['intent']}",
                ))

            # 更新 agent_chain 状态
            for c in context.agent_chain:
                if c.get("role") == self.role.value:
                    c["status"] = "completed"
                    c["name"] = self.name
                    break

            # 将补全后的意图注入上下文，传递给下游 Agent
            context.enriched_intent = intent.get("enriched_intent", context.user_message)

            # 通知进度
            self._emit_progress(context)

            # 分发给目标 Agent
            target_role = intent["intent"]
            registry = get_registry()
            target_agent = registry.get(target_role)

            if target_agent is None:
                logger.warning(f"[IntentRouter] Agent {target_role} 未注册，回退到 LLM")
                target_agent = registry.get(AgentRole.LLM.value)
                target_role = AgentRole.LLM.value

            if target_agent is None:
                return AgentResult(
                    success=False,
                    answer="系统暂时不可用，没有可用的 Agent 处理您的请求。",
                    agent_role=self.role.value,
                    agent_name=self.name,
                    processing_time=time.time() - start,
                    error="无可用 Agent",
                    steps=context.steps,
                )

            # 检查目标 Agent 是否已初始化
            if not target_agent.is_initialized:
                if target_role == AgentRole.GBMP_QA.value:
                    return AgentResult(
                        success=False,
                        answer="知识问答系统尚未初始化，请先在页面上初始化系统。",
                        agent_role=self.role.value,
                        agent_name=self.name,
                        processing_time=time.time() - start,
                        error="QA Agent 未初始化",
                        meta={"intent": target_role, "reason": intent["reason"]},
                        steps=context.steps,
                    )

            # 在 agent_chain 中追加目标 Agent（running 状态）
            context.agent_chain.append({
                "role": target_role,
                "name": target_agent.name,
                "status": "running",
            })
            context.current_agent_role = target_role

            # 调度目标 Agent 执行
            result = await target_agent.execute(context)

            # 在结果中附加路由信息
            result.meta["intent"] = target_role
            result.meta["reason"] = intent["reason"]
            result.meta["enriched_intent"] = context.enriched_intent
            result.steps = context.steps

            return result

        except Exception as e:
            logger.error(f"[IntentRouter] 意图识别失败: {e}", exc_info=True)
            return AgentResult(
                success=False,
                answer=f"意图识别失败: {str(e)}",
                agent_role=self.role.value,
                agent_name=self.name,
                processing_time=time.time() - start,
                error=str(e),
                steps=context.steps,
            )

    @staticmethod
    def _emit_progress(context: AgentContext):
        """将当前进度推送到前端（通过 task_store）"""
        if hasattr(context, '_progress_callback') and callable(context._progress_callback):
            try:
                context._progress_callback({
                    "steps": [s.model_dump() for s in context.steps],
                    "agent_chain": context.agent_chain,
                })
            except Exception:
                pass

    async def _classify_intent(self, message: str, history_hint: str = "") -> Dict[str, Any]:
        """调用 LLM 进行意图分类与补全"""
        from app.services.agents.llm_client import get_llm_client

        llm = get_llm_client()
        result = await llm.ask(
            question=f"{self._CLASSIFY_PROMPT}\n\n用户消息：{message}{history_hint}",
            system_message="你是一个意图分类器，只返回 JSON 格式的分类结果。",
            temperature=0.3,
        )

        if not result.get("success"):
            return {
                "intent": "llm",
                "reason": "意图识别失败，回退到通用问答",
                "enriched_intent": message,
                "intent_confidence": 1,
            }

        answer = result.get("answer", "")
        try:
            if "```json" in answer:
                answer = answer.split("```json")[1].split("```")[0]
            elif "```" in answer:
                answer = answer.split("```")[1].split("```")[0]

            parsed = json.loads(answer.strip())
            intent = parsed.get("intent", "llm")

            valid_intents = {"gbmp_qa", "modeling", "llm"}
            if intent not in valid_intents:
                intent = "llm"

            return {
                "intent": intent,
                "reason": parsed.get("reason", ""),
                "enriched_intent": parsed.get("enriched_intent", message),
                "intent_confidence": min(5, max(1, int(parsed.get("intent_confidence", 3)))),
            }
        except (json.JSONDecodeError, AttributeError, ValueError):
            logger.warning(f"[IntentRouter] JSON 解析失败: {answer[:200]}")
            return {
                "intent": "llm",
                "reason": "无法解析分类结果，回退到通用问答",
                "enriched_intent": message,
                "intent_confidence": 1,
            }

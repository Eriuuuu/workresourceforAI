"""
智能建模 Agent — 建筑结构建模

流水线：结构化输入 → 执行计划(按楼层排序) → 生成GBMP脚本 → 生成bat → 运行建模
"""
import os
import time
import json
from typing import Dict, Any, List
from loguru import logger

from app.services.agents.base import (
    BaseAgent, AgentRole, AgentResult, AgentContext,
    StepStatus,
)


# ==================== 建模步骤定义 ====================

class ModelingStep:
    """
    建模流程中的可扩展步骤基类。

    每个步骤:
      - name: 步骤名称
      - description: 步骤描述
      - run(context, step_input): 执行逻辑，返回 step_output
    """

    name: str = ""
    description: str = ""

    async def run(self, context: AgentContext, step_input: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


# -------------------- 步骤1: 结构化输入 --------------------

class StructurizeInputStep(ModelingStep):
    """步骤1: 结构化用户输入信息 — 专业建筑设计师角色"""

    name = "结构化输入"
    description = "通过 LLM 梳理用户需求，提取建筑构件信息"

    _PROMPT = """你是一名专业的建造师、建筑设计师和建筑结构设计师。请根据用户的描述，对房屋进行完整的结构设计。

## 设计原则

1. **充分理解用户需求**：对不完整或缺少的信息（如具体尺寸、构件数量等），根据建筑规范和工程经验自行合理补充和优化
2. **三维空间坐标系**：以毫米(mm)为单位
   - X 轴：水平方向（左右）
   - Y 轴：水平方向（前后）
   - Z 轴：竖直方向（上下），Z=0 为基础顶面
3. **按楼层分层设计**：明确房屋结构类型、总层数、每层层高、每层的构件布局和每个构件的坐标位置
4. **构件类型**：梁、柱、板、墙等结构构件

## 坐标规范

- 坐标原点为建筑左下角
- 梁的 Z 坐标 = 所在楼层顶标高（即 floor_number × height_per_floor）
- 柱的 bottom_z = (floor_number - 1) × height_per_floor，top_z = floor_number × height_per_floor
- 编号规则：梁 B{楼层}-{序号}，柱 C{楼层}-{序号}，板 S{楼层}-{序号}，墙 W{楼层}-{序号}

请以 JSON 格式返回以下信息：
{
  "building_type": "建筑结构类型（如框架结构、剪力墙结构、框架剪力墙结构等）",
  "total_floors": 层数（整数）,
  "height_per_floor": 每层高度（毫米，整数，常见值3000、3300、3600等）,
  "total_area": "总建筑面积（平方米）",
  "floor_plans": [
    {
      "floor_number": 1,
      "base_z": 0,
      "top_z": 3000,
      "beams": [
        {"id": "B1-1", "start_x": 0, "start_y": 0, "start_z": 3000, "end_x": 6000, "end_y": 0, "end_z": 3000, "section": "300x500"}
      ],
      "columns": [
        {"id": "C1-1", "x": 0, "y": 0, "bottom_z": 0, "top_z": 3000, "section": "400x400"}
      ],
      "slabs": [
        {"id": "S1-1", "floor": 1, "thickness": 120, "corners": [[0,0], [6000,0], [6000,9000], [0,9000]]}
      ],
      "walls": [
        {"id": "W1-1", "start_x": 0, "start_y": 0, "end_x": 6000, "end_y": 0, "bottom_z": 0, "top_z": 3000, "thickness": 200}
      ]
    }
  ]
}

只返回 JSON，不要其他内容。"""

    async def run(self, context: AgentContext, step_input: Dict[str, Any]) -> Dict[str, Any]:
        from app.services.agents.llm_client import get_llm_client

        llm = get_llm_client()
        result = await llm.ask(
            question=f"{self._PROMPT}\n\n用户描述：{context.user_message}",
            system_message="你是一名专业的建筑结构设计师，只返回 JSON 格式的设计数据。",
        )

        if not result.get("success"):
            raise RuntimeError(f"结构化输入失败: {result.get('error')}")

        answer = result.get("answer", "")
        # 提取 JSON
        if "```json" in answer:
            answer = answer.split("```json")[1].split("```")[0]
        elif "```" in answer:
            answer = answer.split("```")[1].split("```")[0]

        return json.loads(answer.strip())


# -------------------- 步骤2: 执行计划（按楼层排序） --------------------

class BuildExecutionPlanStep(ModelingStep):
    """步骤2: 按楼层生成建模执行顺序"""

    name = "执行计划"
    description = "按楼层排序生成建模执行顺序"

    async def run(self, context: AgentContext, step_input: Dict[str, Any]) -> Dict[str, Any]:
        floor_plans = step_input.get("floor_plans", [])
        height_per_floor = step_input.get("height_per_floor", 3000)

        actions: List[Dict[str, Any]] = []

        # 1. 新建项目
        actions.append({"type": "new_project", "description": "新建项目"})

        # 2. 逐楼层：切换楼层 → 创建梁 → 创建柱
        for fp in floor_plans:
            floor_num = fp.get("floor_number", 1)
            base_z = (floor_num - 1) * height_per_floor

            # 切换至当前楼层平面视图
            actions.append({
                "type": "switch_floor",
                "floor": floor_num,
                "base_z": base_z,
                "description": f"切换至楼层 {floor_num}",
            })

            # 创建梁
            beams = fp.get("beams", [])
            if beams:
                actions.append({
                    "type": "create_beams",
                    "floor": floor_num,
                    "beams": beams,
                    "description": f"创建楼层 {floor_num} 的 {len(beams)} 根梁",
                })

            # 创建柱
            columns = fp.get("columns", [])
            if columns:
                actions.append({
                    "type": "create_columns",
                    "floor": floor_num,
                    "columns": columns,
                    "description": f"创建楼层 {floor_num} 的 {len(columns)} 根柱",
                })

        # 3. 切换至三维视图 → 缩放适应
        actions.append({"type": "switch_3d_view", "description": "切换至三维视图"})
        actions.append({"type": "zoom_fit", "description": "缩放至适应窗口"})

        return {
            "actions": actions,
            "total_steps": len(actions),
            # 透传上游数据
            "building_type": step_input.get("building_type", ""),
            "total_floors": step_input.get("total_floors", 0),
            "height_per_floor": height_per_floor,
            "floor_plans": floor_plans,
        }


# -------------------- 步骤3: 生成 GBMP 建模脚本 --------------------

class GenerateScriptStep(ModelingStep):
    """步骤3: 将执行计划映射为 GBMP 建模脚本命令"""

    name = "生成脚本"
    description = "将执行计划转换为 GBMP 建模脚本"

    # ---------- GBMP 命令模板 ----------

    @staticmethod
    def _cmd_new_project() -> List[str]:
        """新建项目"""
        return [
            'JrnCmd.ProcessCommand("gmSetDebugModeCmd", "");',
            'JrnCmd.ProcessCommand("gmToggleDebugModeOptionsCmd", "DontCompareTransactionInReplay:\\"DontCompareTransactionInReplay\\" | ");',
            'JrnCmd.ProcessCommand("gmNewProject", "");',
            'JrnWdt.MousePress("QPushButton","pushButtonOK-NewFileDlg","Left");',
            'JrnWdt.MouseRelease("QPushButton","pushButtonOK-NewFileDlg","Left");',
        ]

    @staticmethod
    def _cmd_switch_floor(floor: int, base_z: float) -> List[str]:
        """切换至指定楼层平面视图"""
        floor_z = base_z + 0.5
        return [
            f'// ===== 切换至楼层 {floor} =====',
            f'JrnWdt.MousePress("QTreeWidget","modelViewTree-ModelViewDlg","Left",'
            f'"平面视图$楼层 {floor}$0"/*TreeNodePath*/,65/*X*/,8/*Y*/,'
            f'"IsHorizontalScrollVisible:false$IsVerticalScrollVisible:false$ItemCheckState:-1$ItemModifier:0"/*ExtendedParam*/);',
            f'JrnWdt.MouseRelease("QTreeWidget","modelViewTree-ModelViewDlg","Left",'
            f'"平面视图$楼层 {floor}$0"/*TreeNodePath*/,65/*X*/,8/*Y*/,'
            f'"IsHorizontalScrollVisible:false$IsVerticalScrollVisible:false$ItemCheckState:-1$ItemModifier:0"/*ExtendedParam*/);',
            f'JrnWdt.MouseDoubleClick("QTreeWidget","modelViewTree-ModelViewDlg","Left",'
            f'"平面视图$楼层 {floor}$0"/*TreeNodePath*/,65/*X*/,8/*Y*/,'
            f'"IsHorizontalScrollVisible:false$IsVerticalScrollVisible:false$ItemCheckState:-1$ItemModifier:0"/*ExtendedParam*/);',
            f'JrnWdt.MouseRelease("QTreeWidget","modelViewTree-ModelViewDlg","Left",'
            f'"平面视图$楼层 {floor}$0"/*TreeNodePath*/,65/*X*/,8/*Y*/,'
            f'"IsHorizontalScrollVisible:false$IsVerticalScrollVisible:false$ItemCheckState:-1$ItemModifier:0"/*ExtendedParam*/);',
            f'JrnCmd.ProcessCommand("gm.view.navigate", '
            f'"Direction_X:-0.0 | ,WindowWidth:1682 | ,ViewName:\\"楼层 {floor}\\" | '
            f',CameraType:1 | ,Position_X:0.0 | ,Position_Y:0.0 | ,Position_Z:{floor_z} | '
            f',Direction_Y:-0.0 | ,Direction_Z:-1.0 | ,UpDirection_X:0.0 | ,UpDirection_Y:1.0 | '
            f',OrthoWindowHeight:30000.0 | ,UpDirection_Z:0.0 | ,NearDist:0.0 | ,FarDist:1200.0 | '
            f',AspectRatio:1.9764982461929321 | ,FieldOfView:0.52359877559829882 | ,WindowHeight:851 | ");',
            f'JrnCmd.MouseMove(-29576.968854343947896, 11862.514615058898926, {base_z});',
        ]

    @staticmethod
    def _cmd_create_beam(beam: Dict[str, Any]) -> List[str]:
        """创建单根梁：起点点击 + 终点点击"""
        bid = beam.get("id", "")
        sx, sy, sz = beam.get("start_x", 0), beam.get("start_y", 0), beam.get("start_z", 0)
        ex, ey, ez = beam.get("end_x", 0), beam.get("end_y", 0), beam.get("end_z", 0)
        section = beam.get("section", "")
        return [
            f'// 梁 {bid}  截面:{section}',
            f'JrnCmd.MouseMove({sx}, {sy}, 0.5);',
            f'JrnCmd.LButtonDown({sx}, {sy}, 0.5);',
            f'JrnCmd.MouseMove({sx}, {sy}, 0.5);',
            f'JrnCmd.LButtonUp({sx}, {sy}, 0.5);',
            f'JrnCmd.MouseMove({ex}, {ey}, {ez});',
            f'JrnCmd.LButtonDown({ex}, {ey}, {ez});',
            f'JrnCmd.MouseMove({ex}, {ey}, {ez});',
            f'JrnCmd.LButtonUp({ex}, {ey}, {ez});',
        ]

    @staticmethod
    def _cmd_create_column(col: Dict[str, Any]) -> List[str]:
        """创建单根柱"""
        cid = col.get("id", "")
        cx, cy = col.get("x", 0), col.get("y", 0)
        bz, tz = col.get("bottom_z", 0), col.get("top_z", 0)
        section = col.get("section", "")
        return [
            f'// 柱 {cid}  截面:{section}  底Z={bz} 顶Z={tz}',
            f'JrnCmd.ProcessCommand("gmDrawStructureVerticalColumn", "");',
            f'JrnCmd.KeyUp(27/*Esc*/);',
        ]

    @staticmethod
    def _cmd_switch_3d_view() -> List[str]:
        """切换至三维视图"""
        return [
            '// ===== 切换至三维视图 =====',
            'JrnWdt.MousePress("QTreeWidget","modelViewTree-ModelViewDlg","Left",'
            '"三维视图$三维$0"/*TreeNodePath*/,30/*X*/,8/*Y*/,'
            '"IsHorizontalScrollVisible:false$IsVerticalScrollVisible:false$ItemCheckState:-1$ItemModifier:0"/*ExtendedParam*/);',
            'JrnWdt.MouseRelease("QTreeWidget","modelViewTree-ModelViewDlg","Left",'
            '"三维视图$三维$0"/*TreeNodePath*/,30/*X*/,8/*Y*/,'
            '"IsHorizontalScrollVisible:false$IsVerticalScrollVisible:false$ItemCheckState:-1$ItemModifier:0"/*ExtendedParam*/);',
            'JrnWdt.MouseDoubleClick("QTreeWidget","modelViewTree-ModelViewDlg","Left",'
            '"三维视图$三维$0"/*TreeNodePath*/,30/*X*/,8/*Y*/,'
            '"IsHorizontalScrollVisible:false$IsVerticalScrollVisible:false$ItemCheckState:-1$ItemModifier:0"/*ExtendedParam*/);',
            'JrnWdt.MouseRelease("QTreeWidget","modelViewTree-ModelViewDlg","Left",'
            '"三维视图$三维$0"/*TreeNodePath*/,30/*X*/,8/*Y*/,'
            '"IsHorizontalScrollVisible:false$IsVerticalScrollVisible:false$ItemCheckState:-1$ItemModifier:0"/*ExtendedParam*/);',
            'JrnCmd.ProcessCommand("gm.view.navigate", '
            '"WindowWidth:1682 | ,Direction_X:-0.5 | ,ViewName:\\"三维\\" | '
            ',CameraType:1 | ,Position_X:9521.1113339959466 | ,Position_Y:-9521.1113339959466 | '
            ',Position_Z:13464.884777401261 | ,Direction_Y:0.5 | ,Direction_Z:-0.70710678118654757 | '
            ',UpDirection_X:-0.5 | ,UpDirection_Y:0.5 | ,OrthoWindowHeight:30000.0 | '
            ',UpDirection_Z:0.70710678118654746 | ,NearDist:0.0 | ,FarDist:38011.95496931197 | '
            ',AspectRatio:1.9764982461929321 | ,FieldOfView:0.52359877559829882 | ,WindowHeight:851 | ");',
        ]

    @staticmethod
    def _cmd_zoom_fit() -> List[str]:
        """缩放至适应窗口"""
        return [
            '// ===== 缩放视图 =====',
            'JrnCmd.MouseMove(-7278.8264429041464609, -20839.262979036753677, 17341.09292425267995);',
            'JrnCmd.RButtonDown(-7278.8264429041464609, -20839.262979036753677, 17341.09292425267995);',
            'JrnCmd.RButtonUp(-7278.8264429041464609, -20839.262979036753677, 17341.09292425267995);',
            'JrnCmd.ProcessCommand("gmZoomFitCmd", '
            '"Vector3d_X:-7278.8264429041465 | ,Vector3d_Y:-20839.262979036754 | ,Vector3d_Z:17341.09292425268 | ");',
            'JrnCmd.ProcessCommand("gm.view.navigate", '
            '"WindowWidth:1682 | ,Direction_X:-0.5 | ,ViewName:\\"三维\\" | '
            ',CameraType:1 | ,Position_X:6718.0307291987956 | ,Position_Y:-8542.0605143550456 | '
            ',Position_Z:16139.255554960144 | ,Direction_Y:0.5 | ,Direction_Z:-0.70710678118654757 | '
            ',UpDirection_X:-0.5 | ,UpDirection_Y:0.5 | ,OrthoWindowHeight:19005.9765625 | '
            ',UpDirection_Z:0.70710678118654746 | ,NearDist:0.0 | ,FarDist:38011.95496931197 | '
            ',AspectRatio:1.9764982461929321 | ,FieldOfView:0.52359877559829882 | ,WindowHeight:851 | ");',
        ]

    # ---------- 主逻辑 ----------

    async def run(self, context: AgentContext, step_input: Dict[str, Any]) -> Dict[str, Any]:
        actions = step_input.get("actions", [])
        lines = [
            "// GBMP 自动建模脚本",
            f"// 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"// 建筑类型: {step_input.get('building_type', '')}",
            f"// 总层数: {step_input.get('total_floors', 0)}",
            f"// 层高: {step_input.get('height_per_floor', 0)}mm",
            "",
        ]

        for act in actions:
            act_type = act.get("type")

            if act_type == "new_project":
                lines.append("// ===== 新建项目 =====")
                lines.extend(self._cmd_new_project())
                lines.append("")

            elif act_type == "switch_floor":
                floor = act.get("floor", 1)
                base_z = act.get("base_z", 0)
                lines.extend(self._cmd_switch_floor(floor, base_z))
                lines.append("")

            elif act_type == "create_beams":
                beams = act.get("beams", [])
                floor = act.get("floor", 1)
                lines.append(f"// ===== 楼层 {floor}: 创建 {len(beams)} 根梁 =====")
                # 进入梁绘制命令（仅一次）
                lines.append('JrnCmd.ProcessCommand("CmdCreateStraightStructureBeam", "");')
                for beam in beams:
                    lines.extend(self._cmd_create_beam(beam))
                    # ESC 一次：完成当前梁，准备绘制下一根
                    lines.append('JrnCmd.KeyUp(27/*Esc*/);')
                # ESC 两次退出梁绘制命令
                lines.append('JrnCmd.KeyUp(27/*Esc*/);')
                lines.append("")

            elif act_type == "create_columns":
                columns = act.get("columns", [])
                floor = act.get("floor", 1)
                lines.append(f"// ===== 楼层 {floor}: 创建 {len(columns)} 根柱 =====")
                for col in columns:
                    lines.extend(self._cmd_create_column(col))
                lines.append("")

            elif act_type == "switch_3d_view":
                lines.extend(self._cmd_switch_3d_view())
                lines.append("")

            elif act_type == "zoom_fit":
                lines.extend(self._cmd_zoom_fit())
                lines.append("")

        script_content = "\n".join(lines)
        output = {"script_content": script_content, "script_name": "新文件1.js"}
        for key in ("building_type", "total_floors", "height_per_floor", "floor_plans", "actions", "total_steps"):
            if key in step_input:
                output[key] = step_input[key]
        return output


# -------------------- 步骤4: 生成 bat --------------------

class GenerateBatStep(ModelingStep):
    """步骤4: 生成 .bat 启动脚本"""

    name = "生成运行脚本"
    description = "生成 .bat 启动脚本"

    # 默认 GBMP 程序路径（可通过配置覆盖）
    _GBMP_EXE_DIR = r"I:\001程序测试\bin"

    async def run(self, context: AgentContext, step_input: Dict[str, Any]) -> Dict[str, Any]:
        script_name = step_input.get("script_name", "新文件1.js")

        # 查找最新的 GBMP 目录
        exe_dir = self._find_gbmp_dir()
        if not exe_dir:
            raise RuntimeError(f"未找到 GBMP 程序目录: {self._GBMP_EXE_DIR}")

        bat_content = f'''@echo off
cd /d "{exe_dir}"
start "" AppGbmp.exe "{script_name}"
'''

        # 输出目录
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "output_modeling")
        os.makedirs(output_dir, exist_ok=True)

        bat_path = os.path.join(output_dir, "run_model.bat")
        js_path = os.path.join(output_dir, script_name)

        # 写入文件
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)
        with open(js_path, "w", encoding="utf-8") as f:
            f.write(step_input.get("script_content", ""))

        return {
            "bat_path": bat_path,
            "js_path": js_path,
            "exe_dir": exe_dir,
            # 透传上游数据
            "building_type": step_input.get("building_type", ""),
            "total_floors": step_input.get("total_floors", 0),
            "height_per_floor": step_input.get("height_per_floor", 0),
            "floor_plans": step_input.get("floor_plans", []),
            "total_steps": step_input.get("total_steps", 0),
        }

    def _find_gbmp_dir(self) -> str:
        """查找最新的 GBMP 程序目录"""
        parent = self._GBMP_EXE_DIR
        if not os.path.exists(parent):
            return ""
        dirs = [d for d in os.listdir(parent) if d.startswith("GBMP_")]
        if not dirs:
            return ""
        dirs.sort(reverse=True)
        return os.path.join(parent, dirs[0])


# -------------------- 步骤5: 运行建模 --------------------

class RunBatStep(ModelingStep):
    """步骤5: 执行 .bat 文件启动建模"""

    name = "运行建模"
    description = "执行 .bat 文件启动 GBMP 建模程序"

    async def run(self, context: AgentContext, step_input: Dict[str, Any]) -> Dict[str, Any]:
        import subprocess

        bat_path = step_input.get("bat_path", "")
        if not bat_path or not os.path.exists(bat_path):
            raise RuntimeError(f"bat 文件不存在: {bat_path}")

        logger.info(f"[RunBat] 开始执行: {bat_path}")
        # 使用 subprocess 启动进程（非阻塞），不等待程序退出
        process = subprocess.Popen(
            ["cmd", "/c", "start", "", bat_path],
            cwd=os.path.dirname(bat_path),
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        return {
            "run_status": "launched",
            "process_pid": process.pid,
            "bat_path": bat_path,
            # 透传上游数据
            "building_type": step_input.get("building_type", ""),
            "total_floors": step_input.get("total_floors", 0),
            "height_per_floor": step_input.get("height_per_floor", 0),
            "floor_plans": step_input.get("floor_plans", []),
            "total_steps": step_input.get("total_steps", 0),
            "js_path": step_input.get("js_path", ""),
            "exe_dir": step_input.get("exe_dir", ""),
        }


# ==================== 智能建模 Agent ====================

class ModelingAgent(BaseAgent):
    """
    智能建模 Agent

    流程：结构化输入 → 执行计划(按楼层) → 生成GBMP脚本 → 生成bat → 运行建模
    步骤通过 pipeline 模式串联，支持扩展。
    """

    role = AgentRole.MODELING
    name = "智能建模"
    description = "建筑结构建模，自动生成 GBMP 建模脚本"

    def __init__(self):
        super().__init__()
        # 默认步骤流水线（可扩展/替换）
        self._pipeline: List[ModelingStep] = [
            StructurizeInputStep(),
            BuildExecutionPlanStep(),
            GenerateScriptStep(),
            GenerateBatStep(),
            RunBatStep(),
        ]

    def set_pipeline(self, steps: List[ModelingStep]) -> None:
        """替换默认流水线（用于扩展）"""
        self._pipeline = steps

    async def execute(self, context: AgentContext) -> AgentResult:
        start = time.time()
        logger.info(f"[{self.name}] 开始建模: {context.user_message[:100]}")

        step_input: Dict[str, Any] = {}

        try:
            for i, modeling_step in enumerate(self._pipeline, 1):
                step = StepStatus(
                    step_name=modeling_step.name,
                    status="running",
                    detail=modeling_step.description,
                )
                context.steps.append(step)
                logger.info(f"[{self.name}] 步骤 {i}/{len(self._pipeline)}: {modeling_step.name}")

                step_input = await modeling_step.run(context, step_input)

                step.status = "completed"
                step.detail = f"{modeling_step.description} - 完成"

            # 从 floor_plans 汇总统计数据
            floor_plans = step_input.get("floor_plans", [])
            total_beams = sum(len(fp.get("beams", [])) for fp in floor_plans)
            total_cols = sum(len(fp.get("columns", [])) for fp in floor_plans)
            total_slabs = sum(len(fp.get("slabs", [])) for fp in floor_plans)
            total_walls = sum(len(fp.get("walls", [])) for fp in floor_plans)

            bat_path = step_input.get("bat_path", "")
            js_path = step_input.get("js_path", "")
            total_steps = step_input.get("total_steps", 0)
            building_info = step_input.get("building_type", "")
            total_floors = step_input.get("total_floors", 0)

            answer = (
                f"**建模方案已生成并启动**\n\n"
                f"- 建筑类型：{building_info}\n"
                f"- 总层数：{total_floors}\n"
                f"- 构件统计：{total_beams} 根梁、{total_cols} 根柱、{total_slabs} 块板、{total_walls} 面墙\n"
                f"- 建模步骤：{total_steps} 步\n"
                f"- 脚本文件：`{js_path}`\n"
                f"- 启动脚本：`{bat_path}`\n"
            )

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
                processing_time=time.time() - start,
                meta={
                    "building_type": building_info,
                    "total_floors": total_floors,
                    "beams_count": total_beams,
                    "columns_count": total_cols,
                    "slabs_count": total_slabs,
                    "walls_count": total_walls,
                    "bat_path": bat_path,
                    "js_path": js_path,
                    "structured_data": step_input,
                },
                steps=context.steps,
            )

        except Exception as e:
            logger.error(f"[{self.name}] 建模失败: {e}", exc_info=True)
            # 标记当前步骤失败
            for s in reversed(context.steps):
                if s.status == "running":
                    s.status = "failed"
                    s.detail = str(e)
                    break

            context.agent_chain.append({
                "role": self.role.value,
                "name": self.name,
                "status": "failed",
            })

            return AgentResult(
                success=False,
                answer=f"建模失败: {str(e)}",
                agent_role=self.role.value,
                agent_name=self.name,
                processing_time=time.time() - start,
                error=str(e),
                steps=context.steps,
            )

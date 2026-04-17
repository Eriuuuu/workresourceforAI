<template>
<div class="tcgen-page">
    <div class="tcgen-container">
    <!-- 步骤进度条 -->
    <div class="progress-bar-section">
        <div class="progress-steps">
        <div class="progress-step" :class="{ done: activeStep > 0, current: activeStep === 0 }">
            <div class="step-dot">
            <el-icon v-if="activeStep > 0"><CircleCheckFilled /></el-icon>
            <span v-else>1</span>
            </div>
            <span class="step-text">上传文档</span>
        </div>
        <div class="progress-line" :class="{ active: activeStep > 0 }"></div>
        <div class="progress-step" :class="{ done: activeStep > 1, current: activeStep === 1 }">
            <div class="step-dot">
            <el-icon v-if="activeStep > 1"><CircleCheckFilled /></el-icon>
            <span v-else>2</span>
            </div>
            <span class="step-text">解析图谱</span>
        </div>
        <div class="progress-line" :class="{ active: activeStep > 1 }"></div>
        <div class="progress-step" :class="{ done: activeStep > 2, current: activeStep === 2 }">
            <div class="step-dot">
            <el-icon v-if="activeStep >= 3"><CircleCheckFilled /></el-icon>
            <span v-else>3</span>
            </div>
            <span class="step-text">生成用例</span>
        </div>
        </div>
    </div>

    <!-- 上传与操作区 -->
    <div class="card">
        <div class="card-title">
        <el-icon :size="18"><Upload /></el-icon>
        <span>文档上传</span>
        </div>
        <el-upload
        drag
        action=""
        :auto-upload="false"
        :on-change="handleFileChange"
        :on-remove="handleFileRemove"
        :limit="1"
        accept=".docx"
        class="upload-area"
        >
        <div class="upload-placeholder">
            <el-icon :size="36" color="#6366f1"><UploadFilled /></el-icon>
            <p>拖放 DOCX 文件到此处，或 <em>点击上传</em></p>
            <span class="upload-hint">支持 .docx 格式</span>
        </div>
        </el-upload>

        <div v-if="selectedFile" class="selected-file-bar">
        <el-icon color="#6366f1"><Document /></el-icon>
        <span class="file-name">{{ selectedFile.name }}</span>
        <span class="file-size">{{ formatFileSize(selectedFile.size) }}</span>
        <el-button type="danger" size="small" circle @click="handleFileRemove">
            <el-icon><Close /></el-icon>
        </el-button>
        </div>

        <div class="action-row">
        <el-button
            type="primary"
            :loading="parsingLoading"
            :disabled="!selectedFile"
            @click="parseDocument"
        >
            <el-icon><Connection /></el-icon>
            <span>解析文档</span>
        </el-button>
        <el-button
            type="primary"
            :loading="generatingLoading"
            :disabled="!hasGraphData"
            @click="generateTestCases"
        >
            <el-icon><MagicStick /></el-icon>
            <span>生成用例</span>
        </el-button>
        </div>
    </div>

    <!-- 状态信息 -->
    <div class="status-row" v-if="parseStatus || generateStatus">
        <div v-if="parseStatus" class="status-chip" :class="parseStatusType">
        <el-icon v-if="parseStatusType === 'success'"><CircleCheckFilled /></el-icon>
        <el-icon v-else-if="parseStatusType === 'error'"><CircleCloseFilled /></el-icon>
        <el-icon v-else><Loading /></el-icon>
        <span>{{ parseStatus }}</span>
        </div>
        <div v-if="generateStatus" class="status-chip" :class="generateStatusType">
        <el-icon v-if="generateStatusType === 'success'"><CircleCheckFilled /></el-icon>
        <el-icon v-else-if="generateStatusType === 'error'"><CircleCloseFilled /></el-icon>
        <el-icon v-else><Loading /></el-icon>
        <span>{{ generateStatus }}</span>
        </div>
    </div>

    <!-- 知识图谱 -->
    <div class="card">
        <div class="card-title-row">
        <div class="card-title">
            <el-icon :size="18"><DataLine /></el-icon>
            <span>知识图谱</span>
        </div>
        <div class="graph-stats" v-if="graphData.nodes.length > 0">
            <el-tag size="small" type="info">{{ graphData.nodes.length }} 节点</el-tag>
            <el-tag size="small" type="info">{{ graphData.edges.length }} 关系</el-tag>
        </div>
        </div>
        <div class="card-body-inner">
        <div v-if="graphData.nodes.length > 0" class="graph-container" ref="graphContainer" style="width:100%;height:420px;"></div>
        <div v-else class="empty-state">
            <el-icon :size="48" color="#cbd5e1"><DataLine /></el-icon>
            <p>上传并解析文档后，将在此处显示知识图谱</p>
        </div>
        </div>
    </div>

    <!-- 测试用例 -->
    <div class="card">
        <div class="card-title-row">
        <div class="card-title">
            <el-icon :size="18"><Grid /></el-icon>
            <span>测试用例</span>
            <span v-if="testCases.length > 0" class="case-count">{{ testCases.length }} 条</span>
        </div>
        <el-button
            type="success"
            size="small"
            :disabled="!testCases.length"
            @click="exportToExcel"
        >
            <el-icon><Download /></el-icon>
            <span>导出 Excel</span>
        </el-button>
        </div>
        <div class="card-body-inner">
        <el-table
            v-if="testCases.length > 0"
            :data="testCases"
            style="width:100%"
            max-height="520"
            stripe
            :row-class-name="testCaseRowClassName"
        >
            <el-table-column prop="id" label="ID" width="65" />
            <el-table-column prop="name" label="用例名称" min-width="160" show-overflow-tooltip />
            <el-table-column prop="description" label="描述" min-width="220" show-overflow-tooltip />
            <el-table-column label="优先级" width="90">
            <template #default="scope">
                <el-tag :type="scope.row.priority === '高' ? 'danger' : scope.row.priority === '中' ? 'warning' : 'info'" size="small">
                {{ scope.row.priority }}
                </el-tag>
            </template>
            </el-table-column>
            <el-table-column label="操作" width="70" fixed="right">
            <template #default="scope">
                <el-button type="primary" size="small" circle @click="viewTestCaseDetail(scope.row)" title="查看详情">
                <el-icon><View /></el-icon>
                </el-button>
            </template>
            </el-table-column>
        </el-table>
        <div v-else class="empty-state">
            <el-icon :size="48" color="#cbd5e1"><Grid /></el-icon>
            <p>生成测试用例后，将在此处显示结果</p>
        </div>
        </div>
    </div>
    </div>

    <!-- 用例详情对话框 -->
    <el-dialog v-model="detailDialogVisible" title="测试用例详情" width="600px">
    <div v-if="selectedTestCase" class="detail-content">
        <h3 class="detail-name">{{ selectedTestCase.name }}</h3>
        <div class="detail-meta">
        <el-tag :type="selectedTestCase.priority === '高' ? 'danger' : selectedTestCase.priority === '中' ? 'warning' : 'info'" size="small">
            {{ selectedTestCase.priority }}
        </el-tag>
        <span>ID: {{ selectedTestCase.id }}</span>
        </div>

        <div class="detail-section">
        <h4>描述</h4>
        <p>{{ selectedTestCase.description }}</p>
        </div>

        <div class="detail-section">
        <h4>前置条件</h4>
        <p>{{ selectedTestCase.preconditions || '无' }}</p>
        </div>

        <div class="detail-section">
        <h4>预期结果</h4>
        <p>{{ selectedTestCase.expected_result || '无' }}</p>
        </div>

        <div class="detail-section" v-if="selectedTestCase.target_api">
        <h4>目标接口</h4>
        <p>{{ selectedTestCase.target_api }}</p>
        </div>

        <div class="detail-section">
        <h4>测试步骤</h4>
        <div class="steps-list">
            <div v-for="(step, index) in (selectedTestCase.steps || [])" :key="index" class="step-row">
            <span class="step-num">{{ index + 1 }}</span>
            <div class="step-body">
                <span>{{ typeof step === 'string' ? step : (step?.action || '') }}</span>
                <span v-if="typeof step !== 'string' && step?.expected" class="step-expected">
                预期: {{ step.expected }}
                </span>
            </div>
            </div>
        </div>
        </div>

        <div class="detail-meta-row">
        <span>状态: {{ selectedTestCase.status }}</span>
        <span>创建: {{ selectedTestCase.created_at }}</span>
        <span>更新: {{ selectedTestCase.updated_at }}</span>
        </div>
    </div>
    </el-dialog>
</div>
</template>

<script lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from "vue";
import { ElMessage } from "element-plus";
import * as XLSX from "xlsx";
import {
    Document,
    Upload,
    UploadFilled,
    Connection,
    MagicStick,
    Download,
    Close,
    CircleCheckFilled,
    CircleCloseFilled,
    Loading,
    DataLine,
    Grid,
    View,
} from "@element-plus/icons-vue";
import { AIApi, type GraphNode, type GraphEdge, type TaskStatusResponse } from '@/api/testcasegen';

declare global {
    interface Window { __lastParsedContent?: string }
}

export default {
    name: "TestCasesGen",
    components: {
        Document, Upload, UploadFilled, Connection, MagicStick, Download,
        Close, CircleCheckFilled, CircleCloseFilled, Loading, DataLine, Grid, View,
    },
    setup() {
        // ========== 响应式数据 ==========
        const selectedFile = ref<any>(null);
        const parsingLoading = ref(false);
        const generatingLoading = ref(false);
        const parseStatus = ref("");
        const parseStatusType = ref("info");
        const generateStatus = ref("");
        const generateStatusType = ref("info");
        const graphData = reactive<{ nodes: any[]; edges: any[] }>({ nodes: [], edges: [] });
        const testCases = ref<any[]>([]);
        const detailDialogVisible = ref(false);
        const selectedTestCase = ref<any>(null);
        const graphContainer = ref<HTMLElement | null>(null);
        let chartInstance: any = null;

        // ========== 异步任务管理 ==========
        let pollTimer: ReturnType<typeof setTimeout> | null = null;
        let pollingActive = false;
        let componentMounted = false;
        const POLL_INTERVAL = 3000;
        const TASK_STORAGE_KEY = 'tcgen_active_tasks';
        const PARSED_CONTENT_KEY = 'tcgen_parsed_content';
        const activeParseTaskId = ref<string | null>(null);
        const activeGenerateTaskId = ref<string | null>(null);

        const saveActiveTasks = () => {
            const tasks: Record<string, string> = {};
            if (activeParseTaskId.value) tasks.parse_graph = activeParseTaskId.value;
            if (activeGenerateTaskId.value) tasks.generate_cases = activeGenerateTaskId.value;
            sessionStorage.setItem(TASK_STORAGE_KEY, JSON.stringify(tasks));
        };

        const restoreActiveTasks = () => {
            try {
                const stored = sessionStorage.getItem(TASK_STORAGE_KEY);
                if (stored) {
                    const tasks = JSON.parse(stored);
                    if (tasks.parse_graph) activeParseTaskId.value = tasks.parse_graph;
                    if (tasks.generate_cases) activeGenerateTaskId.value = tasks.generate_cases;
                }
            } catch { /* ignore */ }
        };

        const cleanupTask = (taskType: 'parse_graph' | 'generate_cases', reason: string) => {
            if (taskType === 'parse_graph') {
                activeParseTaskId.value = null;
                parsingLoading.value = false;
                parseStatus.value = reason;
                parseStatusType.value = "error";
            } else {
                activeGenerateTaskId.value = null;
                generatingLoading.value = false;
                generateStatus.value = reason;
                generateStatusType.value = "error";
            }
            saveActiveTasks();
            if (!activeParseTaskId.value && !activeGenerateTaskId.value) stopPolling();
        };

        const startPolling = () => {
            if (pollingActive) return;
            pollingActive = true;
            scheduleNextPoll();
        };

        const scheduleNextPoll = () => {
            if (!pollingActive) return;
            if (pollTimer) clearTimeout(pollTimer);
            pollTimer = setTimeout(pollAllTasks, POLL_INTERVAL);
        };

        const stopPolling = () => {
            pollingActive = false;
            if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
        };

        const pollAllTasks = async () => {
            if (!componentMounted || !pollingActive) return;

            const taskIds: Array<{ id: string; type: 'parse_graph' | 'generate_cases' }> = [];
            if (activeParseTaskId.value) taskIds.push({ id: activeParseTaskId.value, type: 'parse_graph' });
            if (activeGenerateTaskId.value) taskIds.push({ id: activeGenerateTaskId.value, type: 'generate_cases' });

            if (taskIds.length === 0) { stopPolling(); return; }

            for (const task of taskIds) {
                if (!componentMounted || !pollingActive) return;
                try {
                    const status: TaskStatusResponse = await AIApi.getTaskStatus(task.id);
                    if (!componentMounted || !pollingActive) return;
                    await handleTaskResult(task.type, status);
                    if (!componentMounted || !pollingActive) return;
                } catch (error: any) {
                    if (!componentMounted) return;
                    if (error?.response?.status === 404) {
                        const label = task.type === 'parse_graph' ? '文档解析' : '用例生成';
                        cleanupTask(task.type, `${label}任务已失效，请重新操作`);
                        ElMessage.warning(`${label}任务已失效，请重新提交`);
                        return;
                    }
                }
            }

            if (componentMounted && pollingActive && (activeParseTaskId.value || activeGenerateTaskId.value)) {
                scheduleNextPoll();
            }
        };

        const handleTaskResult = async (taskType: 'parse_graph' | 'generate_cases', status: TaskStatusResponse) => {
            if (!componentMounted) return;

            if (status.status === 'processing' || status.status === 'pending') {
                if (taskType === 'parse_graph') {
                    parseStatus.value = status.status === 'pending' ? "任务排队中..." : "正在构建知识图谱...";
                    parseStatusType.value = "info";
                    parsingLoading.value = true;
                } else {
                    generateStatus.value = status.status === 'pending' ? "任务排队中..." : "正在生成测试用例...";
                    generateStatusType.value = "info";
                    generatingLoading.value = true;
                }
            } else if (status.status === 'completed' && status.result) {
                if (taskType === 'parse_graph') {
                    activeParseTaskId.value = null;
                    parsingLoading.value = false;
                    const nodes = status.result?.graph_nodes;
                    const edges = status.result?.graph_edges;
                    if (nodes && nodes.length > 0) {
                        graphData.nodes = nodes.map((n: GraphNode, idx: number) => ({
                            id: n.id || `n${idx}`, name: n.name, label: n.label, type: n.type, properties: n.properties || {},
                        }));
                    }
                    if (edges && edges.length > 0) {
                        graphData.edges = edges.map((e: GraphEdge, idx: number) => ({
                            source: e.source || `s${idx}`, target: e.target || `t${idx}`, label: e.label, properties: e.properties || {},
                        }));
                    }
                    if (graphData.nodes.length > 0) {
                        await nextTick();
                        if (!componentMounted) return;
                        await initKnowledgeGraph();
                    }
                    const elapsed = status.result.processing_time?.toFixed(1) || '0';
                    parseStatus.value = `解析完成 (${elapsed}s) — ${status.result.message || ''}`;
                    parseStatusType.value = "success";
                    ElMessage.success("知识图谱构建成功");
                } else {
                    activeGenerateTaskId.value = null;
                    generatingLoading.value = false;
                    const cases = status.result?.test_cases;
                    if (cases && cases.length > 0) {
                        testCases.value = cases;
                        const elapsed = status.result?.processing_time?.toFixed(1) || '0';
                        generateStatus.value = `生成完成 (${elapsed}s) — 共 ${cases.length} 条用例`;
                        generateStatusType.value = "success";
                        ElMessage.success(`成功生成 ${cases.length} 条测试用例`);
                    } else {
                        generateStatus.value = "未生成任何测试用例，请检查文档内容";
                        generateStatusType.value = "error";
                        ElMessage.warning("未生成任何测试用例");
                    }
                }
                saveActiveTasks();
                if (!activeParseTaskId.value && !activeGenerateTaskId.value) stopPolling();
            } else if (status.status === 'failed') {
                if (taskType === 'parse_graph') {
                    activeParseTaskId.value = null;
                    parsingLoading.value = false;
                    parseStatus.value = `解析失败: ${status.error || '未知错误'}`;
                    parseStatusType.value = "error";
                    ElMessage.error(status.error || "文档解析失败");
                } else {
                    activeGenerateTaskId.value = null;
                    generatingLoading.value = false;
                    generateStatus.value = `生成失败: ${status.error || '未知错误'}`;
                    generateStatusType.value = "error";
                    ElMessage.error(status.error || "用例生成失败");
                }
                saveActiveTasks();
                if (!activeParseTaskId.value && !activeGenerateTaskId.value) stopPolling();
            }
        };

        // ========== 计算属性 ==========
        const activeStep = computed(() => {
            if (testCases.value.length > 0) return 3;
            if (graphData.nodes.length > 0) return 2;
            if (selectedFile.value) return 1;
            return 0;
        });

        const hasGraphData = computed(() => graphData.nodes.length > 0);

        // ========== 方法 ==========
        const handleFileChange = (file: any) => {
            selectedFile.value = file.raw;
            ElMessage.success(`已选择: ${file.name}`);
        };

        const handleFileRemove = () => {
            selectedFile.value = null;
        };

        const formatFileSize = (bytes: number) => {
            if (bytes === 0) return "0 B";
            const k = 1024;
            const sizes = ["B", "KB", "MB", "GB"];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
        };

        const parseDocument = async () => {
            if (!selectedFile.value) { ElMessage.warning("请先选择文档"); return; }

            parsingLoading.value = true;
            parseStatus.value = "正在上传并解析文档...";
            parseStatusType.value = "info";
            graphData.nodes = [];
            graphData.edges = [];
            testCases.value = [];
            generateStatus.value = "";
            generateStatusType.value = "info";
            generatingLoading.value = false;
            activeGenerateTaskId.value = null;
            saveActiveTasks();

            try {
                const formData = new FormData();
                formData.append('file', selectedFile.value);
                formData.append('filename', selectedFile.value.name);
                formData.append('uploadTime', new Date().toISOString());

                const docResult = await AIApi.loaddocxfile(formData);
                if (!componentMounted) return;
                if (!docResult.success) throw new Error(docResult.error || "文档解析失败");

                const rawContent = docResult.raw_content;
                if (!rawContent || rawContent.trim().length < 10) throw new Error("文档内容为空或过短");

                sessionStorage.setItem(PARSED_CONTENT_KEY, rawContent);
                window.__lastParsedContent = rawContent;

                const taskResult = await AIApi.submitTask('parse_graph', rawContent);
                if (!componentMounted) return;
                if (!taskResult.task_id) throw new Error("提交任务失败");

                activeParseTaskId.value = taskResult.task_id;
                saveActiveTasks();
                startPolling();
                ElMessage.info("解析任务已提交，后台处理中");
            } catch (error: any) {
                if (!componentMounted) return;
                const msg = error?.response?.data?.detail || error?.message || "文档解析失败";
                parseStatus.value = `解析失败: ${msg}`;
                parseStatusType.value = "error";
                ElMessage.error(msg);
                parsingLoading.value = false;
            }
        };

        const generateTestCases = async () => {
            if (!hasGraphData.value && !window.__lastParsedContent) {
                ElMessage.warning("请先解析文档并生成知识图谱");
                return;
            }

            generatingLoading.value = true;
            generateStatus.value = "正在提交用例生成任务...";
            generateStatusType.value = "info";

            try {
                const requirementText = sessionStorage.getItem(PARSED_CONTENT_KEY) || window.__lastParsedContent || "";
                const taskResult = await AIApi.submitTask('generate_cases', requirementText);
                if (!componentMounted) return;
                if (!taskResult.task_id) throw new Error("提交任务失败");

                activeGenerateTaskId.value = taskResult.task_id;
                saveActiveTasks();
                startPolling();
                ElMessage.info("用例生成任务已提交，后台处理中");
            } catch (error: any) {
                if (!componentMounted) return;
                const msg = error?.response?.data?.detail || error?.message || "用例生成失败";
                generateStatus.value = `生成失败: ${msg}`;
                generateStatusType.value = "error";
                ElMessage.error(msg);
                generatingLoading.value = false;
            }
        };

        // ========== 知识图谱可视化 ==========
        const TYPE_DISPLAY_MAP: Record<string, string> = {
            FunctionalRequirement: '功能需求', NonFunctionalRequirement: '非功能需求',
            BusinessRule: '业务规则', Constraint: '约束条件', UserStory: '用户故事',
            UseCase: '用例场景', BusinessGoal: '业务目标', Actor: '角色',
            SystemComponent: '系统组件', Document: '文档', Requirement: '需求',
            Entity: '实体', TestPoint: '测试点',
        };
        const TYPE_COLOR_PALETTE = ['#6366f1','#10b981','#f59e0b','#ef4444','#8b5cf6','#ec4899','#06b6d4','#84cc16','#f97316','#64748b','#14b8a6','#a855f7'];
        const typeColorMap: Record<string, string> = {};
        let colorIdx = 0;
        const getNodeColor = (type: string): string => {
            if (!typeColorMap[type]) { typeColorMap[type] = TYPE_COLOR_PALETTE[colorIdx++ % TYPE_COLOR_PALETTE.length]; }
            return typeColorMap[type] as string;
        };
        const getDisplayName = (type: string, label: string) => {
            if (TYPE_DISPLAY_MAP[type]) return TYPE_DISPLAY_MAP[type];
            if (TYPE_DISPLAY_MAP[label]) return TYPE_DISPLAY_MAP[label];
            return label || type || '未知';
        };

        const handleResize = () => { if (chartInstance) chartInstance.resize(); };

        const initKnowledgeGraph = async () => {
            if (!graphContainer.value || graphData.nodes.length === 0) return;
            try {
                const echarts = await import("echarts");
                if (chartInstance) { chartInstance.dispose(); chartInstance = null; }

                const container = graphContainer.value;
                if (container.clientWidth === 0) { container.style.width = '100%'; container.style.height = '420px'; }
                chartInstance = echarts.init(container);

                const typeSet = new Set<string>();
                graphData.nodes.forEach(n => typeSet.add(n.type || n.label || 'Unknown'));
                const categories = Array.from(typeSet).map(t => ({ name: getDisplayName(t, ''), itemStyle: { color: getNodeColor(t) } }));
                const typeToIdx: Record<string, number> = {};
                Array.from(typeSet).forEach((t, i) => { typeToIdx[t] = i; });

                const nodes = graphData.nodes.map(n => {
                    const key = n.type || n.label || 'Unknown';
                    return {
                        id: n.id, name: n.name, category: typeToIdx[key] ?? 0, symbolSize: 35,
                        itemStyle: { color: getNodeColor(key) },
                        label: { show: true, position: 'right', fontSize: 11, formatter: n.name.length > 12 ? n.name.substring(0, 12) + '...' : n.name },
                        _raw: n,
                    };
                });

                const edges = graphData.edges.map(e => ({
                    source: e.source, target: e.target,
                    label: { show: graphData.edges.length <= 60, formatter: e.label || '', fontSize: 9 },
                    lineStyle: { width: 1.2, curveness: 0.2, color: '#94a3b8' },
                }));

                chartInstance.setOption({
                    tooltip: {
                        trigger: 'item',
                        formatter: (params: any) => {
                            if (params.dataType === 'node') {
                                const r = params.data._raw;
                                return `<b>${r.name}</b><br>类型: ${getDisplayName(r.type, r.label)}${r.description ? '<br>' + r.description : ''}`;
                            }
                            return `关系: ${params.data.label?.formatter || params.data.label || '关联'}`;
                        },
                    },
                    legend: { data: categories.map(c => c.name), textStyle: { color: '#64748b' }, top: 'bottom', type: 'scroll' },
                    animationDuration: 1200,
                    animationEasingUpdate: 'quinticInOut',
                    series: [{
                        type: 'graph', layout: 'force',
                        force: { repulsion: 300, edgeLength: [80, 160], gravity: 0.08 },
                        draggable: true, data: nodes, links: edges, categories,
                        roam: true, lineStyle: { color: 'source', curveness: 0.2 },
                        emphasis: { focus: 'adjacency', lineStyle: { width: 3 } },
                    }],
                });
                window.addEventListener('resize', handleResize);
            } catch (error) {
                console.error('初始化图表失败:', error);
                ElMessage.warning('知识图谱渲染失败');
            }
        };

        // ========== 用例操作 ==========
        const viewTestCaseDetail = (testCase: any) => {
            selectedTestCase.value = testCase;
            detailDialogVisible.value = true;
        };

        const exportToExcel = async () => {
            if (testCases.value.length === 0) { ElMessage.warning("没有可导出的测试用例"); return; }
            try {
                const worksheetData = testCases.value.map((tc) => ({
                    用例ID: tc.id, 用例名称: tc.name, 描述: tc.description,
                    所属模块: tc.module || '', 优先级: tc.priority, 状态: tc.status,
                    前置条件: tc.preconditions || '无',
                    测试步骤: (tc.steps || [])
                        .map((step: any, i: number) => {
                            if (typeof step === 'string') return `${i + 1}. ${step}`;
                            if (!step) return '';
                            return `${i + 1}. ${step.action || ''}${step.expected ? ' (预期: ' + step.expected + ')' : ''}`;
                        })
                        .join('\n'),
                    创建时间: tc.created_at, 最后更新: tc.updated_at,
                }));

                const worksheet = XLSX.utils.json_to_sheet(worksheetData);
                worksheet['!cols'] = [
                    { wch: 10 }, { wch: 28 }, { wch: 45 }, { wch: 15 },
                    { wch: 8 }, { wch: 10 }, { wch: 30 }, { wch: 60 },
                    { wch: 18 }, { wch: 18 },
                ];
                const workbook = XLSX.utils.book_new();
                XLSX.utils.book_append_sheet(workbook, worksheet, '测试用例');
                const wbOut = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' });
                const blob = new Blob([wbOut], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
                const defaultName = `测试用例_${new Date().toLocaleDateString('zh-CN').replace(/\//g, '')}.xlsx`;

                if ('showSaveFilePicker' in window) {
                    try {
                        const handle = await (window as any).showSaveFilePicker({
                            suggestedName: defaultName,
                            types: [{ description: 'Excel 文件', accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] } }],
                        });
                        const writable = await handle.createWritable();
                        await writable.write(blob);
                        await writable.close();
                        ElMessage.success(`已导出 ${testCases.value.length} 条测试用例`);
                        return;
                    } catch (e: any) { if (e.name === 'AbortError') return; }
                }

                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = defaultName;
                a.click();
                URL.revokeObjectURL(url);
                ElMessage.success(`已导出 ${testCases.value.length} 条测试用例`);
            } catch (error: any) {
                ElMessage.error(`导出失败: ${error.message}`);
            }
        };

        const testCaseRowClassName = ({ row }: { row: any }) => `case-row-${row.priority}`;

        // ========== 生命周期 ==========
        onMounted(async () => {
            componentMounted = true;
            sessionStorage.removeItem('tcgen_graph_data');
            sessionStorage.removeItem('tcgen_testcases');

            const storedContent = sessionStorage.getItem(PARSED_CONTENT_KEY);
            if (storedContent) window.__lastParsedContent = storedContent;

            restoreActiveTasks();

            if (activeParseTaskId.value || activeGenerateTaskId.value) {
                if (activeParseTaskId.value) {
                    parsingLoading.value = true;
                    parseStatus.value = "检测到未完成的解析任务，正在恢复...";
                    parseStatusType.value = "info";
                }
                if (activeGenerateTaskId.value) {
                    generatingLoading.value = true;
                    generateStatus.value = "检测到未完成的生成任务，正在恢复...";
                    generateStatusType.value = "info";
                }
                startPolling();
                await pollAllTasks();
            }
        });

        onUnmounted(() => {
            componentMounted = false;
            stopPolling();
            if (chartInstance) { chartInstance.dispose(); chartInstance = null; }
            window.removeEventListener("resize", handleResize);
        });

        return {
            selectedFile, parsingLoading, generatingLoading,
            parseStatus, parseStatusType, generateStatus, generateStatusType,
            graphData, testCases, detailDialogVisible, selectedTestCase,
            graphContainer, activeStep, hasGraphData,
            handleFileChange, handleFileRemove, formatFileSize,
            parseDocument, generateTestCases, viewTestCaseDetail, exportToExcel,
            testCaseRowClassName,
        };
    },
};
</script>

<style scoped>
.tcgen-page {
    max-width: 1100px;
    margin: 0 auto;
    padding: 24px 0 48px;
}

/* 进度步骤 */
.progress-bar-section {
    margin-bottom: 24px;
    padding: 20px 28px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 1px 4px rgba(0,0,0,.06);
}

.progress-steps {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0;
}

.progress-step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
}

.step-dot {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 600;
    background: #f1f5f9;
    color: #94a3b8;
    border: 2px solid #e2e8f0;
    transition: all .3s;
}

.progress-step.current .step-dot {
    background: #fff;
    border-color: #6366f1;
    color: #6366f1;
}

.progress-step.done .step-dot {
    background: #10b981;
    border-color: #10b981;
    color: #fff;
}

.step-text {
    font-size: 13px;
    color: #94a3b8;
    font-weight: 500;
}

.progress-step.current .step-text { color: #6366f1; }
.progress-step.done .step-text { color: #10b981; }

.progress-line {
    flex: 1;
    height: 2px;
    background: #e2e8f0;
    margin: 0 12px;
    margin-bottom: 26px;
    transition: background .3s;
}

.progress-line.active { background: #10b981; }

/* 卡片 */
.card {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 1px 4px rgba(0,0,0,.06);
    margin-bottom: 20px;
    overflow: hidden;
}

.card-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 16px;
    font-weight: 600;
    color: #1e293b;
    padding: 18px 24px 0;
}

.card-title-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 18px 24px 0;
}

.card-body-inner {
    padding: 16px 24px 24px;
}

.case-count {
    font-size: 13px;
    font-weight: 400;
    color: #64748b;
    margin-left: 4px;
}

.graph-stats {
    display: flex;
    gap: 6px;
}

/* 上传 */
.upload-area { width: 100%; }

:deep(.el-upload-dragger) {
    width: 100%;
    padding: 36px 20px;
    border: 2px dashed #e2e8f0;
    border-radius: 10px;
    transition: border-color .2s;
}

:deep(.el-upload-dragger:hover) {
    border-color: #6366f1;
}

.upload-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    color: #64748b;
}

.upload-placeholder p {
    margin: 0;
    font-size: 14px;
}

.upload-placeholder em {
    color: #6366f1;
    font-style: normal;
}

.upload-hint {
    font-size: 12px;
    color: #94a3b8;
}

.selected-file-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 12px 0 0;
    padding: 10px 16px;
    background: #f8fafc;
    border-radius: 8px;
    font-size: 14px;
}

.selected-file-bar .file-name {
    font-weight: 500;
    color: #1e293b;
}

.selected-file-bar .file-size {
    color: #94a3b8;
    font-size: 13px;
}

.action-row {
    display: flex;
    gap: 12px;
    padding: 16px 24px 20px;
}

/* 状态行 */
.status-row {
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
    flex-wrap: wrap;
}

.status-chip {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    flex: 1;
    min-width: 240px;
}

.status-chip.success { background: #ecfdf5; color: #065f46; }
.status-chip.error { background: #fef2f2; color: #991b1b; }
.status-chip.info { background: #eff6ff; color: #1e40af; }

.status-chip.warning { background: #fffbeb; color: #92400e; }

/* 空状态 */
.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 48px 20px;
    color: #94a3b8;
    gap: 12px;
}

.empty-state p {
    margin: 0;
    font-size: 14px;
}

/* 用例详情 */
.detail-content {
    padding: 0 4px;
}

.detail-name {
    margin: 0 0 8px;
    font-size: 18px;
    color: #1e293b;
}

.detail-meta {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
    font-size: 13px;
    color: #64748b;
}

.detail-section {
    margin-bottom: 16px;
}

.detail-section h4 {
    margin: 0 0 6px;
    font-size: 14px;
    font-weight: 600;
    color: #475569;
}

.detail-section p {
    margin: 0;
    font-size: 14px;
    color: #334155;
    line-height: 1.6;
}

.steps-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.step-row {
    display: flex;
    gap: 10px;
    align-items: flex-start;
}

.step-num {
    flex-shrink: 0;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: #f1f5f9;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 600;
    color: #64748b;
}

.step-body {
    flex: 1;
    font-size: 14px;
    color: #334155;
    line-height: 1.6;
}

.step-expected {
    display: block;
    font-size: 13px;
    color: #64748b;
    margin-top: 2px;
}

.detail-meta-row {
    display: flex;
    gap: 20px;
    padding-top: 16px;
    border-top: 1px solid #f1f5f9;
    font-size: 13px;
    color: #94a3b8;
}
</style>

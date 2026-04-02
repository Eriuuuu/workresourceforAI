<template>
<div class="document-processor">
    <!-- 顶部导航栏 -->
    <div class="top-nav">
    <div class="nav-content">
        <div class="logo-section">
        <div class="logo-icon">
            <el-icon :size="24" color="white"><Document /></el-icon>
        </div>
        <div class="logo-text">
            <h1>IntelliCases</h1>
            <p>智能用例生成系统</p>
        </div>
        </div>
        <div class="user-info">
        <el-avatar
            :size="36"
            src="https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png"
        />
        <span class="user-name">Admin</span>
        </div>
    </div>
    </div>

    <div class="main-content">
    <!-- 步骤指示器 -->
    <div class="process-steps-container">
        <div class="process-steps">
        <div class="steps-header">
            <h3>处理流程</h3>
            <div class="step-progress">
            <span>当前进度：</span>
            <span class="progress-text">{{ getStepText(activeStep) }}</span>
            </div>
        </div>

        <div class="steps-wrapper">
            <div class="steps-track">
            <div
                class="progress-bar"
                :style="{ width: `${(activeStep / 3) * 100}%` }"
            ></div>

            <div
                class="step-item"
                :class="{ active: activeStep >= 1, completed: activeStep > 1 }"
            >
                <div class="step-circle">
                <div class="step-number">1</div>
                <div class="step-check" v-if="activeStep > 1">
                    <el-icon><CircleCheckFilled /></el-icon>
                </div>
                </div>
                <div class="step-label">上传文档</div>
                <div class="step-desc">选择DOCX文件</div>
            </div>

            <div
                class="step-item"
                :class="{ active: activeStep >= 2, completed: activeStep > 2 }"
            >
                <div class="step-circle">
                <div class="step-number">2</div>
                <div class="step-check" v-if="activeStep > 2">
                    <el-icon><CircleCheckFilled /></el-icon>
                </div>
                </div>
                <div class="step-label">知识图谱</div>
                <div class="step-desc">解析文档结构</div>
            </div>

            <div
                class="step-item"
                :class="{ active: activeStep >= 3, completed: activeStep >= 3 }"
            >
                <div class="step-circle">
                <div class="step-number">3</div>
                <div class="step-check" v-if="activeStep >= 3">
                    <el-icon><CircleCheckFilled /></el-icon>
                </div>
                </div>
                <div class="step-label">生成用例</div>
                <div class="step-desc">输出测试用例</div>
            </div>
            </div>
        </div>
        </div>
    </div>

    <div class="content-wrapper">
        <!-- 左侧面板 -->
        <div class="left-panel">
        <!-- 文档上传卡片 -->
        <div class="glass-card upload-card">
            <div class="card-header">
            <div class="header-icon">
                <el-icon :size="20" color="white"><Upload /></el-icon>
            </div>
            <div class="header-content">
                <h3>文档上传</h3>
                <p>上传DOCX文档开始处理流程</p>
            </div>
            </div>

            <div class="card-body">
            <div class="upload-section">
                <el-upload
                class="upload-area"
                drag
                action=""
                :auto-upload="false"
                :on-change="handleFileChange"
                :on-remove="handleFileRemove"
                :limit="1"
                accept=".docx"
                >
                <div class="upload-content">
                    <div class="upload-icon">
                    <el-icon :size="32" color="#6366f1"><UploadFilled /></el-icon>
                    </div>
                    <div class="upload-text">
                    <h4>拖放文件到此处</h4>
                    <p>或点击选择DOCX文档</p>
                    </div>
                    <div class="upload-format">
                    <span>.docx</span>
                    </div>
                </div>
                <template #tip>
                    <div class="upload-tip">
                    <el-icon><InfoFilled /></el-icon>
                    <span>支持最大10MB的DOCX文档</span>
                    </div>
                </template>
                </el-upload>

                <div v-if="selectedFile" class="selected-file">
                <div class="file-icon">
                    <el-icon :size="20" color="#6366f1"><Document /></el-icon>
                </div>
                <div class="file-details">
                    <div class="file-name">{{ selectedFile.name }}</div>
                    <div class="file-size">{{ formatFileSize(selectedFile.size) }}</div>
                </div>
                <div class="file-actions">
                    <el-button
                    type="danger"
                    size="small"
                    circle
                    @click="handleFileRemove"
                    >
                    <el-icon><Close /></el-icon>
                    </el-button>
                </div>
                </div>
            </div>

            <div class="action-buttons">
                <el-button
                class="process-btn parse-btn"
                :loading="parsingLoading"
                :disabled="!selectedFile"
                @click="parseDocument"
                >
                <div class="btn-content">
                    <div class="btn-icon">
                    <el-icon :size="20" color="white"><Connection /></el-icon>
                    </div>
                    <div class="btn-text">
                    <div class="btn-title">解析文档</div>
                    <div class="btn-subtitle">生成知识图谱</div>
                    </div>
                </div>
                </el-button>

                <el-button
                class="process-btn generate-btn"
                :loading="generatingLoading"
                :disabled="!hasGraphData"
                @click="generateTestCases"
                >
                <div class="btn-content">
                    <div class="btn-icon">
                    <el-icon :size="20" color="white"><MagicStick /></el-icon>
                    </div>
                    <div class="btn-text">
                    <div class="btn-title">生成用例</div>
                    <div class="btn-subtitle">基于图谱创建</div>
                    </div>
                </div>
                </el-button>
            </div>
            </div>
        </div>

        <!-- 处理状态卡片 -->
        <div class="glass-card status-card">
            <div class="card-header">
            <div class="header-icon">
                <el-icon :size="20" color="white"><Loading /></el-icon>
            </div>
            <div class="header-content">
                <h3>处理状态</h3>
                <p>实时更新处理进度</p>
            </div>
            </div>

            <div class="card-body">
            <div class="status-list">
                <div class="status-item" :class="{ active: parseStatus }">
                <div class="status-icon">
                    <div class="icon-wrapper" :class="parseStatusType">
                    <el-icon v-if="parseStatusType === 'success'"
                        ><CircleCheckFilled
                    /></el-icon>
                    <el-icon v-else-if="parseStatusType === 'error'"
                        ><CircleCloseFilled
                    /></el-icon>
                    <el-icon v-else><Loading /></el-icon>
                    </div>
                </div>
                <div class="status-content">
                    <div class="status-title">
                    <span>文档解析</span>
                    <el-tag v-if="parseStatus" :type="parseStatusType" size="small">
                        {{
                        parseStatusType === "success"
                            ? "已完成"
                            : parseStatusType === "error"
                            ? "失败"
                            : "处理中"
                        }}
                    </el-tag>
                    </div>
                    <div class="status-desc" v-if="parseStatus">{{ parseStatus }}</div>
                    <div class="status-desc" v-else>等待上传文档文件</div>
                </div>
                </div>

                <div class="status-divider"></div>

                <div class="status-item" :class="{ active: generateStatus }">
                <div class="status-icon">
                    <div class="icon-wrapper" :class="generateStatusType">
                    <el-icon v-if="generateStatusType === 'success'"
                        ><CircleCheckFilled
                    /></el-icon>
                    <el-icon v-else-if="generateStatusType === 'error'"
                        ><CircleCloseFilled
                    /></el-icon>
                    <el-icon v-else><Loading /></el-icon>
                    </div>
                </div>
                <div class="status-content">
                    <div class="status-title">
                    <span>用例生成</span>
                    <el-tag
                        v-if="generateStatus"
                        :type="generateStatusType"
                        size="small"
                    >
                        {{
                        generateStatusType === "success"
                            ? "已完成"
                            : generateStatusType === "error"
                            ? "失败"
                            : "处理中"
                        }}
                    </el-tag>
                    </div>
                    <div class="status-desc" v-if="generateStatus">
                    {{ generateStatus }}
                    </div>
                    <div class="status-desc" v-else>等待知识图谱数据</div>
                </div>
                </div>
            </div>
            </div>
        </div>
        </div>

        <!-- 右侧面板 -->
        <div class="right-panel">
        <!-- 知识图谱卡片 -->
        <div class="glass-card graph-card">
            <div class="card-header">
            <div class="header-content">
                <div class="title-section">
                <h3>知识图谱</h3>
                <div class="graph-stats" v-if="graphData.nodes.length > 0">
                    <el-tag type="info" size="small" class="stat-tag">
                    <el-icon><DataLine /></el-icon>
                    <span>{{ graphData.nodes.length }} 节点</span>
                    </el-tag>
                    <el-tag type="info" size="small" class="stat-tag">
                    <el-icon><Connection /></el-icon>
                    <span>{{ graphData.edges.length }} 关系</span>
                    </el-tag>
                </div>
                </div>
                <p v-if="graphData.nodes.length > 0">文档解析生成的语义网络</p>
                <p v-else>文档解析后生成知识图谱</p>
            </div>
            <div class="header-actions">
                <el-button-group>
                <el-button
                    :type="!showGraphAsTable ? 'primary' : 'default'"
                    size="small"
                    @click="showGraphAsTable = false"
                    title="图表视图"
                >
                    <el-icon><DataLine /></el-icon>
                </el-button>
                <el-button
                    :type="showGraphAsTable ? 'primary' : 'default'"
                    size="small"
                    @click="showGraphAsTable = true"
                    title="表格视图"
                >
                    <el-icon><Grid /></el-icon>
                </el-button>
                </el-button-group>
            </div>
            </div>

            <div class="card-body">
            <!-- 知识图谱可视化 -->
            <div v-if="!showGraphAsTable" class="graph-content">
                <div
                v-if="graphData.nodes.length > 0"
                class="graph-container"
                ref="graphContainer"
                >
                <div class="graph-placeholder" v-if="!chartInitialized">
                    <div class="placeholder-content">
                    <div class="placeholder-icon">
                        <el-icon :size="48" color="#94a3b8"><Loading /></el-icon>
                    </div>
                    <div class="placeholder-text">
                        <p>正在渲染知识图谱...</p>
                    </div>
                    </div>
                </div>
                </div>

                <!-- 空状态 -->
                <div v-if="graphData.nodes.length === 0" class="empty-state">
                <div class="empty-icon">
                    <el-icon :size="64" color="#cbd5e1"><DataLine /></el-icon>
                </div>
                <div class="empty-text">
                    <h4>暂无知识图谱数据</h4>
                    <p>上传并解析文档后，将在此处显示知识图谱</p>
                </div>
                </div>
            </div>

            <!-- 知识图谱表格视图 -->
            <div v-else class="graph-table-view">
                <div v-if="graphData.nodes.length > 0" class="graph-table">
                <el-tabs class="custom-tabs" v-model="graphActiveTab">
                    <el-tab-pane label="节点" name="nodes">
                    <div class="table-container">
                        <el-table
                        :data="graphData.nodes"
                        style="width: 100%"
                        height="300"
                        :row-class-name="tableRowClassName"
                        >
                        <el-table-column prop="id" label="ID" width="70">
                            <template #default="scope">
                            <div class="node-id">{{ scope.row.id }}</div>
                            </template>
                        </el-table-column>
                        <el-table-column prop="label" label="类型" width="100">
                            <template #default="scope">
                            <el-tag
                                :type="getNodeTagType(scope.row.type)"
                                class="type-tag"
                            >
                                {{ scope.row.label }}
                            </el-tag>
                            </template>
                        </el-table-column>
                        <el-table-column prop="name" label="名称" />
                        <el-table-column label="属性" width="120">
                            <template #default="scope">
                            <div class="properties">
                                {{ formatProperties(scope.row.properties) }}
                            </div>
                            </template>
                        </el-table-column>
                        </el-table>
                    </div>
                    </el-tab-pane>
                    <el-tab-pane label="关系" name="edges">
                    <div class="table-container">
                        <el-table
                        :data="graphData.edges"
                        style="width: 100%"
                        height="300"
                        >
                        <el-table-column label="关系" width="200">
                            <template #default="scope">
                            <div class="relation-cell">
                                <div class="relation-source">
                                {{ getNodeName(scope.row.source) }}
                                </div>
                                <div class="relation-arrow">
                                <el-icon><Right /></el-icon>
                                </div>
                                <div class="relation-target">
                                {{ getNodeName(scope.row.target) }}
                                </div>
                            </div>
                            </template>
                        </el-table-column>
                        <el-table-column prop="label" label="类型" />
                        <el-table-column label="属性" width="120">
                            <template #default="scope">
                            <div class="properties">
                                {{ formatProperties(scope.row.properties) }}
                            </div>
                            </template>
                        </el-table-column>
                        </el-table>
                    </div>
                    </el-tab-pane>
                </el-tabs>
                </div>

                <!-- 空状态 -->
                <div v-else class="empty-state">
                <div class="empty-icon">
                    <el-icon :size="64" color="#cbd5e1"><Grid /></el-icon>
                </div>
                <div class="empty-text">
                    <h4>暂无知识图谱数据</h4>
                    <p>上传并解析文档后，将在此处显示数据表格</p>
                </div>
                </div>
            </div>
            </div>
        </div>

        <!-- 测试用例卡片 -->
        <div class="glass-card testcase-card">
            <div class="card-header">
            <div class="header-content">
                <div class="title-section">
                <h3>测试用例</h3>
                <div v-if="testCases.length > 0" class="case-stats">
                    <div class="stat-item">
                    <div class="stat-value">{{ testCases.length }}</div>
                    <div class="stat-label">用例总数</div>
                    </div>
                    <div class="stat-item">
                    <div class="stat-value">{{ highPriorityCount }}</div>
                    <div class="stat-label">高优先级</div>
                    </div>
                    <div class="stat-item">
                    <div class="stat-value">{{ mediumPriorityCount }}</div>
                    <div class="stat-label">中优先级</div>
                    </div>
                    <div class="stat-item">
                    <div class="stat-value">{{ lowPriorityCount }}</div>
                    <div class="stat-label">低优先级</div>
                    </div>
                </div>
                </div>
                <p v-if="testCases.length > 0">基于知识图谱生成的测试用例</p>
                <p v-else>生成测试用例后，将在此处显示</p>
            </div>
            <div class="header-actions">
                <el-button
                type="success"
                :disabled="!testCases.length"
                @click="exportToExcel"
                class="export-btn"
                >
                <el-icon><Download /></el-icon>
                <span>导出Excel</span>
                </el-button>
                <el-button
                :type="showJsonView ? 'primary' : 'default'"
                :disabled="!testCases.length"
                @click="showJsonView = !showJsonView"
                :title="showJsonView ? '切换到表格视图' : '切换到JSON视图'"
                >
                <el-icon><Document /></el-icon>
                </el-button>
            </div>
            </div>

            <div class="card-body">
            <!-- JSON视图 -->
            <div v-if="showJsonView" class="json-view-container">
                <div v-if="testCases.length > 0" class="json-view">
                <div class="json-header">
                    <div class="json-title">
                    <el-icon><Document /></el-icon>
                    <span>JSON格式数据</span>
                    </div>
                    <div class="json-actions">
                    <el-button size="small" @click="copyJson">
                        <el-icon><DocumentCopy /></el-icon>
                        <span>复制</span>
                    </el-button>
                    </div>
                </div>
                <div class="json-content">
                    <pre><code>{{ formatJson(testCases) }}</code></pre>
                </div>
                </div>

                <!-- 空状态 -->
                <div v-else class="empty-state">
                <div class="empty-icon">
                    <el-icon :size="64" color="#cbd5e1"><Document /></el-icon>
                </div>
                <div class="empty-text">
                    <h4>暂无JSON数据</h4>
                    <p>生成测试用例后，将在此处显示JSON格式</p>
                </div>
                </div>
            </div>

            <!-- 表格视图 -->
            <div v-else class="table-view-container">
                <div v-if="testCases.length > 0" class="table-view">
                <div class="table-container">
                    <el-table
                    :data="testCases"
                    style="width: 100%"
                    height="300"
                    :row-class-name="testCaseRowClassName"
                    v-loading="generatingLoading"
                    >
                    <el-table-column prop="id" label="ID" width="70">
                        <template #default="scope">
                        <div class="case-id">{{ scope.row.id }}</div>
                        </template>
                    </el-table-column>
                    <el-table-column prop="name" label="用例名称" width="180">
                        <template #default="scope">
                        <div class="case-name">{{ scope.row.name }}</div>
                        </template>
                    </el-table-column>
                    <el-table-column prop="description" label="描述" />
                    <el-table-column prop="priority" label="优先级" width="90">
                        <template #default="scope">
                        <div class="priority-badge" :class="scope.row.priority">
                            <span>{{ scope.row.priority }}</span>
                        </div>
                        </template>
                    </el-table-column>
                    <el-table-column prop="status" label="状态" width="100">
                        <template #default="scope">
                        <div class="status-badge" :class="scope.row.status">
                            <span>{{ scope.row.status }}</span>
                        </div>
                        </template>
                    </el-table-column>
                    <el-table-column label="操作" width="80">
                        <template #default="scope">
                        <el-button
                            type="primary"
                            size="small"
                            circle
                            @click="viewTestCaseDetail(scope.row)"
                            title="查看详情"
                        >
                            <el-icon><View /></el-icon>
                        </el-button>
                        </template>
                    </el-table-column>
                    </el-table>
                </div>
                </div>

                <!-- 空状态 -->
                <div v-else class="empty-state">
                <div class="empty-icon">
                    <el-icon :size="64" color="#cbd5e1"><Grid /></el-icon>
                </div>
                <div class="empty-text">
                    <h4>暂无测试用例</h4>
                    <p>生成测试用例后，将在此处显示表格</p>
                </div>
                </div>
            </div>
            </div>
        </div>
        </div>
    </div>
    </div>

    <!-- 用例详情对话框 -->
    <el-dialog
    v-model="detailDialogVisible"
    title="测试用例详情"
    width="600px"
    class="detail-dialog"
    >
    <div v-if="selectedTestCase" class="detail-content">
        <div class="detail-header">
        <div class="detail-title">
            <h3>{{ selectedTestCase.name }}</h3>
            <div class="detail-meta">
            <div class="detail-id">ID: {{ selectedTestCase.id }}</div>
            <div class="detail-priority" :class="selectedTestCase.priority">
                {{ selectedTestCase.priority }}
            </div>
            </div>
        </div>
        </div>

        <div class="detail-body">
        <div class="detail-section">
            <h4>描述</h4>
            <p>{{ selectedTestCase.description }}</p>
        </div>

        <div class="detail-section">
            <h4>前置条件</h4>
            <p>{{ selectedTestCase.preconditions || "无" }}</p>
        </div>

        <div class="detail-section">
            <h4>测试步骤</h4>
            <div class="steps-list">
            <div
                v-for="(step, index) in selectedTestCase.steps"
                :key="index"
                class="step-item"
            >
                <div class="step-number">{{ index + 1 }}</div>
                <div class="step-content">
                <div class="step-action">{{ step.action }}</div>
                <div class="step-expected" v-if="step.expected">
                    <span>预期结果：</span>{{ step.expected }}
                </div>
                </div>
            </div>
            </div>
        </div>

        <div class="detail-footer">
            <div class="detail-info">
            <div class="info-item">
                <span class="info-label">状态：</span>
                <span class="info-value" :class="selectedTestCase.status">{{
                selectedTestCase.status
                }}</span>
            </div>
            <div class="info-item">
                <span class="info-label">创建时间：</span>
                <span class="info-value">{{ selectedTestCase.created_at }}</span>
            </div>
            <div class="info-item">
                <span class="info-label">最后更新：</span>
                <span class="info-value">{{ selectedTestCase.updated_at }}</span>
            </div>
            </div>
        </div>
        </div>
    </div>
    </el-dialog>

    <!-- 底部信息 -->
    <div class="bottom-info">
    <p>
        基于 MFQ 测试方法的用例生成助手
    </p>
    </div>
</div>
</template>

<script>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import * as XLSX from "xlsx";
import {
Document,
Upload,
UploadFilled,
Connection,
MagicStick,
Download,
InfoFilled,
Close,
CircleCheckFilled,
CircleCloseFilled,
Loading,
DataLine,
Grid,
DocumentCopy,
View,
Right,
} from "@element-plus/icons-vue";
import { AIApi } from '@/api/testcasegen'
// import { type } from 'os';
// import { apiClient } from "@/api/client";


export default {
name: "DocumentProcessor",
components: {
    Document,
    Upload,
    UploadFilled,
    Connection,
    MagicStick,
    Download,
    InfoFilled,
    Close,
    CircleCheckFilled,
    CircleCloseFilled,
    Loading,
    DataLine,
    Grid,
    DocumentCopy,
    View,
    Right,
},
setup() {
    
    // 响应式数据
    const selectedFile = ref(null);
    const parsingLoading = ref(false);
    const generatingLoading = ref(false);
    const parseStatus = ref("");
    const parseStatusType = ref("info");
    const generateStatus = ref("");
    const generateStatusType = ref("info");
    const graphData = reactive({ nodes: [], edges: [] });
    const showGraphAsTable = ref(false);
    const graphActiveTab = ref("nodes");
    const testCases = ref([]);
    const showJsonView = ref(false);
    const detailDialogVisible = ref(false);
    const selectedTestCase = ref(null);
    const graphContainer = ref(null);
    const chartInitialized = ref(false);
    let chartInstance = null;

    // 计算当前步骤
    const activeStep = computed(() => {
    if (testCases.value.length > 0) return 3;
    if (graphData.nodes.length > 0) return 2;
    if (selectedFile.value) return 1;
    return 0;
    });

    // 计算属性
    const hasGraphData = computed(() => {
    return graphData.nodes && graphData.nodes.length > 0;
    });

    const highPriorityCount = computed(() => {
    return testCases.value.filter((tc) => tc.priority === "高").length;
    });

    const mediumPriorityCount = computed(() => {
    return testCases.value.filter((tc) => tc.priority === "中").length;
    });

    const lowPriorityCount = computed(() => {
    return testCases.value.filter((tc) => tc.priority === "低").length;
    });

    // 方法
    const handleFileChange = (file) => {
    selectedFile.value = file.raw;
    ElMessage.success(`已选择文件: ${file.name}`);
    };

    const handleFileRemove = () => {
    selectedFile.value = null;
    ElMessage.info("已移除文件");
    };

    const formatFileSize = (bytes) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    };

    const getStepText = (step) => {
    const steps = ["等待开始", "文档已上传", "知识图谱已生成", "测试用例已生成"];
    return steps[step] || "处理完成";
    };

    // 模拟调用文档解析接口
    const parseDocument = async () => {
        if (!selectedFile.value) {
            ElMessage.warning("请先选择文档");
            
            return;
        }

        parsingLoading.value = true;
        parseStatus.value = "正在解析文档并存入知识图谱...";
        parseStatusType.value = "info";

        // 模拟API调用延迟
        console.log(selectedFile)
        const formData = new FormData()
        formData.append('file', selectedFile.value)
        formData.append('filename', selectedFile.value.name)
        formData.append('uploadTime', new Date().toISOString())
        const docx_parse = await AIApi.loaddocxfile(formData)
        console.log('解析成功:', docx_parse)
        console.log('解析成功:',typeof docx_parse)

        const docx_string =docx_parse.data.raw_content
        console.log(docx_string)
        const testcases = await AIApi.generateTestCases(docx_string)

    };

    // 模拟调用用例生成接口
    const generateTestCases = async () => {
    if (!hasGraphData.value) {
        ElMessage.warning("请先解析文档并生成知识图谱");
        return;
    }

    generatingLoading.value = true;
    generateStatus.value = "正在基于知识图谱生成测试用例...";
    generateStatusType.value = "info";

    // 模拟API调用延迟
    setTimeout(async () => {
        try {
        // 模拟响应数据
        const mockResponse = {
            success: true,
            message: "测试用例生成成功",
            test_cases: [
            {
                id: "TC001",
                name: "用户登录-正确用户名密码",
                description: "验证使用正确的用户名和密码可以成功登录",
                priority: "高",
                status: "未执行",
                preconditions: "用户已注册并拥有有效账号",
                steps: [
                { action: "打开登录页面", expected: "登录页面正常显示" },
                { action: "输入正确的用户名", expected: "用户名输入框显示输入内容" },
                { action: "输入正确的密码", expected: "密码输入框显示掩码字符" },
                { action: "点击登录按钮", expected: "系统跳转到用户主页" },
                ],
                created_at: "2023-10-15 10:30:00",
                updated_at: "2023-10-15 10:30:00",
            },
            {
                id: "TC002",
                name: "用户登录-错误密码",
                description: "验证使用错误密码登录会失败",
                priority: "高",
                status: "未执行",
                preconditions: "用户已注册并拥有有效账号",
                steps: [
                { action: "打开登录页面", expected: "登录页面正常显示" },
                { action: "输入正确的用户名", expected: "用户名输入框显示输入内容" },
                { action: "输入错误的密码", expected: "密码输入框显示掩码字符" },
                { action: "点击登录按钮", expected: "系统显示密码错误提示" },
                ],
                created_at: "2023-10-15 10:32:00",
                updated_at: "2023-10-15 10:32:00",
            },
            {
                id: "TC003",
                name: "用户登录-用户名为空",
                description: "验证用户名为空时登录会失败",
                priority: "中",
                status: "未执行",
                preconditions: "无",
                steps: [
                { action: "打开登录页面", expected: "登录页面正常显示" },
                {
                    action: "不输入用户名，直接输入密码",
                    expected: "密码输入框显示掩码字符",
                },
                { action: "点击登录按钮", expected: "系统显示用户名不能为空提示" },
                ],
                created_at: "2023-10-15 10:35:00",
                updated_at: "2023-10-15 10:35:00",
            },
            {
                id: "TC004",
                name: "用户登录-密码为空",
                description: "验证密码为空时登录会失败",
                priority: "中",
                status: "未执行",
                preconditions: "无",
                steps: [
                { action: "打开登录页面", expected: "登录页面正常显示" },
                {
                    action: "输入用户名，不输入密码",
                    expected: "用户名输入框显示输入内容",
                },
                { action: "点击登录按钮", expected: "系统显示密码不能为空提示" },
                ],
                created_at: "2023-10-15 10:38:00",
                updated_at: "2023-10-15 10:38:00",
            },
            {
                id: "TC005",
                name: "用户登录-密码加密传输",
                description: "验证密码在传输过程中是加密的",
                priority: "低",
                status: "未执行",
                preconditions: "已安装网络抓包工具",
                steps: [
                { action: "打开网络抓包工具", expected: "工具正常启动" },
                { action: "在登录页面输入密码", expected: "密码输入框显示掩码字符" },
                { action: "点击登录按钮", expected: "网络请求中的密码字段是加密的" },
                ],
                created_at: "2023-10-15 10:40:00",
                updated_at: "2023-10-15 10:40:00",
            },
            ],
        };

        if (mockResponse.success) {
            testCases.value = mockResponse.test_cases;
            generateStatus.value = mockResponse.message;
            generateStatusType.value = "success";
            ElMessage.success("测试用例生成成功");
        } else {
            generateStatus.value = "测试用例生成失败";
            generateStatusType.value = "error";
            ElMessage.error("测试用例生成失败");
        }
        } catch (error) {
        generateStatus.value = `生成出错: ${error.message}`;
        generateStatusType.value = "error";
        ElMessage.error("测试用例生成过程中发生错误");
        } finally {
        generatingLoading.value = false;
        }
    }, 3000);
    };

    // 初始化知识图谱可视化
    const initKnowledgeGraph = async () => {
    if (!graphContainer.value || graphData.nodes.length === 0) return;

    try {
        // 动态引入 ECharts
        const echarts = await import("echarts");

        // 销毁之前的实例
        if (chartInstance) {
        chartInstance.dispose();
        chartInstance = null;
        }

        chartInstance = echarts.init(graphContainer.value);
        chartInitialized.value = true;

        // 准备图表数据
        const categories = [
        { name: "需求", itemStyle: { color: "#6366f1" } },
        { name: "功能", itemStyle: { color: "#10b981" } },
        { name: "测试点", itemStyle: { color: "#f59e0b" } },
        { name: "组件", itemStyle: { color: "#ef4444" } },
        ];

        const nodes = graphData.nodes.map((node) => ({
        id: node.id,
        name: node.name,
        category: categories.findIndex((cat) => cat.name === node.label),
        symbolSize:
            node.type === "requirement" ? 45 : node.type === "function" ? 35 : 25,
        itemStyle: {
            color: getNodeColor(node.type),
        },
        label: {
            show: true,
            position: "right",
            fontSize: 12,
            formatter:
            node.name.length > 10 ? node.name.substring(0, 10) + "..." : node.name,
        },
        }));

        const edges = graphData.edges.map((edge) => ({
        source: edge.source,
        target: edge.target,
        label: {
            show: true,
            formatter: edge.label,
            fontSize: 10,
        },
        lineStyle: {
            width: 1.5,
            curveness: 0.2,
            color: "#94a3b8",
        },
        }));

        const option = {
        tooltip: {
            trigger: "item",
            formatter: function (params) {
            if (params.dataType === "node") {
                const node = graphData.nodes.find((n) => n.id === params.data.id);
                return `
                <div style="font-weight:bold; margin-bottom:5px">${node.name}</div>
                <div>类型: ${node.label}</div>
                ${
                    node.properties && Object.keys(node.properties).length > 0
                    ? `<div style="margin-top:5px">属性: ${JSON.stringify(
                        node.properties
                        )}</div>`
                    : ""
                }
                `;
            } else if (params.dataType === "edge") {
                return `关系: ${params.data.label?.formatter || "关联"}`;
            }
            },
        },
        legend: {
            data: categories.map((c) => c.name),
            textStyle: {
            color: "#64748b",
            },
            top: "bottom",
        },
        animationDuration: 1500,
        animationEasingUpdate: "quinticInOut",
        series: [
            {
            type: "graph",
            layout: "force",
            force: {
                repulsion: 250,
                edgeLength: 100,
                gravity: 0.1,
            },
            draggable: true,
            data: nodes,
            links: edges,
            categories: categories,
            roam: true,
            label: {
                show: true,
                position: "right",
            },
            lineStyle: {
                color: "source",
                curveness: 0.3,
            },
            emphasis: {
                focus: "adjacency",
                lineStyle: {
                width: 3,
                },
            },
            },
        ],
        };

        chartInstance.setOption(option);

        // 响应窗口大小变化
        window.addEventListener("resize", handleResize);
    } catch (error) {
        console.error("初始化图表失败:", error);
    }
    };

    // 处理窗口大小变化
    const handleResize = () => {
    if (chartInstance) {
        chartInstance.resize();
    }
    };

    // 获取节点颜色
    const getNodeColor = (type) => {
    switch (type) {
        case "requirement":
        return "#6366f1";
        case "function":
        return "#10b981";
        case "test_point":
        return "#f59e0b";
        case "component":
        return "#ef4444";
        default:
        return "#8b5cf6";
    }
    };

    // 获取节点标签类型
    const getNodeTagType = (type) => {
    switch (type) {
        case "requirement":
        return "primary";
        case "function":
        return "success";
        case "test_point":
        return "warning";
        case "component":
        return "danger";
        default:
        return "info";
    }
    };

    // 格式化属性显示
    const formatProperties = (properties) => {
    if (!properties || Object.keys(properties).length === 0) return "无";
    return Object.entries(properties)
        .map(([key, value]) => `${key}: ${value}`)
        .join(", ");
    };

    // 获取节点名称
    const getNodeName = (id) => {
    const node = graphData.nodes.find((n) => n.id === id);
    return node ? node.name : id;
    };

    // 查看用例详情
    const viewTestCaseDetail = (testCase) => {
    selectedTestCase.value = testCase;
    detailDialogVisible.value = true;
    };

    // 导出到Excel
    const exportToExcel = () => {
    if (testCases.value.length === 0) {
        ElMessage.warning("没有可导出的测试用例");
        return;
    }

    ElMessageBox.confirm("测试用例将导出为Excel格式，是否继续？", "导出确认", {
        confirmButtonText: "导出",
        cancelButtonText: "取消",
        type: "warning",
    })
        .then(() => {
        try {
            // 准备Excel数据
            const worksheetData = testCases.value.map((tc) => ({
            用例ID: tc.id,
            用例名称: tc.name,
            描述: tc.description,
            优先级: tc.priority,
            状态: tc.status,
            前置条件: tc.preconditions || "无",
            测试步骤: tc.steps
                .map((step) => `· ${step.action} (预期: ${step.expected})`)
                .join("\n"),
            创建时间: tc.created_at,
            最后更新: tc.updated_at,
            }));

            // 创建工作表
            const worksheet = XLSX.utils.json_to_sheet(worksheetData);

            // 设置列宽
            const colWidths = [
            { wch: 10 }, // 用例ID
            { wch: 25 }, // 用例名称
            { wch: 40 }, // 描述
            { wch: 8 }, // 优先级
            { wch: 10 }, // 状态
            { wch: 30 }, // 前置条件
            { wch: 60 }, // 测试步骤
            { wch: 18 }, // 创建时间
            { wch: 18 }, // 最后更新
            ];
            worksheet["!cols"] = colWidths;

            // 创建工作簿
            const workbook = XLSX.utils.book_new();
            XLSX.utils.book_append_sheet(workbook, worksheet, "测试用例");

            // 生成Excel文件
            XLSX.writeFile(workbook, `测试用例_${new Date().getTime()}.xlsx`);

            ElMessage.success("测试用例已成功导出为Excel文件");
        } catch (error) {
            ElMessage.error(`导出失败: ${error.message}`);
        }
        })
        .catch(() => {
        // 用户取消
        });
    };

    // 复制JSON
    const copyJson = async () => {
    try {
        const jsonText = JSON.stringify(testCases.value, null, 2);
        await navigator.clipboard.writeText(jsonText);
        ElMessage.success("JSON数据已复制到剪贴板");
    } catch (err) {
        ElMessage.error("复制失败，请手动复制");
    }
    };

    // 格式化JSON显示
    const formatJson = (data) => {
    return JSON.stringify(data, null, 2);
    };

    // 表格行样式
    const tableRowClassName = ({ row }) => {
    return `node-row-${row.type}`;
    };

    const testCaseRowClassName = ({ row }) => {
    return `case-row-${row.priority}`;
    };

    // 生命周期钩子
    onMounted(() => {
    // 可以在这里初始化一些数据
    });

    onUnmounted(() => {
    // 清理图表实例
    if (chartInstance) {
        chartInstance.dispose();
        chartInstance = null;
    }
    window.removeEventListener("resize", handleResize);
    });

    return {
    selectedFile,
    parsingLoading,
    generatingLoading,
    parseStatus,
    parseStatusType,
    generateStatus,
    generateStatusType,
    graphData,
    showGraphAsTable,
    graphActiveTab,
    testCases,
    showJsonView,
    detailDialogVisible,
    selectedTestCase,
    graphContainer,
    chartInitialized,
    activeStep,
    hasGraphData,
    highPriorityCount,
    mediumPriorityCount,
    lowPriorityCount,
    handleFileChange,
    handleFileRemove,
    formatFileSize,
    getStepText,
    parseDocument,
    generateTestCases,
    formatProperties,
    getNodeName,
    getNodeTagType,
    viewTestCaseDetail,
    exportToExcel,
    copyJson,
    formatJson,
    tableRowClassName,
    testCaseRowClassName,
    };
},
};
</script>

<style scoped>
/* 全局样式 */
:root {
--primary-color: #6366f1;
--primary-light: #818cf8;
--primary-dark: #4f46e5;
--primary-gradient: linear-gradient(135deg, #6366f1, #4f46e5);
--success-color: #10b981;
--success-light: #34d399;
--warning-color: #f59e0b;
--warning-light: #fbbf24;
--danger-color: #ef4444;
--danger-light: #f87171;
--info-color: #3b82f6;
--info-light: #60a5fa;
--bg-color: #f8fafc;
--card-bg: rgba(255, 255, 255, 0.98);
--text-primary: #1e293b;
--text-secondary: #64748b;
--text-light: #94a3b8;
--border-color: #e2e8f0;
--border-light: #f1f5f9;
--shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
--shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
--shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
--shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
--glass-border: rgba(255, 255, 255, 0.8);
--glass-shadow: 0 8px 32px rgba(99, 102, 241, 0.1);
}

.document-processor {
min-height: 100vh;
background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
    "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
}

/* 顶部导航栏 */
.top-nav {
background: var(--primary-gradient);
box-shadow: var(--shadow-lg);
position: relative;
z-index: 100;
}

.top-nav::after {
content: "";
position: absolute;
bottom: 0;
left: 0;
right: 0;
height: 1px;
background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
}

.nav-content {
max-width: 1400px;
margin: 0 auto;
padding: 0 24px;
display: flex;
justify-content: space-between;
align-items: center;
height: 70px;
}

.logo-section {
display: flex;
align-items: center;
gap: 16px;
}

.logo-icon {
width: 44px;
height: 44px;
background: rgba(255, 255, 255, 0.2);
border-radius: 12px;
display: flex;
align-items: center;
justify-content: center;
backdrop-filter: blur(10px);
box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.logo-text h1 {
margin: 0;
font-size: 22px;
font-weight: 800;
color: white;
letter-spacing: -0.5px;
text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.logo-text p {
margin: 4px 0 0;
font-size: 13px;
color: rgba(255, 255, 255, 0.9);
font-weight: 500;
}

.user-info {
display: flex;
align-items: center;
gap: 12px;
color: white;
padding: 8px 12px;
background: rgba(255, 255, 255, 0.15);
border-radius: 12px;
backdrop-filter: blur(10px);
}

.user-name {
font-weight: 600;
font-size: 14px;
}

/* 步骤指示器 */
.process-steps-container {
padding: 24px 24px 40px;
max-width: 1400px;
margin: 0 auto;
}

.process-steps {
background: var(--card-bg);
border-radius: 20px;
box-shadow: var(--glass-shadow);
border: 1px solid var(--glass-border);
overflow: hidden;
backdrop-filter: blur(10px);
}

.steps-header {
padding: 24px 32px;
border-bottom: 1px solid var(--border-light);
background: linear-gradient(
    135deg,
    rgba(99, 102, 241, 0.05) 0%,
    rgba(99, 102, 241, 0.02) 100%
);
}

.steps-header h3 {
margin: 0 0 8px;
font-size: 20px;
font-weight: 700;
color: var(--text-primary);
display: flex;
align-items: center;
gap: 10px;
}

.steps-header h3::before {
content: "";
display: block;
width: 6px;
height: 20px;
background: var(--primary-color);
border-radius: 3px;
}

.step-progress {
display: flex;
align-items: center;
gap: 8px;
font-size: 14px;
color: var(--text-secondary);
}

.progress-text {
color: var(--primary-color);
font-weight: 600;
}

.steps-wrapper {
padding: 40px 32px;
}

.steps-track {
display: flex;
justify-content: space-between;
align-items: center;
position: relative;
margin: 0 20px;
}

.steps-track::before {
content: "";
position: absolute;
top: 30px;
left: 0;
right: 0;
height: 4px;
background: var(--border-color);
border-radius: 2px;
z-index: 1;
}

.progress-bar {
position: absolute;
top: 30px;
left: 0;
height: 4px;
background: var(--primary-gradient);
border-radius: 2px;
z-index: 2;
transition: width 0.6s ease;
}

.step-item {
display: flex;
flex-direction: column;
align-items: center;
position: relative;
z-index: 3;
flex: 1;
}

.step-circle {
width: 60px;
height: 60px;
border-radius: 50%;
background: white;
border: 4px solid var(--border-color);
display: flex;
align-items: center;
justify-content: center;
margin-bottom: 16px;
position: relative;
transition: all 0.3s ease;
box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.step-item.active .step-circle {
border-color: var(--primary-color);
background: white;
box-shadow: 0 6px 20px rgba(99, 102, 241, 0.3);
}

.step-item.completed .step-circle {
border-color: var(--success-color);
background: var(--success-color);
}

.step-number {
font-size: 20px;
font-weight: 700;
color: var(--text-light);
transition: all 0.3s ease;
}

.step-item.active .step-number {
color: var(--primary-color);
}

.step-item.completed .step-number {
display: none;
}

.step-check {
position: absolute;
top: 50%;
left: 50%;
transform: translate(-50%, -50%);
color: white;
font-size: 24px;
}

.step-label {
font-size: 16px;
font-weight: 600;
color: var(--text-primary);
margin-bottom: 4px;
}

.step-desc {
font-size: 13px;
color: var(--text-secondary);
text-align: center;
max-width: 120px;
}

/* 主要内容区域 */
.content-wrapper {
max-width: 1400px;
margin: 0 auto;
padding: 0 24px 40px;
display: grid;
grid-template-columns: 1fr 1fr;
gap: 24px;
}

/* 玻璃卡片效果 */
.glass-card {
background: var(--card-bg);
border: 1px solid var(--glass-border);
border-radius: 20px;
box-shadow: var(--glass-shadow);
overflow: hidden;
transition: all 0.3s ease;
backdrop-filter: blur(10px);
}

.glass-card:hover {
transform: translateY(-4px);
box-shadow: var(--shadow-xl);
}

/* 卡片头部 */
.card-header {
padding: 24px;
border-bottom: 1px solid var(--border-light);
display: flex;
justify-content: space-between;
align-items: flex-start;
background: linear-gradient(
    135deg,
    rgba(99, 102, 241, 0.05) 0%,
    rgba(99, 102, 241, 0.02) 100%
);
}

.card-header h3 {
margin: 0 0 8px;
font-size: 18px;
font-weight: 700;
color: var(--text-primary);
}

.card-header p {
margin: 0;
font-size: 14px;
color: var(--text-secondary);
}

.title-section {
display: flex;
align-items: center;
gap: 16px;
margin-bottom: 8px;
}

.graph-stats {
display: flex;
gap: 8px;
}

.stat-tag {
background: rgba(99, 102, 241, 0.1);
border: none;
color: var(--primary-color);
font-weight: 500;
}

.stat-tag .el-icon {
margin-right: 4px;
}

.header-icon {
width: 44px;
height: 44px;
background: var(--primary-gradient);
border-radius: 12px;
display: flex;
align-items: center;
justify-content: center;
color: white;
margin-right: 16px;
box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.card-header > div:first-child {
display: flex;
align-items: flex-start;
}

.header-actions {
display: flex;
gap: 8px;
align-items: center;
}

/* 卡片主体 */
.card-body {
padding: 24px;
}

/* 上传区域 */
.upload-area {
width: 100%;
}

:deep(.el-upload-dragger) {
width: 100%;
padding: 48px 24px;
background: linear-gradient(
    135deg,
    rgba(99, 102, 241, 0.03) 0%,
    rgba(99, 102, 241, 0.01) 100%
);
border: 2px dashed var(--border-color);
border-radius: 16px;
transition: all 0.3s ease;
}

:deep(.el-upload-dragger:hover) {
border-color: var(--primary-color);
background: linear-gradient(
    135deg,
    rgba(99, 102, 241, 0.08) 0%,
    rgba(99, 102, 241, 0.04) 100%
);
transform: translateY(-2px);
}

.upload-content {
display: flex;
flex-direction: column;
align-items: center;
gap: 20px;
}

.upload-icon {
width: 72px;
height: 72px;
background: white;
border-radius: 50%;
display: flex;
align-items: center;
justify-content: center;
color: var(--primary-color);
box-shadow: 0 8px 24px rgba(99, 102, 241, 0.2);
transition: transform 0.3s ease;
}

:deep(.el-upload-dragger:hover) .upload-icon {
transform: scale(1.05);
}

.upload-text h4 {
margin: 0;
font-size: 20px;
font-weight: 700;
color: var(--text-primary);
}

.upload-text p {
margin: 8px 0 0;
font-size: 14px;
color: var(--text-secondary);
}

.upload-format {
padding: 8px 16px;
background: var(--primary-gradient);
color: white;
border-radius: 24px;
font-size: 13px;
font-weight: 600;
letter-spacing: 0.5px;
}

.upload-tip {
display: flex;
align-items: center;
justify-content: center;
gap: 8px;
margin-top: 16px;
font-size: 13px;
color: var(--text-secondary);
padding: 8px 16px;
background: rgba(99, 102, 241, 0.05);
border-radius: 8px;
}

/* 已选择文件 */
.selected-file {
margin-top: 20px;
padding: 20px;
background: white;
border: 1px solid var(--border-color);
border-radius: 16px;
display: flex;
align-items: center;
gap: 16px;
box-shadow: var(--shadow-sm);
transition: all 0.3s ease;
}

.selected-file:hover {
border-color: var(--primary-color);
box-shadow: 0 4px 12px rgba(99, 102, 241, 0.1);
}

.file-icon {
width: 48px;
height: 48px;
background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(99, 102, 241, 0.05));
border-radius: 12px;
display: flex;
align-items: center;
justify-content: center;
color: var(--primary-color);
}

.file-details {
flex: 1;
}

.file-name {
font-weight: 600;
color: var(--text-primary);
margin-bottom: 4px;
font-size: 16px;
}

.file-size {
font-size: 13px;
color: var(--text-secondary);
}

/* 处理按钮 */
.action-buttons {
margin-top: 32px;
display: grid;
grid-template-columns: 1fr 1fr;
gap: 16px;
}

.process-btn {
height: auto !important;
padding: 24px !important;
border-radius: 16px !important;
border: none !important;
transition: all 0.3s ease !important;
box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.parse-btn {
background: var(--primary-gradient) !important;
color: white !important;
}

.parse-btn:hover:not(:disabled) {
transform: translateY(-4px);
box-shadow: 0 12px 32px rgba(99, 102, 241, 0.4) !important;
}

.generate-btn {
background: linear-gradient(
    135deg,
    var(--success-color),
    var(--success-light)
) !important;
color: white !important;
}

.generate-btn:hover:not(:disabled) {
transform: translateY(-4px);
box-shadow: 0 12px 32px rgba(16, 185, 129, 0.4) !important;
}

.process-btn:disabled {
opacity: 0.5;
cursor: not-allowed;
transform: none !important;
box-shadow: none !important;
}

.btn-content {
display: flex;
align-items: center;
gap: 16px;
}

.btn-icon {
width: 48px;
height: 48px;
background: rgba(255, 255, 255, 0.2);
border-radius: 12px;
display: flex;
align-items: center;
justify-content: center;
backdrop-filter: blur(10px);
}

.btn-text {
text-align: left;
color: white;
}

.btn-title {
font-size: 18px;
font-weight: 700;
margin-bottom: 4px;
}

.btn-subtitle {
font-size: 13px;
opacity: 0.9;
font-weight: 500;
}

/* 状态卡片 */
.status-card .card-header {
background: linear-gradient(
    135deg,
    rgba(59, 130, 246, 0.05) 0%,
    rgba(59, 130, 246, 0.02) 100%
);
}

.status-list {
display: flex;
flex-direction: column;
gap: 20px;
}

.status-item {
display: flex;
align-items: flex-start;
gap: 16px;
padding: 20px;
background: white;
border: 1px solid var(--border-color);
border-radius: 16px;
transition: all 0.3s ease;
}

.status-item.active {
border-color: var(--primary-color);
box-shadow: 0 4px 16px rgba(99, 102, 241, 0.15);
}

.status-icon {
flex-shrink: 0;
}

.icon-wrapper {
width: 48px;
height: 48px;
border-radius: 12px;
display: flex;
align-items: center;
justify-content: center;
font-size: 24px;
}

.icon-wrapper.info {
background: rgba(59, 130, 246, 0.1);
color: var(--info-color);
}

.icon-wrapper.success {
background: rgba(16, 185, 129, 0.1);
color: var(--success-color);
}

.icon-wrapper.error {
background: rgba(239, 68, 68, 0.1);
color: var(--danger-color);
}

.status-content {
flex: 1;
}

.status-title {
display: flex;
align-items: center;
gap: 12px;
margin-bottom: 8px;
}

.status-title span {
font-weight: 600;
color: var(--text-primary);
font-size: 16px;
}

.status-desc {
font-size: 14px;
color: var(--text-secondary);
line-height: 1.5;
}

.status-divider {
height: 1px;
background: linear-gradient(90deg, transparent, var(--border-color), transparent);
margin: 0 20px;
}

/* 知识图谱卡片 */
.graph-content {
width: 100%;
border-radius: 16px;
overflow: hidden;
background: #f8fafc;
}

.graph-container {
width: 100%;
height: 400px;
}

.graph-placeholder {
width: 100%;
height: 100%;
display: flex;
align-items: center;
justify-content: center;
background: linear-gradient(135deg, #f8fafc, #f1f5f9);
}

.placeholder-content {
text-align: center;
}

.placeholder-icon {
margin-bottom: 20px;
}

.placeholder-text p {
margin: 0;
color: var(--text-secondary);
font-size: 14px;
font-weight: 500;
}

/* 知识图谱表格 */
.graph-table-view {
height: 100%;
display: flex;
flex-direction: column;
}

.custom-tabs {
flex: 1;
display: flex;
flex-direction: column;
}

.custom-tabs :deep(.el-tabs__header) {
margin: 0;
flex-shrink: 0;
}

.custom-tabs :deep(.el-tabs__nav-wrap) {
padding: 0 24px;
}

.custom-tabs :deep(.el-tabs__item) {
font-weight: 600;
padding: 0 24px;
}

.custom-tabs :deep(.el-tabs__content) {
flex: 1;
padding: 0;
overflow: hidden;
}

.table-container {
padding: 16px 24px;
height: 100%;
overflow: auto;
}

:deep(.el-table) {
border-radius: 12px;
overflow: hidden;
border: 1px solid var(--border-color);
}

:deep(.el-table__header) {
background: linear-gradient(135deg, #f8fafc, #f1f5f9);
}

:deep(.el-table th) {
background: transparent;
color: var(--text-primary);
font-weight: 700;
border-bottom: 1px solid var(--border-color);
}

:deep(.el-table__row) {
transition: background-color 0.2s ease;
}

:deep(.el-table__row:hover) {
background-color: rgba(99, 102, 241, 0.05);
}

.node-id {
font-family: "JetBrains Mono", "Courier New", monospace;
font-size: 12px;
color: var(--text-secondary);
font-weight: 600;
}

.type-tag {
border-radius: 8px;
font-weight: 600;
padding: 4px 10px;
}

.relation-cell {
display: flex;
align-items: center;
gap: 12px;
padding: 4px 0;
}

.relation-source,
.relation-target {
padding: 6px 12px;
background: linear-gradient(135deg, #f8fafc, #f1f5f9);
border-radius: 8px;
font-size: 13px;
font-weight: 600;
color: var(--text-primary);
flex: 1;
text-align: center;
overflow: hidden;
text-overflow: ellipsis;
white-space: nowrap;
}

.relation-arrow {
width: 32px;
display: flex;
align-items: center;
justify-content: center;
color: var(--primary-color);
}

.properties {
font-size: 12px;
color: var(--text-secondary);
overflow: hidden;
text-overflow: ellipsis;
white-space: nowrap;
padding: 4px 8px;
background: rgba(99, 102, 241, 0.05);
border-radius: 6px;
}

/* 测试用例卡片 */
.case-stats {
display: flex;
gap: 20px;
margin-top: 4px;
}

.stat-item {
text-align: center;
min-width: 60px;
}

.stat-value {
font-size: 24px;
font-weight: 800;
color: var(--primary-color);
margin-bottom: 4px;
}

.stat-label {
font-size: 12px;
color: var(--text-secondary);
font-weight: 600;
text-transform: uppercase;
letter-spacing: 0.5px;
}

.export-btn {
background: linear-gradient(
    135deg,
    var(--success-color),
    var(--success-light)
) !important;
border: none !important;
color: white !important;
font-weight: 600 !important;
box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3) !important;
}

.export-btn:hover:not(:disabled) {
transform: translateY(-2px);
box-shadow: 0 8px 20px rgba(16, 185, 129, 0.4) !important;
}

.export-btn:disabled {
opacity: 0.5;
cursor: not-allowed;
transform: none !important;
box-shadow: none !important;
}

/* JSON视图 */
.json-view-container {
height: 100%;
display: flex;
flex-direction: column;
}

.json-view {
border-radius: 16px;
overflow: hidden;
border: 1px solid var(--border-color);
height: 100%;
display: flex;
flex-direction: column;
}

.json-header {
padding: 16px 24px;
background: linear-gradient(135deg, #f8fafc, #f1f5f9);
border-bottom: 1px solid var(--border-color);
display: flex;
justify-content: space-between;
align-items: center;
flex-shrink: 0;
}

.json-title {
display: flex;
align-items: center;
gap: 12px;
font-weight: 600;
color: var(--text-primary);
font-size: 16px;
}

.json-content {
background: #1e293b;
color: #e2e8f0;
padding: 24px;
font-family: "JetBrains Mono", "Courier New", monospace;
font-size: 13px;
line-height: 1.6;
flex: 1;
overflow: auto;
}

.json-content pre {
margin: 0;
}

.json-content code {
font-family: inherit;
}

/* 表格视图 */
.table-view-container {
height: 100%;
display: flex;
flex-direction: column;
}

.table-view {
height: 100%;
display: flex;
flex-direction: column;
}

.table-container {
flex: 1;
padding: 0;
overflow: hidden;
}

.table-container :deep(.el-table) {
height: 100%;
}

.case-id {
font-family: "JetBrains Mono", "Courier New", monospace;
font-size: 12px;
color: var(--text-secondary);
font-weight: 600;
}

.case-name {
font-weight: 600;
color: var(--text-primary);
font-size: 14px;
overflow: hidden;
text-overflow: ellipsis;
white-space: nowrap;
}

.priority-badge {
display: inline-block;
padding: 6px 12px;
border-radius: 20px;
font-size: 12px;
font-weight: 700;
text-align: center;
min-width: 50px;
letter-spacing: 0.5px;
}

.priority-badge.高 {
background: linear-gradient(135deg, rgba(239, 68, 68, 0.15), rgba(239, 68, 68, 0.1));
color: var(--danger-color);
border: 1px solid rgba(239, 68, 68, 0.2);
}

.priority-badge.中 {
background: linear-gradient(135deg, rgba(245, 158, 11, 0.15), rgba(245, 158, 11, 0.1));
color: var(--warning-color);
border: 1px solid rgba(245, 158, 11, 0.2);
}

.priority-badge.低 {
background: linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(16, 185, 129, 0.1));
color: var(--success-color);
border: 1px solid rgba(16, 185, 129, 0.2);
}

.status-badge {
display: inline-block;
padding: 6px 12px;
border-radius: 20px;
font-size: 12px;
font-weight: 700;
text-align: center;
min-width: 60px;
letter-spacing: 0.5px;
}

.status-badge.未执行 {
background: linear-gradient(
    135deg,
    rgba(100, 116, 139, 0.15),
    rgba(100, 116, 139, 0.1)
);
color: #64748b;
border: 1px solid rgba(100, 116, 139, 0.2);
}

.status-badge.通过 {
background: linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(16, 185, 129, 0.1));
color: var(--success-color);
border: 1px solid rgba(16, 185, 129, 0.2);
}

.status-badge.失败 {
background: linear-gradient(135deg, rgba(239, 68, 68, 0.15), rgba(239, 68, 68, 0.1));
color: var(--danger-color);
border: 1px solid rgba(239, 68, 68, 0.2);
}

/* 空状态 */
.empty-state {
padding: 60px 24px;
text-align: center;
display: flex;
flex-direction: column;
align-items: center;
justify-content: center;
height: 100%;
background: linear-gradient(135deg, #f8fafc, #f1f5f9);
border-radius: 16px;
}

.empty-icon {
margin-bottom: 24px;
opacity: 0.5;
}

.empty-text h4 {
margin: 0 0 12px;
color: var(--text-primary);
font-size: 18px;
font-weight: 700;
}

.empty-text p {
margin: 0;
color: var(--text-secondary);
font-size: 14px;
max-width: 300px;
line-height: 1.5;
}

/* 详情对话框 */
.detail-dialog :deep(.el-dialog) {
border-radius: 20px;
overflow: hidden;
border: 1px solid var(--border-color);
}

.detail-dialog :deep(.el-dialog__header) {
padding: 24px;
border-bottom: 1px solid var(--border-light);
margin: 0;
background: linear-gradient(
    135deg,
    rgba(99, 102, 241, 0.05) 0%,
    rgba(99, 102, 241, 0.02) 100%
);
}

.detail-dialog :deep(.el-dialog__body) {
padding: 0;
}

.detail-content {
padding: 24px;
}

.detail-header {
margin-bottom: 24px;
padding-bottom: 20px;
border-bottom: 1px solid var(--border-light);
}

.detail-title h3 {
margin: 0 0 12px;
color: var(--text-primary);
font-size: 22px;
font-weight: 700;
line-height: 1.4;
}

.detail-meta {
display: flex;
align-items: center;
gap: 16px;
}

.detail-id {
font-family: "JetBrains Mono", "Courier New", monospace;
font-size: 13px;
color: var(--text-secondary);
padding: 4px 12px;
background: rgba(99, 102, 241, 0.05);
border-radius: 6px;
}

.detail-priority {
padding: 6px 16px;
border-radius: 20px;
font-size: 13px;
font-weight: 700;
letter-spacing: 0.5px;
}

.detail-priority.高 {
background: linear-gradient(135deg, rgba(239, 68, 68, 0.15), rgba(239, 68, 68, 0.1));
color: var(--danger-color);
border: 1px solid rgba(239, 68, 68, 0.2);
}

.detail-priority.中 {
background: linear-gradient(135deg, rgba(245, 158, 11, 0.15), rgba(245, 158, 11, 0.1));
color: var(--warning-color);
border: 1px solid rgba(245, 158, 11, 0.2);
}

.detail-priority.低 {
background: linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(16, 185, 129, 0.1));
color: var(--success-color);
border: 1px solid rgba(16, 185, 129, 0.2);
}

.detail-section {
margin-bottom: 24px;
}

.detail-section h4 {
margin: 0 0 12px;
color: var(--text-primary);
font-size: 16px;
font-weight: 700;
display: flex;
align-items: center;
gap: 8px;
}

.detail-section h4::before {
content: "";
display: block;
width: 4px;
height: 16px;
background: var(--primary-color);
border-radius: 2px;
}

.detail-section p {
margin: 0;
color: var(--text-secondary);
line-height: 1.6;
font-size: 14px;
padding-left: 12px;
}

.steps-list {
display: flex;
flex-direction: column;
gap: 16px;
}

.step-item {
display: flex;
gap: 16px;
}

.step-number {
width: 32px;
height: 32px;
background: var(--primary-gradient);
color: white;
border-radius: 50%;
display: flex;
align-items: center;
justify-content: center;
font-size: 14px;
font-weight: 700;
flex-shrink: 0;
box-shadow: 0 4px 8px rgba(99, 102, 241, 0.3);
}

.step-content {
flex: 1;
padding: 16px;
background: #f8fafc;
border-radius: 12px;
border: 1px solid var(--border-light);
}

.step-action {
color: var(--text-primary);
margin-bottom: 8px;
font-size: 14px;
font-weight: 600;
line-height: 1.5;
}

.step-expected {
font-size: 13px;
color: var(--text-secondary);
line-height: 1.5;
padding-top: 8px;
border-top: 1px solid var(--border-color);
}

.step-expected span {
font-weight: 600;
color: var(--primary-color);
}

.detail-footer {
margin-top: 24px;
padding-top: 20px;
border-top: 1px solid var(--border-light);
}

.detail-info {
display: flex;
flex-direction: column;
gap: 12px;
}

.info-item {
display: flex;
align-items: center;
gap: 12px;
font-size: 14px;
}

.info-label {
font-weight: 600;
color: var(--text-primary);
min-width: 80px;
}

.info-value {
color: var(--text-secondary);
font-weight: 500;
}

.info-value.未执行 {
color: #64748b;
}

.info-value.通过 {
color: var(--success-color);
font-weight: 600;
}

.info-value.失败 {
color: var(--danger-color);
font-weight: 600;
}

/* 底部信息 */
.bottom-info {
max-width: 1400px;
margin: 0 auto;
padding: 20px 24px 24px;
text-align: center;
border-top: 1px solid var(--border-light);
background: rgba(255, 255, 255, 0.7);
}

.bottom-info p {
margin: 0;
font-size: 13px;
color: var(--text-secondary);
font-weight: 500;
letter-spacing: 0.3px;
}

/* 响应式设计 */
@media (max-width: 1200px) {
.content-wrapper {
    grid-template-columns: 1fr;
}

.action-buttons {
    grid-template-columns: 1fr;
}

.graph-container {
    height: 400px;
}
}

@media (max-width: 768px) {
.nav-content {
    padding: 0 16px;
}

.process-steps-container {
    padding: 16px 16px 32px;
}

.steps-header {
    padding: 20px 24px;
}

.steps-wrapper {
    padding: 32px 24px;
}

.steps-track {
    margin: 0 10px;
}

.step-circle {
    width: 48px;
    height: 48px;
}

.step-number {
    font-size: 16px;
}

.step-label {
    font-size: 14px;
}

.step-desc {
    font-size: 12px;
}

.content-wrapper {
    padding: 0 16px 32px;
    gap: 16px;
}

.card-header {
    padding: 20px;
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
}

.header-actions {
    width: 100%;
    justify-content: flex-end;
}

.case-stats {
    justify-content: space-between;
}

.stat-item {
    min-width: 50px;
}

.stat-value {
    font-size: 20px;
}

.graph-container {
    height: 300px;
}

.detail-dialog :deep(.el-dialog) {
    width: 90% !important;
    max-width: 500px;
}
}

@media (max-width: 480px) {
.steps-track {
    flex-direction: column;
    gap: 40px;
    margin: 0;
}

.steps-track::before {
    top: 0;
    left: 30px;
    right: auto;
    width: 4px;
    height: 100%;
}

.progress-bar {
    top: 0;
    left: 30px;
    width: 4px;
    height: auto;
}

.step-item {
    flex-direction: row;
    width: 100%;
    align-items: flex-start;
}

.step-circle {
    margin-bottom: 0;
    margin-right: 16px;
}

.step-text {
    text-align: left;
    flex: 1;
}

.step-label {
    margin-bottom: 4px;
}

.step-desc {
    max-width: none;
    text-align: left;
}

.action-buttons {
    gap: 12px;
}

.process-btn {
    padding: 20px !important;
}

.btn-icon {
    width: 40px;
    height: 40px;
}

.btn-title {
    font-size: 16px;
}

.case-stats {
    flex-wrap: wrap;
    gap: 12px;
}

.stat-item {
    min-width: 45px;
}
}
</style>

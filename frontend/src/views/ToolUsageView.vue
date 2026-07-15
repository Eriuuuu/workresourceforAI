<template>
  <div class="tool-usage-page">
    <div class="page-header">
      <div>
        <h2>本地工具使用情况</h2>
        <p class="page-subtitle">查看 TesterToolBox 各主机的任务执行记录与统计</p>
      </div>
      <el-button type="primary" :loading="loading" @click="refreshAll">刷新</el-button>
    </div>

    <div v-if="error" class="error-banner">
      <span>{{ error }}</span>
      <el-button link type="primary" @click="refreshAll">重试</el-button>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">总执行次数</div>
        <div class="stat-value">{{ stats?.total_events ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">今日执行</div>
        <div class="stat-value">{{ stats?.today_events ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">成功率</div>
        <div class="stat-value">{{ successRate }}%</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">活跃主机数</div>
        <div class="stat-value">{{ stats?.active_hostnames ?? 0 }}</div>
      </div>
    </div>

    <div class="card chart-card">
      <div class="card-title">近 {{ filters.days }} 日使用趋势</div>
      <div ref="chartRef" class="trend-chart"></div>
    </div>

    <div class="card">
      <div class="card-title">筛选条件</div>
      <div class="filters">
        <el-select v-model="filters.hostname" clearable placeholder="主机名" style="width: 180px">
          <el-option v-for="host in hostnames" :key="host" :label="host" :value="host" />
        </el-select>
        <el-select v-model="filters.feature_id" clearable placeholder="功能" style="width: 200px">
          <el-option
            v-for="item in featureOptions"
            :key="item.feature_id"
            :label="item.feature"
            :value="item.feature_id"
          />
        </el-select>
        <el-select v-model="filters.status" clearable placeholder="状态" style="width: 140px">
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failed" />
          <el-option label="已取消" value="cancelled" />
        </el-select>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 280px"
        />
        <el-input
          v-model="filters.error_keyword"
          clearable
          placeholder="错误关键词"
          style="width: 180px"
        />
        <el-button type="primary" @click="applyFilters">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </div>

    <div class="card">
      <div class="card-title-row">
        <div class="card-title">执行记录</div>
        <span class="summary-text">共 {{ total }} 条记录</span>
      </div>

      <el-table
        v-loading="loading"
        :data="events"
        stripe
        style="width: 100%"
        empty-text="暂无上报记录，请确认本地工具已配置 API 地址"
      >
        <el-table-column prop="client_time" label="使用时间" min-width="160" />
        <el-table-column prop="hostname" label="主机名" min-width="140" />
        <el-table-column prop="feature" label="功能" min-width="140" />
        <el-table-column prop="action" label="操作" width="90" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ formatStatus(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="100">
          <template #default="{ row }">
            {{ formatDuration(row.duration_ms) }}
          </template>
        </el-table-column>
        <el-table-column label="错误摘要" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.error || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="详情" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-bar">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="loadEvents"
          @size-change="handlePageSizeChange"
        />
      </div>
    </div>

    <el-drawer v-model="detailVisible" title="执行详情" size="520px">
      <template v-if="selectedEvent">
        <div class="detail-grid">
          <div><strong>事件 ID：</strong>{{ selectedEvent.event_id }}</div>
          <div><strong>主机名：</strong>{{ selectedEvent.hostname }}</div>
          <div><strong>功能：</strong>{{ selectedEvent.feature }}</div>
          <div><strong>来源：</strong>{{ selectedEvent.source }}</div>
          <div><strong>状态：</strong>{{ formatStatus(selectedEvent.status) }}</div>
          <div><strong>耗时：</strong>{{ formatDuration(selectedEvent.duration_ms) }}</div>
          <div><strong>客户端时间：</strong>{{ selectedEvent.client_time }}</div>
          <div><strong>服务端时间：</strong>{{ formatDateTime(selectedEvent.server_time) }}</div>
        </div>

        <div class="detail-section">
          <h4>输入参数</h4>
          <pre>{{ formatJson(selectedEvent.input) }}</pre>
        </div>
        <div class="detail-section">
          <h4>执行结果</h4>
          <pre>{{ formatJson(selectedEvent.result) }}</pre>
        </div>
        <div class="detail-section" v-if="selectedEvent.error">
          <h4>错误信息</h4>
          <pre class="error-text">{{ selectedEvent.error }}</pre>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { toolboxApi, type ToolboxEvent, type ToolboxStatsResponse } from '@/api/toolbox'

const loading = ref(false)
const error = ref('')
const events = ref<ToolboxEvent[]>([])
const total = ref(0)
const stats = ref<ToolboxStatsResponse | null>(null)
const hostnames = ref<string[]>([])
const page = ref(1)
const pageSize = ref(20)
const detailVisible = ref(false)
const selectedEvent = ref<ToolboxEvent | null>(null)
const chartRef = ref<HTMLElement | null>(null)
const dateRange = ref<[string, string] | null>(null)

let chartInstance: { dispose: () => void; setOption: (option: unknown) => void } | null = null

const filters = ref({
  hostname: '',
  feature_id: '',
  status: '',
  error_keyword: '',
  days: 30,
})

const featureOptions = computed(() => stats.value?.by_feature ?? [])

const successRate = computed(() => {
  const totalEvents = stats.value?.total_events ?? 0
  if (!totalEvents) return 0
  const success = stats.value?.success_count ?? 0
  return Math.round((success / totalEvents) * 1000) / 10
})

const formatStatus = (status: string) => {
  const map: Record<string, string> = {
    success: '成功',
    failed: '失败',
    cancelled: '已取消',
  }
  return map[status] || status
}

const statusTagType = (status: string) => {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  return 'info'
}

const formatDuration = (durationMs?: number | null) => {
  if (!durationMs && durationMs !== 0) return '-'
  if (durationMs < 1000) return `${durationMs} ms`
  const seconds = Math.floor(durationMs / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remain = seconds % 60
  return `${minutes}m ${remain}s`
}

const formatDateTime = (value?: string) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

const formatJson = (value: unknown) => {
  if (value == null) return '-'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

const buildEventQuery = () => {
  const [startDate, endDate] = dateRange.value || []
  return {
    skip: (page.value - 1) * pageSize.value,
    limit: pageSize.value,
    hostname: filters.value.hostname || undefined,
    feature_id: filters.value.feature_id || undefined,
    status: filters.value.status || undefined,
    error_keyword: filters.value.error_keyword || undefined,
    start_time: startDate ? `${startDate} 00:00:00` : undefined,
    end_time: endDate ? `${endDate} 23:59:59` : undefined,
  }
}

const loadEvents = async () => {
  loading.value = true
  error.value = ''
  try {
    const response = await toolboxApi.getEvents(buildEventQuery())
    events.value = response.items
    total.value = response.total
  } catch {
    error.value = '获取执行记录失败，请检查网络连接或登录状态'
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    stats.value = await toolboxApi.getStats({
      days: filters.value.days,
      hostname: filters.value.hostname || undefined,
      feature_id: filters.value.feature_id || undefined,
    })
    await nextTick()
    renderChart()
  } catch {
    if (!error.value) {
      error.value = '获取统计数据失败'
    }
  }
}

const loadHostnames = async () => {
  try {
    hostnames.value = await toolboxApi.getHostnames()
  } catch {
    hostnames.value = []
  }
}

const renderChart = async () => {
  if (!chartRef.value || !stats.value) return
  const echarts = await import('echarts')
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }
  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 30, bottom: 30 },
    xAxis: {
      type: 'category',
      data: stats.value.daily_trend.map((item) => item.date),
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        name: '执行次数',
        type: 'line',
        smooth: true,
        areaStyle: { opacity: 0.12 },
        data: stats.value.daily_trend.map((item) => item.count),
      },
    ],
  })
}

const refreshAll = async () => {
  await Promise.all([loadEvents(), loadStats(), loadHostnames()])
}

const applyFilters = async () => {
  page.value = 1
  await refreshAll()
}

const resetFilters = async () => {
  filters.value = {
    hostname: '',
    feature_id: '',
    status: '',
    error_keyword: '',
    days: 30,
  }
  dateRange.value = null
  page.value = 1
  await refreshAll()
}

const handlePageSizeChange = async () => {
  page.value = 1
  await loadEvents()
}

const openDetail = (event: ToolboxEvent) => {
  selectedEvent.value = event
  detailVisible.value = true
}

onMounted(() => {
  refreshAll()
})

onBeforeUnmount(() => {
  chartInstance?.dispose()
  chartInstance = null
})
</script>

<style scoped>
.tool-usage-page {
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
}

.page-header h2 {
  margin: 0;
  font-size: 1.5rem;
  color: #1a1a2e;
}

.page-subtitle {
  margin: 0.4rem 0 0;
  color: #6c757d;
  font-size: 0.92rem;
}

.error-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  background: #fff5f5;
  color: #c0392b;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}

.stat-card,
.card {
  background: #fff;
  border: 1px solid #e9ecef;
  border-radius: 10px;
  padding: 1rem;
}

.stat-label {
  color: #6c757d;
  font-size: 0.9rem;
}

.stat-value {
  margin-top: 0.4rem;
  font-size: 1.6rem;
  font-weight: 700;
  color: #1a1a2e;
}

.card {
  margin-bottom: 1rem;
}

.card-title {
  font-size: 1rem;
  font-weight: 600;
  color: #1a1a2e;
  margin-bottom: 0.9rem;
}

.card-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.9rem;
}

.summary-text {
  color: #6c757d;
  font-size: 0.9rem;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.chart-card {
  min-height: 320px;
}

.trend-chart {
  width: 100%;
  height: 260px;
}

.pagination-bar {
  display: flex;
  justify-content: flex-end;
  margin-top: 1rem;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.5rem;
  margin-bottom: 1rem;
  font-size: 0.92rem;
}

.detail-section h4 {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
}

.detail-section pre {
  margin: 0;
  padding: 0.75rem;
  border-radius: 8px;
  background: #f8f9fa;
  overflow: auto;
  max-height: 220px;
  font-size: 0.82rem;
  line-height: 1.45;
}

.error-text {
  color: #c0392b;
}

@media (max-width: 900px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>

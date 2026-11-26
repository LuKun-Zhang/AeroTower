<template>
  <el-table :data="rows" size="small" style="width:100%" class="exp-table">
    <el-table-column label="实验" min-width="220">
      <template #default="{ row }">
        <div class="et-name">{{ row.name }}</div>
        <div class="et-sub">{{ row.id }}</div>
      </template>
    </el-table-column>
    <el-table-column label="条件" min-width="250">
      <template #default="{ row }">
        <div class="et-sub">{{ conditionText(row) }}</div>
        <div class="et-sub">种子 {{ row.conditions.seed }} · {{ sizeText(row) }}</div>
      </template>
    </el-table-column>
    <el-table-column label="状态" width="110">
      <template #default="{ row }">
        <span class="et-status" :class="'st-' + row.status">{{ statusText(row.status) }}</span>
      </template>
    </el-table-column>
    <el-table-column label="全程准点率" width="100" align="right">
      <template #default="{ row }">{{ pct(row.summary.on_time_rate) }}</template>
    </el-table-column>
    <el-table-column label="完成率" width="90" align="right">
      <template #default="{ row }">{{ pct(row.summary.completion_rate) }}</template>
    </el-table-column>
    <el-table-column label="创建时间" width="150">
      <template #default="{ row }">{{ row.created_at }}</template>
    </el-table-column>
    <el-table-column label="操作" width="200" align="center">
      <template #default="{ row }">
        <el-button type="text" size="mini" @click="$emit('open', row)">打开</el-button>
        <el-button type="text" size="mini" @click="$emit('rerun', row)">重跑</el-button>
        <el-button type="text" size="mini" @click="$emit('export', row)">导出</el-button>
        <el-button type="text" size="mini" class="et-danger" @click="$emit('remove', row)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<script>
const STATUS = {
  draft: '草稿', running: '运行中', succeeded: '已完成',
  failed: '失败', interrupted: '中断',
}

export default {
  name: 'ExperimentTable',
  props: { rows: { type: Array, default: () => [] } },
  methods: {
    statusText(s) { return STATUS[s] || s },
    pct(v) { return v === null || v === undefined ? '—' : `${v}%` },
    conditionText(row) {
      const c = row.conditions || {}
      const dates = (c.dates || []).join(', ')
      const bases = (c.bases || []).join('/')
      const w = (c.disruption || {}).weather || 'none'
      const wText = {
        none: '无天气', sichuan_storm: '四川雷暴',
        east_rain: '华东强降雨', south_typhoon: '华南台风',
      }[w] || w
      return `${dates} · ${bases} · ${wText}`
    },
    sizeText(row) {
      const fleet = row.conditions.fleet || {}
      const size = fleet.size || 0
      const kb = Math.round((row.size_bytes || 0) / 1024)
      return `${size} 架 · ${kb} KB`
    },
  },
}
</script>

<style scoped>
.exp-table { background: transparent; color: #cdd6f4; }
.et-name { font-size: 13px; font-weight: 500; color: #e6e6f0; }
.et-sub { font-size: 11px; color: #7a7a9a; margin-top: 2px; }
.et-status { font-size: 12px; padding: 2px 8px; border-radius: 10px; }
.st-draft { background: #2d2d44; color: #b4b2a9; }
.st-running { background: rgba(64,158,255,0.18); color: #409eff; }
.st-succeeded { background: rgba(103,194,58,0.18); color: #67c23a; }
.st-failed { background: rgba(245,108,108,0.18); color: #f56c6c; }
.st-interrupted { background: rgba(230,162,60,0.18); color: #e6a23c; }
.et-danger { color: #f56c6c; }
::v-deep .el-table, ::v-deep .el-table tr, ::v-deep .el-table td {
  background: transparent; color: #cdd6f4; border-color: #313145;
}
::v-deep .el-table th { background: #1e1e2e; color: #8a8aaa; }
::v-deep .el-table::before { background: #313145; }
</style>

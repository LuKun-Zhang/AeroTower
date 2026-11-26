<template>
  <div class="exp-page">
    <div class="exp-header">
      <button class="exp-back" @click="$router.push('/')">← 返回首页</button>
      <h2>实验中心</h2>
      <div class="exp-actions">
        <el-button size="small" icon="el-icon-refresh" @click="load">刷新</el-button>
        <el-button type="primary" size="small" icon="el-icon-plus"
                   @click="$router.push('/experiments/new')">新建实验</el-button>
      </div>
    </div>

    <div class="exp-body">
      <div class="exp-summary">
        共 {{ rows.length }} 个实验
        <span v-if="runningCount"> · {{ runningCount }} 个运行中</span>
      </div>
      <ExperimentTable v-if="rows.length" :rows="rows"
                       @open="open" @rerun="rerun" @export="exportOne" @remove="remove" />
      <div v-else class="exp-empty">
        <p>还没有实验</p>
        <p>新建一个实验，跑完即可回放与对比</p>
        <el-button type="primary" size="small" @click="$router.push('/experiments/new')">新建实验</el-button>
      </div>
    </div>
  </div>
</template>

<script>
import ExperimentTable from '@/components/experiment/ExperimentTable'
import api from '@/api/experiment'

export default {
  name: 'ExperimentListView',
  components: { ExperimentTable },
  data() {
    return { rows: [], _timer: null }
  },
  computed: {
    runningCount() {
      return this.rows.filter(r => r.status === 'running').length
    },
  },
  mounted() {
    this.load()
    this._timer = setInterval(() => {
      if (this.runningCount) this.load()
    }, 3000)
  },
  beforeDestroy() {
    if (this._timer) clearInterval(this._timer)
  },
  methods: {
    async load() {
      try {
        this.rows = await api.list()
      } catch (e) {
        this.$message.error(e.message || '加载失败')
      }
    },
    open(row) {
      this.$router.push(`/experiments/${row.id}`)
    },
    async rerun(row) {
      try {
        const record = await api.rerun(row.id)
        this.$message.success('已启动重跑')
        this.$router.push(`/experiments/${record.id}`)
      } catch (e) {
        this.$message.error(e.message || '重跑失败')
      }
    },
    async exportOne(row) {
      try {
        await api.export(row.id)
      } catch (e) {
        this.$message.error(e.message || '导出失败')
      }
    },
    async remove(row) {
      try {
        await this.$confirm(`确认删除实验「${row.name}」？`, '提示', {
          confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
        })
        await api.remove(row.id)
        this.$message.success('已删除')
        this.load()
      } catch (e) {
        if (e !== 'cancel') this.$message.error(e.message || '删除失败')
      }
    },
  },
}
</script>

<style scoped>
.exp-page { min-height: 100vh; background: #141428; color: #cdd6f4; overflow-y: auto; }
.exp-header {
  display: flex; align-items: center; gap: 16px;
  padding: 12px 24px; background: #1a1a2e; border-bottom: 1px solid #2d2d44;
}
.exp-header h2 { margin: 0; font-size: 16px; color: #fff; font-weight: 500; }
.exp-actions { margin-left: auto; display: flex; gap: 8px; }
.exp-back {
  padding: 5px 12px; font-size: 13px; color: #409eff; cursor: pointer;
  background: rgba(64,158,255,0.1); border: 1px solid rgba(64,158,255,0.3);
  border-radius: 4px;
}
.exp-body { max-width: 1280px; margin: 0 auto; padding: 18px 24px 40px; }
.exp-summary { font-size: 12px; color: #7a7a9a; margin-bottom: 10px; }
.exp-empty { text-align: center; padding: 80px 0; color: #6a6a8a; font-size: 14px; }
.exp-empty p { margin: 6px 0; }
</style>

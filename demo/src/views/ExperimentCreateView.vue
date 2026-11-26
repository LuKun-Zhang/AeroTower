<template>
  <div class="exp-page">
    <div class="exp-header">
      <button class="exp-back" @click="$router.push('/experiments')">← 实验列表</button>
      <h2>新建实验</h2>
    </div>
    <div class="exp-body">
      <ConditionForm :saving="saving" @submit="onSubmit" />
    </div>
  </div>
</template>

<script>
import ConditionForm from '@/components/experiment/ConditionForm'
import api from '@/api/experiment'

export default {
  name: 'ExperimentCreateView',
  components: { ConditionForm },
  data() {
    return { saving: false }
  },
  methods: {
    async onSubmit(conditions) {
      this.saving = true
      try {
        const record = await api.create({ conditions })
        try {
          await api.run(record.id)
          this.$message.success('实验已启动')
        } catch (runErr) {
          this.$message.warning('实验已保存，但启动失败：' + (runErr.message || ''))
        }
        this.$router.replace(`/experiments/${record.id}`)
      } catch (e) {
        this.$message.error(e.message || '创建失败')
      } finally {
        this.saving = false
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
.exp-back {
  padding: 5px 12px; font-size: 13px; color: #409eff; cursor: pointer;
  background: rgba(64,158,255,0.1); border: 1px solid rgba(64,158,255,0.3);
  border-radius: 4px;
}
.exp-body { max-width: 960px; margin: 0 auto; padding: 20px 24px 40px; }
</style>

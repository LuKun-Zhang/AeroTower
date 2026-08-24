<template>
  <div class="impact-tree">
    <div class="section-title">
      <i class="el-icon-share"></i> 影响传播树
      <span class="badge" v-if="impact">总计 {{ impact.total_impacted_flights }} 个航班受影响</span>
    </div>

    <div v-if="!impact" class="empty-state">
      <i class="el-icon-info"></i>
      <p>请先选择事件并执行影响分析</p>
    </div>

    <div v-else class="tree-container">
      <!-- 根节点：异常事件 -->
      <div class="tree-root">
        <div class="tree-node root">
          <i class="el-icon-warning"></i>
          <span>{{ rootLabel }}</span>
        </div>
      </div>

      <!-- 一级：直接影响 -->
      <div class="tree-level" v-if="directFlights.length">
        <div class="level-label">直接影响</div>
        <div class="level-nodes">
          <div
            v-for="item in directFlights.slice(0, 10)"
            :key="'d'+item.flight_id"
            class="tree-node direct"
          >
            <i class="el-icon-s-promotion"></i>
            <span>{{ item.flight_no || item.flight_id }}</span>
          </div>
          <div v-if="directFlights.length > 10" class="tree-node more">
            +{{ directFlights.length - 10 }} 个
          </div>
        </div>
      </div>

      <!-- 级联影响 -->
      <div class="tree-level" v-if="cascadeByLevel.length">
        <div class="level-label">级联影响</div>
        <div v-for="(group, level) in cascadeByLevel" :key="level" class="level-sub">
          <div class="sub-level-label">L{{ level + 1 }}</div>
          <div class="level-nodes">
            <div
              v-for="item in group.slice(0, 8)"
              :key="item.flight_id"
              class="tree-node cascade"
              :title="item.reason"
            >
              <i class="el-icon-link"></i>
              <span>{{ item.flight_no || item.flight_id }}</span>
              <span class="delay-tag" v-if="item.delay_minutes">+{{ item.delay_minutes }}min</span>
            </div>
            <div v-if="group.length > 8" class="tree-node more">
              +{{ group.length - 8 }} 个
            </div>
          </div>
        </div>
      </div>

      <!-- 需取消的航班 -->
      <div class="tree-level" v-if="canceledFlights.length">
        <div class="level-label danger">需取消航班</div>
        <div class="level-nodes">
          <div v-for="item in canceledFlights.slice(0, 8)" :key="'c'+item.flight_id" class="tree-node cancel">
            <i class="el-icon-circle-close"></i>
            <span>{{ item.flight_no || item.flight_id }}</span>
          </div>
        </div>
      </div>

      <!-- 汇总指标 -->
      <div class="impact-stats">
        <div class="stat-item">
          <span class="stat-val">{{ impact.total_impacted_flights }}</span>
          <span class="stat-label">受影响航班</span>
        </div>
        <div class="stat-item">
          <span class="stat-val">{{ impact.total_delay_minutes }}min</span>
          <span class="stat-label">总延迟</span>
        </div>
        <div class="stat-item">
          <span class="stat-val">{{ impact.total_impacted_aircraft }}</span>
          <span class="stat-label">受影响飞机</span>
        </div>
        <div class="stat-item">
          <span class="stat-val">{{ impact.total_impacted_gates }}</span>
          <span class="stat-label">受影响登机口</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ImpactTree',
  props: {
    impact: { type: Object, default: null },
    eventTitle: { type: String, default: '' },
  },
  computed: {
    rootLabel() {
      return this.eventTitle || '异常事件'
    },
    cascadeByLevel() {
      if (!this.impact || !this.impact.cascade_chains) return []
      const groups = {}
      for (const item of this.impact.cascade_chains) {
        const lv = item.level || 1
        if (!groups[lv]) groups[lv] = []
        groups[lv].push(item)
      }
      return Object.values(groups)
    },
    canceledFlights() {
      if (!this.impact) return []
      const raw = this.impact.flights_to_cancel || []
      return raw.map(item => {
        if (typeof item === 'string') return { flight_id: item, flight_no: '' }
        return item
      })
    },
    directFlights() {
      if (!this.impact) return []
      const raw = this.impact.direct_impacted_flights || []
      return raw.map(item => {
        if (typeof item === 'string') return { flight_id: item, flight_no: '' }
        return item
      })
    },
  },
}
</script>

<style scoped>
.impact-tree {
  background: #fff;
  border-radius: 4px;
  padding: 16px;
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.section-title i { color: #409EFF; }
.badge {
  font-size: 12px;
  font-weight: normal;
  color: #909399;
}
.empty-state {
  text-align: center;
  padding: 40px 0;
  color: #c0c4cc;
}
.empty-state i { font-size: 32px; display: block; margin-bottom: 8px; }
.tree-container {
  overflow: auto;
}
.tree-root {
  margin-bottom: 8px;
}
.tree-node {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  margin: 2px;
  white-space: nowrap;
}
.tree-node.root {
  background: #fef0f0;
  color: #F56C6C;
  font-weight: 600;
  font-size: 13px;
}
.tree-node.direct {
  background: #fdf6ec;
  color: #E6A23C;
  border: 1px solid #faecd8;
}
.tree-node.cascade {
  background: #ecf5ff;
  color: #409EFF;
  border: 1px solid #d9ecff;
}
.tree-node.cancel {
  background: #fef0f0;
  color: #F56C6C;
  border: 1px solid #fde2e2;
}
.tree-node.more {
  background: #f5f7fa;
  color: #909399;
}
.delay-tag {
  font-size: 10px;
  color: #E6A23C;
  margin-left: 4px;
}
.tree-level {
  margin-bottom: 8px;
}
.level-label {
  font-size: 11px;
  color: #909399;
  margin-bottom: 4px;
  padding-left: 4px;
}
.level-label.danger { color: #F56C6C; }
.level-sub { margin-bottom: 4px; }
.sub-level-label {
  font-size: 10px;
  color: #c0c4cc;
  padding-left: 16px;
}
.level-nodes { padding-left: 8px; }
.impact-stats {
  display: flex;
  gap: 12px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
}
.stat-item {
  flex: 1;
  text-align: center;
}
.stat-val {
  display: block;
  font-size: 18px;
  font-weight: 700;
  color: #303133;
}
.stat-label {
  display: block;
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}
</style>

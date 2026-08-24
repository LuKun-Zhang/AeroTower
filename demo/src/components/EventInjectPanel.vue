<template>
  <div class="inject-panel">
    <div class="panel-toggle" @click="open = !open">
      <span>⚡ 异常注入</span>
      <span class="toggle-arrow">{{ open ? '▼' : '▲' }}</span>
    </div>
    <div class="panel-body" v-if="open">
      <!-- 天气状态提示 -->
      <div class="section">
        <div class="section-title">☁ 天气（自动模拟）</div>
        <div class="hint">天气由系统随机生成，RAIN 及以上自动触发容量调整</div>
      </div>

      <!-- 机场异常 -->
      <div class="section">
        <div class="section-title">🛫 机场异常</div>
        <select v-model="injAirport.ap" class="inj-select">
          <option value="">选择机场</option>
          <option v-for="a in airports" :key="a" :value="a">{{ a }}</option>
        </select>
        <select v-model="injAirport.severity" class="inj-select">
          <option value="0.7">轻度 -30%</option>
          <option value="0.5">中度 -50%</option>
          <option value="0.0">关闭</option>
        </select>
        <select v-model="injAirport.dur" class="inj-select">
          <option :value="30">30 分钟</option>
          <option :value="60">1 小时</option>
          <option :value="120">2 小时</option>
        </select>
        <button class="inj-btn" @click="doInjectAirport" :disabled="!injAirport.ap">注入</button>
      </div>

      <!-- 机组请假 -->
      <div class="section">
        <div class="section-title">👤 机组请假</div>
        <select v-model="injCrew.base" class="inj-select" @change="loadCrewRoster">
          <option value="">选择基地</option>
          <option v-for="b in crewBases" :key="b" :value="b">{{ b }}</option>
        </select>
        <div class="crew-checkboxes" v-if="roster.length">
          <div v-for="role in ['captain','first_officer','purser','attendant']" :key="role" class="role-group">
            <div class="role-label">{{ roleLabels[role] }}</div>
            <div v-for="c in rosterByRole(role)" :key="c.crew_id" class="crew-item">
              <label>
                <input type="checkbox" :value="c.name" v-model="injCrew.names" />
                {{ c.name }}
              </label>
            </div>
          </div>
        </div>
        <button class="inj-btn" @click="doInjectCrew" :disabled="!injCrew.names.length">注入</button>
      </div>

      <!-- 飞机故障 -->
      <div class="section">
        <div class="section-title">✈ 飞机故障</div>
        <select v-model="injAircraft.tail" class="inj-select">
          <option value="">选择飞机</option>
          <option v-for="a in aircrafts" :key="a.tail_no" :value="a.tail_no">
            {{ a.tail_no }} ({{ a.ac_type }})
          </option>
        </select>
        <select v-model="injAircraft.dur" class="inj-select">
          <option :value="60">1 小时</option>
          <option :value="120">2 小时</option>
          <option :value="240">4 小时</option>
        </select>
        <button class="inj-btn" @click="doInjectAircraft" :disabled="!injAircraft.tail">注入</button>
      </div>

      <!-- 已注入事件 -->
      <div class="section" v-if="activeEvents.length">
        <div class="section-title">📋 活跃事件 ({{ activeEvents.length }})</div>
        <div v-for="(e, i) in activeEvents" :key="i" class="event-item">
          <span class="event-label">{{ e.label || e.event_type }}</span>
          <button class="event-remove" @click="$emit('removeEvent', i)">✕</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'EventInjectPanel',
  props: {
    airports: { type: Array, default: () => [] },
    aircrafts: { type: Array, default: () => [] },
    crewBases: { type: Array, default: () => [] },
    activeEvents: { type: Array, default: () => [] },
  },
  emits: ['injectAirport', 'injectCrew', 'injectAircraft', 'removeEvent'],
  data() {
    return {
      open: false,
      roster: [],
      roleLabels: { captain: '机长', first_officer: '副驾驶', purser: '乘务长', attendant: '乘务员' },
      injAirport: { ap: '', severity: '0.5', dur: 60 },
      injCrew: { base: '', names: [] },
      injAircraft: { tail: '', dur: 120 },
    }
  },
  methods: {
    async loadCrewRoster() {
      if (!this.injCrew.base) { this.roster = []; return }
      try {
        const resp = await fetch(`/api/crew/by-base?base=${encodeURIComponent(this.injCrew.base)}&airline=四川航空`)
        const json = await resp.json()
        this.roster = (json.data || []).filter(c => c && c.crew_id && c.name)
      } catch (e) {
        this.roster = []
      }
    },
    rosterByRole(role) {
      return this.roster.filter(c => c.role === role)
    },
    doInjectAirport() {
      this.$emit('injectAirport', {
        airport: this.injAirport.ap,
        capacity_ratio: Number(this.injAirport.severity),
        duration_min: this.injAirport.dur,
      })
    },
    doInjectCrew() {
      this.$emit('injectCrew', {
        crew_names: this.injCrew.names,
        base: this.injCrew.base,
      })
    },
    doInjectAircraft() {
      this.$emit('injectAircraft', {
        tail_no: this.injAircraft.tail,
        duration_min: this.injAircraft.dur,
      })
    },
  },
}
</script>

<style scoped>
.inject-panel {
  background: #1e1e2e; border: 1px solid #313145; border-radius: 8px;
  width: 100%; font-size: 12px;
}
.panel-toggle {
  padding: 8px 12px; cursor: pointer; display: flex; justify-content: space-between;
  color: #cdd6f4; font-weight: 600;
}
.panel-body { padding: 0 10px 10px; }
.section { margin-top: 8px; }
.section-title { color: #a0b0e0; font-weight: 600; margin-bottom: 4px; }
.hint { color: #6a6a8a; font-size: 11px; }
.inj-select {
  display: block; width: 100%; margin-bottom: 4px;
  background: #2d2d44; color: #cdd6f4; border: 1px solid #444;
  border-radius: 4px; padding: 4px 6px; font-size: 12px;
}
.inj-btn {
  width: 100%; padding: 4px; margin-top: 4px;
  background: #f44336; color: #fff; border: none; border-radius: 4px;
  cursor: pointer; font-size: 12px;
}
.inj-btn:hover { background: #d32f2f; }
.inj-btn:disabled { background: #555; cursor: not-allowed; }

.crew-checkboxes { max-height: 150px; overflow-y: auto; margin-bottom: 4px; }
.role-group { margin-bottom: 4px; }
.role-label { color: #8a8aaa; font-size: 11px; margin-bottom: 2px; }
.crew-item { padding-left: 8px; }
.crew-item label { color: #cdd6f4; font-size: 11px; cursor: pointer; }
.crew-item input { margin-right: 4px; }

.event-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 4px 6px; margin-bottom: 2px;
  background: #2d2d44; border-radius: 4px;
}
.event-label { color: #cdd6f4; font-size: 11px; }
.event-remove {
  background: none; border: none; color: #f44336; cursor: pointer; font-size: 12px;
}
</style>

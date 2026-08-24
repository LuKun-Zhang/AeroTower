const fs = require('fs')
const d = JSON.parse(fs.readFileSync('../demo/public/terminal_layout.json', 'utf8'))
const code = fs.readFileSync('../demo/src/components/TerminalLayout.vue', 'utf8')

// 解析 TAXI_CHANNELS
const TAXI = { gateToChannel: {}, gateToPlace: {} }
const m1 = code.match(/gateToChannel:\s*\{([\s\S]*?)\n\s*\}/)
if (m1) {
  const re = /'([^']+)'\s*:\s*'([^']+)'/g
  let m
  while ((m = re.exec(m1[1]))) {
    TAXI.gateToChannel[m[1]] = m[2]
  }
}

// 获取所有 gates 和 terminals
const gates = d.gates.filter(g => g.name.includes('矩形'))
const terminals = d.terminals || []

// 检查每个登机口左右两侧的情况
for (const gate of gates) {
  const ch = TAXI.gateToChannel[gate.name]
  if (!ch) continue
  
  const cx = gate.x + gate.w / 2
  const cy = gate.y + gate.h / 2
  
  // 检查左侧(x - 50)和右侧(x + gate.w + 50)是否有其他登机口或指廊
  const leftGates = gates.filter(g => {
    if (g.name === gate.name) return false
    const gc = g.x + g.w/2
    const d = Math.abs(gc - cx)
    const dy = Math.abs((g.y+g.h/2) - cy)
    return g.x < gate.x && Math.abs((g.x+g.w) - gate.x) < 80 && dy < 40
  })
  
  const rightGates = gates.filter(g => {
    if (g.name === gate.name) return false
    const d = Math.abs((g.x+g.w/2) - cx)
    const dy = Math.abs((g.y+g.h/2) - cy)
    return g.x > gate.x && Math.abs(g.x - (gate.x+gate.w)) < 80 && dy < 40
  })
  
  // 检查终端/指廊位置
  const nearbyTerminals = terminals.filter(t => {
    const tc = t.x + t.w/2
    const dist = Math.abs(tc - cx)
    return dist < 200
  })
  
  // 判断应该放在哪一侧
  // 如果左侧有大量相邻登机口，说明指廊在右侧 → 放左侧
  // 如果右侧有大量相邻登机口，说明指廊在左侧 → 放右侧
  let suggested = 'RIGHT'
  if (ch === 't1_left') {
    suggested = 'LEFT'  // 指廊在右侧
  } else if (ch === 't2_right') {
    // t2_right 有些门应该放左侧
    // 检查该门左侧是否有连着的门
    if (leftGates.length >= 1 && leftGates[0].x + leftGates[0].w > gate.x - 10) {
      // 左侧紧挨着其他门 → 可能指廊在右侧
    }
  }
  
  // 检查左边紧邻：如果有门在左边紧挨(<5px gap)，说明门是连排的
  const leftNeighbor = leftGates.find(g => gate.x - (g.x + g.w) < 10 && Math.abs(g.y - gate.y) < 10)
  const rightNeighbor = rightGates.find(g => g.x - (gate.x + gate.w) < 10 && Math.abs(g.y - gate.y) < 10)
  
  if (leftNeighbor && !rightNeighbor) {
    // 左边紧邻有门，右边没有 → 门开口朝右 → 飞机放右侧
    suggested = 'RIGHT'
  } else if (rightNeighbor && !leftNeighbor) {
    // 右边紧邻有门，左边没有 → 门开口朝左 → 飞机放左侧
    suggested = 'LEFT'
  }
  
  // 特别检查：如果门在最左边一列(x ≈ 12)
  if (gate.x < 20) suggested = 'LEFT'
  
  // 如果门在最右边一列
  // t2_right 的 x≈543-581
  
  // 检查门所属的列（同x附近）
  const sameCol = gates.filter(g => {
    if (g.name === gate.name) return false
    return Math.abs(g.x - gate.x) < 5
  })
  
  console.log(
    gate.name.padEnd(8),
    ch.padEnd(10),
    'x=' + gate.x.toFixed(0).padStart(4),
    'y=' + gate.y.toFixed(0).padStart(4),
    'col=' + sameCol.length,
    'L=' + leftGates.length.toString().padEnd(2),
    'R=' + rightGates.length.toString().padEnd(2),
    '=> ' + suggested
  )
}

/** 实验中心 API 封装（统一带 X-Username，避免每个请求拼 query）。 */
const BASE = '/api'

function username() {
  try {
    return JSON.parse(localStorage.getItem('current_user') || '{}').username || 'user1'
  } catch (e) {
    return 'user1'
  }
}

async function request(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', 'X-Username': username() }
  const res = await fetch(BASE + path, { ...options, headers: { ...headers, ...(options.headers || {}) } })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.msg || '请求失败')
  return json.data
}

export default {
  list() {
    return request('/experiments')
  },
  create(payload) {
    return request('/experiments', { method: 'POST', body: JSON.stringify(payload) })
  },
  get(id) {
    return request(`/experiments/${id}`)
  },
  remove(id) {
    return request(`/experiments/${id}`, { method: 'DELETE' })
  },
  run(id) {
    return request(`/experiments/${id}/run`, { method: 'POST' })
  },
  progress(id) {
    return request(`/experiments/${id}/progress`)
  },
  rerun(id) {
    return request(`/experiments/${id}/rerun`, { method: 'POST' })
  },
  async export(id) {
    const res = await fetch(`${BASE}/experiments/${id}/export`, {
      headers: { 'X-Username': username() },
    })
    if (!res.ok) throw new Error('导出失败')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `experiment_${id}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  },
}
